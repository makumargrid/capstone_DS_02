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
BLADE_T       = 2.5        # blade thickness (circumferential), > 2mm DFM min
BLADE_H_BOT   = 15.0       # radial protrusion above cone surface at base (spec: 15mm)
BLADE_H_TOP   = 5.0        # radial protrusion above cone surface at top  (spec: 5mm)
EMBED_DEPTH   = 3.0        # how far blade extends INTO cone (radially inward) for watertight union
TWIST_DEG     = 60.0       # total angular twist from base to top
N_STATIONS    = 16         # loft cross-section count

# ─────────────────────────────────────────────
# CONE GEOMETRY
# ─────────────────────────────────────────────
dRdZ = (HUB_TOP_R - HUB_BASE_R) / HUB_H   # -35/60 ≈ -0.5833


def cone_radius(z):
    return HUB_BASE_R + dRdZ * z


def blade_cross_section(z_station, twist_angle_deg, blade_h, blade_t, embed):
    """
    Rectangular cross-section wire for blade loft at a given station.

    Protrusion direction: PURE RADIAL (XY plane only).
    This guarantees blade tip is at exactly r_cone + blade_h from Z-axis,
    matching the spec: 15mm protrusion at base, 5mm at top.

    The cross-section rectangle:
      - Radial extent: from (r_cone - embed) to (r_cone + blade_h)
      - Circumferential extent: ±blade_t/2
      - Positioned at angular location twist_angle_deg around Z
    """
    r_cone  = cone_radius(z_station)
    ang_rad = math.radians(twist_angle_deg)

    cos_a = math.cos(ang_rad)
    sin_a = math.sin(ang_rad)

    # Pure radial unit vector (XY only — no Z component)
    rx = cos_a
    ry = sin_a

    # Circumferential tangent unit vector
    tx = -sin_a
    ty =  cos_a

    half_t = blade_t / 2.0

    # 4 corners of the rectangular cross-section:
    # inner edge (embedded into hub) → outer edge (blade tip)
    # along pure radial direction; ±half_t in circumferential direction
    def pt(r_offset, t_offset):
        return cq.Vector(
            r_offset * rx + t_offset * tx,
            r_offset * ry + t_offset * ty,
            z_station
        )

    r_inner = r_cone - embed        # inside hub surface
    r_outer = r_cone + blade_h      # blade tip (radially outward)

    # Slightly wider at inner (embedded) base for clean boolean geometry
    half_t_wide = half_t + embed * 0.2

    p0 = pt(r_inner, -half_t_wide)   # inner, -t
    p1 = pt(r_inner, +half_t_wide)   # inner, +t
    p2 = pt(r_outer, +half_t)        # outer tip, +t
    p3 = pt(r_outer, -half_t)        # outer tip, -t

    wire = cq.Wire.makePolygon([p0, p1, p2, p3, p0])
    return wire


def build_one_blade(start_angle_deg=0.0):
    """
    Build a single blade as a loft through N_STATIONS cross-sections.
    Each section uses pure radial protrusion so blade_h directly
    controls the radial distance from the hub surface.
    """
    wires = []
    for i in range(N_STATIONS):
        t     = i / (N_STATIONS - 1)          # 0 → 1
        z_s   = t * HUB_H                      # 0 → 60 mm
        ang_s = start_angle_deg + t * TWIST_DEG  # accumulates 60° twist
        h_s   = BLADE_H_BOT + t * (BLADE_H_TOP - BLADE_H_BOT)  # 15 → 5 mm

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
# 2. CENTRAL BORE — 15mm diameter through Z axis
# ─────────────────────────────────────────────
bore = (
    cq.Workplane("XY")
    .circle(BORE_D / 2.0)
    .extrude(HUB_H)
)
hub = hub.cut(bore)

# ─────────────────────────────────────────────
# 3. BUILD ALL 7 BLADES AND UNION TO HUB
# Blades embedded EMBED_DEPTH mm into hub radially → watertight boolean
# ─────────────────────────────────────────────
blade_angle_step = 360.0 / N_BLADES   # ≈ 51.43°

result_solid = hub

for i in range(N_BLADES):
    start_angle  = i * blade_angle_step
    blade_solid  = build_one_blade(start_angle_deg=start_angle)
    blade_wp     = cq.Workplane("XY").add(blade_solid)
    result_solid = result_solid.union(blade_wp)

# ─────────────────────────────────────────────
# 4. FINAL CLEAN UP
# ─────────────────────────────────────────────
result_solid = result_solid.clean()