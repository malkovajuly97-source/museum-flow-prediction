using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.AI;
using UnityEngine.Networking;
using UnityEngine.SceneManagement;
using Unity.AI.Navigation;
using GLTFast;
#if UNITY_EDITOR
using UnityEditor;
#endif

/// <summary>
/// Единая точка смены плана (модели): подстановка корня, автовыпечка NavMesh Surface на узле Floor, обновление точек для AgentSpawnManager и TrackRecorder.
/// Загрузка .glb/.gltf по кнопке «Load plan» (в WebGL — выбор файла в браузере) через GLTFast Runtime Import.
/// Требуется пакет: com.unity.cloud.gltfast (Window → Package Manager → Add package by name).
/// Структура плана: узлы Floor, Attractions, Entrance, Exit под корнем.
/// </summary>
public class PlanController : MonoBehaviour
{
    [Header("Ссылки")]
    [Tooltip("Менеджер спавна агентов — ему подставляется pointsSourceRoot и вызывается RefreshPointsFromLayerNodes().")]
    public AgentSpawnManager spawnManager;

    [Tooltip("Контейнер, в который подставляется корень плана (текущая модель или загруженный glTF). Например AR Content или пустой объект.")]
    public Transform planContainer;

    [Tooltip("Опционально: запись треков. После смены плана обновляются floorTransform и attractionsContainer.")]
    public TrackRecorder trackRecorder;

    [Tooltip("Опционально: экспорт плана и треков в DXF. После смены плана подставляются floorTransform, wallsContainer, attractionsContainer загруженного плана.")]
    public PlanAndTrackExporter planAndTrackExporter;

    [Header("Имена узлов в плане")]
    [Tooltip("Имя узла пола (для NavMesh). Должен содержать меш и компонент NavMeshSurface или он будет добавлен.")]
    public string floorNodeName = "Floor";

    [Header("Загрузка glTF (кнопка)")]
    [Tooltip("URL тестового .glb для быстрой проверки. Оставь пустым, если используешь только выбор файла.")]
    public string gltfTestUrl = "";

    [Header("Внешний вид плана (WebGL)")]
    [Tooltip("Серый материал для плана. Создай Material (Create → Material), выбери шейдер URP Lit, поставь серый цвет — и перетащи сюда. Тогда план будет виден в WebGL-билде. Если пусто — материал создаётся через Shader.Find (может не попасть в билд).")]
    public Material defaultPlanMaterial;

    [Tooltip("Скрыть модель плана в игре (оставить только логику и NavMesh). Объекты не отключаются — только выключаются Renderer.")]
    public bool hidePlanModelInPlay = true;

    Transform _currentPlanRoot;

    void Awake()
    {
        if (spawnManager == null)
        {
            var spawns = FindObjectsByType<AgentSpawnManager>(FindObjectsInactive.Include, FindObjectsSortMode.None);
            if (spawns != null && spawns.Length > 0) spawnManager = spawns[0];
            if (spawnManager != null)
            {
                Debug.Log("PlanController: Spawn Manager подставлен автоматически.");
                if (spawnManager.agentPrefab == null)
                {
                    spawnManager.agentPrefab = Resources.Load<GameObject>("AgentPrefab");
                    if (spawnManager.agentPrefab == null) spawnManager.agentPrefab = Resources.Load<GameObject>("Agent");
                    if (spawnManager.agentPrefab != null) Debug.Log("PlanController: Agent Prefab подставлен из Resources.");
                }
            }
            else Debug.LogWarning("PlanController: AgentSpawnManager не найден в сцене.");
        }
        if (planContainer == null)
        {
            var go = GameObject.Find("AR Content");
            if (go != null)
                planContainer = go.transform;
            if (planContainer == null && SceneManager.GetActiveScene().isLoaded)
            {
                foreach (var root in SceneManager.GetActiveScene().GetRootGameObjects())
                {
                    var found = FindChildRecursive(root.transform, "AR Content");
                    if (found != null) { planContainer = found; break; }
                }
            }
            if (planContainer != null) Debug.Log("PlanController: Plan Container (AR Content) подставлен автоматически.");
            else Debug.LogWarning("PlanController: объект 'AR Content' не найден в сцене.");
        }
        if (trackRecorder == null)
        {
            var recorders = FindObjectsByType<TrackRecorder>(FindObjectsInactive.Include, FindObjectsSortMode.None);
            if (recorders != null && recorders.Length > 0) trackRecorder = recorders[0];
        }
        if (planAndTrackExporter == null)
        {
            var exporters = FindObjectsByType<PlanAndTrackExporter>(FindObjectsInactive.Include, FindObjectsSortMode.None);
            if (exporters != null && exporters.Length > 0) planAndTrackExporter = exporters[0];
        }
        if (defaultPlanMaterial == null)
            defaultPlanMaterial = Resources.Load<Material>("PlanDefaultGrey");
    }

    void Start()
    {
        if (planContainer != null && planContainer.childCount > 0 && planAndTrackExporter != null)
        {
            Transform planRoot = planContainer.GetChild(0);
            Transform floor = FindChildRecursive(planRoot, floorNodeName);
            planAndTrackExporter.floorTransform = floor;
            planAndTrackExporter.wallsContainer = FindChildRecursive(planRoot, "Walls");
            planAndTrackExporter.attractionsContainer = FindChildRecursive(planRoot, "Attractions");
        }
        if (!hidePlanModelInPlay || planContainer == null) return;
        for (int i = 0; i < planContainer.childCount; i++)
        {
            Transform child = planContainer.GetChild(i);
            if (child != null)
                SetPlanRenderersEnabled(child, false);
        }
    }

#if UNITY_WEBGL && !UNITY_EDITOR
    [System.Runtime.InteropServices.DllImport("__Internal")]
    static extern void OpenFilePickerWebGL(string objectName);
#endif

#if UNITY_STANDALONE_WIN && !UNITY_EDITOR
    [DllImport("comdlg32.dll", CharSet = CharSet.Auto)]
    static extern bool GetOpenFileName([In, Out] ref OpenFileName ofn);

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Auto)]
    struct OpenFileName
    {
        public int lStructSize;
        public IntPtr hwndOwner;
        public IntPtr hInstance;
        public string lpstrFilter;
        public string lpstrCustomFilter;
        public int nMaxCustFilter;
        public int nFilterIndex;
        public IntPtr lpstrFile;
        public int nMaxFile;
        public string lpstrFileTitle;
        public int nMaxFileTitle;
        public string lpstrInitialDir;
        public string lpstrTitle;
        public int Flags;
        public short nFileOffset;
        public short nFileExtension;
        public string lpstrDefExt;
        public IntPtr lCustData;
        public IntPtr lpfnHook;
        public string lpTemplateName;
        public IntPtr pvReserved;
        public int dwReserved;
        public int flagsEx;
    }

    const int OFN_FILEMUSTEXIST = 0x1000;
    const int OFN_PATHMUSTEXIST = 0x800;
    const int MAX_PATH = 260;

    static string OpenFileDialogStandaloneWin(string title, string filter)
    {
        int bufferSize = MAX_PATH * 4;
        var ofn = new OpenFileName();
        ofn.lStructSize = Marshal.SizeOf(ofn);
        ofn.lpstrFilter = filter;
        ofn.lpstrFile = Marshal.AllocHGlobal(bufferSize);
        ofn.nMaxFile = bufferSize / 2;
        ofn.lpstrTitle = title;
        ofn.Flags = OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST;
        try
        {
            if (GetOpenFileName(ref ofn))
                return Marshal.PtrToStringAuto(ofn.lpstrFile);
        }
        finally
        {
            Marshal.FreeHGlobal(ofn.lpstrFile);
        }
        return null;
    }
#endif

    /// <summary>Подставить новый план: остановить симуляцию, заменить корень, выпечь NavMesh, обновить точки у spawnManager и trackRecorder.</summary>
    public void SetActivePlan(Transform planRoot)
    {
        if (planRoot == null)
        {
            Debug.LogWarning("PlanController: planRoot is null.");
            return;
        }

        if (spawnManager != null)
        {
            spawnManager.ClearAgentsAndAllowRestart();
            Time.timeScale = 0f;
        }

        if (planContainer != null)
        {
            // Удалить все текущие дочерние объекты контейнера (в т.ч. дефолтный план из сцены), чтобы под контейнером был только новый план
            for (int i = planContainer.childCount - 1; i >= 0; i--)
            {
                Transform child = planContainer.GetChild(i);
                if (child != planRoot)
                {
                    if (Application.isPlaying)
                        Destroy(child.gameObject);
                    else
                        DestroyImmediate(child.gameObject);
                }
            }
            planRoot.SetParent(planContainer);
            planRoot.localPosition = Vector3.zero;
            planRoot.localRotation = Quaternion.identity;
            planRoot.localScale = Vector3.one;
        }

        _currentPlanRoot = planRoot;

        MakeMeshesReadable(planRoot);
        ApplyDefaultPlanMaterial(planRoot, defaultPlanMaterial);

        Transform floor = FindChildRecursive(planRoot, floorNodeName);
        if (spawnManager != null)
        {
            spawnManager.pointsSourceRoot = planRoot;
            spawnManager.RefreshPointsFromLayerNodes();
        }

        if (floor != null)
            StartCoroutine(BakeNavMeshNextFrame(floor));
        else
            Debug.LogWarning("PlanController: узел пола '" + floorNodeName + "' не найден под " + planRoot.name + ". NavMesh не выпечен.");

        if (trackRecorder != null)
        {
            trackRecorder.floorTransform = floor;
            trackRecorder.attractionsContainer = spawnManager != null ? spawnManager.attractionsContainer : FindChildRecursive(planRoot, "Attractions");
            trackRecorder.wallsContainer = FindChildRecursive(planRoot, "Walls");
        }

        if (planAndTrackExporter != null)
        {
            planAndTrackExporter.floorTransform = floor;
            planAndTrackExporter.wallsContainer = FindChildRecursive(planRoot, "Walls");
            planAndTrackExporter.attractionsContainer = spawnManager != null ? spawnManager.attractionsContainer : FindChildRecursive(planRoot, "Attractions");
        }

        Debug.Log("PlanController: план установлен — " + planRoot.name + ". Нажмите «Start» для запуска симуляции.");
    }

    static Transform FindChildRecursive(Transform parent, string childName)
    {
        if (parent == null || string.IsNullOrEmpty(childName)) return null;
        for (int i = 0; i < parent.childCount; i++)
        {
            Transform c = parent.GetChild(i);
            if (string.Equals(c.name, childName, StringComparison.OrdinalIgnoreCase)) return c;
            var found = FindChildRecursive(c, childName);
            if (found != null) return found;
        }
        return null;
    }

    /// <summary>Включить или выключить отрисовку модели плана (объекты остаются активными — NavMesh и логика работают).</summary>
    static void SetPlanRenderersEnabled(Transform planRoot, bool enabled)
    {
        if (planRoot == null) return;
        foreach (var r in planRoot.GetComponentsInChildren<Renderer>(true))
            r.enabled = enabled;
    }

    static Material _defaultPlanMaterial;

    static Material GetOrCreateDefaultPlanMaterial()
    {
        if (_defaultPlanMaterial != null) return _defaultPlanMaterial;
        string[] shaderNames = {
            "Universal Render Pipeline/Lit",
            "Universal Render Pipeline/Unlit",
            "Universal Render Pipeline/Simple Lit",
            "Shader Graphs/Lit",
            "Standard",
            "Unlit/Color",
            "Unlit/Texture",
            "Sprites/Default",
            "Legacy Shaders/Diffuse",
            "Legacy Shaders/VertexLit"
        };
        foreach (string name in shaderNames)
        {
            Shader sh = Shader.Find(name);
            if (sh != null)
            {
                _defaultPlanMaterial = new Material(sh) { name = "PlanDefaultGrey" };
                _defaultPlanMaterial.color = new Color(0.6f, 0.6f, 0.6f);
                return _defaultPlanMaterial;
            }
        }
        // Запас: шейдер из любого материала в сцене (кроме встроенного «ошибка»)
        var allMats = Resources.FindObjectsOfTypeAll<Material>();
        foreach (var mat in allMats)
        {
            if (mat == null || mat.shader == null) continue;
            if (mat.shader.name.Contains("Error") || mat.shader.name.Contains("InternalError")) continue;
            _defaultPlanMaterial = new Material(mat.shader) { name = "PlanDefaultGrey" };
            _defaultPlanMaterial.color = new Color(0.6f, 0.6f, 0.6f);
            return _defaultPlanMaterial;
        }
        Debug.LogWarning("PlanController: не найден подходящий шейдер для серого материала плана.");
        return null;
    }

    /// <summary>Подставляет серый материал всем рендерерам под планом (убирает розовый «Missing» после загрузки glTF). Если задан defaultPlanMaterial в инспекторе — используется он (рекомендуется для WebGL).</summary>
    static void ApplyDefaultPlanMaterial(Transform root, Material overrideMaterial = null)
    {
        if (root == null) return;
        Material grey = overrideMaterial != null ? overrideMaterial : GetOrCreateDefaultPlanMaterial();
        if (grey == null) return;
        var renderers = root.GetComponentsInChildren<Renderer>(true);
        foreach (var r in renderers)
        {
            if (r == null) continue;
            int count = r.sharedMaterials?.Length ?? 0;
            if (count == 0) continue;
            var mats = new Material[count];
            for (int i = 0; i < count; i++)
                mats[i] = grey;
            r.sharedMaterials = mats;
        }
    }

    /// <summary>Делает меши под корнем читаемыми (копия с Read/Write), чтобы RuntimeNavMeshBuilder мог выпечь NavMesh.
    /// Один общий меш (sharedMesh) копируется один раз и подставляется во все MeshFilter/SkinnedMeshRenderer.</summary>
    static void MakeMeshesReadable(Transform root)
    {
        if (root == null) return;
        var meshToCopy = new Dictionary<Mesh, Mesh>();

        Mesh CreateReadableCopy(Mesh mesh)
        {
            if (mesh == null) return null;
            try
            {
                List<Vector3> vertList = new List<Vector3>();
                mesh.GetVertices(vertList);
                if (vertList == null || vertList.Count == 0)
                {
                    Vector3[] verts = mesh.vertices;
                    if (verts == null || verts.Length == 0) return null;
                    vertList = new List<Vector3>(verts);
                }
                if (vertList.Count == 0) return null;

                Mesh copy = new Mesh { name = mesh.name + "_Readable" };
                copy.SetVertices(vertList);
                copy.SetTriangles(mesh.triangles, 0);
                if (mesh.normals != null && mesh.normals.Length == mesh.vertexCount)
                    copy.SetNormals(mesh.normals);
                else
                    copy.RecalculateNormals();
                if (mesh.uv != null && mesh.uv.Length == mesh.vertexCount)
                    copy.SetUVs(0, mesh.uv);
                copy.RecalculateBounds();
                return copy;
            }
            catch (Exception e)
            {
                Debug.LogWarning("PlanController: не удалось сделать меш читаемым (" + mesh.name + "): " + e.Message);
                return null;
            }
        }

        int replaced = 0, failed = 0;
        var filters = root.GetComponentsInChildren<MeshFilter>(true);
        foreach (var mf in filters)
        {
            if (mf == null || mf.sharedMesh == null) continue;
            Mesh mesh = mf.sharedMesh;
            if (!meshToCopy.TryGetValue(mesh, out Mesh copy))
            {
                copy = CreateReadableCopy(mesh);
                if (copy != null) meshToCopy[mesh] = copy;
                else failed++;
            }
            if (copy != null)
            {
                mf.sharedMesh = copy;
                replaced++;
            }
        }

        var skinned = root.GetComponentsInChildren<SkinnedMeshRenderer>(true);
        foreach (var smr in skinned)
        {
            if (smr == null || smr.sharedMesh == null) continue;
            Mesh mesh = smr.sharedMesh;
            if (!meshToCopy.TryGetValue(mesh, out Mesh copy))
            {
                copy = CreateReadableCopy(mesh);
                if (copy != null) meshToCopy[mesh] = copy;
                else failed++;
            }
            if (copy != null)
            {
                smr.sharedMesh = copy;
                replaced++;
            }
        }

        if (failed > 0)
            Debug.LogWarning("PlanController: не удалось сделать читаемыми " + failed + " мешей (NavMesh может не построиться). Убедитесь, что в пакете UnityGLTF меши создаются с Read/Write.");
        else if (replaced > 0)
            Debug.Log("PlanController: заменено мешей на читаемые копии: " + replaced);
    }

    IEnumerator BakeNavMeshNextFrame(Transform floor)
    {
        yield return null;
        if (_currentPlanRoot != null)
            MakeMeshesReadable(_currentPlanRoot);
        NavMesh.RemoveAllNavMeshData();
        BakeNavMeshOnFloor(floor);
        yield return null;
        Debug.Log("PlanController: NavMesh выпечен. Нажмите «Start» для запуска симуляции.");
    }

    void BakeNavMeshOnFloor(Transform floor)
    {
        var surface = floor.GetComponent<NavMeshSurface>();
        if (surface == null)
            surface = floor.gameObject.AddComponent<NavMeshSurface>();
        surface.BuildNavMesh();
    }

    /// <summary>Загрузить план из .glb по URL и подставить через SetActivePlan. Вызывать из кнопки UI.</summary>
    public void LoadGltfFromUrl(string url)
    {
        if (string.IsNullOrEmpty(url)) url = gltfTestUrl;
        if (string.IsNullOrEmpty(url))
        {
            Debug.LogWarning("PlanController: укажите URL в gltfTestUrl или передайте url в LoadGltfFromUrl.");
            return;
        }
        StartCoroutine(LoadGltfFromUrlCoroutine(url));
    }

    /// <summary>По кнопке Load: в редакторе — окно выбора файла; в WebGL — диалог браузера; в остальных билдах — загрузка по gltfTestUrl.</summary>
    public void OnLoadPlanButtonClicked()
    {
        Debug.Log("Load plan: кнопка нажата");
#if UNITY_EDITOR
        string path = EditorUtility.OpenFilePanel("Выберите план (.glb / .gltf)", "", "glb,gltf");
        if (!string.IsNullOrEmpty(path))
        {
            try
            {
                byte[] bytes = File.ReadAllBytes(path);
                LoadGltfFromBytes(bytes);
            }
            catch (Exception e)
            {
                Debug.LogException(e);
            }
        }
#elif UNITY_WEBGL && !UNITY_EDITOR
        OpenFilePickerWebGL(gameObject.name);
#else
#if UNITY_STANDALONE_WIN
        string path = OpenFileDialogStandaloneWin("Выберите план (.glb / .gltf)", "GLB/GLTF (*.glb;*.gltf)\0*.glb;*.gltf\0All (*.*)\0*.*\0");
        if (!string.IsNullOrEmpty(path))
        {
            try
            {
                byte[] bytes = File.ReadAllBytes(path);
                LoadGltfFromBytes(bytes);
            }
            catch (Exception e)
            {
                Debug.LogException(e);
            }
        }
#else
        LoadGltfFromUrl(gltfTestUrl);
#endif
#endif
    }

    /// <summary>Вызывается из WebGL jslib после выбора файла. base64 — содержимое .glb/.gltf.</summary>
    public void OnFilePickedBase64(string base64)
    {
        if (string.IsNullOrEmpty(base64)) return;
        try
        {
            byte[] bytes = Convert.FromBase64String(base64);
            LoadGltfFromBytes(bytes);
        }
        catch (Exception e)
        {
            Debug.LogException(e);
        }
    }

    IEnumerator LoadGltfFromUrlCoroutine(string url)
    {
        using (var req = UnityWebRequest.Get(url))
        {
            yield return req.SendWebRequest();
            if (req.result != UnityWebRequest.Result.Success)
            {
                Debug.LogError("PlanController: ошибка загрузки " + url + " — " + req.error);
                yield break;
            }
            byte[] bytes = req.downloadHandler.data;
            if (bytes == null || bytes.Length == 0)
            {
                Debug.LogError("PlanController: пустой ответ по " + url);
                yield break;
            }
            yield return LoadGltfFromBytesCoroutine(bytes, url);
        }
    }

    /// <summary>Загрузить план из байтов .glb (например, после выбора файла через jslib в WebGL).</summary>
    public void LoadGltfFromBytes(byte[] bytes)
    {
        if (bytes == null || bytes.Length == 0)
        {
            Debug.LogWarning("PlanController: LoadGltfFromBytes — пустой массив.");
            return;
        }
        StartCoroutine(LoadGltfFromBytesCoroutine(bytes, null));
    }

    IEnumerator LoadGltfFromBytesCoroutine(byte[] bytes, string baseUri)
    {
        GameObject root = null;
        yield return LoadGltfBytesWithGLTFast(bytes, baseUri, result => root = result);
        if (root != null)
            SetActivePlan(root.transform);
        else
            Debug.LogError("PlanController: не удалось создать объекты из glTF.");
    }

    /// <summary>Загрузка .glb/.gltf из byte[] через GLTFast (Runtime Import). После инстанцирования вызывается SetActivePlan → автовыпечка NavMesh на узле Floor.</summary>
    IEnumerator LoadGltfBytesWithGLTFast(byte[] bytes, string baseUri, Action<GameObject> onRootCreated)
    {
        if (bytes == null || bytes.Length == 0)
        {
            onRootCreated?.Invoke(null);
            yield break;
        }

        var root = new GameObject("LoadedPlan");
        Uri uri = string.IsNullOrEmpty(baseUri) ? null : new Uri(baseUri, UriKind.RelativeOrAbsolute);
        using (var gltf = new GltfImport())
        {
            Task<bool> loadTask = gltf.Load(bytes, uri);
            while (!loadTask.IsCompleted)
                yield return null;
            if (loadTask.IsFaulted)
            {
                Debug.LogException(loadTask.Exception);
                Destroy(root);
                onRootCreated?.Invoke(null);
                yield break;
            }
            if (!loadTask.Result)
            {
                Debug.LogError("PlanController: GLTFast Load вернул false.");
                Destroy(root);
                onRootCreated?.Invoke(null);
                yield break;
            }

            Task<bool> instTask = gltf.InstantiateMainSceneAsync(root.transform);
            while (!instTask.IsCompleted)
                yield return null;
            if (instTask.IsFaulted)
            {
                Debug.LogException(instTask.Exception);
                Destroy(root);
                onRootCreated?.Invoke(null);
                yield break;
            }
            if (!instTask.Result)
            {
                Debug.LogError("PlanController: GLTFast InstantiateMainSceneAsync вернул false.");
                Destroy(root);
                onRootCreated?.Invoke(null);
                yield break;
            }
        }

        onRootCreated?.Invoke(root);
    }
}
