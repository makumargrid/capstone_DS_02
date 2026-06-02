import cadquery as cq
import math

# ── Parameters ────────────────────────────────────────────────────────────────
HUB_R_BASE   = 50.0      # base radius at Z=0  (diameter 100mm)
HUB_R_TOP    = 15.0      # top radius  at Z=60 (diameter  30mm)
HUB_H        = 60.0      # hub height mm
BORE_R       = 7.5       # central bore radius (diameter 15mm)
NUM_BLADES   = 7
BLADE_T      = 3.5       # blade thickness mm — increased well above 2.5mm DFM floor
                          # (worst face 0.784mm needs large margin; 3.5/2.8 = 1.25× boost)
BLADE_H_BOT  = 15.0      # blade protrusion at base (mm, normal to cone)
BLADE_H_TOP  = 5.0       # blade protrusion at top  (mm, normal to cone)
TWIST_DEG    = 60.0      # total CCW twist degrees from Z=0 to Z=60
N_SEC        = 26        # loft cross-section count (more = smoother transitions)
EMBED        = 6.0       # mm blade embeds INTO cone surface — increased to bury slivers

# Blade z_frac range — extend well beyond [0,1] so blade ends are deeply
# buried inside hub body; intersection faces never appear near Z=0 or Z=60
Z_FRAC_MIN   = -0.15     # 9mm below Z=0
Z_FRAC_MAX   =  1.15     # 9mm above Z=60

# Cap disc thickness added to hub top and bottom to sandwich blade roots
CAP_T        = 3.5       # mm — same as blade thickness for consistent wall

# ── Cone geometry ─────────────────────────────────────────────────────────────
dR_dZ = (HUB_R_TOP - HUB_R_BASE) / HUB_H   # = -35/60 ≈ -0.58333

# Outward unit normal to cone surface
mag    = math.sqrt(1.0 + dR_dZ**2)
nR_hat =  1.0 / mag          # radial component  ≈ 0.864
nZ_hat = -dR_dZ / mag        # Z component       ≈ 0.504 (positive = upward)

print(f"Cone normal: nR={nR_hat:.4f}, nZ={nZ_hat:.4f}")
print(f"Blade tip radius at base: {HUB_R_BASE + BLADE_H_BOT*nR_hat:.2f} mm")
print(f"Z at top blade tip:       {HUB_H + BLADE_H_TOP*nZ_hat:.2f} mm")

# ── Helper: one blade cross-section wire ─────────────────────────────────────
def make_section_wire(z_frac, base_twist_deg=0.0):
    """
    Closed quadrilateral wire for the blade cross-section at z_frac.
    z_frac may be outside [0,1] — blade ends buried inside hub.
    Winding: ALWAYS b0 → b1 → t2 → t3 → b0 (consistent CCW from outside).
    """
    z_val  = z_frac * HUB_H
    r_cone = HUB_R_BASE + dR_dZ * z_val
    # Clamp radius: never below bore + clearance
    r_cone = max(r_cone, BORE_R + BLADE_T + 2.0)

    # Angular position: CCW twist accumulates with height
    theta = math.radians(base_twist_deg + TWIST_DEG * z_frac)

    # Centre point on (extrapolated) cone surface
    cx = r_cone * math.cos(theta)
    cy = r_cone * math.sin(theta)
    cz = z_val

    # Tangent unit vector: CCW in XY plane, zero Z
    tx = -math.sin(theta)
    ty =  math.cos(theta)

    # Outward surface normal
    nx = nR_hat * math.cos(theta)
    ny = nR_hat * math.sin(theta)
    nz = nZ_hat

    # Blade protrusion — clamp z_frac to [0,1] for taper interpolation
    zf_c    = max(0.0, min(1.0, z_frac))
    h_blade = BLADE_H_BOT + (BLADE_H_TOP - BLADE_H_BOT) * zf_c

    half_t  = BLADE_T / 2.0

    # Base corners: EMBED mm INSIDE cone surface (along -normal)
    # Deeply embedded to ensure no sliver faces at Z-boundaries
    b0 = cq.Vector(cx - half_t*tx - EMBED*nx,
                   cy - half_t*ty - EMBED*ny,
                   cz              - EMBED*nz)
    b1 = cq.Vector(cx + half_t*tx - EMBED*nx,
                   cy + half_t*ty - EMBED*ny,
                   cz              - EMBED*nz)

    # Tip corners: h_blade mm OUTSIDE cone surface (along +normal)
    t2 = cq.Vector(cx + half_t*tx + h_blade*nx,
                   cy + half_t*ty + h_blade*ny,
                   cz              + h_blade*nz)
    t3 = cq.Vector(cx - half_t*tx + h_blade*nx,
                   cy - half_t*ty + h_blade*ny,
                   cz              + h_blade*nz)

    # Assemble closed wire — consistent winding b0 → b1 → t2 → t3 → b0
    edges = [
        cq.Edge.makeLine(b0, b1),
        cq.Edge.makeLine(b1, t2),
        cq.Edge.makeLine(t2, t3),
        cq.Edge.makeLine(t3, b0),
    ]
    return cq.Wire.assembleEdges(edges)

# ── Step 1: Hub frustum — exact Z=0 to Z=60 ──────────────────────────────────
hub_solid = (
    cq.Workplane("XY")
    .circle(HUB_R_BASE)
    .workplane(offset=HUB_H)
    .circle(HUB_R_TOP)
    .loft()
    .val()
)

# ── Step 2: Add bottom cap disc — seals blade roots at Z=0 ───────────────────
# Flat disc: radius=HUB_R_BASE, thickness=CAP_T, from Z=-CAP_T to Z=0
# This adds solid material below Z=0 so blade-base intersections are
# sandwiched inside solid, not exposed as boundary faces
bot_cap = (
    cq.Workplane("XY")
    .workplane(offset=-CAP_T)
    .circle(HUB_R_BASE)
    .extrude(CAP_T)
    .val()
)
hub_solid = hub_solid.fuse(bot_cap)

# ── Step 3: Add top cap disc — seals blade tips at Z=60 ──────────────────────
# Flat disc: radius=HUB_R_TOP, thickness=CAP_T, from Z=60 to Z=60+CAP_T
top_cap = (
    cq.Workplane("XY")
    .workplane(offset=HUB_H)
    .circle(HUB_R_TOP)
    .extrude(CAP_T)
    .val()
)
hub_solid = hub_solid.fuse(top_cap)

# ── Step 4: Central bore — full through-hole including caps ───────────────────
bore_solid = (
    cq.Workplane("XY")
    .workplane(offset=-(CAP_T + 2.0))
    .circle(BORE_R)
    .extrude(HUB_H + 2.0 * CAP_T + 4.0)
    .val()
)
hub_solid = hub_solid.cut(bore_solid)
print(f"Hub + caps built. Bore R={BORE_R}mm cut through.")

# ── Step 5: Build blade-0 loft solid ─────────────────────────────────────────
z_fracs  = [
    Z_FRAC_MIN + i * (Z_FRAC_MAX - Z_FRAC_MIN) / (N_SEC - 1)
    for i in range(N_SEC)
]
wires_b0 = [make_section_wire(zf, base_twist_deg=0.0) for zf in z_fracs]
blade0   = cq.Solid.makeLoft(wires_b0, ruled=False)
print(f"Blade 0 lofted: {N_SEC} sections, z_frac [{Z_FRAC_MIN:.2f}, {Z_FRAC_MAX:.2f}]")

# ── Step 6: Fuse all 7 blades into hub ───────────────────────────────────────
blade_angle_step = 360.0 / NUM_BLADES   # ≈ 51.4286°
running = hub_solid

for i in range(NUM_BLADES):
    angle_deg = i * blade_angle_step
    blade_i   = blade0.rotate(
        cq.Vector(0.0, 0.0, 0.0),
        cq.Vector(0.0, 0.0, 1.0),
        angle_deg
    )
    running = running.fuse(blade_i)
    print(f"  Blade {i} fused at {angle_deg:.2f}°")

print("All 7 blades fused into hub.")

# ── Step 7: Fillet blade-to-cone junctions for DFM compliance ────────────────
final_solid = running
for fillet_r in [1.5, 1.0, 0.6]:
    try:
        final_solid = running.fillet(fillet_r)
        print(f"Fillet {fillet_r}mm applied successfully.")
        break
    except Exception as e:
        print(f"Fillet {fillet_r}mm failed: {e}")
        final_solid = running

# ── Step 8: Wrap into Workplane and centre on XY origin ──────────────────────
result_solid = cq.Workplane("XY").add(final_solid)

bb = result_solid.val().BoundingBox()
cx_off = -((bb.xmin + bb.xmax) / 2.0)
cy_off = -((bb.ymin + bb.ymax) / 2.0)
# Z base stays at 0 — do NOT shift Z
result_solid = result_solid.translate((cx_off, cy_off, 0))

# ── Diagnostics ───────────────────────────────────────────────────────────────
bb2 = result_solid.val().BoundingBox()
print("\n=== Centrifugal Compressor Impeller — Final ===")
print(f"X: {bb2.xmin:.2f} → {bb2.xmax:.2f}  ({bb2.xmax-bb2.xmin:.2f}mm, expect ~130)")
print(f"Y: {bb2.ymin:.2f} → {bb2.ymax:.2f}  ({bb2.ymax-bb2.ymin:.2f}mm, expect ~130)")
print(f"Z: {bb2.zmin:.2f} → {bb2.zmax:.2f}  ({bb2.zmax-bb2.zmin:.2f}mm, expect ~72)")
print(f"BLADE_T={BLADE_T}mm | EMBED={EMBED}mm | CAP_T={CAP_T}mm")
print(f"Z_FRAC range=[{Z_FRAC_MIN}, {Z_FRAC_MAX}]")