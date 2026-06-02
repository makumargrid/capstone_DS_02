import cadquery as cq
import math

def get_t_h(R):
    """
    Calculates the horizontal thickness needed to achieve a true normal 
    thickness of 2.5mm, compensating for the twisted path.
    """
    twist_rate = math.pi / 180.0  # 60 degrees twist over 60mm height = 1 deg/mm
    path_angle = math.atan(R * twist_rate)
    return 2.5 / math.cos(path_angle)

def blade_section(Z):
    """
    Returns the 4 points defining the cross-section of a blade at a given Z.
    """
    R_hub = 50.0 - 35.0 * (Z / 60.0)
    R_in = max(0.1, R_hub - 2.0)  # Embed 2mm into hub for clean union
    Protr = 15.0 - 10.0 * (Z / 60.0)
    R_out = R_hub + Protr
    
    theta = math.radians(Z)  # 1 degree twist per 1mm height
    
    t_h_in = get_t_h(R_in)
    t_h_out = get_t_h(R_out)
    
    Cx_in = R_in * math.cos(theta)
    Cy_in = R_in * math.sin(theta)
    Tx_in = -math.sin(theta)
    Ty_in = math.cos(theta)
    
    p1 = (Cx_in + (t_h_in / 2.0) * Tx_in, Cy_in + (t_h_in / 2.0) * Ty_in)
    p4 = (Cx_in - (t_h_in / 2.0) * Tx_in, Cy_in - (t_h_in / 2.0) * Ty_in)
    
    Cx_out = R_out * math.cos(theta)
    Cy_out = R_out * math.sin(theta)
    Tx_out = -math.sin(theta)
    Ty_out = math.cos(theta)
    
    p2 = (Cx_out + (t_h_out / 2.0) * Tx_out, Cy_out + (t_h_out / 2.0) * Ty_out)
    p3 = (Cx_out - (t_h_out / 2.0) * Tx_out, Cy_out - (t_h_out / 2.0) * Ty_out)
    
    return [p1, p2, p3, p4]

# 1. Create a single over-extended lofted blade from Z=-5 to Z=65
z_levels = [-5.0 + 5.0 * i for i in range(15)]
blade_wp = cq.Workplane("XY")
for i, Z in enumerate(z_levels):
    pts = blade_section(Z)
    if i == 0:
        blade_wp = blade_wp.workplane(offset=Z).polyline(pts).close()
    else:
        blade_wp = blade_wp.workplane(offset=5.0).polyline(pts).close()

blade = blade_wp.loft()

# 2. Base Hub (Truncated Cone)
impeller = cq.Workplane("XY").circle(50.0).workplane(offset=60.0).circle(15.0).loft()

# 3. Pattern and Union the 7 blades
for i in range(7):
    angle = i * (360.0 / 7.0)
    rotated_blade = blade.rotate((0, 0, 0), (0, 0, 1), angle)
    impeller = impeller.union(rotated_blade)

# 4. Trim Top and Bottom Over-extensions (guarantees completely flat top and bottom)
cut_top = cq.Workplane("XY").workplane(offset=60.0).rect(200, 200).extrude(50.0)
impeller = impeller.cut(cut_top)

cut_bottom = cq.Workplane("XY").workplane(offset=-50.0).rect(200, 200).extrude(50.0)
impeller = impeller.cut(cut_bottom)

# 5. Central Bore Cut (15mm diameter)
bore = cq.Workplane("XY").workplane(offset=-10.0).circle(7.5).extrude(80.0)
result_solid = impeller.cut(bore)