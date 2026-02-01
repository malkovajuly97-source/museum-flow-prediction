using System;
using System.IO;
using UnityEngine;
using UnityEditor;

/// <summary>
/// Editor-скрипт: создаёт 135 пустых объектов по координатам из JSON и подставляет их в AgentPath у Capsule.
/// Меню: Tools → Floor0 → Create 135 Attraction Points from JSON
/// </summary>
public static class CreateAttractionPointsEditor
{
    const string JsonFileName = "floor0_attractions.json";

    [Serializable]
    class PointData
    {
        public string id;
        public float x;
        public float y;
    }

    [Serializable]
    class JsonWrapper
    {
        public PointData[] points;
    }

    /// <summary>
    /// Границы объекта в его локальном пространстве (по Renderer или Collider у самого объекта и у дочерних).
    /// </summary>
    static bool GetLocalBounds(Transform tr, out Bounds localBounds)
    {
        Bounds result = new Bounds(Vector3.zero, Vector3.zero);
        bool hasAny = false;

        void AddBounds(Bounds worldBounds)
        {
            if (worldBounds.size.sqrMagnitude < 0.0001f)
                return;
            Vector3[] corners = new Vector3[]
            {
                new Vector3(worldBounds.min.x, worldBounds.min.y, worldBounds.min.z),
                new Vector3(worldBounds.max.x, worldBounds.min.y, worldBounds.min.z),
                new Vector3(worldBounds.min.x, worldBounds.max.y, worldBounds.min.z),
                new Vector3(worldBounds.max.x, worldBounds.max.y, worldBounds.min.z),
                new Vector3(worldBounds.min.x, worldBounds.min.y, worldBounds.max.z),
                new Vector3(worldBounds.max.x, worldBounds.min.y, worldBounds.max.z),
                new Vector3(worldBounds.min.x, worldBounds.max.y, worldBounds.max.z),
                new Vector3(worldBounds.max.x, worldBounds.max.y, worldBounds.max.z)
            };
            for (int i = 0; i < corners.Length; i++)
            {
                Vector3 local = tr.InverseTransformPoint(corners[i]);
                if (!hasAny)
                {
                    result = new Bounds(local, Vector3.zero);
                    hasAny = true;
                }
                else
                    result.Encapsulate(local);
            }
        }

        var renderers = tr.GetComponentsInChildren<Renderer>(true);
        foreach (var r in renderers)
        {
            if (r != null && r.bounds.size.sqrMagnitude > 0.0001f)
                AddBounds(r.bounds);
        }
        var colliders = tr.GetComponentsInChildren<Collider>(true);
        foreach (var c in colliders)
        {
            if (c != null && c.bounds.size.sqrMagnitude > 0.0001f)
                AddBounds(c.bounds);
        }

        localBounds = result;
        return hasAny;
    }

    [MenuItem("Tools/Floor0/Create 135 Attraction Points from JSON")]
    static void CreateAttractionPoints()
    {
        string path = Path.Combine(Application.streamingAssetsPath, JsonFileName);
        if (!File.Exists(path))
        {
            EditorUtility.DisplayDialog("Файл не найден",
                "Положи floor0_attractions.json в папку:\n" + Application.streamingAssetsPath + "\n\n(Создай StreamingAssets в Assets, если её нет.)",
                "OK");
            return;
        }

        GameObject floor = GameObject.Find("Floor");
        if (floor == null)
        {
            EditorUtility.DisplayDialog("Объект не найден", "В сцене нет объекта с именем \"Floor\". Создай его или выбери пол и переименуй в Floor.", "OK");
            return;
        }

        // Ищем границы: у Floor и его детей, при необходимости у родителей
        Bounds localBounds = new Bounds(Vector3.zero, new Vector3(100f, 0.01f, 100f));
        Transform walk = floor.transform;
        while (walk != null)
        {
            if (GetLocalBounds(walk, out Bounds ancBounds))
            {
                if (walk == floor.transform)
                    localBounds = ancBounds;
                else
                {
                    Vector3[] corners = new Vector3[]
                    {
                        new Vector3(ancBounds.min.x, ancBounds.min.y, ancBounds.min.z),
                        new Vector3(ancBounds.max.x, ancBounds.min.y, ancBounds.min.z),
                        new Vector3(ancBounds.min.x, ancBounds.max.y, ancBounds.min.z),
                        new Vector3(ancBounds.max.x, ancBounds.max.y, ancBounds.min.z),
                        new Vector3(ancBounds.min.x, ancBounds.min.y, ancBounds.max.z),
                        new Vector3(ancBounds.max.x, ancBounds.min.y, ancBounds.max.z),
                        new Vector3(ancBounds.min.x, ancBounds.max.y, ancBounds.max.z),
                        new Vector3(ancBounds.max.x, ancBounds.max.y, ancBounds.max.z)
                    };
                    localBounds = new Bounds(floor.transform.InverseTransformPoint(walk.TransformPoint(corners[0])), Vector3.zero);
                    for (int i = 1; i < corners.Length; i++)
                        localBounds.Encapsulate(floor.transform.InverseTransformPoint(walk.TransformPoint(corners[i])));
                }
                break;
            }
            walk = walk.parent;
        }

        // Мировые границы пола (XZ — площадь, Y — высота)
        Transform floorTransform = floor.transform;
        Vector3[] localCorners = new Vector3[]
        {
            new Vector3(localBounds.min.x, localBounds.min.y, localBounds.min.z),
            new Vector3(localBounds.max.x, localBounds.min.y, localBounds.min.z),
            new Vector3(localBounds.min.x, localBounds.max.y, localBounds.min.z),
            new Vector3(localBounds.max.x, localBounds.max.y, localBounds.min.z),
            new Vector3(localBounds.min.x, localBounds.min.y, localBounds.max.z),
            new Vector3(localBounds.max.x, localBounds.min.y, localBounds.max.z),
            new Vector3(localBounds.min.x, localBounds.max.y, localBounds.max.z),
            new Vector3(localBounds.max.x, localBounds.max.y, localBounds.max.z)
        };
        Bounds worldBounds = new Bounds(floorTransform.TransformPoint(localCorners[0]), Vector3.zero);
        for (int i = 1; i < localCorners.Length; i++)
            worldBounds.Encapsulate(floorTransform.TransformPoint(localCorners[i]));

        if (walk == null)
            Debug.LogWarning("CreateAttractionPoints: у Floor и родителей не найдены Renderer/Collider. Используется фиксированный прямоугольник по позиции пола.");

        string json = File.ReadAllText(path);
        JsonWrapper wrapper = JsonUtility.FromJson<JsonWrapper>(json);
        if (wrapper == null || wrapper.points == null || wrapper.points.Length == 0)
        {
            EditorUtility.DisplayDialog("Ошибка", "Не удалось прочитать точки из JSON.", "OK");
            return;
        }

        PointData[] data = wrapper.points;
        int count = data.Length;

        float minX = float.MaxValue, maxX = float.MinValue;
        float minY = float.MaxValue, maxY = float.MinValue;
        for (int i = 0; i < count; i++)
        {
            if (data[i].x < minX) minX = data[i].x;
            if (data[i].x > maxX) maxX = data[i].x;
            if (data[i].y < minY) minY = data[i].y;
            if (data[i].y > maxY) maxY = data[i].y;
        }
        float rangeX = maxX - minX;
        float rangeY = maxY - minY;
        if (rangeX < 0.001f) rangeX = 1f;
        if (rangeY < 0.001f) rangeY = 1f;

        // Масштаб и центр из мировых границ пола
        float sizeX = worldBounds.size.x;
        float sizeZ = worldBounds.size.z;
        if (sizeX < 0.001f) sizeX = 100f;
        if (sizeZ < 0.001f) sizeZ = 100f;
        float centerX = worldBounds.center.x;
        float centerZ = worldBounds.center.z;
        float worldY = worldBounds.max.y; // точки чуть выше пола

        GameObject parent = new GameObject("Attractions");
        Undo.RegisterCreatedObjectUndo(parent, "Create Attractions");

        Transform[] transforms = new Transform[count];
        for (int i = 0; i < count; i++)
        {
            PointData p = data[i];
            string name = string.IsNullOrEmpty(p.id) ? ("P" + (i + 1)) : p.id;
            GameObject go = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            go.name = name;
            go.transform.SetParent(parent.transform, true);

            // Нормализованные координаты плана [0..1] -> мировая позиция в границах пола
            float t = (p.x - minX) / rangeX;
            float s = (p.y - minY) / rangeY;
            float wx = centerX - sizeX * 0.5f + t * sizeX;
            float wz = centerZ - sizeZ * 0.5f + s * sizeZ;
            go.transform.position = new Vector3(wx, worldY, wz);
            go.transform.localScale = Vector3.one * 0.3f;

            var col = go.GetComponent<Collider>();
            if (col != null) UnityEngine.Object.DestroyImmediate(col);

            transforms[i] = go.transform;
            Undo.RegisterCreatedObjectUndo(go, "Create Attraction");
        }

        // Находим Capsule с AgentPath и подставляем точки (в мировых координатах через transform)
        GameObject capsule = GameObject.Find("Capsule");
        if (capsule == null)
            capsule = Selection.activeGameObject;

        AgentPath agentPath = capsule != null ? capsule.GetComponent<AgentPath>() : null;
        if (agentPath != null)
        {
            agentPath.points = transforms;
            EditorUtility.SetDirty(capsule);
            Debug.Log("AgentPath на " + capsule.name + ": назначено " + count + " точек.");
        }
        else
        {
            Debug.LogWarning("Capsule с AgentPath не найден. Создано " + count + " объектов под Floor/Attractions. Назначь Points вручную или выбери Capsule и запусти снова.");
        }

        Selection.activeGameObject = parent;
        EditorUtility.DisplayDialog("Готово", "Создано " + count + " точек (Floor/Attractions).\nТочки привязаны к полу. Points у Capsule/AgentPath заполнены автоматически.", "OK");
    }
}
