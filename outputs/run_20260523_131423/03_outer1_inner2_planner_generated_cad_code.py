import cadquery as cq
import math

# Define Z levels from -5 to 65 (every 5mm) to safely over-extend the loft
z_levels = [-5.0 + 5.0 * i for i in range(15)]

blade_wp = cq.Workplane("XY")

for i, Z in enumerate(z_levels):
    # Calculate hub radius and blade protrusion at current Z
    R_hub = 50.0 - 35.0 * (Z / 60.0)
    R_in = max(0.1, R_hub - 2.0)  # Embed 2mm into hub for clean union
    Protr = 15.0 - 10.0 * (Z / 60.0)
    R_out = R_hub + Protr
    
    # 1 degree twist per 1mm height (60 degrees total twist over 60mm)
    theta = math.radians(Z)
    
    # Calculate horizontal thickness to ensure a true normal thickness of 2.5mm
    twist_rate = math.pi / 180.0  # radians per mm
    
    path_angle_in = math.atan(R_in * twist_rate)
    t_h_in = 2.5 / math.cos(path_angle_in)
    
    path_angle_out = math.atan(R_out * twist_rate)
    t_h_out = 2.5 / math.cos(path_angle_out)
    
    # Inner blade points
    Cx_in = R_in * math.cos(theta)
    Cy_in = R_in * math.sin(theta)
    Tx_in = -math.sin(theta)
    Ty_in = math.cos(theta)
    
    p1 = (Cx_in + (t_h_in / 2.0) * Tx_in, Cy_in + (t_h_in / 2.0) * Ty_in)
    p4 = (Cx_in - (t_h_in / 2.0) * Tx_in, Cy_in - (t_h_in / 2.0) * Ty_in)
    
    # Outer blade points
    Cx_out = R_out * math.cos(theta)
    Cy_out = R_out * math.sin(theta)
    Tx_out = -math.sin(theta)
    Ty_out = math.cos(theta)
    
    p2 = (Cx_out + (t_h_out / 2.0) * Tx_out, Cy_out + (t_h_out / 2.0) * Ty_out)
    p3 = (Cx_out - (t_h_out / 2.0) * Tx_out, Cy_out - (t_h_out / 2.0) * Ty_out)
    
    pts = [p1, p2, p3, p4]
    
    # Chain the workplanes offset by 5mm each time
    if i == 0:
        blade_wp = blade_wp.workplane(offset=Z).polyline(pts).close()
    else:
        blade_wp = blade_wp.workplane(offset=5.0).polyline(pts).close()

# Generate the single blade
blade = blade_wp.loft()

# Base Hub: Truncated Cone from R=50 at Z=0 to R=15 at Z=60
impeller = cq.Workplane("XY").circle(50.0).workplane(offset=60.0).circle(15.0).loft()

# Pattern and union the 7 blades
for i in range(7):
    angle = i * (360.0 / 7.0)
    rotated_blade = blade.rotate((0, 0, 0), (0, 0, 1), angle)
    impeller = impeller.union(rotated_blade)

# Trim top and bottom over-extensions
cut_top = cq.Workplane("XY").workplane(offset=60.0).rect(200, 200).extrude(50.0)
impeller = impeller.cut(cut_top)

cut_bottom = cq.Workplane("XY").workplane(offset=-50.0).rect(200, 200).extrude(50.0)
impeller = impeller.cut(cut_bottom)

# Central Bore Cut (15mm diameter / 7.5mm radius)
bore = cq.Workplane("XY").workplane(offset=-10.0).circle(7.5).extrude(80.0)
result_solid = impeller.cut(bore)