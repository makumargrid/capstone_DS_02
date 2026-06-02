import cadquery as cq
import math

# ─────────────────────────────────────────────────────────────────
# GLOBAL PARAMETERS (all in mm)
# ─────────────────────────────────────────────────────────────────
HUB_BASE_R   = 50.0    # cone base radius at Z=0
HUB_TOP_R    = 15.0    # cone top  radius at Z=60
HUB_H        = 60.0    # total hub height
BORE_R       = 7.5     # shaft bore radius (15mm diameter)
N_BLADES     = 7       # number of blades
BLADE_TWIST  = 60.0    # total twist in degrees from base to top
BLADE_T      = 2.0     # blade tangential thickness (mm)
BLADE_H_BOT  = 15.0    # radial protrusion at base (mm)
BLADE_H_TOP  = 5.0     # radial protrusion at top  (mm)
N_STATIONS   = 24      # loft cross-section count (more = smoother, safer)
EMBED        = 1.0     # mm embedded into cone surface for watertight union

# ─────────────────────────────────────────────────────────────────
# 1. HUB — truncated cone via profile revolve
# ─────────────────────────────────────────────────────────────────
# Profile drawn in XZ plane (X=radius, Z=height)
# Polyline: base-outer → top-outer → top-center → base-center → close
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

# ─────────────────────────────────────────────────────────────────
# 2. BORE — central cylindrical hole for driveshaft
# ─────────────────────────────────────────────────────────────────
bore = (
    cq.Workplane("XY")
    .workplane(offset=-1.0)      # start 1mm below Z=0
    .circle(BORE_R)
    .extrude(HUB_H + 2.0)        # extend 1mm past top face
)
hub = hub.cut(bore)

# ─────────────────────────────────────────────────────────────────
# 3. BLADE WIRE BUILDER
#    Each cross-section is a flat horizontal rectangle at height z:
#      inner edge : r_cone - EMBED  (dips into hub surface)
#      outer edge : r_cone + h_prot (protrudes radially outward)
#      width      : BLADE_T (tangential, 2mm)
# ─────────────────────────────────────────────────────────────────
def make_blade_wire(z_frac, blade_rot_rad):
    z_pos   = z_frac * HUB_H
    r_cone  = HUB_BASE_R  + (HUB_TOP_R  - HUB_BASE_R)  * z_frac   # linear taper
    h_prot  = BLADE_H_BOT + (BLADE_H_TOP - BLADE_H_BOT) * z_frac   # linear taper

    theta   = math.radians(BLADE_TWIST * z_frac) + blade_rot_rad

    r_inner = max(r_cone - EMBED, BORE_R + 1.0)
    r_outer = r_cone + h_prot

    ht = BLADE_T / 2.0

    cos_t   =  math.cos(theta)
    sin_t   =  math.sin(theta)
    # tangential unit vector (CCW 90° from radial)
    tan_cos = -math.sin(theta)
    tan_sin =  math.cos(theta)

    # Four corners — flat rectangle at z_pos
    p0 = cq.Vector(r_inner*cos_t + ht*tan_cos,  r_inner*sin_t + ht*tan_sin,  z_pos)
    p1 = cq.Vector(r_inner*cos_t - ht*tan_cos,  r_inner*sin_t - ht*tan_sin,  z_pos)
    p2 = cq.Vector(r_outer*cos_t - ht*tan_cos,  r_outer*sin_t - ht*tan_sin,  z_pos)
    p3 = cq.Vector(r_outer*cos_t + ht*tan_cos,  r_outer*sin_t + ht*tan_sin,  z_pos)

    edges = [
        cq.Edge.makeLine(p0, p1),
        cq.Edge.makeLine(p1, p2),
        cq.Edge.makeLine(p2, p3),
        cq.Edge.makeLine(p3, p0),
    ]
    return cq.Wire.assembleEdges(edges)

# ─────────────────────────────────────────────────────────────────
# 4. BUILD BLADES AND UNION WITH HUB
# ─────────────────────────────────────────────────────────────────
result_solid = hub

angle_step_rad = 2.0 * math.pi / float(N_BLADES)

for k in range(N_BLADES):
    blade_rot = k * angle_step_rad

    # Collect loft cross-section wires
    wire_list = []
    for i in range(N_STATIONS + 1):
        frac = float(i) / float(N_STATIONS)
        w = make_blade_wire(frac, blade_rot)
        wire_list.append(w)

    # Build loft solid (ruled=True → linear ruled surface, avoids OCC smoothing artifacts)
    blade_solid = cq.Solid.makeLoft(wire_list, ruled=True)

    # Wrap in Workplane for boolean union
    blade_wp = cq.Workplane("XY").add(blade_solid)
    result_solid = result_solid.union(blade_wp)