#!/usr/bin/env python3

import os
import shutil
import sqlite3
import subprocess
import argparse
import re
import sys
import csv
from sqlite3 import Connection
from threading import Lock
import datetime
import json
from typing import List, Dict, Optional
from pathlib import Path

USERS_FILE = "users.csv"
UNKNOWN_USERS_FILE = "unknown_users.csv"

# Структуры для кеширования данных
user_mapping = {}
unknown_users_set = set()  # Используем set для предотвращения дублирования
unknown_users_list = []  # Список для сохранения порядка неизвестных пользователей

# Глобальная переменная lock для синхронизации потоков SQLite
lock = Lock()

# Глобальная мапа для отслеживания переименований файлов
file_renames = {}

# Счётчик прогресса (общее количество обработанных коммитов)
progress_counter = 0

# Сохраняем директорию, из которой был вызван скрипт
ORIGINAL_DIRECTORY = os.getcwd()

def load_users_csv(users_file):
    """
    Загружает список пользователей из файла users.csv в словарь.
    Формат: {email_wildcard: (name, team)}
    """
    users_file = os.path.join(ORIGINAL_DIRECTORY, users_file)
    global user_mapping
    if not os.path.exists(users_file):
        print(f"Ошибка: файл {users_file} не найден.")
        return

    with open(users_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            email_wildcard = row['email'].strip()
            name = row['user'].strip()
            team = row['team'].strip()

            user_mapping[email_wildcard] = (name, team)

def save_unknown_users(unknown_users_file):
    """
    Записывает список неизвестных пользователей в unknown_users.csv
    в порядке появления.
    """
    unknown_users_file = os.path.join(ORIGINAL_DIRECTORY, unknown_users_file)
    with open(unknown_users_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "email","team"])  # Заголовок для файла

        # Пишем данные в порядке добавления
        for name, email in unknown_users_list:
            writer.writerow([name, email, "unknown"])



def resolve_user_and_team(original_name, original_email):
    """
    Ищет пользователя по email в users.csv через wildcard (*).
    Игнорирует регистр букв (case-insensitive).

    Если пользователь найден:
        - Возвращает его имя и команду (из users.csv).
    Если не найден:
        - Добавляет в unknown_users_list (сохраняя порядок).
    """
    global user_mapping, unknown_users_list, unknown_users_set

    # Приведение original_email к нижнему регистру для сравнения
    lower_email = original_email.lower()

    # Поиск совпадения по wildcard в user_mapping
    for email_wildcard, (name, team) in user_mapping.items():
        # Приводим wildcard тоже к нижнему регистру
        if email_wildcard.strip("*").lower() in lower_email:
            return name, team

    # Если пользователь не найден, добавляем в unknown_users_list и unknown_users_set
    unknown_user_tuple = (original_name, original_email)
    if unknown_user_tuple not in unknown_users_set:  # Быстрый поиск через set
        unknown_users_list.append(unknown_user_tuple)  # Добавляем в список
        unknown_users_set.add(unknown_user_tuple)  # Добавляем в множество

    return original_name, 'unknown'


# Функция для бэкапа существующей базы данных
def backup_database_if_exists(filename, remove_old):
    # Полный путь к базе данных
    db_path = os.path.join(ORIGINAL_DIRECTORY, filename)
    # Полный путь к файлу бэкапа
    backup_path = f"{db_path}.back"

    if os.path.exists(db_path):  # Если текущая база данных существует
        print(f"Бэкапим существующую базу данных: {db_path} -> {backup_path}")
        if os.path.exists(backup_path):  # Если бэкап уже существует, удаляем его
            print(f"Удаляем старый бэкап: {backup_path}")
            os.remove(backup_path)
        if remove_old:
            shutil.move(db_path, backup_path)  # Переименовываем файл в бэкап
        else:
            print("Дополняем старую базу новыми коммитами")
            shutil.copy(db_path, backup_path)

        print(f"Бэкап успешно создан: {backup_path}")
    else:
        print(f"База данных {db_path} не существует, бэкап не требуется.")

def get_git_root():
    """
    Определяет корневую директорию Git-репозитория.
    """
    process = subprocess.Popen(["git", "rev-parse", "--show-toplevel"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        raise RuntimeError("Эта директория не является частью Git-репозитория.")
    return stdout.strip()


def ensure_git_root():
    """
    Изменяет рабочую директорию на корневую директорию репозитория.
    """
    git_root = get_git_root()
    print(f"Переход в корневую директорию репозитория: {git_root}")
    os.chdir(git_root)


def create_database(filename: str) -> sqlite3.Connection:
    """
    Создаёт SQLite базу данных и таблицы.
    """
    db_connection = sqlite3.connect(filename)
    db_connection.execute("PRAGMA journal_mode=WAL;")
    
    # Создаем таблицу для коммитов
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS commits (
            id TEXT UNIQUE,
            summary TEXT,
            author_name TEXT,
            author_email TEXT,
            commit_date TEXT
        );
    """)
    
    # Создаем таблицу для измененных файлов
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS commit_files (
            commit_id TEXT,
            filename TEXT,
            added INT,
            deleted INT,
            FOREIGN KEY (commit_id) REFERENCES commits(id)
        );
    """)
    
    print(f"База данных создана: {filename}")
    return db_connection


def parse_file_rename(line):
    # Сложные случаи с фигурными скобками {old => new}
    match = re.match(r"^(.*)\{(.+?)?\s*=>\s*(.+?)?\}(.*)$", line)
    if match:
        path_prefix = match.group(1).strip()
        old_part = match.group(2).strip() if match.group(2) else ""
        new_part = match.group(3).strip() if match.group(3) else ""
        path_suffix = match.group(4).strip()

        # Конструируем старый и новый пути файла
        old_file = f"{path_prefix}{old_part}{path_suffix}".replace("//", "/")
        new_file = f"{path_prefix}{new_part}{path_suffix}".replace("//", "/")

        return old_file, new_file

    # Простые случаи переименования old => new
    if "=>" in line:
        parts = line.split("=>")
        old_file = parts[0].strip()
        new_file = parts[1].strip()

        return old_file, new_file

    # Если не найдено переименование
    return None, None

def add_commit_to_db(connection, commit_id, author_name, author_email, date, summary):

    cursor = connection.cursor()
    cursor.execute("SELECT 1 FROM commits WHERE id = ?", (commit_id,))
    if cursor.fetchone():
        print(f"Коммит {commit_id} уже существует в базе. Останавливаем обработку.")
        return False  # Прекращаем чтение

    resolved_name, resolved_team = resolve_user_and_team(author_name, author_email)
    """
    Добавляет информацию о коммите в таблицу commits.
    """
    connection.execute("""
        INSERT INTO commits (id, summary, author_name, author_email, commit_date)
        VALUES (?, ?, ?, ?, ?)
    """, (commit_id, summary, resolved_name, author_email, date))
    return True

def resolve_name(file_name):
    if file_name in file_renames:
        file_name = file_renames[file_name]
    return file_name
def add_files_to_db(connection, commit_id, files):
    """
    Добавляет в базу данных файлы, связанные с коммитом. Исправляет их имена.
    """
    global file_renames
    for file in files:
        original_filename = file["name"]
        if "=>" in original_filename:
            old_name, new_name = parse_file_rename(original_filename)
            # Переименование всех вхождений старого имени файла в базе данных

            corrected_filename = new_name
            if new_name in file_renames:
                corrected_filename = file_renames[new_name]
                del file_renames[new_name]
            file_renames[old_name] = corrected_filename
            connection.execute("""
                UPDATE commit_files
                SET filename = ?
                WHERE filename = ?;
            """, (corrected_filename, old_name))
            connection.commit()
        else:
            corrected_filename = resolve_name(original_filename)

        connection.execute("""
            INSERT INTO commit_files (commit_id, filename, added, deleted)
            VALUES (?, ?, ?, ?)
        """, (commit_id, corrected_filename, file["added"], file["deleted"]))


def process_commit_block(commit_block, connection):
    global progress_counter

    connection.execute("PRAGMA journal_mode=WAL;")

    commit_info = None
    files = []

    for line in commit_block:
        line = line.strip()
        if re.match(r"^[a-f0-9]+\|.*", line):
            parts = line.split("|", 4)
            commit_id = parts[0]
            author_name = parts[1]
            author_email = parts[2]
            date = parts[3]
            summary = parts[4]
            commit_info = (commit_id, author_name, author_email, date, summary)
            files = []
        elif re.match(r"^\d+\s+\d+\s+.+", line):
            parts = line.split("\t")
            if len(parts) >= 3:
                added, deleted, filename = parts[0], parts[1], parts[2]

                files.append({
                    "name": filename,
                    "added": int(added) if added.isdigit() else 0,
                    "deleted": int(deleted) if deleted.isdigit() else 0
                })

    if commit_info and files:
        if not add_commit_to_db(connection, *commit_info):
            return False
        add_files_to_db(connection, commit_info[0], files)

    progress_counter += 1
    sys.stdout.write(f"\rОбработано коммитов: {progress_counter}")
    sys.stdout.flush()
    return True


def parse_git_log(connection, params_extr, patterns=None):

    git_command = [
        "git", "log",
        "--pretty=format:%H|%an|%ae|%aI|%s",
        "--numstat",
        "--no-merges",
    ]

    if params_extr.get("since"):
        git_command.append(f"--since={params_extr['since']}")
    if params_extr.get("until"):
        git_command.append(f"--until={params_extr['until']}")

    if patterns:
        git_command.append("--")
        git_command.extend(patterns)

    try:
        process = subprocess.Popen(
            git_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )

        current_block = []

        for line in process.stdout:
            if re.match(r"^[a-f0-9]+\|.*", line):
                if current_block:
                    sys.stdout.flush()
                    if not process_commit_block(current_block, connection):
                        try:
                            process.terminate()
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            print("Процесс завершился некорректно. Принудительная остановка...")
                            process.kill()  # Принудительное завершение
                        break
                    current_block = []
            current_block.append(line)

        connection.commit()
        connection.close()
    except Exception as e:
        print(f"\nОшибка: {e}")

def show_usage_and_exit():
    usage_message = (
        "По умолчанию имя БД git_log.db\n"
        "Пример использования:\n"
        "python3 git2sqlite.py --since \"last year\" --database \"commits.db\" -p \"*.h\" \"*.cpp\"\n"
        "python3 git2sqlite.py --since \"last year\" --until \"last month\" -p \"*.h\" \"*.cpp\""
    )
    print(usage_message)
    sys.exit(1)

def get_git_history(days: int = 30, repo_path: Optional[str] = None) -> List[Dict]:
    """
    Получает историю Git-репозитория за указанное количество дней.
    """
    print(f"\nНачало получения истории Git за последние {days} дней")
    print(f"Путь к репозиторию: {repo_path if repo_path else 'текущая директория'}")
    
    since_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime('%Y-%m-%d')
    print(f"Дата начала анализа: {since_date}")
    
    # Сохраняем текущую директорию
    original_dir = os.getcwd()
    print(f"Текущая директория: {original_dir}")
    
    try:
        # Если указан путь к репозиторию, переходим в него
        if repo_path:
            print(f"Переход в директорию репозитория: {repo_path}")
            os.chdir(repo_path)
            print(f"Текущая директория после перехода: {os.getcwd()}")
        
        # Используем другой формат для git log, который не требует JSON парсинга
        cmd = ['git', 'log', 
               '--since', since_date,
               '--pretty=format:%H|%an|%ae|%ad|%s',
               '--date=iso',
               '--numstat']
        
        print(f"\nВыполнение команды: {' '.join(cmd)}")
        result = subprocess.run(cmd, 
                              capture_output=True, 
                              text=True, 
                              check=True)
        
        print(f"Команда выполнена успешно. Размер вывода: {len(result.stdout)} символов")
        
        commits = []
        current_commit = None
        current_files = []
        total_lines = len(result.stdout.strip().split('\n'))
        processed_lines = 0
        
        print("\nНачало обработки вывода git log")
        for line in result.stdout.strip().split('\n'):
            processed_lines += 1
            if processed_lines % 100 == 0:
                print(f"Обработано строк: {processed_lines}/{total_lines}")
            
            if '|' in line:
                # Если это новый коммит, сохраняем предыдущий
                if current_commit:
                    current_commit['files'] = current_files
                    commits.append(current_commit)
                    print(f"Обработан коммит: {current_commit['commit'][:8]}... ({len(current_files)} файлов)")
                
                # Парсим информацию о коммите
                try:
                    commit_id, author, email, date, message = line.split('|', 4)
                    current_commit = {
                        'commit': commit_id,
                        'author': author,
                        'email': email,
                        'date': date,
                        'message': message
                    }
                    current_files = []
                except ValueError as e:
                    print(f"Ошибка при разборе строки коммита: {line}")
                    print(f"Ошибка: {e}")
                    continue
            elif line.strip():
                # Обрабатываем статистику файлов
                parts = line.split('\t')
                if len(parts) >= 3:
                    added, deleted, filename = parts[0], parts[1], parts[2]
                    try:
                        current_files.append({
                            'name': filename,
                            'added': int(added) if added != '-' else 0,
                            'deleted': int(deleted) if deleted != '-' else 0
                        })
                    except ValueError as e:
                        print(f"Ошибка при разборе статистики файла: {line}")
                        print(f"Ошибка: {e}")
                        continue
        
        # Добавляем последний коммит
        if current_commit:
            current_commit['files'] = current_files
            commits.append(current_commit)
            print(f"Обработан последний коммит: {current_commit['commit'][:8]}... ({len(current_files)} файлов)")
        
        print(f"\nОбработка завершена. Всего коммитов: {len(commits)}")
        return commits
    
    except subprocess.CalledProcessError as e:
        print(f"\nОшибка при выполнении git log: {e}")
        print(f"Команда: {' '.join(cmd)}")
        print(f"Вывод ошибки: {e.stderr}")
        return []
    except Exception as e:
        print(f"\nНеожиданная ошибка: {e}")
        print(f"Строка, вызвавшая ошибку: {line}")
        return []
    finally:
        # Возвращаемся в исходную директорию
        print(f"\nВозврат в исходную директорию: {original_dir}")
        os.chdir(original_dir)

def save_to_database(connection: sqlite3.Connection, commits: List[Dict]) -> None:
    """
    Сохраняет коммиты и информацию о файлах в базу данных.
    """
    cursor = connection.cursor()
    
    for commit in commits:
        # Сохраняем информацию о коммите
        cursor.execute("""
            INSERT OR IGNORE INTO commits (id, summary, author_name, author_email, commit_date)
            VALUES (?, ?, ?, ?, ?)
        """, (
            commit['commit'],
            commit['message'],
            commit['author'],
            commit['email'],
            commit['date']
        ))
        
        # Сохраняем информацию о файлах
        for file in commit.get('files', []):
            cursor.execute("""
                INSERT INTO commit_files (commit_id, filename, added, deleted)
                VALUES (?, ?, ?, ?)
            """, (
                commit['commit'],
                file['name'],
                file['added'],
                file['deleted']
            ))
    
    connection.commit()

def main():
    # Создаем парсер аргументов
    # parser = argparse.ArgumentParser(description='Анализ истории Git-репозитория')
    # parser.add_argument('--repo-path', type=str, help='Путь к Git-репозиторию')
    # parser.add_argument('--days', type=int, default=30, help='Количество дней для анализа (по умолчанию 30)')
    # parser.add_argument('--db-file', type=str, default='git_history.db', help='Имя файла базы данных (по умолчанию git_history.db)')
    
    # args = parser.parse_args()
    
    # Проверяем, является ли указанный путь Git-репозиторием
    repo_path = "/Users/sergeykanaykin/Documents/Work/homescapes"
    db_file = "git_history.db"
    days = 50
    if repo_path:
        if not os.path.exists(os.path.join(repo_path, '.git')):
            print(f"Ошибка: {repo_path} не является Git-репозиторием")
            sys.exit(1)
    
    # Создаем базу данных
    connection = create_database(db_file)
    
    # Получаем историю Git
    commits = get_git_history(days, repo_path)
    
    # Сохраняем в базу данных
    save_to_database(connection, commits)
    
    # Выводим статистику
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM commits")
    commit_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM commit_files")
    file_count = cursor.fetchone()[0]
    
    print(f"\nСтатистика:")
    print(f"Количество коммитов: {commit_count}")
    print(f"Количество измененных файлов: {file_count}")
    
    connection.close()

if __name__ == "__main__":
    main()
