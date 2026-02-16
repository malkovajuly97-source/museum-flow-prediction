using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

/// <summary>
/// Экспортирует план этажа (пол + стены) из Unity в JSON.
/// Прикрепи к GameObject, назначь Floor и Walls Container, затем ПКМ → «Экспорт плана в JSON».
/// </summary>
public class ExportPlanToJson : MonoBehaviour
{
    [Header("План этажа")]
    [Tooltip("Объект пола (Floor) — меш экспортируется как внешний контур.")]
    public Transform floorTransform;

    [Tooltip("Контейнер Walls — родитель со стенами. Или пусто — ищу объекты с \"Wall\" в имени.")]
    public Transform wallsContainer;

    [Header("Сохранение")]
    public string outputFileName = "unity_plan.json";
    public bool saveToStreamingAssets = true;

    const float Eps = 0.001f;
    const float EpsSq = 0.000001f;

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

        var outline = largest; // RemoveSpokeVertices отключён — сохраняем все точки контура
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

    static List<Vector2> RemoveSpokeVertices(List<Vector2> pts)
    {
        if (pts == null || pts.Count < 4) return pts;
        var result = new List<Vector2>(pts);
        bool changed = true;
        while (changed && result.Count >= 4)
        {
            changed = false;
            for (int i = result.Count - 1; i >= 0; i--)
            {
                int prev = (i + result.Count - 1) % result.Count;
                int next = (i + 1) % result.Count;
                var p = result[i];
                var a = result[prev];
                var b = result[next];
                float cross = (b.x - p.x) * (a.y - p.y) - (b.y - p.y) * (a.x - p.x);
                if (cross <= 0) continue;
                if (PointInPolygon(p, result, i))
                {
                    result.RemoveAt(i);
                    changed = true;
                }
            }
        }
        return result;
    }

    static bool PointInPolygon(Vector2 p, List<Vector2> poly, int skipIndex)
    {
        int n = poly.Count;
        bool inside = false;
        for (int i = 0, j = n - 1; i < n; j = i++)
        {
            if (i == skipIndex || j == skipIndex) continue;
            var vi = poly[i];
            var vj = poly[j];
            if (Mathf.Abs(vj.y - vi.y) < Eps) continue;
            if (((vi.y > p.y) != (vj.y > p.y)) && (p.x < (vj.x - vi.x) * (p.y - vi.y) / (vj.y - vi.y) + vi.x))
                inside = !inside;
        }
        return inside;
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
                var b = r.bounds;
                minX = b.min.x;
                maxX = b.max.x;
                minZ = b.min.z;
                maxZ = b.max.z;
            }
        }
    }

    [ContextMenu("Экспорт плана в JSON")]
    public void ExportToJson()
    {
        string dir = saveToStreamingAssets ? Application.streamingAssetsPath : Application.persistentDataPath;
        string path = Path.Combine(dir, outputFileName);
        try
        {
            if (!Directory.Exists(dir)) Directory.CreateDirectory(dir);
            var data = new PlanJsonData();

            Transform floor = floorTransform != null ? floorTransform : GameObject.Find("Floor")?.transform;
            if (floor != null)
            {
                var outline = GetMeshOutlineXZ(floor);
                if (outline != null && outline.Count >= 3)
                {
                    data.floor_outline = new List<Point2D>();
                    foreach (var p in outline)
                        data.floor_outline.Add(new Point2D { x = p.x, y = p.y });
                }
            }

            var wallTransforms = new List<Transform>();
            if (wallsContainer != null)
            {
                for (int i = 0; i < wallsContainer.childCount; i++)
                {
                    var w = wallsContainer.GetChild(i);
                    if (w != null) wallTransforms.Add(w);
                }
            }
            else
            {
                var walls = GameObject.Find("Walls")?.transform;
                if (walls != null)
                {
                    for (int i = 0; i < walls.childCount; i++)
                    {
                        var w = walls.GetChild(i);
                        if (w != null) wallTransforms.Add(w);
                    }
                }
                else
                {
                    foreach (var go in FindObjectsByType<Transform>(FindObjectsInactive.Exclude, FindObjectsSortMode.None))
                    {
                        if (go != null && go.name.IndexOf("Wall", StringComparison.OrdinalIgnoreCase) >= 0)
                            wallTransforms.Add(go);
                    }
                }
            }

            if (wallTransforms.Count > 0)
            {
                data.wall_outlines = new List<WallOutlineData>();
                foreach (var w in wallTransforms)
                {
                    var outline = GetMeshOutlineXZ(w);
                    if (outline != null && outline.Count >= 2)
                    {
                        var pts = new List<Point2D>();
                        foreach (var p in outline) pts.Add(new Point2D { x = p.x, y = p.y });
                        data.wall_outlines.Add(new WallOutlineData { points = pts });
                    }
                    else
                    {
                        GetWallRect(w, out float mnx, out float mnz, out float mxx, out float mxz);
                        if (mxx - mnx < 0.0001f && mxz - mnz < 0.0001f) continue;
                        data.wall_rects = data.wall_rects ?? new List<WallRectData>();
                        data.wall_rects.Add(new WallRectData { minX = mnx, minZ = mnz, maxX = mxx, maxZ = mxz });
                    }
                }
            }

            string json = JsonUtility.ToJson(data, true);
            File.WriteAllText(path, json);
            Debug.Log($"ExportPlanToJson: план сохранён в {path}");
        }
        catch (Exception ex)
        {
            Debug.LogError($"ExportPlanToJson: {ex.Message}");
        }
    }

    [Serializable]
    class Point2D { public float x; public float y; }

    [Serializable]
    class WallRectData { public float minX, minZ, maxX, maxZ; }

    [Serializable]
    class WallOutlineData { public List<Point2D> points; }

    [Serializable]
    class PlanJsonData
    {
        public List<Point2D> floor_outline;
        public List<WallRectData> wall_rects;
        public List<WallOutlineData> wall_outlines;
    }
}
