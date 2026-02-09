using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

// Записывает треки агентов и план этажа из Unity в JSON. Всё в координатах Unity (X, Z) — треки и план совпадают.
// Положи на сцену, укажи Floor и Attractions Container.
public class TrackRecorder : MonoBehaviour
{
    [Header("План этажа")]
    [Tooltip("Объект пола (Floor) — контур пола экспортируется для наложения треков.")]
    public Transform floorTransform;

    [Tooltip("Контейнер Walls (стены) — дочерние объекты с Collider/Renderer экспортируются как прямоугольники плана.")]
    public Transform wallsContainer;

    [Tooltip("Контейнер Attractions (точки притяжения) — экспортируются как plan_points.")]
    public Transform attractionsContainer;

    [Header("Запись")]
    [Tooltip("Интервал записи позиции (сек).")]
    [Range(0.1f, 2f)]
    public float recordInterval = 0.5f;

    [Tooltip("Клавиша для сохранения треков (JSON и при включённой опции — CSV BIRD).")]
    public KeyCode saveKey = KeyCode.S;

    [Header("Сохранение")]
    [Tooltip("Имя файла для сохранения.")]
    public string outputFileName = "unity_tracks.json";

    [Tooltip("Сохранять в StreamingAssets (true) или persistentDataPath (false).")]
    public bool saveToStreamingAssets = false;

    [Tooltip("Подпапка для экспорта CSV в формате BIRD.")]
    public string outputCsvFolder = "unity_tracks_bird";

    [Tooltip("Значение floorNumber в CSV (0 для этажа 0).")]
    public int floorNumber = 0;

    [Tooltip("При сохранении (S) также экспортировать CSV в формате BIRD.")]
    public bool exportBirdsCsvOnSave = true;

    class TrackPoint { public float time; public Vector2 pos; }
    Dictionary<string, List<TrackPoint>> _tracks = new Dictionary<string, List<TrackPoint>>();
    float _lastRecordTime;
    Bounds _floorWorldBounds;

    void Start()
    {
        UpdateFloorBounds();
    }

    Bounds GetBounds(Transform t)
    {
        var r = t.GetComponentInChildren<Renderer>(true);
        if (r != null && r.bounds.size.sqrMagnitude > 0.0001f) return r.bounds;
        var c = t.GetComponentInChildren<Collider>(true);
        if (c != null && c.bounds.size.sqrMagnitude > 0.0001f) return c.bounds;
        return new Bounds(t.position, Vector3.zero);
    }

    List<Point2D> GetFloorOutline(Transform floor)
    {
        var mfs = floor.GetComponentsInChildren<MeshFilter>(true);
        if (mfs == null || mfs.Length == 0) return null;
        var list = new List<Point2D>();
        foreach (var mf in mfs)
        {
            if (mf == null || mf.sharedMesh == null) continue;
            var mesh = mf.sharedMesh;
            var verts = mesh.vertices;
            if (verts == null) continue;
            var m = mf.transform.localToWorldMatrix;
            for (int i = 0; i < verts.Length; i++)
            {
                Vector3 w = m.MultiplyPoint3x4(verts[i]);
                list.Add(new Point2D { x = w.x, y = w.z });
            }
        }
        return list.Count > 0 ? list : null;
    }

    void UpdateFloorBounds()
    {
        Transform floor = floorTransform != null ? floorTransform : GameObject.Find("Floor")?.transform;
        if (floor == null) return;
        var renderers = floor.GetComponentsInChildren<Renderer>(true);
        bool hasBounds = false;
        _floorWorldBounds = new Bounds(floor.position, Vector3.zero);
        foreach (var r in renderers)
        {
            if (r != null && r.bounds.size.sqrMagnitude > 0.0001f)
            {
                if (!hasBounds) { _floorWorldBounds = r.bounds; hasBounds = true; }
                else _floorWorldBounds.Encapsulate(r.bounds);
            }
        }
        var colliders = floor.GetComponentsInChildren<Collider>(true);
        foreach (var c in colliders)
        {
            if (c != null && c.bounds.size.sqrMagnitude > 0.0001f)
            {
                if (!hasBounds) { _floorWorldBounds = c.bounds; hasBounds = true; }
                else _floorWorldBounds.Encapsulate(c.bounds);
            }
        }
    }

    bool _loggedFirstRecord;

    void Update()
    {
        if (Time.time - _lastRecordTime < recordInterval) return;
        _lastRecordTime = Time.time;

        var agents = FindObjectsOfType<AgentPath>();
        if (!_loggedFirstRecord && agents != null)
        {
            _loggedFirstRecord = true;
            Debug.Log($"TrackRecorder: найдено {agents.Length} агентов (AgentPath). Запись каждые {recordInterval} сек.");
        }
        foreach (var ap in agents)
        {
            if (ap == null) continue;
            string id = ap.gameObject.name;
            if (string.IsNullOrEmpty(id)) id = "Agent_" + ap.GetInstanceID();
            if (!_tracks.ContainsKey(id)) _tracks[id] = new List<TrackPoint>();
            Vector3 pos = ap.transform.position;
            _tracks[id].Add(new TrackPoint { time = Time.time, pos = new Vector2(pos.x, pos.z) });
        }
    }

    void LateUpdate()
    {
#if ENABLE_INPUT_SYSTEM
        if (saveKey != KeyCode.None && Keyboard.current != null && GetKeyPressed(saveKey))
            SaveTracks();
#else
        if (saveKey != KeyCode.None && Input.GetKeyDown(saveKey))
            SaveTracks();
#endif
    }

#if ENABLE_INPUT_SYSTEM
    static bool GetKeyPressed(KeyCode kc)
    {
        var kb = Keyboard.current;
        if (kb == null) return false;
        Key? key = kc switch
        {
            KeyCode.S => Key.S,
            KeyCode.F => Key.F,
            KeyCode.P => Key.P,
            KeyCode.Escape => Key.Escape,
            _ => null
        };
        return key.HasValue && kb[key.Value].wasPressedThisFrame;
    }
#endif

    void OnDisable()
    {
        if (_tracks != null)
            SaveTracks();
    }

    [ContextMenu("Сохранить треки")]
    public void SaveTracks()
    {
        UpdateFloorBounds();
        var list = new List<TrajectoryData>();
        foreach (var kv in _tracks)
        {
            if (kv.Value.Count < 2) continue;
            var pts = new List<Point2D>();
            foreach (var pt in kv.Value)
                pts.Add(new Point2D { x = pt.pos.x, y = pt.pos.y });
            list.Add(new TrajectoryData { trajectory_id = kv.Key, points = pts });
        }
        string dir = saveToStreamingAssets ? Application.streamingAssetsPath : Application.persistentDataPath;
        string path = Path.Combine(dir, outputFileName);
        try
        {
            if (!Directory.Exists(dir))
                Directory.CreateDirectory(dir);

            var wrapper = new TrajectoryJsonWrapper { trajectories = list };

            // План этажа из Unity — в тех же координатах (X, Z), что и треки
            Transform floor = floorTransform != null ? floorTransform : GameObject.Find("Floor")?.transform;
            if (floor != null)
            {
                var outline = GetFloorOutline(floor);
                if (outline != null && outline.Count > 0)
                    wrapper.floor_outline = outline;
                else if (_floorWorldBounds.size.sqrMagnitude > 0.0001f)
                {
                    wrapper.floor_bounds = new FloorBoundsData
                    {
                        minX = _floorWorldBounds.min.x,
                        minZ = _floorWorldBounds.min.z,
                        maxX = _floorWorldBounds.max.x,
                        maxZ = _floorWorldBounds.max.z
                    };
                }
            }

            Transform att = attractionsContainer != null ? attractionsContainer : GameObject.Find("Attractions")?.transform;
            if (att != null)
            {
                var planPts = new List<Point2D>();
                for (int i = 0; i < att.childCount; i++)
                {
                    var t = att.GetChild(i);
                    if (t != null)
                        planPts.Add(new Point2D { x = t.position.x, y = t.position.z });
                }
                wrapper.plan_points = planPts;
            }

            Transform walls = wallsContainer != null ? wallsContainer : GameObject.Find("Walls")?.transform;
            if (walls != null)
            {
                var wallList = new List<WallRectData>();
                for (int i = 0; i < walls.childCount; i++)
                {
                    var w = walls.GetChild(i);
                    if (w == null) continue;
                    Bounds b = GetBounds(w);
                    if (b.size.sqrMagnitude < 0.0001f) continue;
                    var rect = new WallRectData
                    {
                        minX = b.min.x, minZ = b.min.z,
                        maxX = b.max.x, maxZ = b.max.z
                    };
                    wallList.Add(rect);
                }
                wrapper.wall_rects = wallList;
            }

            string json = JsonUtility.ToJson(wrapper, true);
            File.WriteAllText(path, json);
            Debug.Log($"TrackRecorder: сохранено {list.Count} треков.\nПуть: {path}\n(Скопируй путь и вставь в проводник)");
            if (exportBirdsCsvOnSave) SaveTracksToBirdsCsv();
            if (list.Count == 0 && _tracks.Count > 0)
                Debug.LogWarning($"TrackRecorder: записано {_tracks.Count} агентов, но у всех меньше 2 точек. Подожди, пока агенты походят.");
            if (list.Count == 0 && _tracks.Count == 0)
                Debug.LogWarning("TrackRecorder: агенты не найдены. Проверь, что на сцене есть объекты с компонентом AgentPath.");
        }
        catch (System.Exception ex)
        {
            Debug.LogError($"TrackRecorder: ошибка сохранения: {ex.Message}\nПуть: {path}");
        }
    }

    [ContextMenu("Экспорт в CSV (BIRD)")]
    public void SaveTracksToBirdsCsv()
    {
        string baseDir = saveToStreamingAssets ? Application.streamingAssetsPath : Application.persistentDataPath;
        string csvDir = Path.Combine(baseDir, outputCsvFolder);
        try
        {
            if (!Directory.Exists(csvDir)) Directory.CreateDirectory(csvDir);
            int count = 0;
            foreach (var kv in _tracks)
            {
                if (kv.Value.Count < 2) continue;
                float t0 = kv.Value[0].time;
                var sb = new System.Text.StringBuilder();
                sb.AppendLine("timestamp,x,y,floorNumber");
                foreach (var pt in kv.Value)
                {
                    float timestamp = pt.time - t0;
                    sb.AppendLine(string.Format(System.Globalization.CultureInfo.InvariantCulture, "{0},{1},{2},{3}", timestamp, pt.pos.x, pt.pos.y, floorNumber));
                }
                string safeId = string.Join("_", kv.Key.Split(Path.GetInvalidFileNameChars()));
                string filePath = Path.Combine(csvDir, safeId + "_traj.csv");
                File.WriteAllText(filePath, sb.ToString());
                count++;
            }
            if (count > 0)
                Debug.Log($"TrackRecorder: экспорт CSV: {count} треков.\nПапка: {csvDir}");
        }
        catch (System.Exception ex)
        {
            Debug.LogError($"TrackRecorder: ошибка экспорта CSV: {ex.Message}\nПапка: {csvDir}");
        }
    }

    [System.Serializable]
    class Point2D { public float x; public float y; }
    [System.Serializable]
    class TrajectoryData { public string trajectory_id; public List<Point2D> points; }
    [System.Serializable]
    class FloorBoundsData { public float minX, minZ, maxX, maxZ; }
    [System.Serializable]
    class WallRectData { public float minX, minZ, maxX, maxZ; }
    [System.Serializable]
    class TrajectoryJsonWrapper
    {
        public List<TrajectoryData> trajectories;
        public List<Point2D> floor_outline;
        public FloorBoundsData floor_bounds;
        public List<WallRectData> wall_rects;
        public List<Point2D> plan_points;
    }
}
