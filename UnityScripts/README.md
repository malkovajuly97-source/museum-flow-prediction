# Unity Scripts — Описание

Скрипты для симуляции посетителей музея и экспорта плана этажа с треками агентов.

---

## Агенты

### AgentPath.cs
**Назначение:** Управление движением агента по точкам аттракций с помощью NavMeshAgent.

**Функции:**
- Обход точек (картин) по маршруту (по умолчанию 5 объектов)
- Поддержка `allPointsContainer` — выбор случайных N точек при старте
- **preferNeighbors** — следующий пункт выбирается из K ближайших не посещённых (логично для музея)
- Избегание толпы: пропуск точки, если рядом ≥ N агентов
- После обхода — переход к ближайшей точке выхода (5 лестниц) и исчезновение (Destroy)
- Зацикливание маршрута (опционально)

**Зависимости:** NavMeshAgent

---

### AgentSpawnManager.cs
**Назначение:** Создание агентов с разнесённым по времени появлением.

**Функции:**
- Спавн префаба агента по интервалу (min..max сек)
- Передача контейнера аттракций и точек выхода каждому агенту
- Случайное количество точек маршрута на агента (min..max, по умолчанию 5–25)

**Настройка:** Префаб агента, Attractions Container, Spawn Points, Exit Points (5). Если Exit Points пуст — автоматически ищет объект Exit и его дочерние (лестницы).

---

## Экспорт плана и треков

### ExportPlanToDxf.cs
**Назначение:** Экспорт геометрии пола и стен в JSON для последующей конвертации в DXF.

**Функции:**
- Извлечение внешнего контура пола из меша (граничные рёбра)
- Экспорт стен: контуры или прямоугольники (wall_outlines / wall_rects)
- Сохранение в `unity_plan.json`

**Использование:** ПКМ по компоненту → «Экспорт плана в JSON». Затем: `python export_unity_plan_to_dxf.py unity_plan.json`

---

### ExportPlanToJson.cs
**Назначение:** Экспорт плана этажа (пол + стены) в JSON.

**Функции:** Аналогично ExportPlanToDxf — контур пола, стены (outlines/rects). Сохраняет в `unity_plan.json`.

**Использование:** ПКМ → «Экспорт плана в JSON»

---

### PlanAndTrackExporter.cs
**Назначение:** Объединённый экспорт плана этажа и треков агентов в один JSON.

**Функции:**
- Запись позиций агентов (AgentPath) каждые `recordInterval` сек
- Экспорт: trajectories, floor_outline, wall_outlines, wall_rects, plan_points (Attractions)
- Приоритет контура пола: `unity_plan.json` → Floor mesh → floor_bounds
- `floorFallbackTransform` — запасной объект для bounds, если Floor не даёт контур

**Использование:** ПКМ → «Экспорт план + треки» или клавиша **S** в Play mode

**Выход:** `unity_plan_and_tracks.json`

---

### TrackRecorder.cs
**Назначение:** Запись треков агентов и плана этажа в JSON (отдельно от PlanAndTrackExporter).

**Функции:**
- Запись позиций агентов (AgentPath) по интервалу
- Экспорт: trajectories, floor_outline/floor_bounds, wall_rects, plan_points

**Использование:** ПКМ → «Сохранить треки» или клавиша **S**

**Выход:** `unity_tracks.json`

---

## Editor

### Editor/CreateAttractionPointsEditor.cs
**Назначение:** Editor-скрипт для создания точек аттракций из JSON.

**Функции:**
- Читает `floor0_attractions.json` из StreamingAssets
- Создаёт пустые объекты (Sphere) по координатам, масштабирует под границы Floor
- Создаёт контейнер Attractions и заполняет AgentPath.points у Capsule

**Использование:** Меню **Tools → Floor0 → Create 135 Attraction Points from JSON**

**Требования:** Объект Floor в сцене, файл `floor0_attractions.json` в StreamingAssets

---

## Связи между скриптами

```
AgentSpawnManager → создаёт агентов с AgentPath
AgentPath         → использует Attractions (точки картин)
PlanAndTrackExporter / TrackRecorder → записывают AgentPath, экспортируют план
ExportPlanToDxf / ExportPlanToJson   → только план (пол + стены)
CreateAttractionPointsEditor         → создаёт Attractions из JSON
```

---

## Файлы вывода

| Файл | Скрипт |
|------|--------|
| `unity_plan.json` | ExportPlanToDxf, ExportPlanToJson |
| `unity_plan_and_tracks.json` | PlanAndTrackExporter |
| `unity_tracks.json` | TrackRecorder |
