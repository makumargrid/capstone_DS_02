import cadquery as cq
import math

# ── Parameters ────────────────────────────────────────────────────────────────
HUB_R_BASE   = 50.0      # base radius at Z=0  (diameter 100mm)
HUB_R_TOP    = 15.0      # top radius  at Z=60 (diameter  30mm)
HUB_H        = 60.0      # hub height mm
BORE_R       = 7.5       # central bore radius (diameter 15mm)
NUM_BLADES   = 7
BLADE_T      = 2.8       # blade thickness mm (≥2.5mm DFM floor)
BLADE_H_BOT  = 15.0      # blade protrusion at base (mm, normal to cone)
BLADE_H_TOP  = 5.0       # blade protrusion at top  (mm, normal to cone)
TWIST_DEG    = 60.0      # total CCW twist degrees from Z=0 to Z=60
N_SEC        = 24        # number of loft cross-sections per blade
EMBED        = 4.5       # mm blade embeds INTO cone surface (along -normal)

# Blade z_frac range — slightly beyond [0,1] so blade ends are buried
# inside the hub body, not coincident with hub top/bottom faces
Z_FRAC_MIN   = -0.06     # ~3.6mm below Z=0
Z_FRAC_MAX   =  1.06     # ~3.6mm above Z=60

# ── Cone geometry ─────────────────────────────────────────────────────────────
# Radius at height z: r(z) = HUB_R_BASE + dR_dZ * z
dR_dZ = (HUB_R_TOP - HUB_R_BASE) / HUB_H   # = -35/60 ≈ -0.58333

# Outward unit normal to cone surface (points away from axis AND upward)
# Cone implicit: F(r,z) = r - R_BASE - dR_dZ*z = 0
# ∇F in (r,z) = (1, -dR_dZ)  →  normalize:
mag    = math.sqrt(1.0 + dR_dZ**2)
nR_hat =  1.0 / mag          # radial component  ≈ 0.864
nZ_hat = -dR_dZ / mag        # Z component       ≈ 0.504  (positive = upward)

print(f"Cone normal: nR={nR_hat:.4f}, nZ={nZ_hat:.4f}")
print(f"Max blade tip radius at base: {HUB_R_BASE + BLADE_H_BOT*nR_hat:.2f}mm")
print(f"Max Z at top blade tip: {HUB_H + BLADE_H_TOP*nZ_hat:.2f}mm")

# ── Helper: one blade cross-section wire ─────────────────────────────────────
def make_section_wire(z_frac, base_twist_deg=0.0):
    """
    Returns a closed CadQuery Wire (quadrilateral) for the blade cross-section
    at fractional height z_frac (may be outside [0,1] to bury blade ends).
    base_twist_deg: additional rotation offset for blade instancing.
    Winding: ALWAYS b0 → b1 → t2 → t3 → b0 (consistent CCW from outside).
    """
    z_val  = z_frac * HUB_H
    r_cone = HUB_R_BASE + dR_dZ * z_val
    # Clamp radius so it never goes below bore + clearance
    r_cone = max(r_cone, BORE_R + BLADE_T + 1.5)

    # Angular position: CCW twist accumulates linearly with height
    theta = math.radians(base_twist_deg + TWIST_DEG * z_frac)

    # Centre point on cone surface at this station
    cx = r_cone * math.cos(theta)
    cy = r_cone * math.sin(theta)
    cz = z_val

    # Tangent unit vector: CCW direction in XY plane, zero Z
    tx = -math.sin(theta)
    ty =  math.cos(theta)
    # tz = 0

    # Outward surface normal at this angular position
    nx = nR_hat * math.cos(theta)
    ny = nR_hat * math.sin(theta)
    nz = nZ_hat

    # Blade protrusion — clamp z_frac to [0,1] for taper interpolation
    zf_c    = max(0.0, min(1.0, z_frac))
    h_blade = BLADE_H_BOT + (BLADE_H_TOP - BLADE_H_BOT) * zf_c

    half_t  = BLADE_T / 2.0

    # ── Four corners of the blade cross-section rectangle ──
    # Base pair: EMBED mm INSIDE the cone surface (along -normal)
    b0 = cq.Vector(cx - half_t*tx - EMBED*nx,
                   cy - half_t*ty - EMBED*ny,
                   cz              - EMBED*nz)
    b1 = cq.Vector(cx + half_t*tx - EMBED*nx,
                   cy + half_t*ty - EMBED*ny,
                   cz              - EMBED*nz)

    # Tip pair: h_blade mm OUTSIDE the cone surface (along +normal)
    t2 = cq.Vector(cx + half_t*tx + h_blade*nx,
                   cy + half_t*ty + h_blade*ny,
                   cz              + h_blade*nz)
    t3 = cq.Vector(cx - half_t*tx + h_blade*nx,
                   cy - half_t*ty + h_blade*ny,
                   cz              + h_blade*nz)

    # Build closed wire with consistent winding order
    edges = [
        cq.Edge.makeLine(b0, b1),
        cq.Edge.makeLine(b1, t2),
        cq.Edge.makeLine(t2, t3),
        cq.Edge.makeLine(t3, b0),
    ]
    return cq.Wire.assembleEdges(edges)

# ── Step 1: Hub frustum — exact design dimensions Z=0 to Z=60 ────────────────
hub_solid = (
    cq.Workplane("XY")
    .circle(HUB_R_BASE)
    .workplane(offset=HUB_H)
    .circle(HUB_R_TOP)
    .loft()
    .val()
)
print(f"Hub built: R_base={HUB_R_BASE}, R_top={HUB_R_TOP}, H={HUB_H}")

# ── Step 2: Central bore — full through-hole ──────────────────────────────────
# Bore starts 2mm below Z=0 and ends 2mm above Z=60 for clean cut
bore_solid = (
    cq.Workplane("XY")
    .workplane(offset=-2.0)
    .circle(BORE_R)
    .extrude(HUB_H + 4.0)
    .val()
)
hub_solid = hub_solid.cut(bore_solid)
print(f"Bore cut: R={BORE_R}, through Z=-2 to Z={HUB_H+2}")

# ── Step 3: Build blade-0 loft solid ─────────────────────────────────────────
z_fracs = [
    Z_FRAC_MIN + i * (Z_FRAC_MAX - Z_FRAC_MIN) / (N_SEC - 1)
    for i in range(N_SEC)
]

wires_b0 = [make_section_wire(zf, base_twist_deg=0.0) for zf in z_fracs]
blade0   = cq.Solid.makeLoft(wires_b0, ruled=False)
print(f"Blade 0 lofted with {N_SEC} sections, z_frac [{Z_FRAC_MIN}, {Z_FRAC_MAX}]")

# ── Step 4: Fuse all 7 blades into the hub ────────────────────────────────────
blade_angle_step = 360.0 / NUM_BLADES   # ≈ 51.4286°
running = hub_solid

for i in range(NUM_BLADES):
    angle_deg = i * blade_angle_step
    blade_i = blade0.rotate(
        cq.Vector(0.0, 0.0, 0.0),
        cq.Vector(0.0, 0.0, 1.0),
        angle_deg
    )
    running = running.fuse(blade_i)
    print(f"  Blade {i} fused at {angle_deg:.2f}°")

print("All blades fused.")

# ── Step 5: Attempt fillet on blade-to-cone junctions ────────────────────────
final_solid = running
try:
    final_solid = running.fillet(1.2)
    print("Fillet 1.2mm applied successfully.")
except Exception as e:
    print(f"Fillet 1.2mm failed: {e}")
    try:
        final_solid = running.fillet(0.6)
        print("Fallback fillet 0.6mm applied.")
    except Exception as e2:
        print(f"All fillets failed: {e2} — proceeding without fillet.")
        final_solid = running

# ── Step 6: Wrap into Workplane and centre on XY origin ──────────────────────
result_solid = cq.Workplane("XY").add(final_solid)

bb = result_solid.val().BoundingBox()
cx_off = -((bb.xmin + bb.xmax) / 2.0)
cy_off = -((bb.ymin + bb.ymax) / 2.0)
# Z stays at base=0; do NOT shift Z
result_solid = result_solid.translate((cx_off, cy_off, 0))

# ── Diagnostics ───────────────────────────────────────────────────────────────
bb2 = result_solid.val().BoundingBox()
print("\n=== Centrifugal Compressor Impeller — Final Dimensions ===")
print(f"X span: {bb2.xmin:.2f} → {bb2.xmax:.2f}  width  = {bb2.xmax - bb2.xmin:.2f} mm  (expect ~130)")
print(f"Y span: {bb2.ymin:.2f} → {bb2.ymax:.2f}  width  = {bb2.ymax - bb2.ymin:.2f} mm  (expect ~130)")
print(f"Z span: {bb2.zmin:.2f} → {bb2.zmax:.2f}  height = {bb2.zmax - bb2.zmin:.2f} mm  (expect ~72)")
print(f"BLADE_T={BLADE_T}mm | EMBED={EMBED}mm | N_SEC={N_SEC}")
print(f"nR_hat={nR_hat:.4f} | nZ_hat={nZ_hat:.4f}")