import os
import csv
import sqlite3
import sys
from pathlib import Path
from argparse import ArgumentParser
from gen_graph_gs import gen_report_new  # Предполагается, что `main` – это основная функция из `gen_graph.py`

from deserializer import JsonDeserializer
from project import Project
from module import Module

# Константа (по умолчанию для modules.csv)
DEFAULT_MODULES_FILE = "modules.csv"


def get_git_root():
    """
    Возвращает корневую директорию Git-репозитория или завершает программу с ошибкой.
    """
    from subprocess import check_output, CalledProcessError

    try:
        git_root = check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
        print(f"Корневая директория Git-репозитория: {git_root}")
        return git_root
    except CalledProcessError:
        print("Ошибка: Текущая директория не является частью Git-репозитория.")
        sys.exit(1)


def validate_modules_file(modules_file):
    """
    Проверяет наличие файла modules.csv.
    """
    if not os.path.isfile(modules_file):
        print(f"Ошибка: Файл {modules_file} не найден!")
        sys.exit(1)


def create_output_dir(output_dir):
    """
    Создаёт папку для отчётов, если её нет.
    """
    os.makedirs(output_dir, exist_ok=True)


def process_modules_file(project: Project, output_dir: str, since: str, until: str):
    """
    Обрабатывает модули проекта и генерирует отчеты для каждого модуля.
    
    Args:
        project: Объект Project с модулями
        output_dir: Директория для сохранения отчетов
        since: Начальная дата для фильтрации коммитов
        until: Конечная дата для фильтрации коммитов
    """
    print(f"\nНачало обработки модулей проекта '{project.name}'")
    print(f"Всего модулей: {len(project.modules)}")
    
    def process_module(module: Module, parent_path: str = ""):
        """
        Рекурсивно обрабатывает модуль и его подмодули.
        
        Args:
            module: Объект Module для обработки
            parent_path: Путь родительского модуля (для подмодулей)
        """
        # Формируем полный путь к модулю
        module_path = f"{parent_path}/{module.name}" if parent_path else module.name
        
        # Определяем выходной HTML-файл
        output_file = os.path.join(output_dir, f"{module_path.replace('/', '_')}.html")
        
        # Выводим информацию о процессе генерации
        print(f"\nОбработка модуля '{module.name}'")
        if module.description:
            print(f"Описание: {module.description}")
        if module.owners:
            print(f"Владельцы: {', '.join(module.owners)}")
        print(f"Пути: {', '.join(module.paths)}")
        print(f"Файлов: {len(module.files)}")
        print(f"Подмодулей: {len(module.submodules or [])}")
        
        # Логируем входные параметры для gen_report_new
        print("\nПараметры для генерации отчета:")
        print(f"  - Модуль: {module.name}")
        print(f"  - Пути: {module.paths}")
        print(f"  - Выходной файл: {output_file}")
        print(f"  - Период: с {since} по {until}")
        
        try:
            # Вызываем функцию gen_report_new для генерации отчета
            gen_report_new(
                module=module,  # Объект модуля
                output_html=output_file,  # Путь к файлу отчета
                since=since,  # Фильтрация по времени
                until=until  # Фильтрация по времени
            )
            print("Отчет успешно сгенерирован")
        except Exception as e:
            print(f"Ошибка при генерации отчета: {e}")
        
        # Рекурсивно обрабатываем подмодули
        if module.submodules:
            for submodule in module.submodules:
                process_module(submodule, module_path)
    
    # Обрабатываем все модули проекта
    for module in project.modules:
        process_module(module)
    
    print("\nОбработка модулей завершена")


def get_teams_from_db(database_path):
    """
    Извлекает список уникальных команд из базы данных Git.
    """
    if not os.path.exists(database_path):
        print(f"Ошибка: Не удалось найти базу данных {database_path}.")
        sys.exit(1)

    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT author_team FROM commits WHERE author_team IS NOT NULL AND author_team != '';")
    teams = [row[0] for row in cursor.fetchall()]
    conn.close()

    return teams


def generate_team_reports(database, output_dir, since, until):
    """
    Генерация отчётов для каждой команды.
    """
    teams = get_teams_from_db(database)
    if not teams:
        print("Предупреждение: Команды не найдены в базе данных. Отчёты не будут сгенерированы.")
        return

    for team in teams:
        team_output_file = os.path.join(output_dir, f"{team}.html")

        print(f"Генерация отчёта для команды '{team}' (since={since}, until={until})")

        # Вызываем main с параметром `team`
        main(
            output_html=team_output_file,  # Имя файла отчёта
            team=team,  # Фильтрация по команде
            since=since,  # Фильтрация по времени
            until=until  # Фильтрация по времени
        )

def generate_index_report(output_dir, git_root, since, until):
    """
    Генерирует общий индексный отчёт (основной граф).
    """
    output_file = os.path.join(output_dir, "index.html")
    print(f"Генерация итогового отчёта: {output_file} (since={since}, until={until})")

    # Вызов main напрямую без фильтрации по папкам
    main(
        output_html=output_file,  # Путь для итогового HTML-файла
        since=since,  # Передаём параметр since
        until=until  # Передаём параметр until
    )


if __name__ == "__main__":
    # Парсер аргументов командной строки
    # parser = ArgumentParser(description="Генерация отчетов для модулей из Git-репозитория.")
    # parser.add_argument(
    #     "--modules-file", default=DEFAULT_MODULES_FILE,
    #     help="Путь к файлу modules.csv (по умолчанию: modules.csv)"
    # )
    # parser.add_argument(
    #     "--output-dir", default="reports",
    #     help="Папка для сохранения отчетов (по умолчанию: reports)"
    # )
    # parser.add_argument(
    #     "--since", default=None,
    #     help="Фильтровать коммиты начиная с указанной даты (пример: '2023-01-01', 'last year')."
    # )
    # parser.add_argument(
    #     "--until", default=None,
    #     help="Фильтровать коммиты до указанной даты (пример: '2023-12-31', 'now')."
    # )
    # parser.add_argument(
    #     "--database", default="git_log.db",
    #     help="Путь к базе данных (по умолчанию: git_log.db)"
    # )


# Получаем аргументы
    # args = parser.parse_args()

    # Получаем значения аргументов
    # modules_file = args.modules_file
    # output_dir = args.output_dir
    # since = args.since
    # until = args.until
    # database = args.database

    # modules_file = args.modules_file
    output_dir = "reports"
    since = "last year"
    until = "now"
    database = "git_history.db"

    # Получаем корень Git-репозитория
    # git_root = get_git_root()

    # Проверяем файл modules.csv
    # validate_modules_file(modules_file)

    # Загружаем данные о модулях
    try:
        project = JsonDeserializer.deserialize("result.json")
        print(f"Loaded project with {len(project.modules)} modules")
    except Exception as e:
        print(f"Error loading project: {e}")
        sys.exit(1)

    # Создаём директорию отчётов
    create_output_dir(output_dir)

    # Обрабатываем модули из файла modules.csv
    process_modules_file(project, output_dir, since, until)

    # Генерируем итоговый HTML-отчёт (общий граф)
    # generate_index_report(output_dir, git_root, since, until)

    # Генерация отчётов по каждой команде
    # generate_team_reports(database, output_dir, since, until)

