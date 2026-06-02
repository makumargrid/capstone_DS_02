import cadquery as cq
import math

# ══════════════════════════════════════════════
# ALL PARAMETERS — pre-computed into plain floats
# ══════════════════════════════════════════════
hub_base_r  = float(50.0)   # cone base radius at Z=0  (mm)
hub_top_r   = float(15.0)   # cone top radius at Z=60  (mm)
hub_h       = float(60.0)   # hub height                (mm)
bore_r      = float(7.5)    # shaft bore radius         (mm)
n_blades    = int(7)        # number of blades
twist_deg   = float(60.0)   # total blade twist         (degrees)
blade_t     = float(2.0)    # blade thickness           (mm)
blade_h_bot = float(22.0)   # protrusion at base — increased to hit 139mm X/Y
blade_h_top = float(6.5)    # protrusion at top  — scaled proportionally
n_stations  = int(24)       # loft stations per blade
embed       = float(1.0)    # embed depth into cone     (mm)

# Pre-computed derived values
bore_extrude_h  = hub_h + 2.0
bore_offset_z   = -1.0
angle_step_rad  = 2.0 * math.pi / float(n_blades)
twist_rad_total = math.radians(twist_deg)

# ══════════════════════════════════════════════
# 1. HUB — truncated cone via revolve
# ══════════════════════════════════════════════
_hub_pts = [
    (hub_base_r, 0.0),
    (hub_top_r,  hub_h),
    (0.0,        hub_h),
    (0.0,        0.0),
]

hub_wp = cq.Workplane("XZ")
hub_wp = hub_wp.polyline(_hub_pts)
hub_wp = hub_wp.close()
hub_solid = hub_wp.revolve(360, (0, 0, 0), (0, 1, 0))

# ══════════════════════════════════════════════
# 2. BORE — cylindrical cut for driveshaft
# ══════════════════════════════════════════════
bore_wp = cq.Workplane("XY")
bore_wp = bore_wp.circle(bore_r)
bore_wp = bore_wp.extrude(bore_extrude_h)
bore_solid = bore_wp.translate((0.0, 0.0, bore_offset_z))

hub_solid = hub_solid.cut(bore_solid)

# ══════════════════════════════════════════════
# 3. BLADE WIRE FUNCTION
# ══════════════════════════════════════════════
def make_blade_wire(z_frac, blade_rot_rad,
                    _hub_base_r=hub_base_r,
                    _hub_top_r=hub_top_r,
                    _hub_h=hub_h,
                    _blade_h_bot=blade_h_bot,
                    _blade_h_top=blade_h_top,
                    _blade_t=blade_t,
                    _embed=embed,
                    _bore_r=bore_r,
                    _twist_rad_total=twist_rad_total):

    z_pos  = z_frac * _hub_h
    r_cone = _hub_base_r + (_hub_top_r - _hub_base_r) * z_frac
    h_prot = _blade_h_bot + (_blade_h_top - _blade_h_bot) * z_frac
    theta  = _twist_rad_total * z_frac + blade_rot_rad

    r_inner = r_cone - _embed
    if r_inner < _bore_r + 1.0:
        r_inner = _bore_r + 1.0
    r_outer = r_cone + h_prot

    ht = _blade_t * 0.5

    cos_t   =  math.cos(theta)
    sin_t   =  math.sin(theta)
    tan_cos = -math.sin(theta)
    tan_sin =  math.cos(theta)

    p0 = cq.Vector(r_inner*cos_t + ht*tan_cos,  r_inner*sin_t + ht*tan_sin,  z_pos)
    p1 = cq.Vector(r_inner*cos_t - ht*tan_cos,  r_inner*sin_t - ht*tan_sin,  z_pos)
    p2 = cq.Vector(r_outer*cos_t - ht*tan_cos,  r_outer*sin_t - ht*tan_sin,  z_pos)
    p3 = cq.Vector(r_outer*cos_t + ht*tan_cos,  r_outer*sin_t + ht*tan_sin,  z_pos)

    e0 = cq.Edge.makeLine(p0, p1)
    e1 = cq.Edge.makeLine(p1, p2)
    e2 = cq.Edge.makeLine(p2, p3)
    e3 = cq.Edge.makeLine(p3, p0)

    wire = cq.Wire.assembleEdges([e0, e1, e2, e3])
    return wire

# ══════════════════════════════════════════════
# 4. BUILD ALL BLADES AND UNION WITH HUB
# ══════════════════════════════════════════════
result_solid = hub_solid

for k in range(n_blades):
    rot_rad = float(k) * angle_step_rad

    wire_list = []
    for i in range(n_stations + 1):
        frac = float(i) / float(n_stations)
        w = make_blade_wire(frac, rot_rad)
        wire_list.append(w)

    blade_solid = cq.Solid.makeLoft(wire_list, ruled=True)
    blade_shell = cq.Workplane("XY").add(blade_solid)
    result_solid = result_solid.union(blade_shell)