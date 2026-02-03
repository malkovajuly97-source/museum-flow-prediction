# 135 аттракций для Unity (Nancy_floor0)

Как не расставлять 135 точек вручную: экспорт координат из Python и автоматическое создание точек в Unity.

---

## Шаг 1: Экспорт координат (здесь, в репозитории bird-dataset-main)

1. Открой терминал в папке **bird-dataset-main** (корень репозитория, где лежит `export_floor0_attractions_for_unity.py`).
2. Выполни:
   ```bash
   python export_floor0_attractions_for_unity.py
   ```
3. В корне появится файл **floor0_attractions.json** — в нём координаты всех картин этажа 0.

---

## Шаг 2: Куда вставить файлы в Unity (проект Nancy_floor0)

### 2.1 JSON для Unity

1. В проекте Unity в папке **Assets** создай папку **StreamingAssets**, если её ещё нет (ПКМ по Assets → Create → Folder → `StreamingAssets`).
2. Скопируй **floor0_attractions.json** из репозитория в папку **Assets/StreamingAssets/**.

### 2.2 Скрипты Unity

Скопируй в проект Nancy_floor0 так, чтобы структура папок сохранилась:

| Откуда (в репозитории) | Куда (в Unity) |
|------------------------|-----------------|
| `UnityScripts/AgentPath.cs` | **Assets/AgentPath.cs** (или в папку Scripts) |
| `UnityScripts/AgentSpawnManager.cs` | **Assets/AgentSpawnManager.cs** |
| `UnityScripts/TrackRecorder.cs` | **Assets/TrackRecorder.cs** |
| `UnityScripts/Editor/CreateAttractionPointsEditor.cs` | **Assets/Editor/CreateAttractionPointsEditor.cs** |

Важно: скрипт с меню **обязательно** должен лежать в папке **Editor** (например `Assets/Editor/` или `Assets/Scripts/Editor/`), иначе пункт меню не появится.

---

## Шаг 3: В Unity

1. Убедись, что на сцене есть объект **Capsule** с компонентами **NavMeshAgent** и **AgentPath** (скрипт AgentPath.cs).
2. В меню Unity выбери: **Tools → Floor0 → Create 135 Attraction Points from JSON**.
3. Скрипт:
   - прочитает **floor0_attractions.json** из StreamingAssets;
   - создаст пустой объект **Attractions** и под ним 135 дочерних объектов (P1, P2, … или по id картин);
   - расставит их по координатам плана (масштаб и смещение зашиты в скрипте — см. ниже);
   - найдёт **Capsule**, возьмёт у него **AgentPath** и заполнит массив **Points** этими 135 объектами.

После этого агент (Capsule) будет ходить по всем 135 точкам по порядку.

---

## Если точки «не на плане» (масштаб/смещение)

Координаты в JSON — в единицах плана музея. В редакторе в файле **CreateAttractionPointsEditor.cs** в методе `CreateAttractionPoints()` заданы:

- `scale = 0.01f` — уменьшение плана под размер сцены;
- `offsetX = 400f`, `offsetZ = 4700f` — смещение центра;
- `y = 0f` — высота точек (пол).

Подгони эти три числа под размер и положение твоего этажа в сцене Unity (например, посмотри, где у тебя лежит модель пола, и подбери scale/offset так, чтобы точки оказались на полу).

---

## Запись треков и экспорт в DXF

1. Добавь на сцену пустой объект и повесь на него **TrackRecorder**.
2. В Inspector укажи **Floor** (объект пола) и **Attractions Container** (контейнер с точками аттракций).
   - Floor — для границ пола и преобразования координат.
   - Attractions — если указан, план (контур пола + точки аттракций) экспортируется в тот же JSON. Треки и план будут в одной системе координат.
3. Убедись, что **floor0_attractions.json** лежит в **StreamingAssets** (нужен для границ плана).
4. Запусти сцену, дай агентам походить.
5. ПКМ по TrackRecorder → **Сохранить треки** (или **S**) — треки и план сохранятся в `unity_tracks.json`.
6. Экспорт в DXF: в папке bird-dataset-main выполни:
   ```bash
   python export_unity_tracks_to_dxf.py
   ```
   Или укажи путь к JSON:
   ```bash
   python export_unity_tracks_to_dxf.py путь/к/unity_tracks.json
   ```
   Будет создан **unity_tracks.dxf** рядом с JSON.

---

## Кратко: что куда

| Что | Куда |
|-----|------|
| **floor0_attractions.json** | Unity: **Assets/StreamingAssets/** |
| **AgentPath.cs** | Unity: **Assets/** (или Assets/Scripts/) |
| **CreateAttractionPointsEditor.cs** | Unity: **Assets/Editor/** |
| Запуск | В Unity: меню **Tools → Floor0 → Create 135 Attraction Points from JSON** |
