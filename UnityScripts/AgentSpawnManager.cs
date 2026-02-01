using System.Collections;
using UnityEngine;

/// <summary>
/// Создаёт агентов с разнесённым по времени появлением и передаёт им контейнер аттракций.
/// Положи на сцену, укажи префаб агента (Capsule с AgentPath + NavMeshAgent) и контейнер Attractions.
/// </summary>
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

    [Tooltip("Количество агентов для создания.")]
    public int agentCount = 45;

    [Tooltip("Минимальный интервал (сек) между появлением двух агентов.")]
    public float spawnIntervalMin = 2f;

    [Tooltip("Максимальный интервал (сек) между появлением двух агентов.")]
    public float spawnIntervalMax = 6f;

    [Tooltip("Минимум точек маршрута на одного агента (случайное от min до max).")]
    public int pointsPerAgentMin = 10;

    [Tooltip("Максимум точек маршрута на одного агента.")]
    public int pointsPerAgentMax = 25;

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

    IEnumerator SpawnAgentsOverTime()
    {
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
            }

            float interval = Random.Range(spawnIntervalMin, spawnIntervalMax);
            yield return new WaitForSeconds(interval);
        }

        Debug.Log("AgentSpawnManager: создано " + agentCount + " агентов.");
    }
}
