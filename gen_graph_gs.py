import sqlite3
import json
import os
import colorsys
import subprocess
from collections import Counter
from datetime import datetime, timedelta
import re

def generate_new_color(index):
    """Генерирует уникальный цвет для верхнеуровневых модулей."""
    hue = (index * 0.618033988749895) % 1.0  # Используем золотое сечение
    r, g, b = colorsys.hsv_to_rgb(hue, 0.5, 0.95)
    return f'#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}'


def generate_similar_color(base_color, variation_seed):
    """Генерация понятного визуально и вариативного цвета на основе базового."""
    # Переводим базовый цвет из HEX в RGB
    r, g, b = [int(base_color[i:i + 2], 16) for i in (1, 3, 5)]
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)

    # Добавляем к оттенку вариацию (используем seed)
    hue_variation = ((hash(variation_seed) % 200) - 100) / 1000.0  # Варьируем hue более широко
    saturation_variation = ((hash(variation_seed + 1) % 50) - 25) / 100.0  # Варьируем насыщенность
    value_variation = ((hash(variation_seed + 2) % 50) - 25) / 100.0  # Яркость

    # Применяем вариации, сохраняем диапазон [0, 1]
    h = (h + hue_variation) % 1.0
    s = max(0.4, min(1.0, s + saturation_variation))  # Ограничиваем насыщенность, чтобы цвета не были слишком блеклыми
    v = max(0.7, min(1.0, v + value_variation))  # Ограничиваем яркость

    # Переводим обратно в HEX
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return f'#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}'


def load_modules(file_path):
    """Парсит modules.csv и возвращает маппинги для модулей и цветов."""
    module_colors = {}
    parent_colors = {}

    with open(file_path, 'r') as file:
        lines = file.readlines()[1:]  # Пропустить заголовок
        for index, line in enumerate(lines):
            path, module = line.strip().split(',')
            parent_path = '/'.join(path.split('/')[:-1]) if '/' in path else None

            # Генерация цвета модуля
            if parent_path and parent_path in parent_colors:
                base_color = parent_colors[parent_path]
                module_color = generate_similar_color(base_color, hash(module))
            else:
                module_color = generate_new_color(index)

            # Сохранение цвета
            module_colors[path] = {"module": module, "color": module_color}
            parent_colors[path] = module_color

    return module_colors


def is_file_in_folders(file_path, folders):
    """Проверяет, принадлежит ли файл одной из папок."""
    return any(file_path.startswith(folder) for folder in folders)


def get_repository_url():
    """Возвращает URL Git-репозитория. Преобразует SSH URL в HTTPS и удаляет `.git`."""
    try:
        # Выполняем команду для получения URL
        url = subprocess.check_output(["git", "config", "--get", "remote.origin.url"], stderr=subprocess.DEVNULL)
        url = url.decode("utf-8").strip()  # Конвертируем результат из байт в строку

        # Преобразуем SSH URL в HTTPS
        if url.startswith("git@"):
            url = url.replace(":", "/").replace("git@", "https://")

        # Удаляем суффикс `.git`, если он есть
        if url.endswith(".git"):
            url = url[:-4]

        return url
    except subprocess.CalledProcessError:
        # Если команда завершилась ошибкой (например, это не Git-репозиторий)
        print("Не удалось получить URL репозитория. Убедитесь, что это папка Git-репозитория.")
        return None

def query_graph_data(database, connection_threshold=1, max_files_per_commit=21, folders=None,
                     modules_file='modules.csv', repository_url="None", since=None, until=None, team_filter=None):

    # Загрузка цветов модулей
    module_colors = load_modules(modules_file)

    # Формируем условия для фильтрации по времени
    time_conditions = []
    if since:
        time_conditions.append(f"author_when >= '{since}'")
    if until:
        time_conditions.append(f"author_when <= '{until}'")
    # Если указана команда, добавляем соответствующее условие
    team_condition = ""
    if team_filter:
        team_condition = f"AND author_team = '{team_filter}'"

    team_name = team_filter
    # Объединяем условия в SQL
    time_filter = " AND ".join(time_conditions)

    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Включаем фильтрацию времени в запрос
    cursor.execute(f"""
        SELECT commit_id, filename
        FROM commit_files
        JOIN commits ON commit_files.commit_id = commits.id
        WHERE 1 = 1 {f"AND {time_filter}" if time_conditions else ""} {team_condition}
    """)

    team_files = {row["filename"] for row in cursor.fetchall()}
    # Берём все коммиты и файлы без дополнительной фильтрации по команде
    cursor.execute(f"""
        SELECT commit_id, filename
        FROM commit_files
        JOIN commits ON commit_files.commit_id = commits.id
        WHERE 1 = 1 {f"AND {time_filter}" if time_filter else ""}
    """)

    if not team_files and team_filter:
        print(f"Нет коммитов команды {team_name}")
        return
    rows = cursor.fetchall()

    file_map = {}
    edges = {}

    commit_files_map = {}
    for row in rows:
        # Сокращаем хеш коммита до 15 символов
        commit_id = row["commit_id"][:15]
        filename = row["filename"]

        if team_files and filename not in team_files:
            continue

        if commit_id not in commit_files_map:
            commit_files_map[commit_id] = []
        commit_files_map[commit_id].append(filename)

    # Определяем какие коммиты соответствуют переданным папкам (--folders)
    if folders:
        commits_with_matching_files = {
            commit_id for commit_id, files in commit_files_map.items()
            if any(is_file_in_folders(file, folders) for file in files)
        }
    else:
        commits_with_matching_files = set(commit_files_map.keys())
    # Подсчитываем количество файлов в каждом модуле
    module_file_counts = {}

    for commit_id, files in commit_files_map.items():
        if commit_id not in commits_with_matching_files:
            continue

        if len(files) > max_files_per_commit:
            continue

        for file in files:
            # Определить модуль для файла
            module_path = None
            for mp in module_colors.keys():
                if file.startswith(mp):
                    if module_path is None or len(mp) > len(module_path):
                        module_path = mp

            # Если ничего не найдено, назначаем модуль "Unknown"
            if not module_path:
                module_path = "Unknown"

            # Определение цвета файла
            if folders and is_file_in_folders(file, folders):
                node_color = "green"  # Цвет остаётся зелёным для файлов в папках `--folders`
                module_name = "Current"  # Все файлы из переданных папок считаются модулем 'Current'
            else:
                node_color = module_colors.get(module_path, {}).get("color", "#000000")  # Черный, если модуль не найден
                module_name = module_colors.get(module_path, {}).get("module", "Unknown")

            if module_name not in module_file_counts:
                module_file_counts[module_name] = 0
            module_file_counts[module_name] += 1
            # Если файла ещё нет в file_map, добавляем его
            if file not in file_map:
                file_map[file] = {
                    "id": len(file_map),
                    "name": os.path.basename(file),
                    "full_path": file,
                    "folder": "/".join(file.split("/")[:-1]),
                    "weight": 1.0,
                    "color": node_color,  # Цвет на основе условия
                    "module": module_name,  # Чтобы можно было использовать при фильтрации в легенде
                    "commits": list()
                }

            # Добавляем текущий сокращённый commit_id в список коммитов файла
            file_map[file]["commits"].append(commit_id)

    for commit_id, files in commit_files_map.items():
        if commit_id not in commits_with_matching_files:
            continue

        if len(files) > max_files_per_commit:
            continue
        module_commit_impact = {}
        for i in range(len(files)):
            for j in range(i + 1, len(files)):
                file_a = files[i]
                file_b = files[j]
                edge_key = tuple(sorted([file_a, file_b]))

                if edge_key not in edges:
                    edges[edge_key] = {
                        "source": file_map[file_a]["id"],
                        "target": file_map[file_b]["id"],
                        "weight": 1.0
                    }
                edges[edge_key]["weight"] += 1

                if file_a not in module_commit_impact:
                    module_commit_impact[file_a] = 1.0
                if file_b not in module_commit_impact:
                    module_commit_impact[file_b] = 1.0

                file_map[file_a]["weight"] += module_commit_impact[file_a]
                file_map[file_b]["weight"] += module_commit_impact[file_b]
                module_commit_impact[file_a] *= 0.8
                module_commit_impact[file_b] *= 0.8

    conn.close()

    nodes = []
    for file_data in file_map.values():
        # Преобразуем множество коммитов в список для сериализации
        file_data["commits"] = list(file_data["commits"])
        nodes.append(file_data)

    links = [edge for edge in edges.values() if edge["weight"] >= connection_threshold]

    # Извлечем все commit_ids и их время
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(f"""
            SELECT id, author_when, author_name, author_team, summary
            FROM commits
            WHERE 1 = 1 {f"AND {time_filter}" if time_conditions else ""}
        """)
    commit_rows = cursor.fetchall()

    commit_times = []
    teams_data = {}  # Собираем команды во временный словарь

    for row in commit_rows:
        author_when = row["author_when"]
        team_name = row["author_team"]
        author_name = row["author_name"]

        try:
            normalized_author_when = author_when.replace('Z', '+00:00')
            commit_time = datetime.fromisoformat(normalized_author_when)
            commit_times.append(commit_time)
        except ValueError:
            continue

        # Если команда не указана, заменяем на Unknown
        if not team_name:
            team_name = "Unknown"

        # Инициализируем команду, если её ещё нет
        if team_name not in teams_data:
            teams_data[team_name] = set()

        # Добавляем участника в соответствующую команду
        if author_name:
            teams_data[team_name].add(author_name)

    # Заполняем teams_list
    teams_list = [
        {
            "name": team_name,
            "members": [{"name": member_name} for member_name in members]
        }
        for team_name, members in teams_data.items()
    ]

# Закрываем подключение
    conn.close()

    if commit_times:
        first_commit_time = min(commit_times)
        last_commit_time = max(commit_times)
        start_opacity = 0.3
        # Нормализуем время в диапазон [0.1, 1]
        def normalize_time(commit_time):
            normalized = (commit_time - first_commit_time).total_seconds() / (
                    last_commit_time - first_commit_time).total_seconds()
            return start_opacity + (normalized * (1.0 - start_opacity))

        for node in nodes:
            if node["commits"]:
                # Берём последние изменения для файла
                filtered_rows = [row for row in commit_rows if row["id"][:15] in node["commits"]]

                latest_commit_time = max(
                    datetime.fromisoformat(row["author_when"].replace('Z', '+00:00'))
                    for row in commit_rows if row["id"][:15] in node["commits"]
                )
                author_commit_counts = Counter(row["author_name"] for row in filtered_rows)
                team_commit_counts = Counter(row["author_team"] for row in filtered_rows)
                node["commit_time_normalized"] = normalize_time(latest_commit_time)
                node["commits"] = [
                    {
                        "id": row["id"][:15],  # Сокращённый хэш коммита
                        "author_name": row["author_name"],  # Имя автора
                        "author_team": row["author_team"],  # Команда автора
                        "summary" : row["summary"]
                    }
                    for row in filtered_rows
                ]

                node["users"] = [{"name": name, "commits": count} for name, count in author_commit_counts.items()]
                node["teams"] = [{"name": name, "commits": count} for name, count in team_commit_counts.items()]

    # Подготовим данные для легенды
    used_modules = {file_map[file]["folder"] for file in file_map}


    # Для каждого link добавляем нормализованное время коммита
    for link in links:
        # Получаем исходный и целевой файлы
        source_file = next(node for node in nodes if node["id"] == link["source"])
        target_file = next(node for node in nodes if node["id"] == link["target"])

        # Если оба узла имеют связанные коммиты
        if source_file["commits"] and target_file["commits"]:
            # Находим общие коммиты между файлами
            common_commits = (
                    {commit["id"] for commit in source_file["commits"]} &
                    {commit["id"] for commit in target_file["commits"]}
            )


            # Если есть хотя бы один общий коммит
            if common_commits:
                # Выбираем последнее время из общего набора
                latest_common_commit_time = max(
                    datetime.fromisoformat(row["author_when"].replace('Z', '+00:00'))
                    for row in commit_rows if row["id"][:15] in common_commits
                )

                # Нормализуем время
                link["commit_time_normalized"] = normalize_time(latest_common_commit_time)
            else:
                # Если общих коммитов нет, устанавливаем минимальное значение
                link["commit_time_normalized"] = start_opacity
        else:
            # Если у одного из файлов нет коммитов, минимальное значение
            link["commit_time_normalized"] = start_opacity

    # Добавляем модули в легенду, только если они реально использовались
    used_module_legend = [
        {
            "module": module_data["module"],
            "color": module_data["color"],
            "file_count": module_file_counts.get(module_data["module"], 0)  # Возвращаем 0, если ключ отсутствует
        }
        for module_path, module_data in module_colors.items()
        if module_file_counts.get(module_data["module"], 0) > 0
    ]

    # Сортировка по количеству файлов
    used_module_legend.sort(key=lambda x: x["file_count"], reverse=True)

    # Если есть папки из параметра --folders, добавляем их в начало
    if folders:
        module_legend = [{"module": "Current", "color": "green", "file_count": 0}]
        module_legend.extend(used_module_legend)
    else:
        module_legend = used_module_legend

    # Создаем карту commit_time_map с временем для каждого укороченного commit_id
    commit_time_map = {}
    for row in commit_rows:
        commit_id = row["id"][:15]  # Урезаем commit_id до 15 символов
        try:
            # Конвертируем `author_when` в объект datetime
            commit_time = datetime.fromisoformat(row["author_when"].replace('Z', '+00:00'))
            commit_time_map[commit_id] = commit_time
        except (ValueError, TypeError):
            # Если есть ошибки в формате времени, просто пропускаем
            continue

    # Сортируем коммиты в каждом узле на основании commit_time_map
    for node in nodes:
        if node["commits"]:
            node["commits"].sort(
                key=lambda commit: commit_time_map.get(commit["id"], datetime.min),
                reverse=True  # Сортировка от самого нового к старому
            )



    return {
        "nodes": nodes,
        "links": links,
        "modules": module_legend,
        "repository_url": repository_url,
        "teams": teams_list  # Добавили команды
    }


def generate_html_with_improvements(graph_data, template_path, output_path):
    with open(template_path, "r", encoding="utf-8") as file:
        html_template = file.read()

    # Вставка JSON графа
    graph_json = json.dumps(graph_data).replace("</", "<\\/")
    html_filled = html_template.replace("{{GRAPH_DATA}}", graph_json)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_filled)

def parse_human_time(human_time):
    """
    Преобразует строку формата "X days/weeks/months/years ago" в дату.
    Например:
    - "3 months ago" -> дата три месяца назад от текущей
    - "1 year ago" -> дата год назад от текущей
    """
    current_time = datetime.now()
    time_map = {
        "day": "days",
        "week": "weeks",
        "month": "months",
        "year": "years",
    }

    # Регулярное выражение для анализа строки
    match = re.match(r"(\d+)\s+(day|week|month|year)s?\s+ago", human_time.strip().lower())
    if not match:
        raise ValueError(f"Не удалось распознать значение времени: {human_time}")

    value, unit = match.groups()
    value = int(value)

    # Простой расчёт для дней, недель, месяцев и лет
    if unit == "day":
        return current_time - timedelta(days=value)
    elif unit == "week":
        return current_time - timedelta(weeks=value)
    elif unit == "month":
        # Упрощённая обработка месяцев: считаем 30 дней = 1 месяц
        return current_time - timedelta(days=value * 30)
    elif unit == "year":
        # Упрощённая обработка лет: считаем 365 дней = 1 год
        return current_time - timedelta(days=value * 365)

    raise ValueError(f"Неизвестный формат времени: {unit}")
def main(database="git_log.db", template="template.html", output_html="graph.html", connection_threshold=1,
         max_files_per_commit=21, folders=None, modules_file='modules.csv', repository_url=None,
         since=None, until=None, team=None
         ):
    # Преобразуем "человеческие" строки для `since` и `until` в объекты datetime
    if since:
        if "ago" in since.lower():
            since = parse_human_time(since)
        else:
            since = datetime.strptime(since, "%Y-%m-%d %H:%M:%S")
        since = since.strftime('%Y-%m-%d %H:%M:%S')  # Конвертируем в строку для SQLite

    if until:
        if "ago" in until.lower():
            until = parse_human_time(until)
        else:
            until = datetime.strptime(until, "%Y-%m-%d %H:%M:%S")
        until = until.strftime('%Y-%m-%d %H:%M:%S')  # Конвертируем в строку для SQLite

    if not repository_url:
        repository_url = get_repository_url()
    if not repository_url:
        print("Предупреждение: Не удалось определить URL Git-репозитория. Укажите его явно через --repository-url.")
        repository_url = "Unknown"

    graph_data = query_graph_data(database, connection_threshold, max_files_per_commit, folders,
                                  modules_file, repository_url, since, until, team)
    generate_html_with_improvements(graph_data, template, output_html)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Генерация интерактивного графа.")
    parser.add_argument("--database", default="git_log.db", help="Путь к базе данных SQLite")
    parser.add_argument("--template", default="template.html", help="HTML-шаблон")
    parser.add_argument("--output", default="reports/index.html", help="Файл для сохранения HTML")
    parser.add_argument("--threshold", type=int, default=1, help="Минимальное количество связей для рёбер")
    parser.add_argument("--max-files", type=int, default=21,
                        help="Максимальное количество файлов в коммите для включения в анализ")
    parser.add_argument("--folders", nargs="*", default=None, help="Учитывать только файлы из указанных папок")
    parser.add_argument("--modules-file", default="modules.csv", help="Файл с определениями модулей")
    parser.add_argument("--team", help="Имя команды для фильтрации файлов.")
    parser.add_argument("--repository-url", default=None,
                    help="URL репозитория (если не указано, будет извлечён автоматически)")
    # Добавляем поддержку аргументов since и until
    parser.add_argument("--since", default=None,
                        help="Фильтровать коммиты начиная с указанной даты (пример: 'last year', '3 months ago', '2023-01-01')")
    parser.add_argument("--until", default=None,
                        help="Фильтровать коммиты до указанной даты (пример: 'yesterday', '2 weeks ago', '2023-10-01')")

    args = parser.parse_args()
    main(
        database=args.database,
        template=args.template,
        output_html=args.output,
        connection_threshold=args.threshold,
        max_files_per_commit=args.max_files,
        folders=args.folders, modules_file=args.modules_file,
        repository_url=args.repository_url,
        since=args.since,
        until=args.until,
        team=args.team
    )
