import json
import os

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

# Path to JSON file
json_file = 'bird-dataset-main/data/NMFA_3floors_plan.json'
output_dxf = 'bird-dataset-main/data/NMFA_3floors_plan.dxf'

print(f"Reading JSON file: {json_file}")

# Read JSON file
with open(json_file, 'r', encoding='utf-8') as f:
    plan_data = json.load(f)

print(f"Museum name: {plan_data.get('name', 'Unknown')}")
print(f"Number of floors: {len(plan_data.get('floors', []))}")

# Create DXF document
doc = ezdxf.new('R2010')  # Create a new DXF document
msp = doc.modelspace()  # Get modelspace

# Process each floor
for floor in plan_data.get('floors', []):
    floor_number = floor.get('number', 0)
    walls = floor.get('walls', [])
    
    # Create separate layers for walls and paintings for this floor
    walls_layer_name = f"FLOOR_{floor_number}_WALLS"
    paintings_layer_name = f"FLOOR_{floor_number}_PAINTINGS"
    
    # Color scheme: different colors for each floor
    # Floor 0: blue (5), Floor 1: magenta (6), Floor 2: yellow (2)
    floor_colors = {0: 5, 1: 6, 2: 2}
    wall_color = floor_colors.get(floor_number, 7)  # Default to white
    
    doc.layers.new(name=walls_layer_name, dxfattribs={'color': wall_color})
    doc.layers.new(name=paintings_layer_name, dxfattribs={'color': 1})  # Red for all paintings
    
    print(f"\nProcessing Floor {floor_number}: {len(walls)} walls")
    
    wall_count = 0
    painting_count = 0
    
    # Process each wall
    for wall in walls:
        wall_id = wall.get('id', '')
        position = wall.get('position', [])
        paintings = wall.get('paintings', [])
        
        if len(position) >= 2:
            # Get wall endpoints
            start_point = position[0]
            end_point = position[1]
            
            x1 = start_point.get('x', 0)
            y1 = start_point.get('y', 0)
            x2 = end_point.get('x', 0)
            y2 = end_point.get('y', 0)
            
            # Draw wall as a line on floor-specific layer
            msp.add_line(
                start=(x1, y1),
                end=(x2, y2),
                dxfattribs={
                    'layer': walls_layer_name,
                    'color': wall_color
                }
            )
            wall_count += 1
            
            # Process paintings on this wall
            for painting in paintings:
                painting_id = painting.get('id', '')
                
                # Calculate painting position on the wall
                # If painting has leftDistance, use it to position along the wall
                left_distance = painting.get('leftDistance', 0)
                
                # Calculate direction vector of the wall
                wall_length = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                
                if wall_length > 0:
                    # Normalized direction vector
                    dx = (x2 - x1) / wall_length
                    dy = (y2 - y1) / wall_length
                    
                    # Painting position (starting from first point)
                    paint_x = x1 + dx * left_distance
                    paint_y = y1 + dy * left_distance
                    
                    # Draw painting as a point or small circle on floor-specific layer
                    msp.add_circle(
                        center=(paint_x, paint_y),
                        radius=50,  # Small circle to mark painting location
                        dxfattribs={
                            'layer': paintings_layer_name,
                            'color': 1  # Red
                        }
                    )
                    
                    # Add text label for painting ID
                    msp.add_text(
                        painting_id,
                        height=100,
                        dxfattribs={
                            'layer': paintings_layer_name,
                            'color': 1,
                            'insert': (paint_x, paint_y + 100)  # Offset above the circle
                        }
                    )
                    painting_count += 1
                else:
                    # If wall has zero length, just mark at start point
                    msp.add_circle(
                        center=(x1, y1),
                        radius=50,
                        dxfattribs={
                            'layer': paintings_layer_name,
                            'color': 1
                        }
                    )
                    painting_count += 1
    
    print(f"  - Added {wall_count} walls")
    print(f"  - Added {painting_count} paintings")

# Save DXF file
doc.saveas(output_dxf)
print(f"\nDXF file saved to: {output_dxf}")
print(f"  - Layers created:")
for floor in plan_data.get('floors', []):
    floor_num = floor.get('number', 0)
    print(f"    * FLOOR_{floor_num}_WALLS")
    print(f"    * FLOOR_{floor_num}_PAINTINGS")
