from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set
from pathlib import Path

from file_info import FileInfo
import logging


@dataclass
class Module:
    """Базовый класс для модулей проекта"""
    name: str
    paths: Set[str]
    owners: Optional[List[str]] = None
    description: Optional[str] = None
    submodules: List[Module] = None
    files: Dict[str, FileInfo] = field(default_factory=dict)  # Словарь {имя: информация о файле}

    @classmethod
    def from_dict(cls, data: dict) -> Module:
        """Создает объект Module из словаря"""
        submodules = []
        if "submodules" in data:
            submodules = [cls.from_dict(submodule) for submodule in data["submodules"]]
        
        return cls(
            name=data["name"],
            paths=set(data["paths"]),
            owners=data.get("owners"),
            description=data.get("description"),
            submodules=submodules,
            files={}
        )
    
    def scan_files(self, root_dir: Optional[Path] = None) -> None:
        """
        Сканирует файлы в путях модуля
        
        Args:
            root_dir: Корневая директория проекта (опционально)
        """
        if root_dir is None:
            root_dir = Path.cwd()
        
        for path_str in self.paths:
            path = Path(path_str)
            if not path.is_absolute():
                path = root_dir / path
            
            if path.is_file():
                self._add_file(path)
            elif path.is_dir():
                for file_path in path.rglob("*"):
                    if file_path.is_file():
                        self._add_file(file_path)

    def _add_file(self, path: Path) -> None:
        """
        Добавляет файл в словарь файлов модуля
        
        Args:
            path: Путь к файлу
        """
        if not path or not path.exists():
            logging.warning(f"Attempted to add invalid path: {path}")
            return

        file_name = path.name
        if file_name not in self.files:
            self.files[file_name] = FileInfo(file_name)
        self.files[file_name].add_path(path)
        logging.debug(f"Added file {file_name} with path {path} to module {self.name}")

    def get_all_files(self) -> Dict[str, FileInfo]:
        """
        Возвращает все файлы модуля и его подмодулей
        
        Returns:
            Dict[str, FileInfo]: Словарь {имя_файла: информация_о_файле}
        """
        result = self.files.copy()
        if self.submodules:
            for submodule in self.submodules:
                for name, file_info in submodule.get_all_files().items():
                    if name in result:
                        for path in file_info.paths:
                            result[name].add_path(path)
                        else:
                            result[name] = file_info
        return result
    
    def get_files_count(self) -> int:
        """
        Возвращает количество уникальных файлов (по имени) в модуле и его подмодулях
        
        Returns:
            int: Количество файлов
        """
        count = len(self.files)
        if self.submodules:
            for submodule in self.submodules:
                count += submodule.get_files_count()
        return count

    def find_module(self, name: str) -> Optional[Module]:
        """Поиск модуля по имени в текущем модуле и его подмодулях"""
        if self.name == name:
            return self
        
        if self.submodules:
            for submodule in self.submodules:
                found = submodule.find_module(name)
                if found:
                    return found
        return None

    def get_all_paths(self) -> List[str]:
        """Получает все пути текущего модуля и его подмодулей"""
        result = list(self.paths)
        if self.submodules:
            for submodule in self.submodules:
                result.extend(submodule.get_all_paths())
        return result

    def get_module_hierarchy(self, level: int = 0) -> str:
        """Возвращает строковое представление иерархии модулей"""
        indent = "  " * level
        result = f"{indent}- {self.name}"
        if self.files:
            result += f" ({len(self.files)} файлов)"
        result += "\n"
        
        if self.description:
            result += f"{indent}  description: {self.description}\n"
        
        if self.owners:
            for owner in self.owners:
                result += f"{indent}  owner: {owner}\n"
        
        if self.paths:
            for path in self.paths:
                result += f"{indent}  path: {path}\n"
        
        if self.submodules:
            result += f"{indent}  submodules:\n"
            for submodule in self.submodules:
                result += submodule.get_module_hierarchy(level + 2)
        return result

    def find_by_owner(self, owner_email: str) -> List[Module]:
        """Поиск всех модулей, где указанный email является владельцем"""
        result = []
        if self.owners and owner_email in self.owners:
            result.append(self)
        
        if self.submodules:
            for submodule in self.submodules:
                result.extend(submodule.find_by_owner(owner_email))
        return result

    def add_path(self, path: str) -> None:
        self.paths.add(path)
        
    def add_submodule(self, module: 'Module') -> None:
        self.submodules.append(module)
        
    def accept(self, visitor) -> None:
        visitor.visit_module(self) 