from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set
from pathlib import Path
import json

from module import Module
from file_info import FileInfo


@dataclass
class Project:
    """Класс для представления проекта"""
    name: str
    root_directory: str = ""
    modules: List[Module] = field(default_factory=list)

    @classmethod
    def from_json(cls, json_path: str | Path) -> Project:
        """Создает объект Project из JSON файла"""
        json_path = Path(json_path)
        with open(json_path, 'r') as f:
            data = json.load(f)
            
        project = cls(
            name=data["project"],
            root_directory=data.get("root_directory", ""),
            modules=[Module.from_dict(module) for module in data["modules"]]
        )
        
        # Сканируем файлы всех модулей
        # Если путь относительный, берем его относительно расположения JSON файла
        root = Path(project.root_directory)
        if not root.is_absolute():
            root = json_path.parent / project.root_directory
        root = root.resolve()  # Преобразуем в абсолютный путь
        
        # for module in project.modules:
            # module.scan_files(root)
        
        return project

    def find_module(self, name: str) -> Optional[Module]:
        """Поиск модуля по имени во всем проекте"""
        for module in self.modules:
            found = module.find_module(name)
            if found:
                return found
        return None

    def get_all_paths(self) -> List[str]:
        """Получает все пути всех модулей проекта"""
        result = []
        for module in self.modules:
            result.extend(module.get_all_paths())
        return result

    def get_project_hierarchy(self) -> str:
        """Возвращает строковое представление иерархии проекта"""
        result = f"Проект: {self.name}\n"
        if self.root_directory:
            result += f"Корневая директория: {self.root_directory}\n"
        
        total_files = sum(module.get_files_count() for module in self.modules)
        result += f"Всего файлов: {total_files}\n\n"
        
        for module in self.modules:
            result += module.get_module_hierarchy(1)
        return result

    def find_by_owner(self, owner_email: str) -> List[Module]:
        """Поиск всех модулей по владельцу во всем проекте"""
        result = []
        for module in self.modules:
            result.extend(module.find_by_owner(owner_email))
        return result

    def get_files_info(self, module_filter: Optional[str] = None) -> Dict[str, Set[FileInfo]]:
        """
        Возвращает информацию о файлах в модулях
        
        Args:
            module_filter: Опциональный фильтр по имени модуля
            
        Returns:
            Dict[str, Set[FileInfo]]: Словарь {имя_модуля: множество_файлов}
        """
        result = {}
        for module in self.modules:
            if not module_filter or module_filter.lower() in module.name.lower():
                files = module.get_all_files()
                if files:  # Пропускаем пустые модули
                    result[module.name] = files
        return result

    def __init__(self, name: str, root_directory: str = "", modules: List[Module] = None):
        self.name = name
        self.root_directory = root_directory
        self.modules = modules or []
        
    def add_module(self, module: Module) -> None:
        self.modules.append(module)
        
    def get_total_files(self) -> int:
        total = 0
        for module in self.modules:
            total += len(module.get_all_files())
        return total
        
    def accept(self, visitor) -> None:
        visitor.visit_project(self)
        for module in self.modules:
            module.accept(visitor) 