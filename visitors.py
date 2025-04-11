from abc import ABC, abstractmethod
import json
from typing import Dict, Any
from pathlib import Path
import logging

class ProjectVisitor(ABC):
    @abstractmethod
    def visit_project(self, project) -> None:
        pass
        
    @abstractmethod
    def visit_module(self, module) -> None:
        pass
        
    @abstractmethod
    def get_result(self) -> str:
        pass

class TextVisitor(ProjectVisitor):
    def __init__(self):
        self._output = []
        self._indent = 0
        
    def visit_project(self, project) -> None:
        self._output.append(f"Project: {project.name}")
        self._output.append(f"Total modules: {len(project.modules)}")
        self._output.append(f"Total files: {project.get_total_files()}")
        
    def visit_module(self, module) -> None:
        indent = "  " * self._indent
        self._output.append(f"{indent}Module: {module.name}")
        if module.description:
            self._output.append(f"{indent}Description: {module.description}")
        if module.owners:
            self._output.append(f"{indent}Owners: {', '.join(module.owners)}")
        if module.paths:
            self._output.append(f"{indent}Paths:")
            for path in module.paths:
                self._output.append(f"{indent}  - {path}")
        
        files = module.get_all_files()
        if files:
            self._output.append(f"{indent}Files:")
            for name, file_info in files.items():
                self._output.append(f"{indent}  {name}:")
                for path in file_info.paths:
                    self._output.append(f"{indent}    - {path}")
        
        self._indent += 1
        for submodule in module.submodules:
            self.visit_module(submodule)
        self._indent -= 1
        
    def get_result(self) -> str:
        return "\n".join(self._output)

class JsonVisitor(ProjectVisitor):
    def __init__(self):
        self._data = {}
        self._current_module = None
        self._module_stack = []
        
    def visit_project(self, project) -> None:
        self._data = {
            "name": project.name,
            "total_modules": len(project.modules),
            "total_files": project.get_total_files(),
            "modules": []
        }
        if hasattr(project, 'root_directory'):
            self._data["root_directory"] = project.root_directory
        
    def visit_module(self, module) -> None:
        module_data = {
            "name": module.name,
            "description": module.description,
            "owners": module.owners,
            "paths": list(module.paths),
            "files": {},
            "submodules": []
        }
        
        # Add files
        logging.debug(f"Processing files for module: {module.name}")
        files = module.get_all_files()
        logging.info(f"Found {len(files)} files in module {module.name}")
        
        for name, file_info in files.items():
            module_data["files"][name] = list(str(p) for p in file_info.paths)
            logging.debug(f"Added file {name} with {len(file_info.paths)} paths to module {module.name}")
            
        # Add to parent or project
        if self._current_module is None:
            self._data["modules"].append(module_data)
        else:
            self._current_module["submodules"].append(module_data)
            
        # Process submodules
        if module.submodules:
            self._module_stack.append(self._current_module)
            self._current_module = module_data
            for submodule in module.submodules:
                self.visit_module(submodule)
            self._current_module = self._module_stack.pop()
        
    def get_result(self) -> str:
        return json.dumps(self._data, indent=2, ensure_ascii=False)

class DetailedTextVisitor(ProjectVisitor):
    def __init__(self, root_directory: Path):
        self._output = []
        self._indent = 0
        self._root_directory = root_directory
        
    def visit_project(self, project) -> None:
        self._output.append(f"Проект: {project.name}")
        if hasattr(project, 'root_directory'):
            self._output.append(f"Корневая директория: {project.root_directory}")
        self._output.append(f"Всего модулей: {len(project.modules)}")
        self._output.append(f"Всего файлов: {project.get_total_files()}")
        
    def visit_module(self, module) -> None:
        indent = "  " * self._indent
        self._output.append(f"\n{indent}Модуль: {module.name}")
        
        if module.description:
            self._output.append(f"{indent}Описание: {module.description}")
        
        if module.owners:
            self._output.append(f"{indent}Владельцы:")
            for owner in module.owners:
                self._output.append(f"{indent}  - {owner}")
        
        if module.paths:
            self._output.append(f"{indent}Пути:")
            for path in module.paths:
                self._output.append(f"{indent}  - {path}")
        
        self._output.append(f"{indent}Количество уникальных файлов: {len(module.get_all_files())}")
        
        files = module.get_all_files()
        if files:
            self._output.append(f"{indent}Файлы:")
            for name, file_info in sorted(files.items()):
                self._output.append(f"{indent}  - {name}")
                for path in sorted(file_info.paths):
                    try:
                        rel_path = path.relative_to(self._root_directory)
                        self._output.append(f"{indent}    → {rel_path}")
                    except ValueError:
                        self._output.append(f"{indent}    → {path}")
        
        self._indent += 1
        for submodule in module.submodules:
            self.visit_module(submodule)
        self._indent -= 1
        
    def get_result(self) -> str:
        return "\n".join(self._output) 