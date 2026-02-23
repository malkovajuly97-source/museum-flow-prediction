# Анализ анкет (questionnaire)

В этой папке — скрипты и результаты анализа анкет посетителей (до и после визита) и их связей с треками.

## Входные данные

- **Анкеты:** `data/questionnaires/pre_questionnaire_formatted.csv`, `post_questionnaire_formatted.csv`  
  Скрипты ищут их в: корень репозитория, `../bird-dataset-main/data/questionnaires/`, а также относительно текущей рабочей директории (`data/questionnaires/` и `bird-dataset-main/data/questionnaires/`).  
  В этом репозитории анкеты ищутся также в `bird-dataset-main/data/questionnaires/` (подпапка датасета).

- **Треки (только для анализа «треки + анкеты»):**  
  `model_search/Openness and size of the space/layout_and_movement.csv`

## Скрипты

1. **`questionnaires_tracks_analysis.py`** — объединение треков и анкет по `visitor_id` = `trajectory_id`, корреляции трек ↔ анкеты, scatter/boxplot, отчёт.
2. **`questionnaires_answers_analysis.py`** — анализ только по ответам анкет (без треков): pre–pre, post–post, pre–post; корреляции, scatter, boxplot по полу/возрасту.

## Выходы

| Файл / папка | Описание |
|--------------|----------|
| `questionnaires_and_tracks.csv` | Трек + pre + post по `visitor_id` (из скрипта 1) |
| `pre_post_merged.csv` | Pre + post по `visitor_id` (из скрипта 2) |
| `correlation_matrix.csv` | Корреляции: треки + анкеты (скрипт 1) |
| `answers_correlation_matrix.csv` | Корреляции: только ответы (скрипт 2) |
| `analysis/` | Графики для анализа «треки + анкеты» |
| `analysis_answers/` | Графики для анализа только по ответам |
| `interpretation_tracks_ru.md` | Краткий отчёт по трекам + анкеты |
| `interpretation_answers_ru.md` | Краткий отчёт по ответам |

## Запуск

```bash
# из корня репозитория
python model_search/questionnaire/questionnaires_tracks_analysis.py
python model_search/questionnaire/questionnaires_answers_analysis.py
```
