import cadquery as cq
import math

# ─────────────────────────────────────────────
# PARAMETERS
# ─────────────────────────────────────────────
BASE_R       = 50.0      # hub base radius at Z=0
TOP_R        = 15.0      # hub top  radius at Z=60
HUB_H        = 60.0      # hub height
BORE_R       = 7.5       # central bore radius
N_BLADES     = 7
TWIST_DEG    = 60.0      # total twist from Z=0 to Z=HUB_H
BLADE_T      = 2.2       # blade thickness (tangential) – slightly over 2mm for safety
PROTRUSION_BASE = 15.0   # blade height off hub at Z=0
PROTRUSION_TOP  =  5.0   # blade height off hub at Z=HUB_H
N_STATIONS   = 10        # number of loft cross-sections per blade

# Cone half-angle (from vertical / Z axis)
# slope in XY per unit Z
CONE_SLOPE   = (BASE_R - TOP_R) / HUB_H   # = 35/60

# ─────────────────────────────────────────────
# 1. HUB – truncated cone via revolve
# ─────────────────────────────────────────────
hub_profile = (
    cq.Workplane("XZ")
    .moveTo(0, 0)
    .lineTo(BASE_R, 0)
    .lineTo(TOP_R, HUB_H)
    .lineTo(0, HUB_H)
    .close()
)
hub = hub_profile.revolve(360, (0, 0, 0), (0, 0, 1))

# ─────────────────────────────────────────────
# 2. BORE – subtract central cylinder
# ─────────────────────────────────────────────
bore = (
    cq.Workplane("XY")
    .workplane(offset=-1.0)
    .circle(BORE_R)
    .extrude(HUB_H + 2.0)
)
hub = hub.cut(bore)

# ─────────────────────────────────────────────
# 3. BLADE HELPER FUNCTIONS
# ─────────────────────────────────────────────

def cone_surface_normal(slope):
    """
    Unit outward normal to the cone lateral surface.
    The cone surface makes angle alpha with the horizontal plane,
    where tan(alpha_from_vertical) = slope.
    Normal (in 2D cross-section, r-z plane) is perpendicular to surface tangent.
    Surface tangent direction (going upward): (dr/ds, dz/ds)
    dr/ds = -slope/sqrt(1+slope^2)  [negative because r decreases going up]
    Wait – let's be explicit:
    Going from base to top: delta_r = -35, delta_z = +60.
    Tangent vector (unit): t = (-35, 60) / sqrt(35^2+60^2) normalised
    Outward normal (rotated 90° clockwise from tangent in r-z plane):
    n = (60, 35) / sqrt(35^2+60^2)   [pointing outward and upward]
    """
    dr = -(BASE_R - TOP_R)   # -35
    dz = HUB_H               # 60
    mag = math.sqrt(dr**2 + dz**2)
    # outward normal in (r, z) plane:  rotate tangent 90° clockwise
    # tangent = (dr, dz)/mag → normal_outward = (dz, -dr)/mag
    nr = dz / mag    # radial component of outward normal
    nz = -dr / mag   # z component (positive, pointing slightly up)
    return nr, nz

NR, NZ = cone_surface_normal(CONE_SLOPE)

def blade_station(z_frac, blade_angle_rad, protrusion):
    """
    Return a CadQuery Workplane wire (closed rectangle profile) for one
    blade cross-section at fractional height z_frac ∈ [0,1].

    The profile rectangle:
      - 'height' = protrusion (along outward cone normal)
      - 'width'  = BLADE_T   (along tangential direction, perpendicular to radial in XY)

    The workplane origin is placed at the hub surface point.
    The workplane normal is the outward cone surface normal at that point.
    """
    z     = z_frac * HUB_H
    r_hub = BASE_R - (BASE_R - TOP_R) * z_frac   # radius at this height

    # Hub surface point
    cx = r_hub * math.cos(blade_angle_rad)
    cy = r_hub * math.sin(blade_angle_rad)
    cz = z

    # Outward normal vector of cone in 3D (NR is radial component)
    nx = NR * math.cos(blade_angle_rad)
    ny = NR * math.sin(blade_angle_rad)
    nz = NZ

    # Tangential direction in XY plane (perpendicular to radial, unit vector)
    tx = -math.sin(blade_angle_rad)
    ty =  math.cos(blade_angle_rad)
    tz = 0.0

    # The blade profile rectangle:
    # We place it so it starts at the hub surface (embed 0.5mm inside for clean union)
    # and extends outward by `protrusion`.
    # Rectangle corners in local (tangential, normal) space:
    # local_t ∈ [-BLADE_T/2, +BLADE_T/2]
    # local_n ∈ [-0.5, protrusion]  (-0.5 embeds into hub surface)

    half_t  = BLADE_T / 2.0
    embed   = 1.0          # mm embedded into hub for clean boolean
    n_start = -embed
    n_end   = protrusion

    # 4 corners in 3D:
    def corner(lt, ln):
        x = cx + lt*tx + ln*nx
        y = cy + lt*ty + ln*ny
        z_ = cz + lt*tz + ln*nz
        return (x, y, z_)

    p1 = corner(-half_t, n_start)
    p2 = corner(+half_t, n_start)
    p3 = corner(+half_t, n_end)
    p4 = corner(-half_t, n_end)

    return [p1, p2, p3, p4]


def make_blade(blade_index):
    """Build one blade as a lofted solid and return it."""
    base_angle = blade_index * (2.0 * math.pi / N_BLADES)
    twist_rad  = math.radians(TWIST_DEG)

    # Collect all station wires
    wires = []
    for i in range(N_STATIONS):
        z_frac = i / (N_STATIONS - 1)
        angle  = base_angle + twist_rad * z_frac
        prot   = PROTRUSION_BASE + (PROTRUSION_TOP - PROTRUSION_BASE) * z_frac

        corners = blade_station(z_frac, angle, prot)

        # Build a closed polygon wire from the 4 corners
        p1, p2, p3, p4 = corners
        wire = (
            cq.Wire.makePolygon([
                cq.Vector(*p1),
                cq.Vector(*p2),
                cq.Vector(*p3),
                cq.Vector(*p4),
                cq.Vector(*p1),   # close
            ])
        )
        wires.append(wire)

    # Loft through all wires
    blade_solid = cq.Solid.makeLoft(wires, ruled=False)
    return blade_solid


# ─────────────────────────────────────────────
# 4. BUILD ALL BLADES & UNION WITH HUB
# ─────────────────────────────────────────────
result_solid = hub

for b in range(N_BLADES):
    blade = make_blade(b)
    blade_wp = cq.Workplane("XY").add(blade)
    result_solid = result_solid.union(blade_wp)