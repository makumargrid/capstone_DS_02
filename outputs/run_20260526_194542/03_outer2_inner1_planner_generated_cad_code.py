import cadquery as cq
import math

# ── Parameters ────────────────────────────────────────────────────────────────
HUB_R_BASE   = 50.0
HUB_R_TOP    = 15.0
HUB_H        = 60.0
BORE_R       = 7.5
NUM_BLADES   = 7
BLADE_T      = 2.2       # slightly over 2mm for DFM safety
BLADE_H_BOT  = 15.0
BLADE_H_TOP  = 5.0
TWIST_DEG    = 60.0
N_SEC        = 18        # number of loft cross-sections
EMBED        = 3.0       # mm blade embeds INTO cone surface

# Cone geometry
dR_dZ = (HUB_R_TOP - HUB_R_BASE) / HUB_H  # = -35/60

# Exact outward unit normal to the cone surface
# Cone: r = R_BASE + dR_dZ * z  →  F = r - R_BASE - dR_dZ*z = 0
# Gradient in (r,z): (1, -dR_dZ), normalized:
mag   = math.sqrt(1.0 + dR_dZ**2)
nR_hat =  1.0 / mag
nZ_hat = -dR_dZ / mag   # positive (pointing upward) because dR_dZ < 0

# ── Helper: build one consistently-wound wire at z_frac ──────────────────────
def make_section_wire(z_frac, base_twist_deg=0.0):
    """
    Returns a cq.Wire (closed quadrilateral) for the blade cross-section
    at fractional height z_frac in [0,1], with an additional base_twist_deg
    rotation for blade instancing.
    All four corners are computed explicitly so winding is always CCW
    when viewed from outside the cone.
    """
    z_val  = z_frac * HUB_H
    r_cone = HUB_R_BASE + dR_dZ * z_val

    # Angle: twist progresses with height; base_twist_deg offsets for each blade
    theta  = math.radians(base_twist_deg + TWIST_DEG * z_frac)

    # Position on cone surface (centre of blade cross-section)
    cx = r_cone * math.cos(theta)
    cy = r_cone * math.sin(theta)
    cz = z_val

    # Tangent unit vector (in-plane, CCW)
    tx = -math.sin(theta)
    ty =  math.cos(theta)
    # tz = 0 always

    # Outward surface normal
    nx = nR_hat * math.cos(theta)
    ny = nR_hat * math.sin(theta)
    nz = nZ_hat

    # Blade protrusion at this station
    h_blade = BLADE_H_BOT + (BLADE_H_TOP - BLADE_H_BOT) * z_frac

    half_t  = BLADE_T / 2.0

    # Base corners: embedded EMBED mm INSIDE the cone (along -normal)
    # This guarantees the blade solid overlaps the hub body
    b0x = cx - half_t*tx - EMBED*nx
    b0y = cy - half_t*ty - EMBED*ny
    b0z = cz              - EMBED*nz

    b1x = cx + half_t*tx - EMBED*nx
    b1y = cy + half_t*ty - EMBED*ny
    b1z = cz              - EMBED*nz

    # Tip corners: protrude h_blade ABOVE cone surface
    t2x = cx + half_t*tx + h_blade*nx
    t2y = cy + half_t*ty + h_blade*ny
    t2z = cz              + h_blade*nz

    t3x = cx - half_t*tx + h_blade*nx
    t3y = cy - half_t*ty + h_blade*ny
    t3z = cz              + h_blade*nz

    # Build wire — always same winding: b0 → b1 → t2 → t3 → b0
    pts = [
        cq.Vector(b0x, b0y, b0z),
        cq.Vector(b1x, b1y, b1z),
        cq.Vector(t2x, t2y, t2z),
        cq.Vector(t3x, t3y, t3z),
        cq.Vector(b0x, b0y, b0z),   # explicitly close
    ]
    edges = [cq.Edge.makeLine(pts[i], pts[i+1]) for i in range(4)]
    return cq.Wire.assembleEdges(edges)

# ── Step 1: Hub frustum ───────────────────────────────────────────────────────
hub = (
    cq.Workplane("XY")
    .circle(HUB_R_BASE)
    .workplane(offset=HUB_H)
    .circle(HUB_R_TOP)
    .loft()
)
hub_solid = hub.val()

# ── Step 2: Central bore ──────────────────────────────────────────────────────
bore = (
    cq.Workplane("XY")
    .workplane(offset=-2.0)
    .circle(BORE_R)
    .extrude(HUB_H + 4.0)
    .val()
)
hub_solid = hub_solid.cut(bore)

# ── Step 3: Build one blade solid (at blade index 0, base_twist = 0°) ────────
z_fracs = [i / (N_SEC - 1) for i in range(N_SEC)]

# Build wire list for blade 0
wires_b0 = [make_section_wire(zf, base_twist_deg=0.0) for zf in z_fracs]

# Loft into a solid — ruled=False for smooth aerodynamic surface
blade0_solid = cq.Solid.makeLoft(wires_b0, ruled=False)

# ── Step 4: Fuse all 7 blades into the hub ────────────────────────────────────
blade_angle_step = 360.0 / NUM_BLADES   # ≈ 51.43°

# Start with the hub
result_cq_solid = hub_solid

for i in range(NUM_BLADES):
    angle_deg = i * blade_angle_step

    # Rotate blade0_solid around Z axis by angle_deg
    blade_i = blade0_solid.rotate(
        cq.Vector(0.0, 0.0, 0.0),
        cq.Vector(0.0, 0.0, 1.0),
        angle_deg
    )

    # Use OpenCASCADE BRep fuse with tolerance for robustness
    try:
        result_cq_solid = result_cq_solid.fuse(blade_i, tolerance=0.05)
    except Exception as e:
        print(f"  Blade {i} fuse failed ({e}), trying union...")
        result_cq_solid = result_cq_solid.fuse(blade_i, tolerance=0.1)

# ── Step 5: Wrap back into Workplane, clean up with small fillet ──────────────
result_solid = cq.Workplane("XY").add(result_cq_solid)

# Attempt a conservative fillet on blade root edges to clean up junction geometry
try:
    result_solid = (
        cq.Workplane("XY")
        .add(result_cq_solid)
        .edges("|Z")
        .fillet(0.5)
    )
except Exception:
    # If edge selection fillet fails, wrap without fillet
    result_solid = cq.Workplane("XY").add(result_cq_solid)

# ── Step 6: Center on XY origin ───────────────────────────────────────────────
bb = result_solid.val().BoundingBox()
cx_offset = -(bb.xmin + bb.xmax) / 2.0
cy_offset = -(bb.ymin + bb.ymax) / 2.0
# Z must stay at 0 base
result_solid = result_solid.translate((cx_offset, cy_offset, 0))

# ── Diagnostics ───────────────────────────────────────────────────────────────
bb2 = result_solid.val().BoundingBox()
print("=== Centrifugal Compressor Impeller ===")
print(f"X span: {bb2.xmin:.2f} → {bb2.xmax:.2f}  ({bb2.xmax - bb2.xmin:.2f} mm)")
print(f"Y span: {bb2.ymin:.2f} → {bb2.ymax:.2f}  ({bb2.ymax - bb2.ymin:.2f} mm)")
print(f"Z span: {bb2.zmin:.2f} → {bb2.zmax:.2f}  ({bb2.zmax - bb2.zmin:.2f} mm)")
print(f"Blades fused: {NUM_BLADES}")
print(f"Blade embed depth: {EMBED} mm")