# ArchTrace

Инструмент для анализа архитектуры проекта и отслеживания файлов в модулях.

## Установка

```bash
# Из директории utils
pip install -e .
```

## Использование

### Базовый синтаксис
```bash
python3 -m ArchTrace.main files [--format FORMAT] [--output FILE]
```

### Параметры

- `--format` - формат вывода (по умолчанию: text)
  - `text` - простой текстовый формат с базовой информацией
  - `detailed` - подробный текстовый формат с полной информацией о модулях и файлах
  - `json` - вывод в формате JSON
- `--output` - путь для сохранения результата в файл (опционально)

### Примеры использования

1. Простой текстовый вывод:
```bash
python3 -m ArchTrace.main files --format text
```

2. Подробный вывод с информацией о файлах:
```bash
python3 -m ArchTrace.main files --format detailed
```

3. Вывод в формате JSON:
```bash
python3 -m ArchTrace.main files --format json
```

4. Сохранение результата в файл:
```bash
python3 -m ArchTrace.main files --format json --output result.json
```

## Конфигурация

Инструмент использует файл `architecture.json` для описания структуры проекта. Файл должен находиться в той же директории, что и скрипт.

### Пример структуры architecture.json:

```json
{
  "name": "Project Name",
  "root_directory": "/path/to/project",
  "modules": [
    {
      "name": "ModuleName",
      "description": "Module description",
      "owners": ["owner1@example.com", "owner2@example.com"],
      "paths": ["path/to/module"],
      "submodules": [
        {
          "name": "SubmoduleName",
          "description": "Submodule description",
          "owners": ["owner3@example.com"],
          "paths": ["path/to/submodule"]
        }
      ]
    }
  ]
}
```

## Форматы вывода

### Text Format
Простой текстовый формат, показывающий базовую информацию о модулях:
- Имя проекта
- Общее количество модулей и файлов
- Список модулей с их описанием и владельцами

### Detailed Format
Расширенный текстовый формат, включающий:
- Всю информацию из простого формата
- Пути к файлам
- Иерархию подмодулей
- Подробную информацию о файлах в каждом модуле

### JSON Format
Структурированный вывод в формате JSON, содержащий:
- Полную информацию о проекте
- Иерархическую структуру модулей
- Детальную информацию о файлах
- Метаданные (количество файлов, пути, владельцы)

## Визуализация

Для визуализации структуры проекта предоставляются два способа:

1. **Статическая визуализация с помощью GraphViz**
   - Генерирует PNG изображение с графом архитектуры
   - Подробнее в разделе [Использование GraphViz](#использование-graphviz)

2. **Интерактивная веб-визуализация с помощью D3.js**
   - Создает интерактивный граф в браузере
   - Позволяет исследовать структуру проекта
   - Подробные инструкции в файле [create_html_visualization.md](create_html_visualization.md)

### Использование GraphViz

Для работы визуализации необходимо установить GraphViz:

```bash
# macOS
brew install graphviz

# Ubuntu/Debian
sudo apt-get install graphviz

# Windows (с помощью chocolatey)
choco install graphviz
```

Также нужно установить Python-пакет:
```bash
pip install graphviz
```

### Использование

1. Сначала сохраните данные в JSON:
```bash
python3 -m ArchTrace.main files --format json --output project.json
```

2. Запустите визуализацию:
```bash
python3 visualize.py project.json [output_file]
```

Где:
- `project.json` - файл с данными о проекте
- `output_file` - опциональное имя выходного файла (по умолчанию: project_architecture)

Скрипт создаст два файла:
- `project_architecture` - исходный DOT файл
- `project_architecture.png` - визуализация в формате PNG

### Особенности визуализации

- Модули отображаются как прямоугольники с закругленными углами
- Для каждого модуля показывается:
  - Название
  - Описание (если есть)
  - Владельцы (если есть)
  - Количество файлов
- Иерархия модулей отображается с помощью стрелок
- Граф располагается горизонтально для лучшей читаемости

### Альтернативные инструменты визуализации

Также можно использовать другие инструменты для визуализации JSON-данных:

- [D3.js](https://d3js.org/) - для интерактивных веб-визуализаций
- [Mermaid.js](https://mermaid-js.github.io/) - для простых диаграмм
- [PlantUML](https://plantuml.com/) - для UML диаграмм 