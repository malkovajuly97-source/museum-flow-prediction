using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.AI;

/// <summary>
/// Агент обходит точки (аттракции) по порядку с помощью NavMeshAgent.
/// Если задан allPointsContainer — строит маршрут из случайных N точек при старте (для менеджера).
/// Поддерживает избегание толпы: пропуск точки, если у неё слишком много агентов.
/// </summary>
[RequireComponent(typeof(NavMeshAgent))]
public class AgentPath : MonoBehaviour
{
    [Header("Маршрут")]
    [Tooltip("Список точек — порядок обхода. Заполняется вручную или из allPointsContainer при старте.")]
    public Transform[] points;

    [Tooltip("Контейнер со всеми аттракциями (134 дочерних). Если задан — в Start выбираются случайные numberOfPointsToVisit точек.")]
    public Transform allPointsContainer;

    [Tooltip("Сколько точек выбрать из allPointsContainer (используется только если allPointsContainer задан).")]
    public int numberOfPointsToVisit = 5;

    [Tooltip("Предпочитать соседние точки: первая — из ближайших к входу, дальше — жадный nearest (логичнее для музея).")]
    public bool preferNeighbors = true;

    [Tooltip("Первая точка: из скольких ближайших к месту спавна (входу) выбирать случайно. Min (включительно).")]
    [Range(1, 20)]
    public int entranceNearestKMin = 5;

    [Tooltip("Первая точка: из скольких ближайших к входу выбирать случайно. Max (включительно). K = random(Min, Max+1).")]
    [Range(1, 20)]
    public int entranceNearestKMax = 10;

    [Tooltip("Следующие точки: из скольких ближайших не посещённых выбирать случайно. 1 = строго ближайшая, 3+ = больше разнообразия маршрутов (рекомендуется при одном входе).")]
    [Range(1, 10)]
    public int chooseFromNearestK = 3;

    [Tooltip("Время ожидания (сек) у каждой картины — случайное от min до max.")]
    public float waitTimeMin = 1.4f;

    [Tooltip("Максимальное время ожидания (сек) у картины.")]
    public float waitTimeMax = 3f;

    [Tooltip("Дистанция до точки, при которой считаем, что агент «прибыл».")]
    public float arrivalDistance = 0.5f;

    [Tooltip("Замкнуть маршрут: после последней точки снова идти к первой.")]
    public bool loop = false;

    [Header("Запись трека")]
    [Tooltip("Записывать ли трек этого агента (для фоновых = false, для отслеживаемых = true).")]
    public bool recordTrack = true;

    [Tooltip("Тип поведения (задаётся AgentSpawnManager).")]
    public BehaviorType behaviorType = BehaviorType.Fast;

    [Header("Точки выхода")]
    [Tooltip("Точки выхода (5 лестниц). После последней картины агент идёт к ближайшей. Задаётся в Inspector или через AgentSpawnManager.")]
    public Transform[] exitPoints;

    [Tooltip("Дистанция до выхода, при которой считаем, что агент «ушел».")]
    public float exitArrivalDistance = 1f;

    [Header("Избегание толпы")]
    [Tooltip("Радиус (м), в котором считаем других агентов у текущей цели.")]
    public float crowdRadius = 2f;

    [Tooltip("Если у цели агентов не меньше этого числа — пропускаем точку и идём к следующей.")]
    public int crowdMaxCount = 3;

    [Tooltip("Интервал (сек) между проверками толпы у текущей цели.")]
    public float crowdCheckInterval = 0.5f;

    NavMeshAgent _agent;
    int _currentIndex;
    bool _waiting;
    bool _goingToExit;
    float _lastCrowdCheck;

    /// <summary>Мировая позиция точки: центр меша (bounds или MeshFilter), иначе transform.position. Для объектов из Rhino/glTF с pivot в (0,0,0) и одинаковым Transform берём центр геометрии.</summary>
    public static Vector3 GetWorldPositionForPoint(Transform t)
    {
        if (t == null) return Vector3.zero;
        var r = t.GetComponentInChildren<Renderer>();
        if (r != null && r.enabled && r.bounds.size.sqrMagnitude > 0.0001f)
            return r.bounds.center;
        var mf = t.GetComponentInChildren<MeshFilter>();
        if (mf != null && mf.sharedMesh != null)
        {
            Bounds b = mf.sharedMesh.bounds;
            Vector3 center = mf.transform.TransformPoint(b.center);
            return center;
        }
        return t.position;
    }

    void Start()
    {
        _agent = GetComponent<NavMeshAgent>();

        if (allPointsContainer != null)
        {
            BuildRandomPointsFromContainer();
        }

        if (points == null || points.Length == 0)
        {
            Debug.LogWarning("AgentPath: нет точек. Назначьте Points или All Points Container.", this);
            return;
        }

        _currentIndex = 0;
        _waiting = false;
        _goingToExit = false;
        _lastCrowdCheck = 0f;
        StartCoroutine(SetDestinationNextFrame());
    }

    IEnumerator SetDestinationNextFrame()
    {
        yield return null;
        if (_agent != null && _agent.isOnNavMesh)
            SetDestinationToCurrent();
    }

    void BuildRandomPointsFromContainer()
    {
        int total = allPointsContainer.childCount;
        if (total == 0)
        {
            points = new Transform[0];
            return;
        }

        int n = Mathf.Clamp(numberOfPointsToVisit, 1, total);

        if (preferNeighbors)
        {
            BuildNeighborPath(n, total);
        }
        else
        {
            var indices = new List<int>(total);
            for (int i = 0; i < total; i++)
                indices.Add(i);

            for (int i = 0; i < n; i++)
            {
                int j = Random.Range(i, indices.Count);
                (indices[i], indices[j]) = (indices[j], indices[i]);
            }

            var selected = new Transform[n];
            for (int i = 0; i < n; i++)
                selected[i] = allPointsContainer.GetChild(indices[i]);

            points = selected;
        }
    }

    /// <summary>Строит маршрут: первая точка — случайная из K ближайших к входу; дальше — случайная из chooseFromNearestK ближайших не посещённых (больше разнообразия). Избегание толпы в рантайме (SkipToNextPoint).</summary>
    void BuildNeighborPath(int n, int total)
    {
        var route = new List<Transform>(n);
        var visited = new HashSet<int>();

        Vector3 entrancePos = transform.position;

        var firstCandidates = new List<(int idx, float sqrDist)>();
        for (int i = 0; i < total; i++)
        {
            Transform t = allPointsContainer.GetChild(i);
            if (t == null) continue;
            Vector3 tp = GetWorldPositionForPoint(t);
            float dx = tp.x - entrancePos.x;
            float dz = tp.z - entrancePos.z;
            firstCandidates.Add((i, dx * dx + dz * dz));
        }
        firstCandidates.Sort((a, b) => a.sqrDist.CompareTo(b.sqrDist));

        int kFirst = Mathf.Clamp(Random.Range(entranceNearestKMin, entranceNearestKMax + 1), 1, firstCandidates.Count);
        int pickFirst = Random.Range(0, kFirst);
        int startIdx = firstCandidates[pickFirst].idx;
        route.Add(allPointsContainer.GetChild(startIdx));
        visited.Add(startIdx);

        for (int step = 1; step < n; step++)
        {
            Vector3 currentPos = GetWorldPositionForPoint(route[route.Count - 1]);
            var candidates = new List<(int idx, float sqrDist)>();

            for (int i = 0; i < total; i++)
            {
                if (visited.Contains(i)) continue;
                Transform t = allPointsContainer.GetChild(i);
                if (t == null) continue;
                Vector3 tp = GetWorldPositionForPoint(t);
                float dx = tp.x - currentPos.x;
                float dz = tp.z - currentPos.z;
                float sqrDist = dx * dx + dz * dz;
                candidates.Add((i, sqrDist));
            }

            if (candidates.Count == 0) break;

            candidates.Sort((a, b) => a.sqrDist.CompareTo(b.sqrDist));
            int k = Mathf.Min(chooseFromNearestK, candidates.Count);
            int pick = Random.Range(0, k);
            int nextIdx = candidates[pick].idx;

            route.Add(allPointsContainer.GetChild(nextIdx));
            visited.Add(nextIdx);
        }

        points = route.ToArray();
    }

    void SetDestinationToCurrent()
    {
        if (_agent == null || !_agent.isOnNavMesh) return;
        if (points == null || _currentIndex < 0 || _currentIndex >= points.Length) return;
        Transform target = points[_currentIndex];
        if (target == null) return;
        _agent.SetDestination(GetWorldPositionForPoint(target));
    }

    bool IsCurrentTargetCrowded()
    {
        if (points == null || _currentIndex < 0 || _currentIndex >= points.Length) return false;
        Vector3 pos = GetWorldPositionForPoint(points[_currentIndex]);
        Collider[] hits = Physics.OverlapSphere(pos, crowdRadius);
        int count = 0;
        foreach (var c in hits)
        {
            if (c.GetComponent<AgentPath>() != null && c.gameObject != gameObject)
                count++;
        }
        return count >= crowdMaxCount;
    }

    void SkipToNextPoint()
    {
        _currentIndex++;
        if (_currentIndex >= points.Length)
        {
            if (loop)
                _currentIndex = 0;
            else
            {
                TryGoToExit();
                return;
            }
        }
        SetDestinationToCurrent();
    }

    void TryGoToExit()
    {
        var exits = exitPoints;
        if (exits == null || exits.Length == 0) return;

        Vector3 pos = transform.position;
        Transform nearest = null;
        float minSqr = float.MaxValue;
        foreach (var t in exits)
        {
            if (t == null) continue;
            Vector3 tp = GetWorldPositionForPoint(t);
            float dx = tp.x - pos.x;
            float dz = tp.z - pos.z;
            float sqr = dx * dx + dz * dz;
            if (sqr < minSqr) { minSqr = sqr; nearest = t; }
        }
        if (nearest != null && _agent.isOnNavMesh)
        {
            _goingToExit = true;
            _agent.SetDestination(GetWorldPositionForPoint(nearest));
        }
        else if (_agent.isOnNavMesh)
        {
            _agent.ResetPath();
        }
    }

    void Update()
    {
        if (_agent == null || !_agent.isOnNavMesh) return;

        if (_goingToExit)
        {
            if (!_agent.pathPending && _agent.remainingDistance <= exitArrivalDistance)
            {
                _agent.ResetPath();
                Destroy(gameObject); // Агент «ушёл» — исчезает из сцены
            }
            return;
        }

        if (points == null || points.Length == 0) return;
        if (_waiting) return;

        if (Time.time - _lastCrowdCheck >= crowdCheckInterval)
        {
            _lastCrowdCheck = Time.time;
            if (IsCurrentTargetCrowded())
            {
                SkipToNextPoint();
                return;
            }
        }

        if (!_agent.pathPending && _agent.isOnNavMesh && _agent.remainingDistance <= arrivalDistance)
        {
            float wait = Random.Range(waitTimeMin, waitTimeMax);
            StartCoroutine(WaitThenNext(wait));
        }
    }

    IEnumerator WaitThenNext(float seconds)
    {
        _waiting = true;
        yield return new WaitForSeconds(seconds);

        _currentIndex++;
        if (_currentIndex >= points.Length)
        {
            if (loop)
                _currentIndex = 0;
            else
            {
                _waiting = false;
                TryGoToExit();
                yield break;
            }
        }

        SetDestinationToCurrent();
        _waiting = false;
    }
}
