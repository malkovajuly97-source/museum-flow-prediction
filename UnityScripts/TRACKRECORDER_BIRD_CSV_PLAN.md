# План: изменение TrackRecorder.cs для экспорта в формате BIRD

## Цель

Добавить в [TrackRecorder.cs](TrackRecorder.cs) экспорт траекторий в CSV формате BIRD (`timestamp,x,y,floorNumber`) для последующего сравнения с датасетом (ranking, transition matrix, density, ToP, stop duration).

---

## Текущее состояние

- Хранит `Dictionary<string, List<Vector2>>` — только позиции, без timestamp.
- Записывает каждые `recordInterval` сек.
- Экспорт только в JSON (`SaveTracks()`).

---

## Изменения

### 1. Структура данных

Заменить:

```csharp
Dictionary<string, List<Vector2>> _tracks
```

на:

```csharp
Dictionary<string, List<TrackPoint>> _tracks
```

Добавить структуру:

```csharp
struct TrackPoint
{
    public float time;   // Time.time в момент записи
    public Vector2 pos;
}
```

---

### 2. Update() — запись с timestamp

Строки 117–126: при добавлении точки сохранять `(Time.time, pos)` вместо только `pos`:

```csharp
if (!_tracks.ContainsKey(id)) _tracks[id] = new List<TrackPoint>();
Vector3 pos = ap.transform.position;
_tracks[id].Add(new TrackPoint { time = Time.time, pos = new Vector2(pos.x, pos.z) });
```

---

### 3. SaveTracks() — адаптация под TrackPoint

Строки 168–174: при сборке `TrajectoryData` для JSON брать `pt.pos`:

```csharp
foreach (var pt in kv.Value)
    pts.Add(new Point2D { x = pt.pos.x, y = pt.pos.y });
```

JSON остаётся без timestamp (обратная совместимость).

---

### 4. Новый метод SaveTracksToBirdsCsv()

```csharp
[ContextMenu("Экспорт в CSV (BIRD)")]
public void SaveTracksToBirdsCsv()
```

**Логика:**

- Базовая папка: та же, что для JSON (`saveToStreamingAssets` ? `streamingAssetsPath` : `persistentDataPath`).
- Подпапка: `outputCsvFolder` (например, `"unity_tracks_bird"`, задаётся в Inspector).
- Для каждой траектории:
  - `t0 = points[0].time`
  - Для каждой точки: `timestamp = pt.time - t0` (нормализация: первая точка = 0).
  - Строка CSV: `timestamp,x,y,floorNumber` (floorNumber = 0).
- Имя файла: `{trajectory_id}_traj.csv` (можно упростить: `Agent_0_traj.csv` и т.п.).
- Заголовок: `timestamp,x,y,floorNumber`.

**Формат CSV (как в BIRD):**

```csv
timestamp,x,y,floorNumber
0.0,12.5,8.3,0
2.0,12.7,8.1,0
4.0,13.0,7.9,0
```

---

### 5. Inspector

Добавить в секцию «Сохранение»:

| Поле | Тип | По умолчанию | Описание |
|------|-----|--------------|----------|
| `outputCsvFolder` | string | `"unity_tracks_bird"` | Подпапка для CSV |
| `floorNumber` | int | 0 | Значение floorNumber в CSV |

---

### 6. Связка с SaveTracks

Варианты:

- **A:** При нажатии S вызывать и `SaveTracks()`, и `SaveTracksToBirdsCsv()` (всегда оба формата).
- **B:** Добавить флаг `exportBirdsCsvOnSave` (bool): при `true` — при S вызывать оба метода.
- **C:** Только ContextMenu «Экспорт в CSV (BIRD)» — CSV сохраняется вручную.

**Рекомендация:** B — по умолчанию `exportBirdsCsvOnSave = true`, чтобы при S сохранялись и JSON, и CSV.

В `SaveTracks()` в конце добавить:

```csharp
if (exportBirdsCsvOnSave) SaveTracksToBirdsCsv();
```

В `OnDisable` уже вызывается `SaveTracks()`, поэтому CSV будет сохраняться автоматически.

---

## Порядок внедрения

1. Добавить `struct TrackPoint` и поменять `_tracks` на `List<TrackPoint>`.
2. Обновить `Update()` — запись с `Time.time`.
3. Обновить `SaveTracks()` — использование `pt.pos` и опциональный вызов `SaveTracksToBirdsCsv()`.
4. Реализовать `SaveTracksToBirdsCsv()`.
5. Добавить поля в Inspector: `outputCsvFolder`, `floorNumber`, `exportBirdsCsvOnSave`.
6. Добавить `[ContextMenu("Экспорт в CSV (BIRD)")]` на `SaveTracksToBirdsCsv()`.

---

## Примечания

- Используется `Time.time` — реальное время записи; нормализация `timestamp = pt.time - t0` даёт относительное время от начала траектории.
- Если `recordInterval = 2`, интервал будет близок к BIRD (2 сек).
- Координаты пишутся «как есть» из Unity (X, Z) — без transform.
