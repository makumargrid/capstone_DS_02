import cadquery as cq
import math

# ─────────────────────────────────────────────
# PARAMETERS
# ─────────────────────────────────────────────
HUB_BASE_R    = 50.0
HUB_TOP_R     = 15.0
HUB_H         = 60.0
BORE_D        = 15.0
N_BLADES      = 7
BLADE_T       = 2.5
BLADE_H_BOT   = 35.0
BLADE_H_TOP   = 5.0
EMBED_DEPTH   = 3.0    # blade embeds 3mm INTO cone surface for watertight union
TWIST_DEG     = 60.0
N_STATIONS    = 16

# ─────────────────────────────────────────────
# CONE GEOMETRY
# ─────────────────────────────────────────────
dRdZ        = (HUB_TOP_R - HUB_BASE_R) / HUB_H   # -35/60
tang_len    = math.sqrt(dRdZ**2 + 1.0)
norm_r_unit = 1.0 / tang_len
norm_z_unit = -dRdZ / tang_len


def cone_radius(z):
    return HUB_BASE_R + dRdZ * z


def blade_cross_section(z_station, twist_angle_deg, blade_h, blade_t, embed):
    """
    Trapezoidal cross-section wire. Extends from -embed (inside cone)
    to +blade_h (outside cone) along cone outward normal.
    Slightly wider at the embedded base for clean boolean.
    """
    r_cone  = cone_radius(z_station)
    ang_rad = math.radians(twist_angle_deg)

    cx = r_cone * math.cos(ang_rad)
    cy = r_cone * math.sin(ang_rad)
    cz = z_station

    # Outward cone normal in 3D
    nx = norm_r_unit * math.cos(ang_rad)
    ny = norm_r_unit * math.sin(ang_rad)
    nz = norm_z_unit

    # Circumferential tangent
    tx = -math.sin(ang_rad)
    ty =  math.cos(ang_rad)

    half_t      = blade_t / 2.0
    half_t_wide = half_t + embed * 0.3

    def pt(n_scale, t_scale):
        return cq.Vector(
            cx + n_scale * nx + t_scale * tx,
            cy + n_scale * ny + t_scale * ty,
            cz + n_scale * nz
        )

    p0 = pt(-embed,   -half_t_wide)
    p1 = pt(-embed,   +half_t_wide)
    p2 = pt(blade_h,  +half_t)
    p3 = pt(blade_h,  -half_t)

    wire = cq.Wire.makePolygon([p0, p1, p2, p3, p0])
    return wire


def build_one_blade(start_angle_deg=0.0):
    """Build a single blade lofted through N_STATIONS cross-sections."""
    wires = []
    for i in range(N_STATIONS):
        t     = i / (N_STATIONS - 1)
        z_s   = t * HUB_H
        ang_s = start_angle_deg + t * TWIST_DEG
        h_s   = BLADE_H_BOT + t * (BLADE_H_TOP - BLADE_H_BOT)
        w = blade_cross_section(z_s, ang_s, h_s, BLADE_T, EMBED_DEPTH)
        wires.append(w)

    blade_solid = cq.Solid.makeLoft(wires, ruled=False)
    return blade_solid


# ─────────────────────────────────────────────
# 1. HUB — truncated cone via loft
# ─────────────────────────────────────────────
hub = (
    cq.Workplane("XY")
    .circle(HUB_BASE_R)
    .workplane(offset=HUB_H)
    .circle(HUB_TOP_R)
    .loft()
)

# ─────────────────────────────────────────────
# 2. CENTRAL BORE
# ─────────────────────────────────────────────
bore = (
    cq.Workplane("XY")
    .circle(BORE_D / 2.0)
    .extrude(HUB_H)
)
hub = hub.cut(bore)

# ─────────────────────────────────────────────
# 3. BUILD ALL 7 BLADES AND UNION TO HUB
# Use .union() on Workplane — correct CadQuery API
# Blades are embedded 3mm into hub for watertight boolean
# ─────────────────────────────────────────────
blade_angle_step = 360.0 / N_BLADES   # ~51.43 degrees

result_solid = hub

for i in range(N_BLADES):
    start_angle = i * blade_angle_step

    # Build the lofted blade solid (cq.Solid)
    blade_solid = build_one_blade(start_angle_deg=start_angle)

    # Wrap in a Workplane for boolean operation
    blade_wp = cq.Workplane("XY").add(blade_solid)

    # .union() is the correct Workplane boolean method
    result_solid = result_solid.union(blade_wp)

# ─────────────────────────────────────────────
# 4. CLEAN UP
# ─────────────────────────────────────────────
result_solid = result_solid.clean()