using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

/// <summary>
/// Объединённый экспорт: план этажа (контур пола + стены) + треки агентов в один JSON.
/// Использует корректное извлечение контура из меша (граничные рёбра).
/// ПКМ → «Экспорт план + треки» или клавиша S в Play mode.
/// </summary>
public class PlanAndTrackExporter : MonoBehaviour
{
    [Header("План этажа")]
    [Tooltip("Объект пола (Floor) — меш экспортируется как внешний контур.")]
    public Transform floorTransform;

    [Tooltip("Контейнер именно СТЕН (объект Walls), не Floor. Если указать Floor — в слой стен попадёт пол.")]
    public Transform wallsContainer;

    [Tooltip("Контейнер Attractions (точки притяжения) — экспортируются как plan_points.")]
    public Transform attractionsContainer;

    [Tooltip("Запасной объект для контура пола (если Floor не даёт контур). Назначь FBX здания, напр. Nancy_Museum.")]
    public Transform floorFallbackTransform;

    [Header("Запись треков")]
    [Tooltip("Интервал записи позиции агентов (сек).")]
    [Range(0.1f, 2f)]
    public float recordInterval = 0.5f;

    [Tooltip("Клавиша для сохранения (план + треки).")]
    public KeyCode saveKey = KeyCode.S;

    [Header("Сохранение")]
    [Tooltip("Имя DXF-файла (план + треки).")]
    public string outputFileName = "unity_plan_and_tracks.dxf";

    [Tooltip("Сохранять в StreamingAssets (true) или persistentDataPath (false).")]
    public bool saveToStreamingAssets = true;

    [Tooltip("Включать стены в DXF (PLAN_WALLS). Если выключено — в DXF только пол и треки.")]
    public bool exportWallsToDxf = false;

    Dictionary<string, List<Vector2>> _tracks = new Dictionary<string, List<Vector2>>();
    float _lastRecordTime;
    Bounds _floorWorldBounds;
    bool _loggedFirstRecord;

    const float Eps = 0.001f;
    const float EpsSq = 0.0001f;

    void Start()
    {
        UpdateFloorBounds();
    }

    void Update()
    {
        if (Time.time - _lastRecordTime < recordInterval) return;
        _lastRecordTime = Time.time;

        var agents = FindObjectsOfType<AgentPath>();
        if (!_loggedFirstRecord && agents != null && agents.Length > 0)
        {
            _loggedFirstRecord = true;
            Debug.Log($"PlanAndTrackExporter: найдено {agents.Length} агентов. Запись каждые {recordInterval} сек.");
        }
        foreach (var ap in agents)
        {
            if (ap == null) continue;
            string id = ap.gameObject.name;
            if (string.IsNullOrEmpty(id)) id = "Agent_" + ap.GetInstanceID();
            if (!_tracks.ContainsKey(id)) _tracks[id] = new List<Vector2>();
            Vector3 pos = ap.transform.position;
            _tracks[id].Add(new Vector2(pos.x, pos.z));
        }
    }

    void LateUpdate()
    {
#if ENABLE_INPUT_SYSTEM
        if (saveKey != KeyCode.None && Keyboard.current != null && GetKeyPressed(saveKey))
            ExportAll();
#else
        if (saveKey != KeyCode.None && Input.GetKeyDown(saveKey))
            ExportAll();
#endif
    }

#if ENABLE_INPUT_SYSTEM
    static bool GetKeyPressed(KeyCode kc)
    {
        var kb = Keyboard.current;
        if (kb == null) return false;
        Key? key = kc switch
        {
            KeyCode.S => Key.S, KeyCode.F => Key.F, KeyCode.P => Key.P, KeyCode.Escape => Key.Escape,
            _ => null
        };
        return key.HasValue && kb[key.Value].wasPressedThisFrame;
    }
#endif

    void OnDisable()
    {
        if (_tracks != null && _tracks.Count > 0)
            ExportAll();
    }

    [ContextMenu("Экспорт план + треки")]
    public void ExportAll()
    {
        UpdateFloorBounds();
        string dir = saveToStreamingAssets ? Application.streamingAssetsPath : Application.persistentDataPath;
        try
        {
            if (!Directory.Exists(dir)) Directory.CreateDirectory(dir);

            var wrapper = new PlanAndTracksData();

            // Треки
            foreach (var kv in _tracks)
            {
                if (kv.Value.Count < 2) continue;
                var pts = new List<Point2D>();
                foreach (var p in kv.Value) pts.Add(new Point2D { x = p.x, y = p.y });
                wrapper.trajectories.Add(new TrajectoryData { trajectory_id = kv.Key, points = pts });
            }

            // План — контур пола из меша Floor Transform
            if (floorTransform != null)
            {
                var outline = GetMeshOutlineXZ(floorTransform);
                if (outline != null && outline.Count >= 3)
                {
                    foreach (var p in outline)
                        wrapper.floor_outline.Add(new Point2D { x = p.x, y = p.y });
                }
            }
            if (wrapper.floor_outline.Count < 3 && floorTransform != null && _floorWorldBounds.size.sqrMagnitude > 0.0001f)
            {
                wrapper.floor_bounds = new FloorBoundsData
                {
                    minX = _floorWorldBounds.min.x, minZ = _floorWorldBounds.min.z,
                    maxX = _floorWorldBounds.max.x, maxZ = _floorWorldBounds.max.z
                };
            }

            // Стены
            var wallTransforms = GetWallTransforms();
            foreach (var w in wallTransforms)
            {
                var outline = GetMeshOutlineXZ(w);
                if (outline != null && outline.Count >= 2)
                {
                    var pts = new List<Point2D>();
                    foreach (var p in outline) pts.Add(new Point2D { x = p.x, y = p.y });
                    wrapper.wall_outlines.Add(new WallOutlineData { points = pts });
                }
                else
                {
                    GetWallRect(w, out float mnx, out float mnz, out float mxx, out float mxz);
                    if (mxx - mnx >= 0.0001f || mxz - mnz >= 0.0001f)
                        wrapper.wall_rects.Add(new WallRectData { minX = mnx, minZ = mnz, maxX = mxx, maxZ = mxz });
                }
            }

            // Attractions
            Transform att = attractionsContainer != null ? attractionsContainer : GameObject.Find("Attractions")?.transform;
            if (att != null)
            {
                for (int i = 0; i < att.childCount; i++)
                {
                    var t = att.GetChild(i);
                    if (t != null)
                        wrapper.plan_points.Add(new Point2D { x = t.position.x, y = t.position.z });
                }
            }

            string dxfPath = Path.Combine(dir, Path.GetFileNameWithoutExtension(outputFileName) + ".dxf");
            try
            {
                WriteDxf(wrapper, dxfPath, exportWallsToDxf);
                Debug.Log($"PlanAndTrackExporter: DXF сохранён в {dxfPath} ({wrapper.trajectories.Count} треков, план)");
            }
            catch (Exception exDxf) { Debug.LogError($"PlanAndTrackExporter DXF: {exDxf.Message}"); }
            if (wrapper.trajectories.Count == 0 && _tracks.Count > 0)
                Debug.LogWarning("Подожди, пока агенты походят (нужно минимум 2 точки на трек).");
            if (wrapper.trajectories.Count == 0 && _tracks.Count == 0)
                Debug.LogWarning("Агенты не найдены. Нужны объекты с компонентом AgentPath.");
        }
        catch (Exception ex)
        {
            Debug.LogError($"PlanAndTrackExporter: {ex.Message}\nПапка: {dir}");
        }
    }

    /// <summary>Пишет DXF напрямую из тех же данных (метры → мм). Без JSON/Python.</summary>
    static void WriteDxf(PlanAndTracksData data, string dxfPath, bool includeWalls)
    {
        const float scale = 1000f; // Unity m → mm
        var inv = System.Globalization.CultureInfo.InvariantCulture;
        var sb = new System.Text.StringBuilder();

        sb.AppendLine("0");
        sb.AppendLine("SECTION");
        sb.AppendLine("2");
        sb.AppendLine("HEADER");
        sb.AppendLine("9");
        sb.AppendLine("$INSUNITS");
        sb.AppendLine("70");
        sb.AppendLine("4");
        sb.AppendLine("0");
        sb.AppendLine("ENDSEC");
        sb.AppendLine("0");
        sb.AppendLine("SECTION");
        sb.AppendLine("2");
        sb.AppendLine("TABLES");
        sb.AppendLine("0");
        sb.AppendLine("TABLE");
        sb.AppendLine("2");
        sb.AppendLine("LAYER");
        sb.AppendLine("70");
        sb.AppendLine(includeWalls ? "3" : "2");
        foreach (var layer in includeWalls ? new[] { ("PLAN_FLOOR", 8), ("PLAN_WALLS", 7), ("TRACKS", 1) } : new[] { ("PLAN_FLOOR", 8), ("TRACKS", 1) })
        {
            sb.AppendLine("0"); sb.AppendLine("LAYER");
            sb.AppendLine("2"); sb.AppendLine(layer.Item1);
            sb.AppendLine("70"); sb.AppendLine("0");
            sb.AppendLine("62"); sb.AppendLine(layer.Item2.ToString(inv));
            sb.AppendLine("6"); sb.AppendLine("Continuous");
        }
        sb.AppendLine("0"); sb.AppendLine("ENDTAB");
        sb.AppendLine("0"); sb.AppendLine("ENDSEC");
        sb.AppendLine("0");
        sb.AppendLine("SECTION");
        sb.AppendLine("2");
        sb.AppendLine("ENTITIES");

        if (data.floor_outline != null && data.floor_outline.Count >= 3)
        {
            sb.AppendLine("0"); sb.AppendLine("LWPOLYLINE");
            sb.AppendLine("8"); sb.AppendLine("PLAN_FLOOR");
            sb.AppendLine("62"); sb.AppendLine("8");
            sb.AppendLine("70"); sb.AppendLine("1");
            foreach (var p in data.floor_outline)
            {
                sb.AppendLine("10"); sb.AppendLine((p.x * scale).ToString(inv));
                sb.AppendLine("20"); sb.AppendLine((p.y * scale).ToString(inv));
            }
        }

        if (includeWalls)
        {
            if (data.wall_rects != null)
                foreach (var w in data.wall_rects)
                {
                    float a = w.minX * scale, b = w.minZ * scale, c = w.maxX * scale, d = w.maxZ * scale;
                    sb.AppendLine("0"); sb.AppendLine("LWPOLYLINE");
                    sb.AppendLine("8"); sb.AppendLine("PLAN_WALLS");
                    sb.AppendLine("62"); sb.AppendLine("7");
                    sb.AppendLine("70"); sb.AppendLine("1");
                    sb.AppendLine("10"); sb.AppendLine(a.ToString(inv)); sb.AppendLine("20"); sb.AppendLine(b.ToString(inv));
                    sb.AppendLine("10"); sb.AppendLine(c.ToString(inv)); sb.AppendLine("20"); sb.AppendLine(b.ToString(inv));
                    sb.AppendLine("10"); sb.AppendLine(c.ToString(inv)); sb.AppendLine("20"); sb.AppendLine(d.ToString(inv));
                    sb.AppendLine("10"); sb.AppendLine(a.ToString(inv)); sb.AppendLine("20"); sb.AppendLine(d.ToString(inv));
                }
            if (data.wall_outlines != null)
                foreach (var wo in data.wall_outlines)
                {
                    var pts = wo?.points;
                    if (pts == null || pts.Count < 2) continue;
                    sb.AppendLine("0"); sb.AppendLine("LWPOLYLINE");
                    sb.AppendLine("8"); sb.AppendLine("PLAN_WALLS");
                    sb.AppendLine("62"); sb.AppendLine("7");
                    sb.AppendLine("70"); sb.AppendLine(pts.Count >= 3 ? "1" : "0");
                    foreach (var p in pts)
                    {
                        sb.AppendLine("10"); sb.AppendLine((p.x * scale).ToString(inv));
                        sb.AppendLine("20"); sb.AppendLine((p.y * scale).ToString(inv));
                    }
                }
        }

        if (data.trajectories != null)
            for (int i = 0; i < data.trajectories.Count; i++)
            {
                var traj = data.trajectories[i];
                var pts = traj?.points;
                if (pts == null || pts.Count < 2) continue;
                int color = (i % 7) + 1;
                sb.AppendLine("0"); sb.AppendLine("LWPOLYLINE");
                sb.AppendLine("8"); sb.AppendLine("TRACKS");
                sb.AppendLine("62"); sb.AppendLine(color.ToString(inv));
                sb.AppendLine("70"); sb.AppendLine("0");
                foreach (var p in pts)
                {
                    sb.AppendLine("10"); sb.AppendLine((p.x * scale).ToString(inv));
                    sb.AppendLine("20"); sb.AppendLine((p.y * scale).ToString(inv));
                }
            }

        sb.AppendLine("0");
        sb.AppendLine("ENDSEC");
        sb.AppendLine("0");
        sb.AppendLine("EOF");
        File.WriteAllText(dxfPath, sb.ToString(), System.Text.Encoding.ASCII);
    }

    void UpdateFloorBounds()
    {
        if (floorTransform == null) return;
        _floorWorldBounds = new Bounds(floorTransform.position, Vector3.zero);
        bool hasBounds = false;
        foreach (var r in floorTransform.GetComponentsInChildren<Renderer>(true))
        {
            if (r != null && r.bounds.size.sqrMagnitude > 0.0001f)
            {
                if (!hasBounds) { _floorWorldBounds = r.bounds; hasBounds = true; }
                else _floorWorldBounds.Encapsulate(r.bounds);
            }
        }
        foreach (var c in floorTransform.GetComponentsInChildren<Collider>(true))
        {
            if (c != null && c.bounds.size.sqrMagnitude > 0.0001f)
            {
                if (!hasBounds) { _floorWorldBounds = c.bounds; hasBounds = true; }
                else _floorWorldBounds.Encapsulate(c.bounds);
            }
        }
        if (!hasBounds && floorFallbackTransform != null)
        {
            foreach (var r in floorFallbackTransform.GetComponentsInChildren<Renderer>(true))
            {
                if (r != null && r.bounds.size.sqrMagnitude > 0.0001f)
                {
                    if (!hasBounds) { _floorWorldBounds = r.bounds; hasBounds = true; }
                    else _floorWorldBounds.Encapsulate(r.bounds);
                }
            }
        }
    }

    List<Transform> GetWallTransforms()
    {
        var list = new List<Transform>();
        if (wallsContainer == null) return list;
        for (int i = 0; i < wallsContainer.childCount; i++)
        {
            var w = wallsContainer.GetChild(i);
            if (w != null) list.Add(w);
        }
        return list;
    }

    // --- Извлечение контура из меша (из ExportPlanToJson) ---
    static List<(Vector2 a, Vector2 b)> GetBoundaryEdgesXZ(Transform t)
    {
        var mfs = t.GetComponentsInChildren<MeshFilter>(true);
        if (mfs == null || mfs.Length == 0) return null;
        var allBoundary = new List<(Vector2 a, Vector2 b)>();
        foreach (var mf in mfs)
        {
            if (mf == null || mf.sharedMesh == null) continue;
            var mesh = mf.sharedMesh;
            var verts = mesh.vertices;
            var tris = mesh.triangles;
            if (verts == null || tris == null || tris.Length < 3) continue;
            var m = mf.transform.localToWorldMatrix;
            var edgeCount = new Dictionary<(int, int), int>();
            var edgeVerts = new Dictionary<(int, int), (Vector2 a, Vector2 b)>();
            for (int i = 0; i < tris.Length; i += 3)
            {
                int i0 = tris[i], i1 = tris[i + 1], i2 = tris[i + 2];
                void AddEdge(int a, int b)
                {
                    int lo = Mathf.Min(a, b), hi = Mathf.Max(a, b);
                    var key = (lo, hi);
                    edgeCount.TryGetValue(key, out int c);
                    edgeCount[key] = c + 1;
                    if (c == 0)
                    {
                        Vector3 v0 = m.MultiplyPoint3x4(verts[a]);
                        Vector3 v1 = m.MultiplyPoint3x4(verts[b]);
                        edgeVerts[key] = (new Vector2(v0.x, v0.z), new Vector2(v1.x, v1.z));
                    }
                }
                AddEdge(i0, i1);
                AddEdge(i1, i2);
                AddEdge(i2, i0);
            }
            foreach (var kv in edgeCount)
            {
                if (kv.Value == 1 && edgeVerts.TryGetValue(kv.Key, out var ev))
                    allBoundary.Add(ev);
            }
        }
        return allBoundary.Count > 0 ? allBoundary : null;
    }

    static List<List<Vector2>> ChainEdgesIntoLoops(List<(Vector2 a, Vector2 b)> edges)
    {
        var loops = new List<List<Vector2>>();
        var used = new HashSet<int>();
        for (int i = 0; i < edges.Count; i++)
        {
            if (used.Contains(i)) continue;
            var loop = new List<Vector2>();
            Vector2 cur = edges[i].a;
            loop.Add(cur);
            int idx = i;
            used.Add(idx);
            while (true)
            {
                Vector2 next = (edges[idx].a - cur).sqrMagnitude < EpsSq ? edges[idx].b : edges[idx].a;
                cur = next;
                loop.Add(cur);
                bool found = false;
                for (int j = 0; j < edges.Count; j++)
                {
                    if (used.Contains(j)) continue;
                    float da = (edges[j].a - cur).sqrMagnitude;
                    float db = (edges[j].b - cur).sqrMagnitude;
                    if (da < EpsSq || db < EpsSq)
                    {
                        idx = j;
                        used.Add(j);
                        found = true;
                        break;
                    }
                }
                if (!found) break;
                if ((cur - loop[0]).sqrMagnitude < EpsSq)
                {
                    loop.RemoveAt(loop.Count - 1);
                    break;
                }
            }
            if (loop.Count >= 3)
            {
                loop = MergeCollinearVertices(loop);
                loop = RemoveDuplicateVertices(loop);
                if (loop.Count >= 3) loops.Add(loop);
            }
        }
        return loops;
    }

    static List<Vector2> RemoveDuplicateVertices(List<Vector2> pts)
    {
        if (pts == null || pts.Count < 3) return pts;
        var result = new List<Vector2> { pts[0] };
        for (int i = 1; i < pts.Count; i++)
        {
            if ((pts[i] - result[result.Count - 1]).sqrMagnitude >= EpsSq)
                result.Add(pts[i]);
        }
        if (result.Count >= 3 && (result[result.Count - 1] - result[0]).sqrMagnitude < EpsSq)
            result.RemoveAt(result.Count - 1);
        return result.Count >= 3 ? result : pts;
    }

    static List<Vector2> MergeCollinearVertices(List<Vector2> pts)
    {
        if (pts == null || pts.Count < 4) return pts;
        var result = new List<Vector2> { pts[0] };
        for (int i = 1; i < pts.Count; i++)
        {
            var p = pts[i];
            var prev = result[result.Count - 1];
            int nextIdx = (i + 1) % pts.Count;
            var next = pts[nextIdx];
            float cross = (next.x - p.x) * (prev.y - p.y) - (next.y - p.y) * (prev.x - p.x);
            if (Mathf.Abs(cross) > EpsSq) result.Add(p);
        }
        return result.Count >= 3 ? result : pts;
    }

    static List<Vector2> GetMeshOutlineXZ(Transform t)
    {
        var edges = GetBoundaryEdgesXZ(t);
        if (edges == null || edges.Count == 0) return null;
        var loops = ChainEdgesIntoLoops(edges);
        if (loops == null || loops.Count == 0) return null;

        var largest = loops[0];
        float maxArea = 0;
        foreach (var loop in loops)
        {
            float area = SignedArea(loop);
            float absArea = Mathf.Abs(area);
            if (absArea > maxArea)
            {
                maxArea = absArea;
                largest = loop;
            }
        }

        var outline = largest;
        if (outline == null || outline.Count < 3) return null;

        if (SignedArea(outline) < 0)
            outline.Reverse();

        return outline;
    }

    static float SignedArea(List<Vector2> loop)
    {
        if (loop == null || loop.Count < 3) return 0;
        float area = 0;
        for (int i = 0; i < loop.Count; i++)
        {
            int j = (i + 1) % loop.Count;
            area += loop[i].x * loop[j].y - loop[j].x * loop[i].y;
        }
        return area * 0.5f;
    }

    static void GetWallRect(Transform t, out float minX, out float minZ, out float maxX, out float maxZ)
    {
        minX = minZ = float.MaxValue;
        maxX = maxZ = float.MinValue;
        var mf = t.GetComponentInChildren<MeshFilter>(true);
        if (mf != null && mf.sharedMesh != null)
        {
            var verts = mf.sharedMesh.vertices;
            var m = mf.transform.localToWorldMatrix;
            foreach (var v in verts)
            {
                Vector3 w = m.MultiplyPoint3x4(v);
                if (w.x < minX) minX = w.x;
                if (w.x > maxX) maxX = w.x;
                if (w.z < minZ) minZ = w.z;
                if (w.z > maxZ) maxZ = w.z;
            }
        }
        else
        {
            var r = t.GetComponentInChildren<Renderer>(true);
            if (r != null && r.bounds.size.sqrMagnitude > 0.0001f)
            {
                minX = r.bounds.min.x;
                maxX = r.bounds.max.x;
                minZ = r.bounds.min.z;
                maxZ = r.bounds.max.z;
            }
        }
    }

    [Serializable]
    class Point2D { public float x; public float y; }

    [Serializable]
    class TrajectoryData { public string trajectory_id; public List<Point2D> points; }

    [Serializable]
    class FloorBoundsData { public float minX, minZ, maxX, maxZ; }

    [Serializable]
    class WallRectData { public float minX, minZ, maxX, maxZ; }

    [Serializable]
    class WallOutlineData { public List<Point2D> points; }

    [Serializable]
    class PlanAndTracksData
    {
        public List<TrajectoryData> trajectories = new List<TrajectoryData>();
        public List<Point2D> floor_outline = new List<Point2D>();
        public FloorBoundsData floor_bounds;
        public List<WallRectData> wall_rects = new List<WallRectData>();
        public List<WallOutlineData> wall_outlines = new List<WallOutlineData>();
        public List<Point2D> plan_points = new List<Point2D>();
    }
}
