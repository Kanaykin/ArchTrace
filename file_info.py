from __future__ import annotations
from dataclasses import dataclass, field
from typing import Set
from pathlib import Path


@dataclass
class FileInfo:
    """Информация о файле"""
    name: str                  # Имя файла без расширения
    paths: Set[Path] = field(default_factory=set)  # Множество путей к файлам с этим именем
    
    @classmethod
    def from_path(cls, path: Path) -> FileInfo:
        """Создает объект FileInfo из пути к файлу"""
        return cls(
            name=path.stem,
            paths={path}
        )
    
    def add_path(self, path: Path) -> None:
        """Добавляет путь к файлу с тем же именем"""
        if path.stem == self.name:
            self.paths.add(path)
    
    def __hash__(self) -> int:
        """Хеш для использования в множествах"""
        return hash(self.name)
    
    def __eq__(self, other: object) -> bool:
        """Сравнение для использования в множествах"""
        if not isinstance(other, FileInfo):
            return NotImplemented
        return self.name == other.name 