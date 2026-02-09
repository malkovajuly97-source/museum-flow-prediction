using System.Collections;
using System.Collections.Generic;
using UnityEngine;

// Создаёт агентов с разнесённым по времени появлением и передаёт им контейнер аттракций.
// Положи на сцену, укажи префаб агента (Capsule с AgentPath + NavMeshAgent) и контейнер Attractions.
public class AgentSpawnManager : MonoBehaviour
{
    [Tooltip("Префаб агента (должен содержать AgentPath и NavMeshAgent).")]
    public GameObject agentPrefab;

    [Tooltip("Контейнер со всеми точками аттракций (Attractions, 134 дочерних объекта).")]
    public Transform attractionsContainer;

    [Tooltip("Одна точка появления (если не используешь массив Spawn Points).")]
    public Transform spawnPoint;

    [Tooltip("Несколько точек входа (лестницы, входы). Если задан — для каждого агента выбирается случайная точка из массива.")]
    public Transform[] spawnPoints;

    [Tooltip("Точки выхода (5 лестниц). После обхода картин агент идёт к ближайшей. Если пусто — ищет объект Exit и его дочерние.")]
    public Transform[] exitPoints = new Transform[5];

    [Tooltip("Количество агентов для создания.")]
    public int agentCount = 51;

    [Tooltip("Минимальный интервал (сек) между появлением двух агентов.")]
    public float spawnIntervalMin = 2f;

    [Tooltip("Максимальный интервал (сек) между появлением двух агентов.")]
    public float spawnIntervalMax = 6f;

    [Tooltip("Минимум точек маршрута на одного агента (случайное от min до max).")]
    public int pointsPerAgentMin = 5;

    [Tooltip("Максимум точек маршрута на одного агента.")]
    public int pointsPerAgentMax = 25;

    [Header("Ожидание у картины")]
    [Tooltip("Минимальное время (сек) у каждой картины.")]
    public float waitTimeMin = 1.4f;

    [Tooltip("Максимальное время (сек) у каждой картины.")]
    public float waitTimeMax = 3f;

    void Start()
    {
        if (agentPrefab == null)
        {
            Debug.LogError("AgentSpawnManager: не назначен Agent Prefab.");
            return;
        }
        if (attractionsContainer == null)
        {
            Debug.LogError("AgentSpawnManager: не назначен Attractions Container.");
            return;
        }
        StartCoroutine(SpawnAgentsOverTime());
    }

    Vector3 GetSpawnPosition()
    {
        if (spawnPoints != null && spawnPoints.Length > 0)
        {
            Transform t = spawnPoints[Random.Range(0, spawnPoints.Length)];
            if (t != null) return t.position;
        }
        if (spawnPoint != null) return spawnPoint.position;
        return transform.position;
    }

    Transform[] GetExitPoints()
    {
        if (exitPoints != null && exitPoints.Length > 0)
        {
            var valid = new List<Transform>();
            foreach (var t in exitPoints)
                if (t != null) valid.Add(t);
            if (valid.Count > 0) return valid.ToArray();
        }
        var exit = GameObject.Find("Exit");
        if (exit != null && exit.transform.childCount > 0)
        {
            var list = new Transform[exit.transform.childCount];
            for (int i = 0; i < exit.transform.childCount; i++)
                list[i] = exit.transform.GetChild(i);
            return list;
        }
        if (exit != null)
            return new Transform[] { exit.transform };
        return (spawnPoints != null && spawnPoints.Length > 0) ? spawnPoints : null;
    }

    IEnumerator SpawnAgentsOverTime()
    {
        var exits = GetExitPoints();
        if (exits == null || exits.Length == 0)
            Debug.LogWarning("AgentSpawnManager: Exit Points пуст. Создай объект Exit с дочерними точками (лестницы) или назначь Exit Points вручную.");

        for (int i = 0; i < agentCount; i++)
        {
            Vector3 spawnPos = GetSpawnPosition();
            GameObject agent = Instantiate(agentPrefab, spawnPos, Quaternion.identity);
            agent.name = agentPrefab.name + "_" + (i + 1);

            AgentPath path = agent.GetComponent<AgentPath>();
            if (path != null)
            {
                path.allPointsContainer = attractionsContainer;
                path.numberOfPointsToVisit = Random.Range(pointsPerAgentMin, pointsPerAgentMax + 1);
                path.exitPoints = exits;
                path.loop = false; // после 5 точек — к выходу, не зацикливать
                path.waitTimeMin = waitTimeMin;
                path.waitTimeMax = waitTimeMax;
            }

            float interval = Random.Range(spawnIntervalMin, spawnIntervalMax);
            yield return new WaitForSeconds(interval);
        }

        Debug.Log("AgentSpawnManager: создано " + agentCount + " агентов.");
    }
}
