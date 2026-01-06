import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
import glob
from pathlib import Path

# Try to import ezdxf for DXF export, install if not available
try:
    import ezdxf
    DXF_AVAILABLE = True
except ImportError:
    print("ezdxf not found. Installing...")
    import subprocess
    subprocess.check_call(["pip", "install", "ezdxf"])
    import ezdxf
    DXF_AVAILABLE = True

# Path to trajectories folder
trajectories_folder = 'bird-dataset-main/data/normalized_trajectories/'
csv_files = glob.glob(os.path.join(trajectories_folder, '*.csv'))

print(f"Found {len(csv_files)} trajectory files")

# Read all trajectories
all_trajectories = []
for csv_file in csv_files:
    try:
        df = pd.read_csv(csv_file)
        trajectory_id = Path(csv_file).stem.replace('_traj_normalized', '')
        df['trajectory_id'] = trajectory_id
        all_trajectories.append(df)
        print(f"Loaded: {trajectory_id} ({len(df)} points)")
    except Exception as e:
        print(f"Error loading {csv_file}: {e}")

if not all_trajectories:
    print("No trajectories loaded!")
    exit(1)

# Combine all trajectories
combined_df = pd.concat(all_trajectories, ignore_index=True)

# Get unique floors
floors = sorted(combined_df['floorNumber'].unique())
n_floors = len(floors)

print(f"\nTotal trajectories: {len(csv_files)}")
print(f"Total points: {len(combined_df)}")
print(f"Floors: {floors}")

# Create visualization with subplots for each floor
fig, axes = plt.subplots(1, n_floors, figsize=(8*n_floors, 8))
if n_floors == 1:
    axes = [axes]

# Use a colormap that provides good distinction
colors = plt.cm.gist_rainbow(np.linspace(0, 1, len(csv_files)))

for idx, floor in enumerate(floors):
    ax = axes[idx]
    
    # Plot each trajectory on this floor
    trajectory_count = 0
    for traj_df in all_trajectories:
        floor_data = traj_df[traj_df['floorNumber'] == floor]
        
        if len(floor_data) > 0:
            color = colors[trajectory_count % len(colors)]
            # Plot trajectory line
            ax.plot(floor_data['x'], floor_data['y'], 
                   color=color, linewidth=1.0, alpha=0.7)
            # Mark start point
            ax.plot(floor_data['x'].iloc[0], floor_data['y'].iloc[0], 
                   'o', color=color, markersize=4, alpha=0.8)
            # Mark end point
            ax.plot(floor_data['x'].iloc[-1], floor_data['y'].iloc[-1], 
                   's', color=color, markersize=4, alpha=0.8)
            trajectory_count += 1
    
    # Settings
    ax.set_xlabel('X coordinate', fontsize=12)
    ax.set_ylabel('Y coordinate', fontsize=12)
    ax.set_title(f'Floor {floor} - All Trajectories ({trajectory_count} trajectories)', 
                fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.invert_yaxis()
    
    # Add info text
    ax.text(0.02, 0.98, f'{trajectory_count} trajectories\n(Start: circle, End: square)', 
           transform=ax.transAxes, fontsize=10, 
           verticalalignment='top', 
           bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

plt.tight_layout()
plt.suptitle('All Visitor Trajectories Visualization', 
             fontsize=16, fontweight='bold', y=1.02)
plt.savefig('all_trajectories_visualization.png', dpi=300, bbox_inches='tight')
print("\nGraph saved to: all_trajectories_visualization.png")

# Export to DXF
print("\nExporting to DXF format...")
doc = ezdxf.new('R2010')  # Create a new DXF document
msp = doc.modelspace()  # Get modelspace

# Create layers for each floor
for floor in floors:
    layer_name = f"FLOOR_{floor}"
    doc.layers.new(name=layer_name, dxfattribs={'color': int(floor) + 1})

# Add trajectories to DXF, organized by floor and trajectory
trajectory_count = 0
for traj_df in all_trajectories:
    trajectory_id = traj_df['trajectory_id'].iloc[0]
    
    for floor in floors:
        floor_data = traj_df[traj_df['floorNumber'] == floor]
        
        if len(floor_data) > 1:
            # Create polyline for this trajectory segment
            points = [(row['x'], row['y'], 0) for _, row in floor_data.iterrows()]
            
            # Add polyline to DXF on appropriate floor layer
            layer_name = f"FLOOR_{floor}"
            polyline = msp.add_lwpolyline(
                points=points,
                dxfattribs={
                    'layer': layer_name, 
                    'color': (trajectory_count % 7) + 1  # Cycle through colors
                }
            )
    
    trajectory_count += 1

# Save DXF file
dxf_filename = 'all_trajectories.dxf'
doc.saveas(dxf_filename)
print(f"DXF file saved to: {dxf_filename}")
print(f"  - Organized by floors: {[f'FLOOR_{f}' for f in floors]}")
print(f"  - Total trajectory segments: {trajectory_count}")

# Print summary statistics
print(f"\n=== Summary Statistics ===")
print(f"Total trajectories: {len(csv_files)}")
print(f"Total data points: {len(combined_df)}")
print(f"Floors: {floors}")
print(f"\nCoordinate ranges:")
print(f"X: min={combined_df['x'].min():.2f}, max={combined_df['x'].max():.2f}, mean={combined_df['x'].mean():.2f}")
print(f"Y: min={combined_df['y'].min():.2f}, max={combined_df['y'].max():.2f}, mean={combined_df['y'].mean():.2f}")

plt.show()
