import cadquery as cq
import math

# ─────────────────────────────────────────────
# PARAMETERS
# ─────────────────────────────────────────────
HUB_BASE_R  = 50.0   # mm, cone base radius at Z=0
HUB_TOP_R   = 15.0   # mm, cone top radius at Z=60
HUB_H       = 60.0   # mm, hub height
BORE_R      = 7.5    # mm, shaft bore radius (15mm diameter)
N_BLADES    = 7
BLADE_TWIST = 60.0   # degrees total twist bottom to top
BLADE_T     = 2.0    # mm, blade thickness (tangential width)
BLADE_H_BOT = 15.0   # mm, radial protrusion at base
BLADE_H_TOP = 5.0    # mm, radial protrusion at top
N_STATIONS  = 20     # number of loft cross-sections per blade
EMBED       = 0.8    # mm, embed blade into cone for watertight union

# Cone half-angle from vertical
cone_alpha = math.atan2(HUB_BASE_R - HUB_TOP_R, HUB_H)  # ~30.26 deg

# ─────────────────────────────────────────────
# 1. HUB — truncated cone via revolve
# ─────────────────────────────────────────────
hub = (
    cq.Workplane("XZ")
    .polyline([
        (HUB_BASE_R, 0.0),
        (HUB_TOP_R,  HUB_H),
        (0.0,        HUB_H),
        (0.0,        0.0),
    ])
    .close()
    .revolve(360, (0, 0, 0), (0, 1, 0))
)

# ─────────────────────────────────────────────
# 2. BORE — subtract central cylinder
# ─────────────────────────────────────────────
bore = (
    cq.Workplane("XY")
    .circle(BORE_R)
    .extrude(HUB_H + 2.0)
    .translate((0, 0, -1.0))
)
hub = hub.cut(bore)

# ─────────────────────────────────────────────
# HELPER: build one blade wire at a given Z-fraction
# The cross-section is a flat rectangle in the horizontal plane at height z,
# with:
#   - inner radius: r_cone - EMBED  (embedded into cone)
#   - outer radius: r_cone + h_prot (protrudes radially outward)
#   - tangential half-width: BLADE_T / 2
# ─────────────────────────────────────────────
def make_blade_wire(z_frac, blade_rotation_rad):
    z      = z_frac * HUB_H
    r_cone = HUB_BASE_R - (HUB_BASE_R - HUB_TOP_R) * z_frac
    h_prot = BLADE_H_BOT + (BLADE_H_TOP - BLADE_H_BOT) * z_frac
    # Total angular position = twist + blade index offset
    theta  = math.radians(BLADE_TWIST * z_frac) + blade_rotation_rad

    r_inner = max(r_cone - EMBED, BORE_R + 0.5)   # don't go past bore
    r_outer = r_cone + h_prot

    ht = BLADE_T / 2.0  # tangential half-width

    # Radial unit vector at angle theta
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    # Tangential unit vector (CCW perpendicular)
    cos_t90 = -math.sin(theta)
    sin_t90 =  math.cos(theta)

    # Four corners of the blade cross-section (flat at height z):
    # inner-left, inner-right, outer-right, outer-left  (CCW winding)
    p0 = (r_inner*cos_t + ht*cos_t90,  r_inner*sin_t + ht*sin_t90,  z)
    p1 = (r_inner*cos_t - ht*cos_t90,  r_inner*sin_t - ht*sin_t90,  z)
    p2 = (r_outer*cos_t - ht*cos_t90,  r_outer*sin_t - ht*sin_t90,  z)
    p3 = (r_outer*cos_t + ht*cos_t90,  r_outer*sin_t + ht*sin_t90,  z)

    verts = [cq.Vector(*p) for p in [p0, p1, p2, p3]]
    edges = [
        cq.Edge.makeLine(verts[0], verts[1]),
        cq.Edge.makeLine(verts[1], verts[2]),
        cq.Edge.makeLine(verts[2], verts[3]),
        cq.Edge.makeLine(verts[3], verts[0]),
    ]
    return cq.Wire.assembleEdges(edges)


# ─────────────────────────────────────────────
# 3. BUILD ALL 7 BLADES AND UNION WITH HUB
# ─────────────────────────────────────────────
result_solid = hub

blade_angle_step_rad = 2.0 * math.pi / N_BLADES

for k in range(N_BLADES):
    rot = k * blade_angle_step_rad

    # Build wire list for this blade
    wires = []
    for i in range(N_STATIONS + 1):
        z_frac = i / float(N_STATIONS)
        w = make_blade_wire(z_frac, rot)
        wires.append(w)

    # Loft the blade solid (ruled=True for linear interpolation — more stable)
    try:
        blade_solid = cq.Solid.makeLoft(wires, ruled=True)
        blade_wp    = cq.Workplane("XY").add(blade_solid)
        result_solid = result_solid.union(blade_wp)
    except Exception as e:
        print(f"Blade {k} loft failed: {e}")