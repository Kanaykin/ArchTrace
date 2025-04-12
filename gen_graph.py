#!/usr/bin/env python3

import json
import os
import colorsys
from datetime import datetime
import logging
from pathlib import Path
import random

from deserializer import JsonDeserializer

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('graph_generation.log'),
        logging.StreamHandler()
    ]
)

def generate_new_color(index, is_submodule=False):
    """Генерирует уникальный цвет для модулей."""
    hue = (index * 0.618033988749895) % 1.0  # Используем золотое сечение
    saturation = 0.3 if is_submodule else 0.5
    value = 0.95
    r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
    return f'#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}'

def extract_module_hierarchy(module_name):
    """Извлекает иерархию модуля из его имени."""
    parts = []
    for path in module_name.split('/'):
        if path and path not in ['src', '..', '.']:
            parts.append(path)
    
    # Строим полную иерархию
    hierarchy = []
    current_path = ""
    for part in parts:
        if current_path:
            current_path += "/"
        current_path += part
        hierarchy.append({
            'level': len(hierarchy),
            'name': part,
            'full_path': current_path
        })
    
    return hierarchy

def process_module_hierarchy(module, hierarchy):
    """Обрабатывает иерархию модуля и создает вложенную структуру."""
    if not hierarchy:
        return None
    
    current_level = hierarchy[0]
    submodules = []
    
    # Обрабатываем текущий уровень
    files = {
        file.name: str(next(iter(file.paths)))
        for file in module.files.values()
        if file.paths and any(
            file.name.startswith(current_level['full_path'])
            for path in file.paths
        )
    }
    
    # Рекурсивно обрабатываем подмодули
    if len(hierarchy) > 1:
        next_level = process_module_hierarchy(module, hierarchy[1:])
        if next_level:
            submodules.append(next_level)
    
    return {
        "name": current_level['name'],
        "full_path": current_level['full_path'],
        "level": current_level['level'],
        "files": files,
        "submodules": submodules
    }

def generate_file_graph(modules):
    """Генерирует граф на основе файлов."""
    graph_data = {
        "nodes": [],
        "links": []
    }
    
    # Собираем все файлы из всех модулей и подмодулей
    all_files = {}  # path -> node_data
    file_to_module = {}  # path -> module_name
    
    for module_name, module_data in modules.items():
        main_module = module_data["main"]
        if not main_module:
            continue
            
        # Функция для рекурсивного сбора файлов из модуля и его подмодулей
        def collect_files_from_module(module, parent_name):
            for file in module.files.values():
                if not file.paths:
                    continue
                    
                file_path = str(next(iter(file.paths)))
                if file_path not in all_files:
                    # Определяем тип файла по расширению
                    ext = os.path.splitext(file_path)[1].lower()
                    color = {
                        '.h': '#4CAF50',    # Зеленый для заголовочных файлов
                        '.cpp': '#2196F3',   # Синий для C++ файлов
                        '.py': '#FFC107',    # Желтый для Python файлов
                        '.lua': '#9C27B0',   # Фиолетовый для Lua файлов
                        '.xml': '#FF5722',   # Оранжевый для XML файлов
                        '.json': '#795548',  # Коричневый для JSON файлов
                    }.get(ext, '#9E9E9E')    # Серый для остальных типов
                    
                    all_files[file_path] = {
                        "id": file_path,
                        "name": os.path.basename(file_path),
                        "full_path": file_path,
                        "type": ext,
                        "color": color,
                        "weight": 20  # Базовый размер для файлов
                    }
                    file_to_module[file_path] = parent_name
            
            # Рекурсивно обрабатываем подмодули
            for submodule in module.submodules:
                collect_files_from_module(submodule, parent_name)
        
        collect_files_from_module(main_module, module_name)
    
    # Добавляем все файлы как узлы
    graph_data["nodes"] = list(all_files.values())
    
    # Создаем связи между файлами
    random.seed(42)  # Для воспроизводимости результатов
    
    # Функция для создания хеша из двух путей
    def path_hash(path1, path2):
        return hash(path1 + path2) % 100
    
    # Создаем связи между файлами
    for file1_path, file1_data in all_files.items():
        for file2_path, file2_data in all_files.items():
            if file1_path >= file2_path:  # Пропускаем дубликаты и связи с самим собой
                continue
                
            should_link = False
            link_type = None
            
            # Файлы из одного модуля имеют больше шансов быть связанными
            if file_to_module[file1_path] == file_to_module[file2_path]:
                should_link = path_hash(file1_path, file2_path) < 30  # 30% шанс
                link_type = "same_module"
            
            # Связи между .h и .cpp файлами
            elif (file1_data["type"] == ".h" and file2_data["type"] == ".cpp" or
                  file1_data["type"] == ".cpp" and file2_data["type"] == ".h"):
                base1 = os.path.splitext(file1_data["name"])[0]
                base2 = os.path.splitext(file2_data["name"])[0]
                if base1 == base2:
                    should_link = True
                    link_type = "header_source"
            
            # Случайные связи между разными модулями
            else:
                should_link = path_hash(file1_path, file2_path) < 5  # 5% шанс
                link_type = "random"
            
            if should_link:
                link_color = {
                    "same_module": "#4CAF50",  # Зеленый для файлов из одного модуля
                    "header_source": "#2196F3", # Синий для связей h-cpp
                    "random": "#9E9E9E"        # Серый для случайных связей
                }[link_type]
                
                graph_data["links"].append({
                    "source": file1_path,
                    "target": file2_path,
                    "weight": 2 if link_type == "header_source" else 1,
                    "color": link_color,
                    "type": link_type
                })
    
    return graph_data

def generate_html_with_improvements(graph_data, template_path, output_path):
    """Генерирует HTML файл с визуализацией на основе шаблона и данных."""
    with open(template_path, "r", encoding="utf-8") as file:
        html_template = file.read()

    # Обновляем легенду для файлового графа
    legend_html = """
    <div class="legend">
        <h3>Legend</h3>
        <h4>File Types:</h4>
        <div class="legend-item"><div class="legend-color" style="background: #4CAF50"></div>Header (.h)</div>
        <div class="legend-item"><div class="legend-color" style="background: #2196F3"></div>Source (.cpp)</div>
        <div class="legend-item"><div class="legend-color" style="background: #FFC107"></div>Python (.py)</div>
        <div class="legend-item"><div class="legend-color" style="background: #9C27B0"></div>Lua (.lua)</div>
        <div class="legend-item"><div class="legend-color" style="background: #FF5722"></div>XML (.xml)</div>
        <div class="legend-item"><div class="legend-color" style="background: #795548"></div>JSON (.json)</div>
        <h4>Connection Types:</h4>
        <div class="legend-item"><div class="legend-color" style="background: #4CAF50"></div>Same Module</div>
        <div class="legend-item"><div class="legend-color" style="background: #2196F3"></div>Header-Source</div>
        <div class="legend-item"><div class="legend-color" style="background: #9E9E9E"></div>Random</div>
    </div>
    """
    
    html_template = html_template.replace('<div class="legend"></div>', legend_html)

    # Вставка JSON графа
    graph_json = json.dumps(graph_data).replace("</", "<\\/")
    html_filled = html_template.replace("{{GRAPH_DATA}}", graph_json)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_filled)

def create_template():
    """Создает HTML шаблон для визуализации."""
    template = """<!DOCTYPE html>
<html>
<head>
    <title>Project Files Visualization</title>
    <meta charset="utf-8">
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f5f5f5;
        }
        #graph {
            width: 100%;
            height: 100vh;
            background-color: white;
        }
        .controls {
            position: fixed;
            top: 20px;
            left: 20px;
            z-index: 1;
            background: rgba(255, 255, 255, 0.9);
            padding: 10px;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .file-info {
            position: fixed;
            right: 20px;
            top: 20px;
            width: 300px;
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            display: none;
            max-height: 80vh;
            overflow-y: auto;
        }
        .search-box {
            width: 200px;
            padding: 5px;
            margin: 5px;
        }
        button {
            margin: 5px;
            padding: 5px 10px;
        }
        .legend {
            position: fixed;
            left: 20px;
            bottom: 20px;
            background: white;
            padding: 10px;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            font-size: 12px;
        }
        .legend-item {
            display: flex;
            align-items: center;
            margin: 5px 0;
        }
        .legend-color {
            width: 15px;
            height: 15px;
            margin-right: 10px;
            border-radius: 3px;
        }
    </style>
    <script src="https://unpkg.com/force-graph"></script>
</head>
<body>
    <div class="controls">
        <input type="text" class="search-box" placeholder="Search files..." onkeyup="searchNodes(this.value)">
        <button onclick="resetCamera()">Reset View</button>
        <button onclick="toggleLabels()">Toggle Labels</button>
        <button onclick="toggleLinks()">Toggle Links</button>
    </div>
    <div class="file-info">
        <h3>File Details</h3>
        <p class="file-path"></p>
        <p class="file-type"></p>
    </div>
    <div id="graph"></div>
    <div class="legend"></div>

    <script>
        const graphData = {{GRAPH_DATA}};
        let showLabels = true;
        let showLinks = true;

        // Создаем граф
        const Graph = ForceGraph()
            (document.getElementById('graph'))
            .graphData(graphData)
            .nodeId('id')
            .nodeVal('weight')
            .nodeLabel('name')
            .nodeColor('color')
            .linkColor(link => link.color)
            .linkWidth(link => link.weight)
            .linkDirectionalParticles(3)
            .linkDirectionalParticleWidth(2)
            .onNodeDragEnd(node => {
                node.fx = node.x;
                node.fy = node.y;
            })
            .onNodeClick(node => {
                const fileInfo = document.querySelector('.file-info');
                const filePath = fileInfo.querySelector('.file-path');
                const fileType = fileInfo.querySelector('.file-type');
                
                filePath.textContent = `Path: ${node.full_path}`;
                fileType.textContent = `Type: ${node.type || 'Unknown'}`;
                fileInfo.style.display = 'block';
            })
            .nodeCanvasObject((node, ctx, globalScale) => {
                const label = node.name;
                const fontSize = 12/globalScale;
                ctx.font = `${fontSize}px Sans-Serif`;
                const textWidth = ctx.measureText(label).width;
                const radius = Math.sqrt(node.weight) * 2;

                ctx.beginPath();
                ctx.fillStyle = node.color;
                ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false);
                ctx.fill();

                if (showLabels && globalScale > 0.4) {
                    ctx.fillStyle = 'black';
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.fillText(label, node.x, node.y + radius + fontSize/2);
                }
            });

        // Функции управления
        function resetCamera() {
            Graph.zoomToFit(400);
        }

        function toggleLabels() {
            showLabels = !showLabels;
            Graph.refresh();
        }

        function toggleLinks() {
            showLinks = !showLinks;
            Graph.linkVisibility(showLinks);
        }

        function searchNodes(query) {
            const searchStr = query.toLowerCase();
            Graph.nodeVisibility(node => 
                !searchStr || 
                node.name.toLowerCase().includes(searchStr) ||
                node.full_path.toLowerCase().includes(searchStr)
            );
        }

        // Начальная подгонка графа под размер экрана
        setTimeout(() => {
            Graph.zoomToFit(400);
        }, 500);
    </script>
</body>
</html>"""
    return template

def main():
    """Основная функция."""
    logging.info("Starting graph generation")
    
    # Загружаем данные о модулях
    try:
        project = JsonDeserializer.deserialize("result.json")
        logging.info(f"Loaded project with {len(project.modules)} modules")
        
        # Группируем модули по иерархии
        module_hierarchy = {}
        for module in project.modules:
            module_hierarchy[module.name] = {
                "main": module,
                "subs": set()
            }
            if module.submodules:
                for submodule in module.submodules:
                    module_hierarchy[module.name]["subs"].add(submodule.name)
        
        # Генерируем граф на основе файлов
        graph_data = generate_file_graph(module_hierarchy)
        
        # Создаем HTML файл с визуализацией
        script_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(script_dir, "template.html")
        output_path = os.path.join(script_dir, "index.html")
        
        if not os.path.exists(template_path):
            with open(template_path, "w", encoding="utf-8") as f:
                f.write(create_template())
        
        generate_html_with_improvements(graph_data, template_path, output_path)
        logging.info(f"Generated graph with {len(graph_data['nodes'])} files and {len(graph_data['links'])} connections")
    except Exception as e:
        logging.error(f"Failed to generate graph: {e}")
        raise

if __name__ == "__main__":
    main() 