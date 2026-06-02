import cadquery as cq
import math

# ─────────────────────────────────────────────
# PARAMETERS
# ─────────────────────────────────────────────
HUB_BASE_R   = 50.0   # radius at Z=0
HUB_TOP_R    = 15.0   # radius at Z=60
HUB_H        = 60.0   # hub height
BORE_D       = 15.0   # central bore diameter
N_BLADES     = 7
BLADE_T      = 2.5    # blade thickness (mm) — slightly above 2mm for DFM safety
BLADE_H_BOT  = 15.0   # protrusion at base
BLADE_H_TOP  = 5.0    # protrusion at top
TWIST_DEG    = 60.0   # total angular twist bottom→top
N_STATIONS   = 10     # loft cross-section stations

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
# 3. BLADE CONSTRUCTION
# ─────────────────────────────────────────────
# Helper: cone surface normal direction at a given Z
# The cone half-angle:  tan(alpha) = (HUB_BASE_R - HUB_TOP_R) / HUB_H
# Normal to cone surface in the RZ plane points outward+upward:
#   nr = cos(alpha),  nz = sin(alpha)   (outward from axis in R direction tilted up)
# Actually the outward normal to a cone surface:
#   surface tangent in Z direction: dR/dZ = (TOP_R - BASE_R)/H  (negative, cone narrows)
#   unit tangent = (dR/dZ, 1) normalised → (-35/60, 1) normalised
#   outward normal = (1, 35/60) normalised  (rotated 90° outward)

dRdZ = (HUB_TOP_R - HUB_BASE_R) / HUB_H          # negative value: -35/60
# Surface tangent in RZ plane (unit): (dRdZ, 1) / |...|
tang_len = math.sqrt(dRdZ**2 + 1.0)
# Outward normal to cone surface in RZ plane:
# rotate tangent (dRdZ, 1) by -90°: (1, -dRdZ) / tang_len  → points outward
norm_r_unit = 1.0 / tang_len          #  positive, outward radial component
norm_z_unit = -dRdZ / tang_len        #  positive (upward), because dRdZ is negative


def cone_radius(z):
    """Cone surface radius at height z."""
    return HUB_BASE_R + dRdZ * z


def blade_cross_section(z_station, twist_angle_deg, blade_h, blade_t):
    """
    Returns a CadQuery Wire representing a rectangular blade cross-section
    at a given station.

    The rectangle is centred on the cone surface point, oriented so that:
      - The 'height' direction follows the cone outward normal (radially outward + tilted)
      - The 'thickness' direction is tangential (circumferential)

    Parameters
    ----------
    z_station      : Z height of the station
    twist_angle_deg: cumulative angular rotation around Z at this station
    blade_h        : blade protrusion height off the cone surface at this station
    blade_t        : blade thickness
    """
    r_cone = cone_radius(z_station)
    ang_rad = math.radians(twist_angle_deg)

    # Centre point ON the cone surface
    cx = r_cone * math.cos(ang_rad)
    cy = r_cone * math.sin(ang_rad)
    cz = z_station

    # Outward normal to cone in 3D (in the radial plane at this angle)
    nx = norm_r_unit * math.cos(ang_rad)
    ny = norm_r_unit * math.sin(ang_rad)
    nz = norm_z_unit

    # Tangent direction (circumferential, perpendicular to radial in XY)
    tx = -math.sin(ang_rad)
    ty =  math.cos(ang_rad)
    tz = 0.0

    # Rectangle corners (blade bottom edge sits ON the cone surface):
    # We place the rectangle so its base is at the cone surface,
    # extending outward by blade_h in the normal direction.
    # Thickness is ±blade_t/2 in tangential direction.
    half_t = blade_t / 2.0

    # 4 corners:
    #  bottom-left, bottom-right, top-right, top-left
    def pt(n_scale, t_scale):
        return cq.Vector(
            cx + n_scale * nx + t_scale * tx,
            cy + n_scale * ny + t_scale * ty,
            cz + n_scale * nz
        )

    p0 = pt(0.0,      -half_t)   # base, -t side
    p1 = pt(0.0,      +half_t)   # base, +t side
    p2 = pt(blade_h,  +half_t)   # tip,  +t side
    p3 = pt(blade_h,  -half_t)   # tip,  -t side

    # Build a closed wire from these 4 points
    wire = (
        cq.Wire.makePolygon([p0, p1, p2, p3, p0])
    )
    return wire


def build_one_blade(start_angle_deg=0.0):
    """Build a single blade as a loft through N_STATIONS cross-sections."""
    wires = []
    for i in range(N_STATIONS):
        t = i / (N_STATIONS - 1)           # 0 → 1
        z_s    = t * HUB_H                 # 0 → 60
        ang_s  = start_angle_deg + t * TWIST_DEG
        h_s    = BLADE_H_BOT + t * (BLADE_H_TOP - BLADE_H_BOT)  # 15 → 5

        w = blade_cross_section(z_s, ang_s, h_s, BLADE_T)
        wires.append(w)

    # Use CadQuery Shell / Loft via the Workplane API
    # We build the loft from a list of wires using cq.Solid.makeLoft
    blade_solid = cq.Solid.makeLoft(wires, ruled=False)
    return blade_solid


# ─────────────────────────────────────────────
# 4. BUILD ALL 7 BLADES AND FUSE TO HUB
# ─────────────────────────────────────────────
blade_angle_step = 360.0 / N_BLADES   # ~51.43°

result_solid = hub

for i in range(N_BLADES):
    start_angle = i * blade_angle_step
    blade = build_one_blade(start_angle_deg=start_angle)

    # Wrap in a Workplane shape for boolean
    blade_wp = cq.Workplane("XY").add(blade)

    # Fuse blade into the accumulating solid
    result_solid = result_solid.union(blade_wp)

# ─────────────────────────────────────────────
# 5. FINAL CLEAN-UP — ensure single solid
# ─────────────────────────────────────────────
result_solid = result_solid.clean()