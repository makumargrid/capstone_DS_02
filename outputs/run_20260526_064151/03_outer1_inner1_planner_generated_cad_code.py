import cadquery as cq
import math

# ─────────────────────────────────────────────
# PARAMETERS
# ─────────────────────────────────────────────
HUB_BASE_R   = 50.0    # mm, radius at Z=0
HUB_TOP_R    = 15.0    # mm, radius at Z=60
HUB_H        = 60.0    # mm, total height
BORE_R       = 7.5     # mm, shaft bore radius
N_BLADES     = 7
BLADE_TWIST  = 60.0    # degrees, total angular sweep
BLADE_T      = 2.0     # mm, blade thickness (tangential)
BLADE_H_BOT  = 15.0    # mm, protrusion at base
BLADE_H_TOP  = 5.0     # mm, protrusion at top
N_STATIONS   = 10      # loft cross-section count

# Cone geometry
# Slant: from (50,0) at Z=0 to (15,0) at Z=60
# Half-angle from vertical axis:
#   delta_r = 50-15 = 35, delta_z = 60
#   alpha = atan(35/60)
cone_alpha = math.atan2(HUB_BASE_R - HUB_TOP_R, HUB_H)  # ~30.26 deg

# Outward normal to cone surface (in the local radial-Z plane):
#   The slant direction (up the cone surface) = (−sin(alpha), +cos(alpha)) in (r,z)
#   The outward normal = (+cos(alpha), +sin(alpha)) in (r,z)
#   i.e., normal_r =  cos(alpha), normal_z = sin(alpha)
norm_r = math.cos(cone_alpha)
norm_z = math.sin(cone_alpha)

# ─────────────────────────────────────────────
# 1. HUB (Truncated Cone via revolve)
# ─────────────────────────────────────────────
hub = (
    cq.Workplane("XZ")
    .polyline([
        (HUB_BASE_R, 0),
        (HUB_TOP_R,  HUB_H),
        (0,          HUB_H),
        (0,          0),
        (HUB_BASE_R, 0),
    ])
    .close()
    .revolve(360, (0, 0, 0), (0, 1, 0))
)

# ─────────────────────────────────────────────
# 2. BORE (subtract central cylinder)
# ─────────────────────────────────────────────
bore_cyl = (
    cq.Workplane("XY")
    .circle(BORE_R)
    .extrude(HUB_H + 2)
    .translate((0, 0, -1))
)
hub = hub.cut(bore_cyl)

# ─────────────────────────────────────────────
# HELPER: build one blade wire at a given Z station
# Returns a cq.Wire (closed rectangle) in 3D space
# ─────────────────────────────────────────────
def blade_wire_at_station(z_frac):
    """
    z_frac: 0.0 (base) to 1.0 (top)
    Returns a closed Wire representing the blade cross-section at this station.
    """
    z      = z_frac * HUB_H
    # Cone radius at this Z
    r_cone = HUB_BASE_R - (HUB_BASE_R - HUB_TOP_R) * z_frac
    # Blade protrusion off cone surface
    h_prot = BLADE_H_BOT + (BLADE_H_TOP - BLADE_H_BOT) * z_frac
    # Angular position (twist) — blade 0, others rotated later
    theta  = math.radians(BLADE_TWIST * z_frac)

    # Unit vectors in 3D for blade profile construction:
    # radial direction (outward in XY at angle theta):
    rad_x  = math.cos(theta)
    rad_y  = math.sin(theta)
    # tangential direction (90° CCW from radial in XY):
    tan_x  = -math.sin(theta)
    tan_y  =  math.cos(theta)
    # outward normal to cone surface:
    #   = norm_r * radial + norm_z * Z-hat
    out_x  = norm_r * rad_x
    out_y  = norm_r * rad_y
    out_z  = norm_z

    # Center point on cone surface
    cx = r_cone * rad_x
    cy = r_cone * rad_y
    cz = z

    # Half-thickness in tangential direction
    ht = BLADE_T / 2.0

    # Four corners of the blade cross-section rectangle:
    # ± ht along tangential, 0 and h_prot along outward normal
    corners = [
        (cx + ht*tan_x,          cy + ht*tan_y,          cz),
        (cx - ht*tan_x,          cy - ht*tan_y,          cz),
        (cx - ht*tan_x + h_prot*out_x, cy - ht*tan_y + h_prot*out_y, cz + h_prot*out_z),
        (cx + ht*tan_x + h_prot*out_x, cy + ht*tan_y + h_prot*out_y, cz + h_prot*out_z),
    ]

    # Build OCC wire from corners
    verts = [cq.Vector(*c) for c in corners]
    edges = [
        cq.Edge.makeLine(verts[0], verts[1]),
        cq.Edge.makeLine(verts[1], verts[2]),
        cq.Edge.makeLine(verts[2], verts[3]),
        cq.Edge.makeLine(verts[3], verts[0]),
    ]
    wire = cq.Wire.assembleEdges(edges)
    return wire


def build_blade():
    """Build a single blade solid by lofting cross-sections along the hub surface."""
    wires = []
    for i in range(N_STATIONS + 1):
        z_frac = i / N_STATIONS
        wires.append(blade_wire_at_station(z_frac))

    blade_solid = cq.Solid.makeLoft(wires, ruled=False)
    return blade_solid


# ─────────────────────────────────────────────
# 3. BUILD & PLACE ALL 7 BLADES
# ─────────────────────────────────────────────
blade_angle_step = 360.0 / N_BLADES

result_solid = hub

for k in range(N_BLADES):
    rotation_deg = k * blade_angle_step
    rotation_rad = math.radians(rotation_deg)

    # Build fresh wires for this blade (rotated around Z-axis)
    wires = []
    for i in range(N_STATIONS + 1):
        z_frac = i / N_STATIONS

        z      = z_frac * HUB_H
        r_cone = HUB_BASE_R - (HUB_BASE_R - HUB_TOP_R) * z_frac
        h_prot = BLADE_H_BOT + (BLADE_H_TOP - BLADE_H_BOT) * z_frac

        # Base twist for aerodynamic shape + rotation for this blade index
        theta  = math.radians(BLADE_TWIST * z_frac) + rotation_rad

        rad_x  = math.cos(theta)
        rad_y  = math.sin(theta)
        tan_x  = -math.sin(theta)
        tan_y  =  math.cos(theta)
        out_x  = norm_r * rad_x
        out_y  = norm_r * rad_y
        out_z  = norm_z

        cx = r_cone * rad_x
        cy = r_cone * rad_y
        cz = z

        ht = BLADE_T / 2.0

        corners = [
            (cx + ht*tan_x,                      cy + ht*tan_y,                      cz),
            (cx - ht*tan_x,                      cy - ht*tan_y,                      cz),
            (cx - ht*tan_x + h_prot*out_x,       cy - ht*tan_y + h_prot*out_y,       cz + h_prot*out_z),
            (cx + ht*tan_x + h_prot*out_x,       cy + ht*tan_y + h_prot*out_y,       cz + h_prot*out_z),
        ]

        verts = [cq.Vector(*c) for c in corners]
        edges = [
            cq.Edge.makeLine(verts[0], verts[1]),
            cq.Edge.makeLine(verts[1], verts[2]),
            cq.Edge.makeLine(verts[2], verts[3]),
            cq.Edge.makeLine(verts[3], verts[0]),
        ]
        wire = cq.Wire.assembleEdges(edges)
        wires.append(wire)

    blade_solid = cq.Solid.makeLoft(wires, ruled=False)
    blade_wp    = cq.Workplane("XY").add(blade_solid)
    result_solid = result_solid.union(blade_wp)