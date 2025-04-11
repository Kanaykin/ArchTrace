#!/usr/bin/env python3

import argparse
from pathlib import Path
from typing import Optional, List, Dict, Set
import json
import sys
import logging
from datetime import datetime

from .project import Project
from .module import Module
from .file_info import FileInfo
from .visitors import TextVisitor, JsonVisitor, DetailedTextVisitor

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'arch_trace_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)

def find_modules_by_owner(project: Project, owner: str) -> List[Module]:
    """Находит все модули, принадлежащие указанному владельцу"""
    logging.info(f"Поиск модулей для владельца: {owner}")
    modules = project.find_by_owner(owner)
    logging.info(f"Найдено модулей: {len(modules)}")
    return modules


def find_module_by_name(project: Project, name: str) -> Optional[Module]:
    """Находит модуль по имени"""
    logging.info(f"Поиск модуля по имени: {name}")
    module = project.find_module(name)
    if module:
        logging.info(f"Модуль найден: {module.name}")
    else:
        logging.warning(f"Модуль не найден: {name}")
    return module


def print_files_info(project: Project, module_filter: Optional[str] = None) -> None:
    """
    Выводит информацию о файлах в модулях
    
    Args:
        project: Объект проекта
        module_filter: Опциональный фильтр по имени модуля
    """
    logging.info(f"Вывод информации о файлах. Фильтр модуля: {module_filter}")
    files_info = project.get_files_info(module_filter)
    root_dir = Path(project.root_directory) if hasattr(project, 'root_directory') else Path.cwd()
    logging.debug(f"Корневая директория: {root_dir}")
    
    # Используем DetailedTextVisitor для вывода
    visitor = DetailedTextVisitor(root_dir)
    project.accept(visitor)
    print(visitor.get_result())


def get_files_data(project: Project, module_filter: Optional[str] = None) -> dict:
    """
    Собирает данные о файлах в формате для JSON
    
    Args:
        project: Объект проекта
        module_filter: Опциональный фильтр по имени модуля
        
    Returns:
        dict: Данные в формате для JSON
    """
    logging.info(f"Сбор данных о файлах в JSON формате. Фильтр модуля: {module_filter}")
    # Используем JsonVisitor для получения данных
    visitor = JsonVisitor()
    project.accept(visitor)
    result = json.loads(visitor.get_result())
    logging.debug(f"Собрано модулей: {len(result.get('modules', []))}")
    return result


def load_project(json_path: str) -> Project:
    logging.info(f"Загрузка проекта из файла: {json_path}")
    # Если путь не абсолютный, ищем относительно директории скрипта
    if not Path(json_path).is_absolute():
        json_path = Path(__file__).parent / json_path
        logging.debug(f"Преобразованный путь: {json_path}")
    
    try:
        with open(json_path) as f:
            data = json.load(f)
            logging.debug("JSON файл успешно прочитан")
    except FileNotFoundError:
        logging.error(f"Файл {json_path} не найден")
        print(f"Ошибка: Файл {json_path} не найден")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logging.error(f"Ошибка декодирования JSON: {e}")
        print(f"Ошибка: Некорректный JSON файл: {e}")
        sys.exit(1)
    
    project = Project(data.get("name", "Unnamed Project"))
    if "root_directory" in data:
        project.root_directory = data["root_directory"]
        logging.debug(f"Установлена корневая директория проекта: {project.root_directory}")
    
    modules_data = data.get("modules", [])
    logging.info(f"Найдено модулей в JSON: {len(modules_data)}")
    
    for module_data in modules_data:
        module = Module.from_dict(module_data)
        project.add_module(module)
        logging.debug(f"Добавлен модуль: {module.name}")
        
    return project


def main():
    logging.info("Запуск программы")
    parser = argparse.ArgumentParser(description="Architecture analysis tool")
    parser.add_argument("command", choices=["files"], help="Command to execute")
    parser.add_argument("--format", choices=["text", "json", "detailed"], default="text", 
                      help="Output format (text=simple format, detailed=detailed format, json=JSON format)")
    parser.add_argument("--output", help="Output file path")
    
    args = parser.parse_args()
    logging.info(f"Аргументы командной строки: {args}")
    
    # Load project
    project = load_project("architecture.json")
    logging.info(f"Проект загружен: {project.name}")
    
    # Get root directory
    root_dir = Path(project.root_directory) if hasattr(project, 'root_directory') else Path.cwd()
    logging.debug(f"Корневая директория: {root_dir}")
    
    # Scan files in all modules
    logging.info("Начало сканирования файлов")
    for module in project.modules:
        logging.debug(f"Сканирование файлов для модуля: {module.name}")
        module.scan_files(root_dir)
    
    # Create appropriate visitor
    logging.info(f"Создание visitor'а для формата: {args.format}")
    if args.format == "json":
        visitor = JsonVisitor()
    elif args.format == "detailed":
        visitor = DetailedTextVisitor(root_dir)
    else:
        visitor = TextVisitor()
    
    # Visit project structure
    logging.info("Обход структуры проекта")
    project.accept(visitor)
    
    # Get and output result
    result = visitor.get_result()
    
    if args.output:
        logging.info(f"Сохранение результата в файл: {args.output}")
        with open(args.output, "w") as f:
            f.write(result)
    else:
        logging.info("Вывод результата в консоль")
        print(result)

    logging.info("Программа завершена")


if __name__ == "__main__":
    main() 