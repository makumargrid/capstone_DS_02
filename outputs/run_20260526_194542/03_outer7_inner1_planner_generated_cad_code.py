import cadquery as cq
import math

# ── Parameters ────────────────────────────────────────────────────────────────
HUB_R_BASE   = 50.0
HUB_R_TOP    = 15.0
HUB_H        = 60.0
BORE_R       = 7.5
NUM_BLADES   = 7
BLADE_T      = 7.0       # 3.5 × 1.96 = 6.86 → 7.0mm (well above 2.5mm floor)
BLADE_H_BOT  = 15.0      # protrusion above cone surface at base
BLADE_H_TOP  = 5.0       # protrusion above cone surface at top
TWIST_DEG    = 60.0      # total CCW twist over full height
N_SEC        = 14        # loft sections (ruled=True, fewer = safer)
EMBED_R      = 8.0       # radial embed depth — increased to bury blade roots deeper

# Base plate added below hub to seal blade-bottom intersections
BASE_PLATE_T = 4.0       # thickness of solid disc added below Z=0

# ── Cone geometry ─────────────────────────────────────────────────────────────
dR_dZ  = (HUB_R_TOP - HUB_R_BASE) / HUB_H   # ≈ -0.5833
mag    = math.sqrt(1.0 + dR_dZ**2)
nR_hat =  1.0 / mag      # radial component of cone outward normal ≈ 0.8137
nZ_hat = -dR_dZ / mag    # Z component of cone outward normal      ≈ 0.5812

print(f"nR={nR_hat:.4f}  nZ={nZ_hat:.4f}")
print(f"Blade tip radius at base: {HUB_R_BASE + BLADE_H_BOT*nR_hat:.1f} mm")
print(f"Z at top blade tip:       {HUB_H + BLADE_H_TOP*nZ_hat:.1f} mm")

# ── Section wire builder ───────────────────────────────────────────────────────
def make_blade_wire(z_frac, base_angle_deg=0.0):
    """
    One blade cross-section wire at normalised height z_frac in [0,1].
    Base edge pushed radially INWARD by EMBED_R (pure XY — no Z folding).
    Tip edge protrudes along cone surface normal.
    Winding: b0 → b1 → t1 → t0 → b0 (consistent CCW from outside).
    """
    z      = z_frac * HUB_H
    r_cone = HUB_R_BASE + dR_dZ * z
    r_cone = max(r_cone, BORE_R + BLADE_T + 2.0)

    theta  = math.radians(base_angle_deg + TWIST_DEG * z_frac)
    cos_t  = math.cos(theta)
    sin_t  = math.sin(theta)

    # Radial outward unit vector (XY plane)
    rx, ry = cos_t, sin_t
    # Tangential CCW unit vector (XY plane)
    tx, ty = -sin_t, cos_t

    # Cone surface outward normal (3D)
    nx = nR_hat * cos_t
    ny = nR_hat * sin_t
    nz = nZ_hat

    # Blade protrusion (linear taper, clamped to [0,1])
    zf_c   = max(0.0, min(1.0, z_frac))
    h      = BLADE_H_BOT + (BLADE_H_TOP - BLADE_H_BOT) * zf_c
    half_t = BLADE_T / 2.0

    # Centre of blade footprint on cone surface
    cx = r_cone * cos_t
    cy = r_cone * sin_t
    cz = z

    # BASE corners: push radially INWARD by EMBED_R (pure XY, no Z component)
    b0 = cq.Vector(cx - half_t*tx - EMBED_R*rx,
                   cy - half_t*ty - EMBED_R*ry,
                   cz)
    b1 = cq.Vector(cx + half_t*tx - EMBED_R*rx,
                   cy + half_t*ty - EMBED_R*ry,
                   cz)

    # TIP corners: protrude h mm along cone surface normal
    t0 = cq.Vector(cx - half_t*tx + h*nx,
                   cy - half_t*ty + h*ny,
                   cz              + h*nz)
    t1 = cq.Vector(cx + half_t*tx + h*nx,
                   cy + half_t*ty + h*ny,
                   cz              + h*nz)

    # Consistent winding: b0 → b1 → t1 → t0 → b0
    edges = [
        cq.Edge.makeLine(b0, b1),
        cq.Edge.makeLine(b1, t1),
        cq.Edge.makeLine(t1, t0),
        cq.Edge.makeLine(t0, b0),
    ]
    return cq.Wire.assembleEdges(edges)

# ── Step 1: Hub frustum — exact Z=0 to Z=60 ──────────────────────────────────
hub_frustum = (
    cq.Workplane("XY")
    .circle(HUB_R_BASE)
    .workplane(offset=HUB_H)
    .circle(HUB_R_TOP)
    .loft()
    .val()
)

# ── Step 2: Base plate — solid disc below Z=0 to seal blade root intersections
# Disc spans Z = -BASE_PLATE_T to Z = 0, radius = HUB_R_BASE
# This ensures blade base intersections are buried inside solid material
base_plate = (
    cq.Workplane("XY")
    .workplane(offset=-BASE_PLATE_T)
    .circle(HUB_R_BASE)
    .extrude(BASE_PLATE_T)
    .val()
)

# ── Step 3: Top cap — small disc above Z=60 to seal blade top intersections ───
# Disc spans Z=60 to Z=60+BASE_PLATE_T, radius = HUB_R_TOP
top_cap = (
    cq.Workplane("XY")
    .workplane(offset=HUB_H)
    .circle(HUB_R_TOP)
    .extrude(BASE_PLATE_T)
    .val()
)

# Fuse hub + base plate + top cap into one solid hub body
hub_solid = hub_frustum.fuse(base_plate)
hub_solid = hub_solid.fuse(top_cap)
print(f"Hub + base plate (Z={-BASE_PLATE_T} to 0) + top cap (Z={HUB_H} to {HUB_H+BASE_PLATE_T}) built.")

# ── Step 4: Central bore — through entire assembly including caps ─────────────
bore_solid = (
    cq.Workplane("XY")
    .workplane(offset=-(BASE_PLATE_T + 2.0))
    .circle(BORE_R)
    .extrude(HUB_H + 2.0 * BASE_PLATE_T + 4.0)
    .val()
)
hub_solid = hub_solid.cut(bore_solid)
print(f"Bore cut: R={BORE_R}mm through full assembly.")

# ── Step 5: Build blade-0 loft (ruled=True — no self-intersection) ────────────
z_fracs  = [i / (N_SEC - 1) for i in range(N_SEC)]
wires_b0 = [make_blade_wire(zf, base_angle_deg=0.0) for zf in z_fracs]
blade0   = cq.Solid.makeLoft(wires_b0, ruled=True)
print(f"Blade 0 lofted: {N_SEC} sections, ruled=True.")

# ── Step 6: Fuse all 7 blades ────────────────────────────────────────────────
blade_step = 360.0 / NUM_BLADES   # ≈ 51.4286°
running    = hub_solid

for i in range(NUM_BLADES):
    ang     = i * blade_step
    blade_i = blade0.rotate(
        cq.Vector(0, 0, 0),
        cq.Vector(0, 0, 1),
        ang
    )
    running = running.fuse(blade_i)
    print(f"  Blade {i} fused at {ang:.2f}°")

print("All 7 blades fused.")

# ── Step 7: Fillet blade-to-hub junctions ────────────────────────────────────
final_solid = running
for fillet_r in [1.5, 1.0, 0.5]:
    try:
        final_solid = running.fillet(fillet_r)
        print(f"Fillet {fillet_r}mm applied.")
        break
    except Exception as ex:
        print(f"Fillet {fillet_r}mm failed: {ex}")
        final_solid = running

# ── Step 8: Wrap into Workplane and centre on XY ─────────────────────────────
result_solid = cq.Workplane("XY").add(final_solid)

bb = result_solid.val().BoundingBox()
cx_off = -((bb.xmin + bb.xmax) / 2.0)
cy_off = -((bb.ymin + bb.ymax) / 2.0)
# Z: base plate sits at -BASE_PLATE_T; shift up so Z=0 is at bottom of base plate
# Actually keep design origin: hub base at Z=0, base plate below is intentional
result_solid = result_solid.translate((cx_off, cy_off, 0))

# ── Diagnostics ───────────────────────────────────────────────────────────────
bb2 = result_solid.val().BoundingBox()
print("\n=== Centrifugal Compressor Impeller ===")
print(f"X: {bb2.xmin:.2f} → {bb2.xmax:.2f}  ({bb2.xmax-bb2.xmin:.2f}mm, expect ~130)")
print(f"Y: {bb2.ymin:.2f} → {bb2.ymax:.2f}  ({bb2.ymax-bb2.ymin:.2f}mm, expect ~130)")
print(f"Z: {bb2.zmin:.2f} → {bb2.zmax:.2f}  ({bb2.zmax-bb2.zmin:.2f}mm, expect ~72)")
print(f"BLADE_T={BLADE_T}mm | EMBED_R={EMBED_R}mm | BASE_PLATE_T={BASE_PLATE_T}mm")