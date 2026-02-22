using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.AI;

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

    [Header("Автозагрузка из модели (слои FBX)")]
    [Tooltip("Корень модели FBX (объект, под которым в иерархии лежат узлы Attractions, Entrance, Exit). Если задан — аттракции, входы и выходы подставятся автоматически, ручное перетаскивание не нужно.")]
    public Transform pointsSourceRoot;

    [Tooltip("Имя узла с точками аттракций (дочерние объекты = точки картин).")]
    public string attractionsNodeName = "Attractions";
    [Tooltip("Имя узла с точками входа (дочерние = позиции появления агентов).")]
    public string entranceNodeName = "Entrance";
    [Tooltip("Имя узла с точками выхода (дочерние = лестницы/выходы).")]
    public string exitNodeName = "Exit";

    [Header("Скорость симуляции")]
    [Tooltip("Time.timeScale: 1 = реальное время, >1 ускорение (например 10 = симуляция в 10 раз быстрее).")]
    [Range(0.25f, 20f)]
    public float simulationTimeScale = 1f;

    [Header("Типы поведения (для отслеживаемых агентов)")]
    [Tooltip("Настройки типов и их доли. Фоновые агенты получают случайный тип из этих же настроек. Отслеживаемые — по процентам.")]
    public BehaviorTypeSettings[] behaviorTypes = new BehaviorTypeSettings[]
    {
        new BehaviorTypeSettings { type = BehaviorType.ActiveExplorer, percentage = 25, speedMin = 1.3f, speedMax = 2f, pointsMin = 80, pointsMax = 135, waitTimeMin = 6f, waitTimeMax = 21f },
        new BehaviorTypeSettings { type = BehaviorType.Fast, percentage = 25, speedMin = 1.5f, speedMax = 2f, pointsMin = 60, pointsMax = 100, waitTimeMin = 7f, waitTimeMax = 17f },
        new BehaviorTypeSettings { type = BehaviorType.Researcher, percentage = 25, speedMin = 1.2f, speedMax = 1.8f, pointsMin = 80, pointsMax = 135, waitTimeMin = 9f, waitTimeMax = 21f },
        new BehaviorTypeSettings { type = BehaviorType.Slow, percentage = 25, speedMin = 1f, speedMax = 1.5f, pointsMin = 70, pointsMax = 100, waitTimeMin = 6f, waitTimeMax = 32f },
    };

    [Header("Фоновые агенты (создаются первыми)")]
    [Tooltip("Минимальное количество фоновых агентов (толпа, треки не записываются).")]
    public int backgroundAgentCountMin = 20;

    [Tooltip("Максимальное количество фоновых агентов (случайное от min до max).")]
    public int backgroundAgentCountMax = 50;

    [Tooltip("Интервал (сек) между появлением фоновых агентов.")]
    public Vector2 backgroundSpawnInterval = new Vector2(1f, 3f);

    [Header("Отслеживаемые агенты (создаются после фоновых)")]
    [Tooltip("Количество отслеживаемых агентов (их треки записываются).")]
    public int trackedAgentCount = 51;

    [Tooltip("Минимальный интервал (сек) между появлением двух отслеживаемых агентов.")]
    public float spawnIntervalMin = 2f;

    [Tooltip("Максимальный интервал (сек) между появлением двух отслеживаемых агентов.")]
    public float spawnIntervalMax = 6f;

    [Header("Цвета агентов")]
    [Tooltip("Цвет фоновых агентов (толпа, треки не записываются).")]
    public Color backgroundAgentColor = new Color(0.5f, 0.5f, 0.5f);

    [Tooltip("Цвет агентов типа Active Explorer (только для отслеживаемых).")]
    public Color colorActiveExplorer = new Color(0.2f, 0.7f, 0.3f);
    [Tooltip("Цвет агентов типа Fast.")]
    public Color colorFast = new Color(0.9f, 0.5f, 0.1f);
    [Tooltip("Цвет агентов типа Researcher.")]
    public Color colorResearcher = new Color(0.2f, 0.5f, 0.9f);
    [Tooltip("Цвет агентов типа Slow.")]
    public Color colorSlow = new Color(0.6f, 0.4f, 0.8f);

    [Header("Запуск")]
    [Tooltip("Если выключено — спавн начнётся только по вызову BeginSpawning() (например, по кнопке Старт в UI).")]
    public bool startSpawningOnStart = true;

    bool _spawnStarted;
    Coroutine _spawnCoroutine;
    List<GameObject> _spawnedAgents = new List<GameObject>();
    int _defaultTrackedAgentCount;
    BehaviorTypeSettings[] _defaultBehaviorTypes;

    void Awake()
    {
        SaveDefaultParams();
        TryLoadPointsFromLayerNodes();
    }

    /// <summary>Если задан pointsSourceRoot — ищем под ним узлы Attractions, Entrance, Exit (в т.ч. вложенные) и подставляем в контейнеры/массивы.</summary>
    void TryLoadPointsFromLayerNodes()
    {
        if (pointsSourceRoot == null) return;

        Transform att = FindChildRecursive(pointsSourceRoot, attractionsNodeName);
        Transform ent = FindChildRecursive(pointsSourceRoot, entranceNodeName);
        Transform ext = FindChildRecursive(pointsSourceRoot, exitNodeName);

        if (att != null)
        {
            attractionsContainer = att;
        }
        if (ent != null)
        {
            var list = new List<Transform>();
            for (int j = 0; j < ent.childCount; j++)
                list.Add(ent.GetChild(j));
            spawnPoints = list.Count > 0 ? list.ToArray() : new Transform[] { ent };
            spawnPoint = null;
        }
        if (ext != null)
        {
            var list = new List<Transform>();
            for (int j = 0; j < ext.childCount; j++)
                list.Add(ext.GetChild(j));
            exitPoints = list.Count > 0 ? list.ToArray() : new Transform[] { ext };
        }

        if (attractionsContainer != null || (spawnPoints != null && spawnPoints.Length > 0) || (exitPoints != null && exitPoints.Length > 0))
            Debug.Log("AgentSpawnManager: точки загружены из слоёв модели (Attractions=" + (attractionsContainer != null ? attractionsContainer.childCount + " точек" : "нет") + ", Entrance=" + (spawnPoints != null ? spawnPoints.Length + " точек" : "нет") + ", Exit=" + (exitPoints != null ? exitPoints.Length + " точек" : "нет") + ").");
    }

    /// <summary>Найти первый дочерний Transform с заданным именем (рекурсивно по всей иерархии). Регистр не учитывается (слои: Floor, Walls, Entrance, Attractions, Exit).</summary>
    static Transform FindChildRecursive(Transform parent, string childName)
    {
        if (parent == null || string.IsNullOrEmpty(childName)) return null;
        for (int i = 0; i < parent.childCount; i++)
        {
            Transform c = parent.GetChild(i);
            if (string.Equals(c.name, childName, System.StringComparison.OrdinalIgnoreCase)) return c;
            var found = FindChildRecursive(c, childName);
            if (found != null) return found;
        }
        return null;
    }

    /// <summary>Заново подставить точки из pointsSourceRoot (вызвать после смены модели или смены Points Source в Inspector).</summary>
    public void RefreshPointsFromLayerNodes()
    {
        TryLoadPointsFromLayerNodes();
    }

    void SaveDefaultParams()
    {
        _defaultTrackedAgentCount = trackedAgentCount;
        if (behaviorTypes == null || behaviorTypes.Length == 0) return;
        _defaultBehaviorTypes = new BehaviorTypeSettings[behaviorTypes.Length];
        for (int i = 0; i < behaviorTypes.Length; i++)
        {
            var s = behaviorTypes[i];
            _defaultBehaviorTypes[i] = new BehaviorTypeSettings
            {
                type = s.type,
                percentage = s.percentage,
                speedMin = s.speedMin, speedMax = s.speedMax,
                pointsMin = s.pointsMin, pointsMax = s.pointsMax,
                waitTimeMin = s.waitTimeMin, waitTimeMax = s.waitTimeMax
            };
        }
    }

    /// <summary>Восстановить исходные параметры (количество агентов и все типы поведения). Вызывать из UI по кнопке Сброс.</summary>
    public void ResetToDefaultParams()
    {
        if (_defaultBehaviorTypes != null && behaviorTypes != null)
        {
            int count = Mathf.Min(_defaultBehaviorTypes.Length, behaviorTypes.Length);
            for (int i = 0; i < count; i++)
            {
                var d = _defaultBehaviorTypes[i];
                behaviorTypes[i].type = d.type;
                behaviorTypes[i].percentage = d.percentage;
                behaviorTypes[i].speedMin = d.speedMin;
                behaviorTypes[i].speedMax = d.speedMax;
                behaviorTypes[i].pointsMin = d.pointsMin;
                behaviorTypes[i].pointsMax = d.pointsMax;
                behaviorTypes[i].waitTimeMin = d.waitTimeMin;
                behaviorTypes[i].waitTimeMax = d.waitTimeMax;
            }
        }
        trackedAgentCount = _defaultTrackedAgentCount;
    }

    void Start()
    {
        if (agentPrefab == null)
        {
            Debug.LogError("AgentSpawnManager: не назначен Agent Prefab.");
            return;
        }
        if (attractionsContainer == null)
        {
            Debug.LogWarning("AgentSpawnManager: план не загружен. Сначала нажмите «Load plan» и выберите .glb/.gltf, затем «Start».");
            return;
        }
        Time.timeScale = simulationTimeScale;
        if (startSpawningOnStart)
        {
            _spawnStarted = true;
            _spawnCoroutine = StartCoroutine(SpawnAllAgents());
        }
    }

    /// <summary>Запустить спавн агентов (вызывать из UI по кнопке Старт). Параметры (trackedAgentCount, behaviorTypes) должны быть уже заданы.</summary>
    public void BeginSpawning()
    {
        if (_spawnStarted) return;
        if (agentPrefab == null)
        {
            Debug.LogWarning("AgentSpawnManager: спавн не запущен — не назначен Agent Prefab. Назначьте префаб в инспекторе или положите префаб в папку Resources с именем AgentPrefab или Agent.");
            return;
        }
        if (attractionsContainer == null)
        {
            Debug.LogWarning("AgentSpawnManager: спавн не запущен — нет контейнера аттракций (загрузите план с узлом Attractions).");
            return;
        }
        _spawnStarted = true;
        Time.timeScale = simulationTimeScale;
        _spawnCoroutine = StartCoroutine(SpawnAllAgents());
    }

    /// <summary>Удалить всех агентов, остановить спавн и разрешить новый запуск (для кнопки Restart в UI).</summary>
    public void ClearAgentsAndAllowRestart()
    {
        if (_spawnCoroutine != null)
        {
            StopCoroutine(_spawnCoroutine);
            _spawnCoroutine = null;
        }
        for (int i = _spawnedAgents.Count - 1; i >= 0; i--)
        {
            if (_spawnedAgents[i] != null)
                Destroy(_spawnedAgents[i]);
        }
        _spawnedAgents.Clear();
        _spawnStarted = false;
    }

    Vector3 GetSpawnPosition()
    {
        if (spawnPoints != null && spawnPoints.Length > 0)
        {
            Transform t = spawnPoints[Random.Range(0, spawnPoints.Length)];
            if (t != null) return AgentPath.GetWorldPositionForPoint(t);
        }
        if (spawnPoint != null) return AgentPath.GetWorldPositionForPoint(spawnPoint);
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

    /// <summary>Сначала фоновые (толпа), потом отслеживаемые (запись треков).</summary>
    IEnumerator SpawnAllAgents()
    {
        var exits = GetExitPoints();
        if (exits == null || exits.Length == 0)
            Debug.LogWarning("AgentSpawnManager: Exit Points пуст. Создай объект Exit с дочерними точками (лестницы) или назначь Exit Points вручную.");

        // 1. Сначала фоновые агенты — создают толпу
        int backgroundCount = Random.Range(backgroundAgentCountMin, backgroundAgentCountMax + 1);
        for (int i = 0; i < backgroundCount; i++)
        {
            SpawnOneAgent(exits, isTracked: false, index: i + 1, namePrefix: "Background");
            float interval = Random.Range(backgroundSpawnInterval.x, backgroundSpawnInterval.y);
            yield return new WaitForSeconds(interval);
        }
        Debug.Log("AgentSpawnManager: создано " + backgroundCount + " фоновых агентов.");

        // 2. Затем отслеживаемые агенты — их треки записываются
        for (int i = 0; i < trackedAgentCount; i++)
        {
            SpawnOneAgent(exits, isTracked: true, index: i + 1, namePrefix: "Tracked");
            float interval = Random.Range(spawnIntervalMin, spawnIntervalMax);
            yield return new WaitForSeconds(interval);
        }
        Debug.Log("AgentSpawnManager: создано " + trackedAgentCount + " отслеживаемых агентов. Всего: " + (backgroundCount + trackedAgentCount));
    }

    void SpawnOneAgent(Transform[] exits, bool isTracked, int index, string namePrefix)
    {
        BehaviorType bType = ChooseBehaviorType(isTracked);
        BehaviorTypeSettings settings = GetSettingsFor(bType);
        if (settings == null)
            settings = new BehaviorTypeSettings { speedMin = 1f, speedMax = 2f, pointsMin = 5, pointsMax = 25, waitTimeMin = 1.4f, waitTimeMax = 3f };

        Vector3 spawnPos = GetSpawnPosition();
        const float sampleRadius = 100f;
        const float fallbackRadius = 200f;
        if (!NavMesh.SamplePosition(spawnPos, out NavMeshHit hit, sampleRadius, NavMesh.AllAreas))
        {
            Vector3 fallbackOrigin = pointsSourceRoot != null ? pointsSourceRoot.position : Vector3.zero;
            if (!NavMesh.SamplePosition(fallbackOrigin, out hit, fallbackRadius, NavMesh.AllAreas))
            {
                Debug.LogWarning("AgentSpawnManager: не найдена точка на NavMesh для спавна агента, пропуск.");
                return;
            }
        }

        GameObject agent = Instantiate(agentPrefab, hit.position, Quaternion.identity);
        agent.name = namePrefix + "_" + index;
        _spawnedAgents.Add(agent);
        agent.SetActive(false);

        AgentPath path = agent.GetComponent<AgentPath>();
        if (path != null)
        {
            path.allPointsContainer = attractionsContainer;
            path.numberOfPointsToVisit = Random.Range(settings.pointsMin, settings.pointsMax + 1);
            path.exitPoints = exits;
            path.loop = false;
            path.waitTimeMin = settings.waitTimeMin;
            path.waitTimeMax = settings.waitTimeMax;
            path.recordTrack = isTracked;
            path.behaviorType = bType;
        }

        var nav = agent.GetComponent<NavMeshAgent>();
        if (nav != null)
        {
            nav.Warp(hit.position);
            nav.speed = Random.Range(settings.speedMin, settings.speedMax);
        }

        agent.SetActive(true);

        Color color = isTracked ? GetColorForType(bType) : backgroundAgentColor;
        foreach (var r in agent.GetComponentsInChildren<Renderer>(true))
        {
            if (r != null && r.material != null)
                r.material.color = color;
        }
    }

    Color GetColorForType(BehaviorType type)
    {
        switch (type)
        {
            case BehaviorType.ActiveExplorer: return colorActiveExplorer;
            case BehaviorType.Fast: return colorFast;
            case BehaviorType.Researcher: return colorResearcher;
            case BehaviorType.Slow: return colorSlow;
            default: return colorFast;
        }
    }

    BehaviorType ChooseBehaviorType(bool forTracked)
    {
        if (behaviorTypes == null || behaviorTypes.Length == 0)
            return BehaviorType.Fast;
        if (forTracked)
        {
            int total = 0;
            foreach (var t in behaviorTypes) total += Mathf.Max(0, t.percentage);
            if (total <= 0) return behaviorTypes[0].type;
            int r = Random.Range(0, total);
            foreach (var t in behaviorTypes)
            {
                int p = Mathf.Max(0, t.percentage);
                if (r < p) return t.type;
                r -= p;
            }
        }
        return behaviorTypes[Random.Range(0, behaviorTypes.Length)].type;
    }

    BehaviorTypeSettings GetSettingsFor(BehaviorType type)
    {
        if (behaviorTypes == null) return null;
        foreach (var t in behaviorTypes)
            if (t.type == type) return t;
        return behaviorTypes.Length > 0 ? behaviorTypes[0] : null;
    }
}

[System.Serializable]
public class BehaviorTypeSettings
{
    public BehaviorType type;
    [Range(0, 100)] public int percentage = 25;
    [Tooltip("Скорость (м/с)")] public float speedMin = 1f, speedMax = 2f;
    [Tooltip("Число точек посещения")] public int pointsMin = 5, pointsMax = 25;
    [Tooltip("Время ожидания у картины (сек)")] public float waitTimeMin = 1f, waitTimeMax = 5f;
}
