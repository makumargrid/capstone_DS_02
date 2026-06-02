import cadquery as cq
import math

# ══════════════════════════════════════════════
# ALL PARAMETERS — plain Python floats only
# ══════════════════════════════════════════════
hub_base_r   = 50.0    # cone base radius at Z=0  (mm)
hub_top_r    = 15.0    # cone top radius at Z=60  (mm)
hub_h        = 60.0    # hub total height          (mm)
bore_r       = 7.5     # shaft bore radius         (mm) → 15mm diameter
n_blades     = 7       # number of blades
twist_deg    = 60.0    # total blade twist         (degrees)
blade_t      = 3.2     # blade tangential thickness (mm) — increased for DFM
blade_h_bot  = 15.0    # radial protrusion at base (mm) — restored to spec
blade_h_top  = 5.0     # radial protrusion at top  (mm) — restored to spec
n_stations   = 24      # loft cross-section count
embed        = 2.0     # mm blade embeds into hub surface (watertight junction)

# ── Derived constants ──────────────────────────
bore_cyl_h      = 64.0    # bore cylinder height (hub_h + 2mm overcut each end)
bore_cyl_z      = -2.0    # bore cylinder starts 2mm below Z=0
twist_rad       = math.radians(twist_deg)   # 60° in radians = 1.0472 rad
angle_step_rad  = 2.0 * math.pi / n_blades  # 51.4286° in radians

# Pre-compute 7 blade base angles explicitly (avoids any loop arithmetic ambiguity)
blade_angles = [k * angle_step_rad for k in range(n_blades)]

# ══════════════════════════════════════════════
# 1. HUB — truncated cone via revolve
#    Profile in XZ plane: X=radius, Z=height
#    Points: base-outer → top-outer → top-axis → base-axis → close
# ══════════════════════════════════════════════
hub_profile_pts = [
    (hub_base_r,  0.0),
    (hub_top_r,   hub_h),
    (0.0,         hub_h),
    (0.0,         0.0),
]

hub_wp = cq.Workplane("XZ")
hub_wp = hub_wp.polyline(hub_profile_pts)
hub_wp = hub_wp.close()
hub_solid = hub_wp.revolve(360, (0, 0, 0), (0, 1, 0))

# ══════════════════════════════════════════════
# 2. BLADE CROSS-SECTION WIRE BUILDER
#
#    At each Z station, the cross-section is a flat horizontal rectangle:
#      • inner radius = r_cone - embed  (dips into hub for watertight union)
#      • outer radius = r_cone + h_prot (protrudes radially outward)
#      • tangential half-width = blade_t / 2
#    The rectangle lies flat in the horizontal plane at z_pos.
#    Angular position = (twist * z_frac) + blade_base_angle
#
#    All geometry variables are passed as default-arg locals to
#    guarantee no runtime global-name lookup failures.
# ══════════════════════════════════════════════
def make_blade_wire(z_frac, base_angle_rad,
                    _hub_base_r  = hub_base_r,
                    _hub_top_r   = hub_top_r,
                    _hub_h       = hub_h,
                    _blade_h_bot = blade_h_bot,
                    _blade_h_top = blade_h_top,
                    _blade_t     = blade_t,
                    _embed       = embed,
                    _bore_r      = bore_r,
                    _twist_rad   = twist_rad):

    # ── Interpolated geometry at this station ──
    z_pos  = z_frac * _hub_h
    r_cone = _hub_base_r + (_hub_top_r - _hub_base_r) * z_frac    # linear cone taper
    h_prot = _blade_h_bot + (_blade_h_top - _blade_h_bot) * z_frac # linear protrusion taper

    # Angular position: twist accumulates from base_angle_rad
    theta  = _twist_rad * z_frac + base_angle_rad

    # Radial bounds
    r_inner = r_cone - _embed
    min_inner = _bore_r + 1.5          # never intrude into bore
    if r_inner < min_inner:
        r_inner = min_inner
    r_outer = r_cone + h_prot

    # Tangential half-width
    ht = _blade_t * 0.5

    # Unit vectors
    cos_t   =  math.cos(theta)
    sin_t   =  math.sin(theta)
    # Tangential = 90° CCW from radial
    tan_c   = -math.sin(theta)
    tan_s   =  math.cos(theta)

    # Four corners: inner-left, inner-right, outer-right, outer-left
    p0 = cq.Vector( r_inner*cos_t + ht*tan_c,  r_inner*sin_t + ht*tan_s,  z_pos )
    p1 = cq.Vector( r_inner*cos_t - ht*tan_c,  r_inner*sin_t - ht*tan_s,  z_pos )
    p2 = cq.Vector( r_outer*cos_t - ht*tan_c,  r_outer*sin_t - ht*tan_s,  z_pos )
    p3 = cq.Vector( r_outer*cos_t + ht*tan_c,  r_outer*sin_t + ht*tan_s,  z_pos )

    edges = [
        cq.Edge.makeLine(p0, p1),
        cq.Edge.makeLine(p1, p2),
        cq.Edge.makeLine(p2, p3),
        cq.Edge.makeLine(p3, p0),
    ]
    return cq.Wire.assembleEdges(edges)


# ══════════════════════════════════════════════
# 3. BUILD ALL 7 BLADES AND UNION WITH HUB
#    (bore is NOT cut yet — done last)
# ══════════════════════════════════════════════
result_solid = hub_solid

for k in range(n_blades):
    base_ang = blade_angles[k]   # exact pre-computed angle for blade k

    # Build wire list: n_stations+1 cross-sections from Z=0 to Z=hub_h
    wire_list = []
    for i in range(n_stations + 1):
        frac = float(i) / float(n_stations)
        w = make_blade_wire(frac, base_ang)
        wire_list.append(w)

    # Loft the blade solid
    # ruled=True: linear ruled surface — avoids OCC smoothing self-intersections
    blade_solid = cq.Solid.makeLoft(wire_list, ruled=True)

    # Union blade into main solid
    blade_wp     = cq.Workplane("XY").add(blade_solid)
    result_solid = result_solid.union(blade_wp)


# ══════════════════════════════════════════════
# 4. BORE — cut LAST to guarantee true through-hole
#    Cylinder: radius=7.5mm, from Z=-2 to Z=62 (overcut both ends)
#    Built at Z=0, then translated down by 2mm
# ══════════════════════════════════════════════
bore_wp     = cq.Workplane("XY")
bore_wp     = bore_wp.circle(bore_r)
bore_wp     = bore_wp.extrude(bore_cyl_h)
bore_solid  = bore_wp.translate((0.0, 0.0, bore_cyl_z))

result_solid = result_solid.cut(bore_solid)