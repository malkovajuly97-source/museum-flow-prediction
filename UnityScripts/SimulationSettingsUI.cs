using System.Collections;
using UnityEngine;
using UnityEngine.UI;
using TMPro;

/// <summary>
/// UI для настроек симуляции: количество отслеживаемых агентов и доли типов поведения.
/// Назначь ссылки в Inspector, затем кнопка Старт применит настройки и запустит спавн (если у AgentSpawnManager выключен startSpawningOnStart).
///
/// Логика: при изменении любого параметра (количество агентов, проценты, Speed/Points/Wait Time) симуляция ставится на паузу.
/// Нажатие Start = перезапуск с нуля с текущими значениями из UI. Reset = восстановить дефолты (без перезапуска).
///
/// Как собрать UI: Canvas → Panel с полем количества агентов, 4 слайдера типов, кнопка Старт/Стоп, кнопка Reset.
/// У AgentSpawnManager снять "Start Spawning On Start", чтобы спавн только по кнопке Старт.
///
/// Вариант с typePanels: назначь 4 панели (Researcher, Active Explorer, Fast, Slow) — исходные значения подтянутся из AgentSpawnManager при старте и по Reset.
/// </summary>
[System.Serializable]
public class BehaviorTypePanelBinding
{
    [Tooltip("Тип поведения (Researcher, Active Explorer, Fast, Slow).")]
    public BehaviorType type;
    [Tooltip("Слайдер процента (0–100%).")]
    public Slider slider;
    [Tooltip("Текст над слайдером (например «Researcher 25%»).")]
    public TMP_Text label;
    public TMP_InputField inputSpeedMin, inputSpeedMax, inputPointsMin, inputPointsMax, inputWaitTimeMin, inputWaitTimeMax;
}

public class SimulationSettingsUI : MonoBehaviour
{
    [Header("Ссылки")]
    [Tooltip("Менеджер спавна агентов.")]
    public AgentSpawnManager spawnManager;

    [Tooltip("Кнопка Старт/Стоп (одна кнопка, текст меняется).")]
    public Button buttonStartStop;

    [Tooltip("Текст на кнопке Старт/Стоп (если не назначен — ищется среди дочерних кнопки).")]
    public TMP_Text labelStartStop;

    [Tooltip("Кнопка восстановления исходных параметров (количество агентов, проценты и 6 параметров по типам). Не перезапускает симуляцию.")]
    public Button buttonReset;

    [Tooltip("Поле ввода: количество отслеживаемых агентов (Input Field или TMP_InputField).")]
    public TMP_InputField inputAgentCount;

    [Header("Доли типов поведения (0–100%)")]
    [Tooltip("Слайдер: доля ActiveExplorer (активный обходчик).")]
    public Slider sliderActiveExplorer;

    [Tooltip("Слайдер: доля Fast (быстрый).")]
    public Slider sliderFast;

    [Tooltip("Слайдер: доля Researcher (исследователь).")]
    public Slider sliderResearcher;

    [Tooltip("Слайдер: доля Slow (медленный).")]
    public Slider sliderSlow;

    [Tooltip("Текст с процентом для Active Explorer (обновляется при движении слайдера).")]
    public TMP_Text labelActiveExplorer;
    [Tooltip("Текст с процентом для Fast.")]
    public TMP_Text labelFast;
    [Tooltip("Текст с процентом для Researcher.")]
    public TMP_Text labelResearcher;
    [Tooltip("Текст с процентом для Slow.")]
    public TMP_Text labelSlow;

    [Header("Параметры Active Explorer (Speed, Points, Wait Time)")]
    [Tooltip("Поле: Speed Min для типа Active Explorer.")]
    public TMP_InputField inputSpeedMinActiveExplorer;
    [Tooltip("Поле: Speed Max для типа Active Explorer.")]
    public TMP_InputField inputSpeedMaxActiveExplorer;
    [Tooltip("Поле: Points Min для типа Active Explorer.")]
    public TMP_InputField inputPointsMinActiveExplorer;
    [Tooltip("Поле: Points Max для типа Active Explorer.")]
    public TMP_InputField inputPointsMaxActiveExplorer;
    [Tooltip("Поле: Wait Time Min для типа Active Explorer.")]
    public TMP_InputField inputWaitTimeMinActiveExplorer;
    [Tooltip("Поле: Wait Time Max для типа Active Explorer.")]
    public TMP_InputField inputWaitTimeMaxActiveExplorer;

    [Header("Панели по типам (опционально)")]
    [Tooltip("Если задано — для каждого типа синхронизируются свои слайдер и 6 полей из AgentSpawnManager. Исходные значения по типам подставляются при старте и по Reset.")]
    public BehaviorTypePanelBinding[] typePanels;

    [Header("Пределы")]
    [Tooltip("Минимальное количество агентов.")]
    public int agentCountMin = 1;

    [Tooltip("Максимальное количество агентов.")]
    public int agentCountMax = 500;

    bool _simulationRunning;

    void Start()
    {
        if (spawnManager == null)
            spawnManager = FindFirstObjectByType<AgentSpawnManager>();

        SyncUIFromManager();
        StartCoroutine(SyncParamsAfterFrame());

        if (typePanels != null && typePanels.Length > 0)
        {
            foreach (var p in typePanels)
            {
                if (p.slider != null)
                {
                    var type = p.type;
                    p.slider.onValueChanged.AddListener(_ => PauseIfRunning());
                    p.slider.onValueChanged.AddListener(v => UpdateTypePanelLabel(p, v));
                    UpdateTypePanelLabel(p, p.slider.value);
                }
                AddEndEditPause(p.inputSpeedMin, p.inputSpeedMax, p.inputPointsMin, p.inputPointsMax, p.inputWaitTimeMin, p.inputWaitTimeMax);
            }
        }
        else
        {
            if (sliderActiveExplorer != null) { sliderActiveExplorer.onValueChanged.AddListener(UpdateActiveExplorerLabel); sliderActiveExplorer.onValueChanged.AddListener(_ => PauseIfRunning()); UpdateActiveExplorerLabel(sliderActiveExplorer.value); }
            if (sliderFast != null) { sliderFast.onValueChanged.AddListener(UpdateFastLabel); sliderFast.onValueChanged.AddListener(_ => PauseIfRunning()); UpdateFastLabel(sliderFast.value); }
            if (sliderResearcher != null) { sliderResearcher.onValueChanged.AddListener(UpdateResearcherLabel); sliderResearcher.onValueChanged.AddListener(_ => PauseIfRunning()); UpdateResearcherLabel(sliderResearcher.value); }
            if (sliderSlow != null) { sliderSlow.onValueChanged.AddListener(UpdateSlowLabel); sliderSlow.onValueChanged.AddListener(_ => PauseIfRunning()); UpdateSlowLabel(sliderSlow.value); }
            if (inputSpeedMinActiveExplorer != null) inputSpeedMinActiveExplorer.onEndEdit.AddListener(_ => PauseIfRunning());
            if (inputSpeedMaxActiveExplorer != null) inputSpeedMaxActiveExplorer.onEndEdit.AddListener(_ => PauseIfRunning());
            if (inputPointsMinActiveExplorer != null) inputPointsMinActiveExplorer.onEndEdit.AddListener(_ => PauseIfRunning());
            if (inputPointsMaxActiveExplorer != null) inputPointsMaxActiveExplorer.onEndEdit.AddListener(_ => PauseIfRunning());
            if (inputWaitTimeMinActiveExplorer != null) inputWaitTimeMinActiveExplorer.onEndEdit.AddListener(_ => PauseIfRunning());
            if (inputWaitTimeMaxActiveExplorer != null) inputWaitTimeMaxActiveExplorer.onEndEdit.AddListener(_ => PauseIfRunning());
        }

        if (inputAgentCount != null)
            inputAgentCount.onEndEdit.AddListener(_ => PauseIfRunning());

        if (buttonStartStop != null)
        {
            buttonStartStop.onClick.AddListener(OnStartStopClicked);
            if (labelStartStop == null && buttonStartStop != null)
                labelStartStop = buttonStartStop.GetComponentInChildren<TMP_Text>();
            UpdateStartStopButtonLabel();
        }
        if (buttonReset != null)
            buttonReset.onClick.AddListener(OnResetClicked);
    }

    void AddEndEditPause(params TMP_InputField[] fields)
    {
        if (fields == null) return;
        foreach (var f in fields)
            if (f != null) f.onEndEdit.AddListener(_ => PauseIfRunning());
    }

    static string GetTypeDisplayName(BehaviorType t)
    {
        switch (t) { case BehaviorType.ActiveExplorer: return "Active Explorer"; case BehaviorType.Fast: return "Fast"; case BehaviorType.Researcher: return "Researcher"; case BehaviorType.Slow: return "Slow"; default: return t.ToString(); }
    }

    void UpdateTypePanelLabel(BehaviorTypePanelBinding p, float value)
    {
        if (p.label != null) p.label.text = GetTypeDisplayName(p.type) + " " + Mathf.RoundToInt(value) + "%";
    }

    void PauseIfRunning()
    {
        if (!_simulationRunning) return;
        Time.timeScale = 0f;
        _simulationRunning = false;
        UpdateStartStopButtonLabel();
    }

    void UpdateStartStopButtonLabel()
    {
        if (labelStartStop == null) return;
        labelStartStop.text = _simulationRunning ? "Stop" : "Start";
    }

    void OnStartStopClicked()
    {
        if (_simulationRunning)
        {
            Time.timeScale = 0f;
            _simulationRunning = false;
            UpdateStartStopButtonLabel();
        }
        else
        {
            if (spawnManager != null)
                spawnManager.ClearAgentsAndAllowRestart();
            ApplyManagerFromUI();
            if (spawnManager != null)
                spawnManager.BeginSpawning();
            if (spawnManager != null)
                Time.timeScale = spawnManager.simulationTimeScale;
            _simulationRunning = true;
            UpdateStartStopButtonLabel();
        }
    }

    void OnResetClicked()
    {
        PauseIfRunning();
        if (spawnManager != null)
            spawnManager.ResetToDefaultParams();
        SyncUIFromManager();
        StartCoroutine(SyncParamsAfterFrame());
    }

    void UpdateActiveExplorerLabel(float value) { if (labelActiveExplorer != null) labelActiveExplorer.text = "Active Explorer " + Mathf.RoundToInt(value) + "%"; }
    void UpdateFastLabel(float value) { if (labelFast != null) labelFast.text = "Fast " + Mathf.RoundToInt(value) + "%"; }
    void UpdateResearcherLabel(float value) { if (labelResearcher != null) labelResearcher.text = "Researcher " + Mathf.RoundToInt(value) + "%"; }
    void UpdateSlowLabel(float value) { if (labelSlow != null) labelSlow.text = "Slow " + Mathf.RoundToInt(value) + "%"; }

    /// <summary>Синхронизировать поля UI из настроек менеджера.</summary>
    public void SyncUIFromManager()
    {
        if (spawnManager == null) return;

        if (inputAgentCount != null)
            inputAgentCount.text = Mathf.Clamp(spawnManager.trackedAgentCount, agentCountMin, agentCountMax).ToString();

        if (spawnManager.behaviorTypes == null || spawnManager.behaviorTypes.Length == 0) return;

        if (typePanels != null && typePanels.Length > 0)
        {
            foreach (var p in typePanels)
            {
                BehaviorTypeSettings s = GetSettingsForType(p.type);
                if (s == null) continue;
                if (p.slider != null) { p.slider.minValue = 0f; p.slider.maxValue = 100f; p.slider.value = Mathf.Clamp(s.percentage, 0, 100); UpdateTypePanelLabel(p, p.slider.value); }
                if (p.inputSpeedMin != null) p.inputSpeedMin.text = s.speedMin.ToString("F2");
                if (p.inputSpeedMax != null) p.inputSpeedMax.text = s.speedMax.ToString("F2");
                if (p.inputPointsMin != null) p.inputPointsMin.text = s.pointsMin.ToString();
                if (p.inputPointsMax != null) p.inputPointsMax.text = s.pointsMax.ToString();
                if (p.inputWaitTimeMin != null) p.inputWaitTimeMin.text = s.waitTimeMin.ToString("F2");
                if (p.inputWaitTimeMax != null) p.inputWaitTimeMax.text = s.waitTimeMax.ToString("F2");
            }
            return;
        }

        SetSliderFromType(sliderActiveExplorer, BehaviorType.ActiveExplorer);
        SetSliderFromType(sliderFast, BehaviorType.Fast);
        SetSliderFromType(sliderResearcher, BehaviorType.Researcher);
        SetSliderFromType(sliderSlow, BehaviorType.Slow);

        if (sliderActiveExplorer != null) UpdateActiveExplorerLabel(sliderActiveExplorer.value);
        if (sliderFast != null) UpdateFastLabel(sliderFast.value);
        if (sliderResearcher != null) UpdateResearcherLabel(sliderResearcher.value);
        if (sliderSlow != null) UpdateSlowLabel(sliderSlow.value);

        SyncActiveExplorerParamsFromManager();
    }

    BehaviorTypeSettings GetSettingsForType(BehaviorType type)
    {
        if (spawnManager == null || spawnManager.behaviorTypes == null) return null;
        foreach (var t in spawnManager.behaviorTypes)
            if (t.type == type) return t;
        return null;
    }

    IEnumerator SyncParamsAfterFrame()
    {
        yield return null;
        if (typePanels != null && typePanels.Length > 0)
            SyncUIFromManager();
        else
            SyncActiveExplorerParamsFromManager();
    }

    void SyncActiveExplorerParamsFromManager()
    {
        if (spawnManager == null || spawnManager.behaviorTypes == null) return;
        foreach (var t in spawnManager.behaviorTypes)
        {
            if (t.type != BehaviorType.ActiveExplorer) continue;
            if (inputSpeedMinActiveExplorer != null) inputSpeedMinActiveExplorer.text = t.speedMin.ToString("F2");
            if (inputSpeedMaxActiveExplorer != null) inputSpeedMaxActiveExplorer.text = t.speedMax.ToString("F2");
            if (inputPointsMinActiveExplorer != null) inputPointsMinActiveExplorer.text = t.pointsMin.ToString();
            if (inputPointsMaxActiveExplorer != null) inputPointsMaxActiveExplorer.text = t.pointsMax.ToString();
            if (inputWaitTimeMinActiveExplorer != null) inputWaitTimeMinActiveExplorer.text = t.waitTimeMin.ToString("F2");
            if (inputWaitTimeMaxActiveExplorer != null) inputWaitTimeMaxActiveExplorer.text = t.waitTimeMax.ToString("F2");
            return;
        }
    }

    void ApplyActiveExplorerParamsToManager()
    {
        if (spawnManager == null || spawnManager.behaviorTypes == null) return;
        foreach (var t in spawnManager.behaviorTypes)
        {
            if (t.type != BehaviorType.ActiveExplorer) continue;
            if (inputSpeedMinActiveExplorer != null && float.TryParse(inputSpeedMinActiveExplorer.text, System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out float v)) t.speedMin = Mathf.Max(0f, v);
            if (inputSpeedMaxActiveExplorer != null && float.TryParse(inputSpeedMaxActiveExplorer.text, System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out v)) t.speedMax = Mathf.Max(0f, v);
            if (inputPointsMinActiveExplorer != null && int.TryParse(inputPointsMinActiveExplorer.text, out int i)) t.pointsMin = Mathf.Max(0, i);
            if (inputPointsMaxActiveExplorer != null && int.TryParse(inputPointsMaxActiveExplorer.text, out i)) t.pointsMax = Mathf.Max(0, i);
            if (inputWaitTimeMinActiveExplorer != null && float.TryParse(inputWaitTimeMinActiveExplorer.text, System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out v)) t.waitTimeMin = Mathf.Max(0f, v);
            if (inputWaitTimeMaxActiveExplorer != null && float.TryParse(inputWaitTimeMaxActiveExplorer.text, System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out v)) t.waitTimeMax = Mathf.Max(0f, v);
            return;
        }
    }

    void SetSliderFromType(Slider slider, BehaviorType type)
    {
        if (slider == null) return;
        foreach (var t in spawnManager.behaviorTypes)
        {
            if (t.type == type)
            {
                slider.minValue = 0f;
                slider.maxValue = 100f;
                slider.value = Mathf.Clamp(t.percentage, 0, 100);
                return;
            }
        }
    }

    void ApplyManagerFromUI()
    {
        if (spawnManager == null) return;

        if (inputAgentCount != null && int.TryParse(inputAgentCount.text, out int count))
            spawnManager.trackedAgentCount = Mathf.Clamp(count, agentCountMin, agentCountMax);

        if (typePanels != null && typePanels.Length > 0)
        {
            foreach (var p in typePanels)
            {
                BehaviorTypeSettings s = GetSettingsForType(p.type);
                if (s == null) continue;
                if (p.slider != null) s.percentage = Mathf.RoundToInt(Mathf.Clamp(p.slider.value, 0f, 100f));
                if (p.inputSpeedMin != null && float.TryParse(p.inputSpeedMin.text, System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out float v)) s.speedMin = Mathf.Max(0f, v);
                if (p.inputSpeedMax != null && float.TryParse(p.inputSpeedMax.text, System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out v)) s.speedMax = Mathf.Max(0f, v);
                if (p.inputPointsMin != null && int.TryParse(p.inputPointsMin.text, out int i)) s.pointsMin = Mathf.Max(0, i);
                if (p.inputPointsMax != null && int.TryParse(p.inputPointsMax.text, out i)) s.pointsMax = Mathf.Max(0, i);
                if (p.inputWaitTimeMin != null && float.TryParse(p.inputWaitTimeMin.text, System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out v)) s.waitTimeMin = Mathf.Max(0f, v);
                if (p.inputWaitTimeMax != null && float.TryParse(p.inputWaitTimeMax.text, System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out v)) s.waitTimeMax = Mathf.Max(0f, v);
            }
            return;
        }

        ApplySliderToType(sliderActiveExplorer, BehaviorType.ActiveExplorer);
        ApplySliderToType(sliderFast, BehaviorType.Fast);
        ApplySliderToType(sliderResearcher, BehaviorType.Researcher);
        ApplySliderToType(sliderSlow, BehaviorType.Slow);

        ApplyActiveExplorerParamsToManager();
    }

    void ApplySliderToType(Slider slider, BehaviorType type)
    {
        if (slider == null) return;
        foreach (var t in spawnManager.behaviorTypes)
        {
            if (t.type == type)
            {
                t.percentage = Mathf.RoundToInt(Mathf.Clamp(slider.value, 0f, 100f));
                return;
            }
        }
    }

}
