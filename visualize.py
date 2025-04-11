#!/usr/bin/env python3

import json
import sys
from pathlib import Path
import graphviz

def create_graph(json_file: str, output_file: str = "project_architecture"):
    """
    Создает визуализацию архитектуры проекта из JSON файла
    
    Args:
        json_file: Путь к JSON файлу с данными
        output_file: Имя выходного файла (без расширения)
    """
    # Создаем направленный граф
    dot = graphviz.Digraph(comment='Project Architecture')
    dot.attr(rankdir='LR')  # Горизонтальное расположение
    
    # Загружаем данные
    with open(json_file) as f:
        data = json.load(f)
    
    def add_module(module, parent=None):
        # Создаем узел для модуля
        node_id = module["name"].replace(" ", "_")
        
        # Формируем метку узла
        label_parts = [module["name"]]
        if module.get("description"):
            label_parts.append(module["description"])
        if module.get("owners"):
            label_parts.append("Owners: " + ", ".join(module["owners"]))
        
        # Добавляем количество файлов
        files_count = len(module.get("files", {}))
        if files_count > 0:
            label_parts.append(f"Files: {files_count}")
        
        label = "\n".join(label_parts)
        
        # Настраиваем стиль узла
        dot.node(node_id, label, 
                shape='box',
                style='rounded,filled',
                fillcolor='lightblue',
                fontname='Arial')
        
        # Добавляем связь с родителем
        if parent:
            dot.edge(parent, node_id)
            
        # Обрабатываем подмодули
        for submodule in module.get("submodules", []):
            add_module(submodule, node_id)
    
    # Добавляем все модули
    for module in data["modules"]:
        add_module(module)
    
    # Сохраняем результат
    try:
        dot.render(output_file, format='png', cleanup=True)
        print(f"Визуализация сохранена в файлы:\n"
              f"- {output_file} (DOT файл)\n"
              f"- {output_file}.png (изображение)")
    except Exception as e:
        print(f"Ошибка при создании визуализации: {e}")
        sys.exit(1)

def main():
    if len(sys.argv) < 2:
        print("Использование: python3 visualize.py <json_file> [output_file]")
        sys.exit(1)
        
    json_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "project_architecture"
    
    if not Path(json_file).exists():
        print(f"Ошибка: Файл {json_file} не найден")
        sys.exit(1)
        
    create_graph(json_file, output_file)

if __name__ == "__main__":
    main() 