"""One-time script to patch model_search_micro.ipynb: sim from unity_plan_and_tracks.dxf."""
import json
from pathlib import Path

path = Path("model_search_micro.ipynb")
nb = json.loads(path.read_text(encoding="utf-8"))

# 1) Constants cell: replace PATH_SIMULATION_CSV and PATH_UNITY_PLAN_DXF with PATH_UNITY_DXF
for cell in nb["cells"]:
    if cell["cell_type"] != "code" or not cell.get("source"):
        continue
    src = cell["source"]
    text = "".join(src)
    if "PATH_SIMULATION_CSV" in text and "PATH_UNITY_PLAN_DXF" in text and "CELL_SIZE_M" in text:
        new_src = []
        for line in src:
            if "PATH_SIMULATION_CSV" in line or "PATH_UNITY_PLAN_DXF" in line:
                continue
            if "CELL_SIZE_M = 1.0" in line:
                new_src.append(line)
                new_src.append(
                    'PATH_UNITY_DXF = str(Path("model_search") / "unity_plan_and_tracks.dxf") '
                    'if (Path.cwd() / "model_search" / "unity_plan_and_tracks.dxf").exists() '
                    'else "unity_plan_and_tracks.dxf"\n'
                )
                continue
            new_src.append(line)
        cell["source"] = new_src
        print("Patched constants cell")
        break

# 2) Find cell with "# Unity-треки" and grid_json / density_Unity
for cell in nb["cells"]:
    if cell["cell_type"] != "code" or not cell.get("source"):
        continue
    src = cell["source"]
    text = "".join(src)
    if "# Unity-треки" not in text or "grid_json.exists()" not in text or "density_Unity" not in text:
        continue
    new_src = []
    i = 0
    while i < len(src):
        line = src[i]
        if "# Unity-треки" in line:
            new_src.append("# Симулированные треки и план из unity_plan_and_tracks.dxf (Outline/PLAN_FLOOR -> метры)\n")
            new_src.append("traj_sim_m = None\n")
            new_src.append("segments_sim = []\n")
            new_src.append("path_floor_dxf = Path(PATH_DXF) if isinstance(PATH_DXF, str) else Path(PATH_DXF)\n")
            new_src.append("path_unity_dxf = Path(PATH_UNITY_DXF) if isinstance(PATH_UNITY_DXF, str) else Path(PATH_UNITY_DXF)\n")
            new_src.append("if path_unity_dxf.exists():\n")
            new_src.append("    try:\n")
            new_src.append("        from room_popularity import load_simulated_trajectories_from_unity_dxf, load_unity_plan_segments_in_floor0_meters\n")
            new_src.append('        traj_sim_raw = load_simulated_trajectories_from_unity_dxf(path_floor_dxf, path_unity_dxf, layer_reference_bird="Outline", layer_tracks_unity="TRACKS")\n')
            new_src.append("        traj_sim_m = [[(x * SCALE_FACTOR, y * SCALE_FACTOR) for (x, y) in tr] for tr in traj_sim_raw]\n")
            new_src.append("        segments_sim = load_unity_plan_segments_in_floor0_meters(path_floor_dxf, path_unity_dxf, scale_factor=SCALE_FACTOR)\n")
            new_src.append("    except Exception as e:\n")
            new_src.append('        print(f"[Симуляция] Не удалось загрузить треки/план из unity DXF: {e}")\n')
            new_src.append("        traj_sim_m = None\n")
            new_src.append("        segments_sim = []\n")
            while i < len(src) and "fig, axes = plt.subplots" not in src[i]:
                i += 1
            continue
        if "extra_segments=segments_unity_red" in line:
            new_src.append("        axes[1], segments_sim, xe, ye, traj_sim_m,\n")
            new_src.append('        f"Симулированные треки (n={len(traj_sim_m)})",\n')
            new_src.append("        track_color=\"tab:orange\",\n")
            new_src.append("    )\n")
            i += 1
            continue
        if "axes[1], segments, xe, ye, traj_sim_m" in line and i + 4 <= len(src) and "extra_segments" in "".join(src[i:i+5]):
            i += 1
            continue
        if "extra_segments_color" in line:
            i += 1
            continue
        new_src.append(line)
        i += 1
    cell["source"] = new_src
    print("Patched tracks cell")
    break

# 3) Density cell
for cell in nb["cells"]:
    if cell["cell_type"] != "code" or not cell.get("source"):
        continue
    src = cell["source"]
    text = "".join(src)
    if "from density_Unity import compute_density_analysis" not in text:
        continue
    new_src = []
    i = 0
    while i < len(src):
        line = src[i]
        if "from density_Unity import compute_density_analysis as density_unity_analysis" in line:
            new_src.append("# d_sim из симулированных треков (unity_plan_and_tracks.dxf), уже в метрах\n")
            new_src.append("d_sim = None\n")
            new_src.append("if 'traj_sim_m' in dir() and traj_sim_m and len(traj_sim_m) > 0:\n")
            new_src.append("    import numpy as np\n")
            new_src.append("    all_x = np.concatenate([[p[0] for p in tr] for tr in traj_sim_m])\n")
            new_src.append("    all_y = np.concatenate([[p[1] for p in tr] for tr in traj_sim_m])\n")
            new_src.append("    xe, ye = d_real[\"x_edges\"], d_real[\"y_edges\"]\n")
            new_src.append("    hm, _, _ = np.histogram2d(all_x, all_y, bins=[xe, ye])\n")
            new_src.append("    hm = hm.T\n")
            new_src.append("    d_sim = {\"heatmap\": hm, \"top_matrix\": np.zeros_like(hm), \"x_edges\": xe, \"y_edges\": ye, \"n_trajectories\": len(traj_sim_m)}\n")
            while i < len(src) and "path_dxf = Path(PATH_DXF)" not in src[i] and "path_unity_dxf = Path(PATH_UNITY" not in src[i]:
                i += 1
            while i < len(src):
                l = src[i]
                if "path_sim" in l or "path_unity_dxf = Path" in l or "density_unity_analysis" in l or (l.strip() == "try:" and i > 0 and "density" in "".join(src[max(0,i-3):i])):
                    i += 1
                    continue
                if "except FileNotFoundError" in l or (l.strip().startswith("d_sim = ") and "None" in l):
                    i += 1
                    continue
                break
            continue
        new_src.append(line)
        i += 1
    cell["source"] = new_src
    print("Patched density cell")
    break

path.write_text(json.dumps(nb, ensure_ascii=False, indent=2), encoding="utf-8")
print("Done.")
