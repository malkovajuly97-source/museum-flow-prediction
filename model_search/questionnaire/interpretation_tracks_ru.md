# Интерпретация: зависимости «треки + анкеты»

Объединённая выборка: **51** посетителей (есть трек и pre-анкета; post — где есть).

## Основные артефакты
- `questionnaires_and_tracks.csv` — объединённая таблица (трек + pre + post).
- `correlation_matrix.csv` — корреляционная матрица числовых переменных треков и анкет.
- Папка `analysis/`: scatter (speed track vs pre, satisfaction vs nb_stops/speed, discovery_interest vs nb_items/nb_stops), boxplot по полу и по уровню satisfaction.

## Ограничения
Малая выборка (N=51): интерпретировать стоит только устойчивые по величине связи (|r| > 0.3).
