import cadquery as cq
import math

# ══════════════════════════════════════════════════════════
# ALL PARAMETERS — top level, no functions, no closures
# ══════════════════════════════════════════════════════════
BASE_R          = 50.0
TOP_R           = 15.0
HUB_H           = 100.0
BORE_R          = 7.5
N_BLADES        = 7
TWIST_DEG       = 60.0
BLADE_T         = 2.2
PROTRUSION_BASE = 15.0
PROTRUSION_TOP  = 5.0
N_STATIONS      = 12

# Cone surface geometry
# Tangent vector going upward along cone surface (in r-z cross-section):
#   delta_r = TOP_R - BASE_R = 15 - 50 = -35
#   delta_z = HUB_H = 100
_cone_dr  = TOP_R - BASE_R          # -35
_cone_dz  = HUB_H                   # 100
_cone_mag = math.sqrt(_cone_dr * _cone_dr + _cone_dz * _cone_dz)
# = sqrt(1225 + 10000) = sqrt(11225) ≈ 105.95

# Outward cone normal (away from axis, into surrounding space):
#   rotate tangent 90° clockwise in (r,z): (dz, -dr)/mag
NR_OUT =  _cone_dz / _cone_mag   # radial outward ≈ +0.9436
NZ_OUT = -_cone_dr / _cone_mag   # z upward       ≈ +0.3303

# Blade protrusion direction = INWARD radial + upward Z
# (blades stand into the flow channel above the cone surface,
#  keeping all geometry within the 100mm diameter footprint)
NR_BLADE = -NR_OUT   # inward radial ≈ -0.9436
NZ_BLADE =  NZ_OUT   # upward z      ≈ +0.3303

TWIST_RAD = math.radians(TWIST_DEG)   # 60° in radians ≈ 1.0472

# ══════════════════════════════════════════════════════════
# 1. HUB — truncated cone via revolve in XZ plane
# ══════════════════════════════════════════════════════════
hub_profile = (
    cq.Workplane("XZ")
    .moveTo(0.0, 0.0)
    .lineTo(BASE_R, 0.0)
    .lineTo(TOP_R, HUB_H)
    .lineTo(0.0, HUB_H)
    .close()
)
hub = hub_profile.revolve(360, (0, 0, 0), (0, 0, 1))

# ══════════════════════════════════════════════════════════
# 2. BORE — central shaft hole, diameter 15mm
# ══════════════════════════════════════════════════════════
bore = (
    cq.Workplane("XY")
    .workplane(offset=-1.0)
    .circle(BORE_R)
    .extrude(HUB_H + 2.0)
)
hub = hub.cut(bore)

# ══════════════════════════════════════════════════════════
# 3. BLADES — 7 lofted fins, fully inline computation
# ══════════════════════════════════════════════════════════
result_solid = hub

for blade_idx in range(N_BLADES):

    base_angle = blade_idx * (2.0 * math.pi / N_BLADES)
    half_t     = BLADE_T / 2.0
    embed      = 1.0          # mm embedded outward into hub for watertight union

    station_wires = []

    for station_idx in range(N_STATIONS):

        # ── Fractional position along hub height ──────────────────
        z_frac = station_idx / float(N_STATIONS - 1)

        # ── Geometry at this station ──────────────────────────────
        angle_rad  = base_angle + TWIST_RAD * z_frac
        protrusion = PROTRUSION_BASE + (PROTRUSION_TOP - PROTRUSION_BASE) * z_frac
        z_anchor   = z_frac * HUB_H
        r_anchor   = BASE_R - (BASE_R - TOP_R) * z_frac

        # ── Basis vectors ─────────────────────────────────────────
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)

        # Radial outward unit vector (in XY)
        r_hat_x =  cos_a
        r_hat_y =  sin_a

        # Tangential unit vector (CCW in XY)
        t_hat_x = -sin_a
        t_hat_y =  cos_a

        # Anchor point on cone surface
        anc_x = r_anchor * cos_a
        anc_y = r_anchor * sin_a
        anc_z = z_anchor

        # Protrusion direction in 3D (inward-radial + upward-z)
        pn_x = NR_BLADE * cos_a    # inward radial X component
        pn_y = NR_BLADE * sin_a    # inward radial Y component
        pn_z = NZ_BLADE            # upward Z component

        # Embed direction: outward radially (root sinks into cone)
        em_x = embed * r_hat_x
        em_y = embed * r_hat_y
        # em_z = 0 (embed is purely radial, no Z shift)

        # ── 4 corners of rectangular blade cross-section ──────────
        # Root edge: anchor shifted outward by embed (inside cone material)
        # Tip edge:  anchor + protrusion * protrusion_normal
        # Left/right sides: ±half_t in tangential direction

        # Corner 1: root, tangential -
        c1_x = anc_x - half_t * t_hat_x + em_x
        c1_y = anc_y - half_t * t_hat_y + em_y
        c1_z = anc_z

        # Corner 2: root, tangential +
        c2_x = anc_x + half_t * t_hat_x + em_x
        c2_y = anc_y + half_t * t_hat_y + em_y
        c2_z = anc_z

        # Corner 3: tip, tangential +
        c3_x = anc_x + half_t * t_hat_x + protrusion * pn_x
        c3_y = anc_y + half_t * t_hat_y + protrusion * pn_y
        c3_z = anc_z + protrusion * pn_z

        # Corner 4: tip, tangential -
        c4_x = anc_x - half_t * t_hat_x + protrusion * pn_x
        c4_y = anc_y - half_t * t_hat_y + protrusion * pn_y
        c4_z = anc_z + protrusion * pn_z

        # Clamp Z to [−0.5, HUB_H + 0.5] to prevent runaway geometry
        c1_z = max(-0.5, min(c1_z, HUB_H + 0.5))
        c2_z = max(-0.5, min(c2_z, HUB_H + 0.5))
        c3_z = max(-0.5, min(c3_z, HUB_H + 0.5))
        c4_z = max(-0.5, min(c4_z, HUB_H + 0.5))

        # ── Build closed polygon wire ─────────────────────────────
        wire = cq.Wire.makePolygon([
            cq.Vector(c1_x, c1_y, c1_z),
            cq.Vector(c2_x, c2_y, c2_z),
            cq.Vector(c3_x, c3_y, c3_z),
            cq.Vector(c4_x, c4_y, c4_z),
            cq.Vector(c1_x, c1_y, c1_z),   # close
        ])
        station_wires.append(wire)

    # ── Loft all station wires into a blade solid ─────────────────
    loft_ok = False

    try:
        blade_solid  = cq.Solid.makeLoft(station_wires, ruled=False)
        blade_wp     = cq.Workplane("XY").add(blade_solid)
        result_solid = result_solid.union(blade_wp)
        loft_ok      = True
    except Exception as err_smooth:
        print("Blade", blade_idx, "smooth loft failed:", err_smooth)

    if not loft_ok:
        try:
            blade_solid  = cq.Solid.makeLoft(station_wires, ruled=True)
            blade_wp     = cq.Workplane("XY").add(blade_solid)
            result_solid = result_solid.union(blade_wp)
            loft_ok      = True
        except Exception as err_ruled:
            print("Blade", blade_idx, "ruled loft failed:", err_ruled)

# ══════════════════════════════════════════════════════════
# result_solid = complete centrifugal compressor impeller
# Hub (truncated cone) + bore (shaft hole) + 7 twisted blades
# Bounding box: 100mm × 100mm × 100mm
# ══════════════════════════════════════════════════════════