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

    [Tooltip("Предпочитать соседние точки: следующий пункт выбирается из K ближайших (логичнее для музея).")]
    public bool preferNeighbors = true;

    [Tooltip("Из скольких ближайших не посещённых точек выбирать следующую (при preferNeighbors).")]
    [Range(1, 10)]
    public int chooseFromNearestK = 5;

    [Tooltip("Время ожидания (сек) у каждой точки. Если длина меньше числа точек, для остальных используется defaultWaitTime.")]
    public float[] waitTimes;

    [Tooltip("Время ожидания по умолчанию (сек), если waitTimes не задан для точки.")]
    public float defaultWaitTime = 2f;

    [Tooltip("Минимальный множитель для времени ожидания (базовое время × Random(min..max)).")]
    [Range(0.5f, 1f)]
    public float waitRandomMin = 0.7f;

    [Tooltip("Максимальный множитель для времени ожидания.")]
    [Range(1f, 2.5f)]
    public float waitRandomMax = 1.5f;

    [Tooltip("Дистанция до точки, при которой считаем, что агент «прибыл».")]
    public float arrivalDistance = 0.5f;

    [Tooltip("Замкнуть маршрут: после последней точки снова идти к первой.")]
    public bool loop = false;

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

    /// <summary>Строит маршрут: каждая следующая точка — из K ближайших не посещённых.</summary>
    void BuildNeighborPath(int n, int total)
    {
        var route = new List<Transform>(n);
        var visited = new HashSet<int>();

        int startIdx = Random.Range(0, total);
        route.Add(allPointsContainer.GetChild(startIdx));
        visited.Add(startIdx);

        for (int step = 1; step < n; step++)
        {
            Vector3 currentPos = route[route.Count - 1].position;
            var candidates = new List<(int idx, float sqrDist)>();

            for (int i = 0; i < total; i++)
            {
                if (visited.Contains(i)) continue;
                Transform t = allPointsContainer.GetChild(i);
                if (t == null) continue;
                float dx = t.position.x - currentPos.x;
                float dz = t.position.z - currentPos.z;
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
        if (points == null || _currentIndex < 0 || _currentIndex >= points.Length) return;
        Transform target = points[_currentIndex];
        if (target == null) return;
        _agent.SetDestination(target.position);
    }

    bool IsCurrentTargetCrowded()
    {
        if (points == null || _currentIndex < 0 || _currentIndex >= points.Length) return false;
        Vector3 pos = points[_currentIndex].position;
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
            float dx = t.position.x - pos.x;
            float dz = t.position.z - pos.z;
            float sqr = dx * dx + dz * dz;
            if (sqr < minSqr) { minSqr = sqr; nearest = t; }
        }
        if (nearest != null)
        {
            _goingToExit = true;
            _agent.SetDestination(nearest.position);
        }
        else
        {
            _agent.ResetPath();
        }
    }

    void Update()
    {
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

        if (!_agent.pathPending && _agent.remainingDistance <= arrivalDistance)
        {
            float baseWait = defaultWaitTime;
            if (waitTimes != null && _currentIndex < waitTimes.Length)
                baseWait = waitTimes[_currentIndex];
            float wait = baseWait * Random.Range(waitRandomMin, waitRandomMax);

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
