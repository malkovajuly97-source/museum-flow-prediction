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
    public int numberOfPointsToVisit = 15;

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
                _agent.ResetPath();
                return;
            }
        }
        SetDestinationToCurrent();
    }

    void Update()
    {
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
                yield break;
            }
        }

        SetDestinationToCurrent();
        _waiting = false;
    }
}
