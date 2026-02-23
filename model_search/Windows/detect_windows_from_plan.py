"""
Автоматическое определение окон по плану этажа 0.

Окна = разрывы в контуре по периметру здания: ищем пары коллинеарных стен с зазором,
но оставляем только те разрывы, которые лежат на внешнем периметре (не внутри здания).

Вход: bird-dataset-main/data/NMFA_3floors_plan.json (стены этажа 0)
Выход: floor0_windows.json (сегменты-разрывы в той же системе координат)
"""

import json
import math
from pathlib import Path

try:
    from shapely.geometry import LineString, Point
    from shapely.ops import polygonize, unary_union
    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False

BASE = Path(__file__).resolve().parent
PROJECT_ROOT = BASE.parent.parent
PLAN_FILE = PROJECT_ROOT / "bird-dataset-main/data/NMFA_3floors_plan.json"
WINDOWS_JSON = BASE / "floor0_windows.json"

# Разрыв считаем окном, если его длина в этих пределах (в единицах плана)
MIN_WINDOW_GAP = 40.0   # меньше = скорее стык стен
MAX_WINDOW_GAP = 750.0  # больше = не окно, а пролёт

# Допуски: одна линия = одинаковый угол и близкая линия (перпендикулярное расстояние)
ANGLE_TOL_DEG = 4.0
PERP_DIST_TOL = 35.0

# Окно на периметре: оба конца в пределах этого расстояния от внешнего кольца здания
ON_PERIMETER_TOL = 180.0

def load_floor0_walls(plan_path: Path):
    """Стены этажа 0: список ((x1,y1), (x2,y2))."""
    if not plan_path.exists():
        return []
    with open(plan_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for floor in data.get("floors", []):
        if floor.get("number") != 0:
            continue
        out = []
        for w in floor.get("walls", []):
            pos = w.get("position", [])
            if len(pos) < 2:
                continue
            p1 = (float(pos[0]["x"]), float(pos[0]["y"]))
            p2 = (float(pos[1]["x"]), float(pos[1]["y"]))
            out.append((p1, p2))
        return out
    return []


def segment_angle(p1, p2):
    """Угол отрезка (p1,p2) в радианах [0, pi)."""
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    return math.atan2(dy, dx) % math.pi


def perpendicular_distance(p, p1, p2):
    """Расстояние от точки p до прямой через p1, p2."""
    x, y = p
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy)
    if L < 1e-10:
        return math.hypot(x - x1, y - y1)
    return abs(dx * (y1 - y) - dy * (x1 - x)) / L


def project_t(p, p1, p2):
    """Параметр t проекции точки p на прямую p1 + t*(p2-p1)."""
    x, y = p
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    L = dx * dx + dy * dy
    if L < 1e-20:
        return 0.0
    return ((x - x1) * dx + (y - y1) * dy) / L


def segments_collinear(s1, s2, angle_tol_rad, perp_tol):
    """Проверка: два отрезка на одной линии (одинаковый угол, малая перпендикулярная дистанция)."""
    (a1, a2), (b1, b2) = s1, s2
    ang1 = segment_angle(a1, a2)
    ang2 = segment_angle(b1, b2)
    if abs(ang1 - ang2) > angle_tol_rad:
        return False
    # Базовая линия — первая
    mid_b = ((b1[0] + b2[0]) * 0.5, (b1[1] + b2[1]) * 0.5)
    d = perpendicular_distance(mid_b, a1, a2)
    return d <= perp_tol


def group_collinear_segments(segments, angle_tol_deg=ANGLE_TOL_DEG, perp_tol=PERP_DIST_TOL):
    """Группируем отрезки по линиям (коллинеарные в одну группу)."""
    angle_tol = math.radians(angle_tol_deg)
    groups = []
    used = [False] * len(segments)
    for i, s in enumerate(segments):
        if used[i]:
            continue
        group = [s]
        used[i] = True
        for j in range(i + 1, len(segments)):
            if used[j]:
                continue
            if segments_collinear(s, segments[j], angle_tol, perp_tol):
                group.append(segments[j])
                used[j] = True
        groups.append(group)
    return groups


def gap_between(s1, s2, p1_ref, p2_ref):
    """
    Для двух коллинеарных отрезков s1, s2 (прямая через p1_ref, p2_ref)
    возвращает (gap_length, point_a, point_b) — концы разрыва, или None.
    """
    (a1, a2), (b1, b2) = s1, s2
    t_a1 = project_t(a1, p1_ref, p2_ref)
    t_a2 = project_t(a2, p1_ref, p2_ref)
    t_b1 = project_t(b1, p1_ref, p2_ref)
    t_b2 = project_t(b2, p1_ref, p2_ref)
    # Концы отрезков с их t
    ends_a = [(t_a1, a1), (t_a2, a2)]
    ends_b = [(t_b1, b1), (t_b2, b2)]
    ends_a.sort(key=lambda x: x[0])
    ends_b.sort(key=lambda x: x[0])
    # Правый конец первого отрезка и левый конец второго (относительно линии)
    right_a_t, right_a_pt = ends_a[1]
    left_b_t, left_b_pt = ends_b[0]
    gap_t = left_b_t - right_a_t
    if gap_t < 1e-6:
        return None
    dx = p2_ref[0] - p1_ref[0]
    dy = p2_ref[1] - p1_ref[1]
    L = math.hypot(dx, dy)
    if L < 1e-10:
        return None
    # t — параметр вдоль направления (p2_ref - p1_ref), не нормализованный; длина отрезка = |t| * L только если мы нормализовали. project_t даёт проекцию в единицах длины направления, т.к. знаменатель L^2 в project_t нет — там (x-x1)*dx + (y-y1)*dy и L = dx^2+dy^2. Так что project_t возвращает скаляр такое что точка = p1 + project_t * (p2-p1) только если (p2-p1) нормализован. У нас (p2-p1) не нормализован, поэтому project_t = ((x-x1)*dx+(y-y1)*dy) / (dx^2+dy^2). Тогда разница t в 1 даёт смещение по направлению на (dx, dy) т.е. длину sqrt(dx^2+dy^2)=L. Значит physical_gap = gap_t * L? Нет: p = p1 + t*(p2-p1) при t как (dot/L^2)*L^2/L = dot/L, тогда шаг по t на 1 даёт шаг (p2-p1), длина L. То есть distance = gap_t * L. Ok.
    physical_gap = gap_t * L
    return (physical_gap, right_a_pt, left_b_pt)


def get_exterior_ring(segments):
    """Внешнее кольцо здания по стенам (unary_union + buffer). Нужно для проверки «на периметре»."""
    if not HAS_SHAPELY or not segments:
        return None
    lines = [LineString([s[0], s[1]]) for s in segments]
    try:
        u = unary_union(lines)
        if u.is_empty:
            return None
        buffered = u.buffer(25.0, cap_style=2, join_style=2)
        if buffered.is_empty:
            return None
        if buffered.geom_type == "Polygon":
            largest = buffered
        elif buffered.geom_type == "MultiPolygon":
            largest = max(buffered.geoms, key=lambda p: p.area)
        else:
            return None
        if largest.exterior and len(largest.exterior.coords) >= 3:
            return LineString(largest.exterior.coords)
    except Exception:
        pass
    return None


def filter_windows_on_perimeter(windows, segments):
    """
    Оставляем только окна на внешнем периметре: оба конца отрезка должны быть
    в пределах ON_PERIMETER_TOL от внешнего кольца здания (разрывы внутри отсекаются).
    """
    if not HAS_SHAPELY or not windows:
        return windows
    perimeter = get_exterior_ring(segments)
    if perimeter is None:
        print("  Предупреждение: не удалось построить периметр, окна не фильтруются.")
        return windows
    result = []
    for gap_len, p1, p2 in windows:
        if Point(p1).distance(perimeter) <= ON_PERIMETER_TOL and Point(p2).distance(perimeter) <= ON_PERIMETER_TOL:
            result.append((gap_len, p1, p2))
    return result


def detect_window_gaps(segments):
    """По списку отрезков возвращает список (gap_len, p1, p2) для каждого разрыва-окна (только на периметре)."""
    groups = group_collinear_segments(segments)
    windows = []
    for group in groups:
        if len(group) < 2:
            continue
        p1_ref, p2_ref = group[0][0], group[0][1]
        with_t = []
        for (a, b) in group:
            t_mid = (project_t(a, p1_ref, p2_ref) + project_t(b, p1_ref, p2_ref)) * 0.5
            with_t.append((t_mid, (a, b)))
        with_t.sort(key=lambda x: x[0])
        ordered = [x[1] for x in with_t]
        for i in range(len(ordered) - 1):
            s1, s2 = ordered[i], ordered[i + 1]
            g = gap_between(s1, s2, p1_ref, p2_ref)
            if g is None:
                continue
            gap_len, pt_a, pt_b = g
            if MIN_WINDOW_GAP <= gap_len <= MAX_WINDOW_GAP:
                windows.append((gap_len, pt_a, pt_b))
    # Только окна на внешнем периметре (не внутри здания)
    windows = filter_windows_on_perimeter(windows, segments)
    return windows


def main():
    segments = load_floor0_walls(PLAN_FILE)
    if not segments:
        print("Стены этажа 0 не найдены.")
        return
    print(f"Загружено стен (отрезков): {len(segments)}")
    windows = detect_window_gaps(segments)
    print(f"Найдено разрывов-окон: {len(windows)}")
    out_segments = [
        {
            "id": f"win_{i+1}",
            "position": [
                {"x": round(p1[0], 4), "y": round(p1[1], 4)},
                {"x": round(p2[0], 4), "y": round(p2[1], 4)},
            ],
        }
        for i, (_, p1, p2) in enumerate(windows)
    ]
    data = {
        "description": "Сегменты контура этажа, где есть разрыв (окно). Автоопределение по плану: коллинеарные стены с зазором.",
        "units": "те же, что в плане (position.x, position.y)",
        "segments": out_segments,
    }
    with open(WINDOWS_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Сохранено: {WINDOWS_JSON}")
    for i, (length, p1, p2) in enumerate(windows):
        print(f"  win_{i+1}: длина разрыва {length:.0f}  ({p1[0]:.0f},{p1[1]:.0f}) — ({p2[0]:.0f},{p2[1]:.0f})")


if __name__ == "__main__":
    main()
