from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Set, Optional
from pathlib import Path
import json
import logging

from .project import Project
from .module import Module
from .file_info import FileInfo


class JsonDeserializer:
    """Класс для десериализации JSON в объекты Project"""

    @staticmethod
    def deserialize_file_info(data: Dict[str, List[str]]) -> Dict[str, FileInfo]:
        """
        Десериализует информацию о файлах из JSON
        
        Args:
            data: Словарь {имя_файла: список_путей}
            
        Returns:
            Dict[str, FileInfo]: Словарь {имя: информация о файле}
        """
        logging.debug(f"Начало десериализации информации о файлах. Количество файлов: {len(data)}")
        result = {}
        for name, paths in data.items():
            file_info = FileInfo(name=name)
            for path in paths:
                file_info.add_path(Path(path))
                logging.debug(f"Добавлен путь {path} для файла {name}")
            result[name] = file_info
        logging.debug(f"Завершена десериализация информации о файлах. Обработано файлов: {len(result)}")
        return result

    @classmethod
    def deserialize_module(cls, data: dict) -> Module:
        """
        Десериализует модуль из JSON
        
        Args:
            data: Словарь с данными модуля
            
        Returns:
            Module: Объект модуля
        """
        module_name = data.get("name", "Unnamed Module")
        logging.debug(f"Начало десериализации модуля: {module_name}")
        
        # Создаем множество путей
        paths = set(data.get("paths", []))
        logging.debug(f"Модуль {module_name}: найдено {len(paths)} путей")
        
        # Десериализуем подмодули, если они есть
        submodules = []
        if "submodules" in data:
            logging.debug(f"Суб Модуль {module_name}: начало десериализации подмодулей")
            submodules = [cls.deserialize_module(submodule) for submodule in data["submodules"]]
            logging.debug(f"Суб Модуль {module_name}: десериализовано {len(submodules)} подмодулей")
        
        # Десериализуем файлы
        logging.debug(f"Модуль {module_name}: начало десериализации файлов")
        files = cls.deserialize_file_info(data.get("files", {}))
        logging.debug(f"Модуль {module_name}: десериализовано {len(files)} файлов")
        
        # Создаем модуль
        module = Module(
            name=module_name,
            paths=paths,
            owners=data.get("owners"),
            description=data.get("description"),
            submodules=submodules,
            files=files
        )
        
        owners = data.get("owners", [])
        if owners:
            logging.debug(f"Модуль {module_name}: владельцы: {', '.join(owners)}")
        
        logging.debug(f"Завершена десериализация модуля {module_name}")
        return module

    @classmethod
    def deserialize(cls, json_path: str | Path) -> Project:
        """
        Десериализует проект из JSON файла
        
        Args:
            json_path: Путь к JSON файлу
            
        Returns:
            Project: Объект проекта
        """
        logging.info(f"Начинаем десериализацию из файла {json_path}")
        
        json_path = Path(json_path)
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logging.debug(f"Размер загруженного JSON: {len(str(data))} байт")
        except FileNotFoundError:
            logging.error(f"Файл {json_path} не найден")
            raise
        except json.JSONDecodeError as e:
            logging.error(f"Ошибка при разборе JSON: {e}")
            raise
            
        logging.info("JSON файл успешно загружен")
        
        try:
            # Создаем проект
            project_name = data.get("name", "Unnamed Project")
            root_directory = data.get("root_directory", "")
            logging.debug(f"Создание проекта: {project_name}, корневая директория: {root_directory}")
            
            project = Project(
                name=project_name,
                root_directory=root_directory,
                modules=[]
            )
            
            # Десериализуем модули
            modules_data = data.get("modules", [])
            logging.info(f"Начало десериализации {len(modules_data)} модулей")
            
            for i, module_data in enumerate(modules_data, 1):
                logging.debug(f"Десериализация модуля {i}/{len(modules_data)}")
                module = cls.deserialize_module(module_data)
                project.add_module(module)
                logging.debug(f"Десериализован модуль {module.name} с {len(module.files)} файлами и {len(module.submodules or [])} подмодулями")
            
            logging.info(f"Проект {project.name} успешно десериализован с {len(project.modules)} модулями")
            return project
            
        except KeyError as e:
            logging.error(f"Отсутствует обязательное поле в JSON: {e}")
            raise
        except Exception as e:
            logging.error(f"Ошибка при десериализации: {e}")
            raise 