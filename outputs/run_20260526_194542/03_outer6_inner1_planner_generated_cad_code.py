import cadquery as cq
import math

# ── Parameters ────────────────────────────────────────────────────────────────
HUB_R_BASE   = 50.0
HUB_R_TOP    = 15.0
HUB_H        = 60.0
BORE_R       = 7.5
NUM_BLADES   = 7
BLADE_T      = 3.5       # blade thickness (tangential direction), mm
BLADE_H_BOT  = 15.0      # protrusion above cone surface at base
BLADE_H_TOP  = 5.0       # protrusion above cone surface at top
TWIST_DEG    = 60.0      # total CCW twist over full height
N_SEC        = 14        # loft sections — fewer = less chance of self-intersection
EMBED_R      = 5.0       # mm blade base embeds radially INTO hub (pure radial, no Z)

# ── Cone geometry ─────────────────────────────────────────────────────────────
dR_dZ  = (HUB_R_TOP - HUB_R_BASE) / HUB_H   # ≈ -0.5833
mag    = math.sqrt(1.0 + dR_dZ**2)
nR_hat =  1.0 / mag      # ≈ 0.8137  radial component of cone outward normal
nZ_hat = -dR_dZ / mag    # ≈ 0.5812  Z component of cone outward normal

print(f"nR={nR_hat:.4f}  nZ={nZ_hat:.4f}")
print(f"Outer radius at base tip: {HUB_R_BASE + BLADE_H_BOT*nR_hat:.1f} mm")
print(f"Z at top tip: {HUB_H + BLADE_H_TOP*nZ_hat:.1f} mm")

# ── Section wire builder ───────────────────────────────────────────────────────
def make_blade_wire(z_frac, base_angle_deg=0.0):
    """
    Build one blade cross-section wire at normalised height z_frac in [0,1].
    The wire is a quadrilateral with:
      - Base edge:  two points INSIDE the hub (radially inward by EMBED_R)
      - Tip edge:   two points OUTSIDE the hub (along cone surface normal)
    Winding is always b0->b1->t1->t0->b0 (consistent across all sections).
    """
    z      = z_frac * HUB_H
    r_cone = HUB_R_BASE + dR_dZ * z
    r_cone = max(r_cone, BORE_R + BLADE_T + 2.0)

    theta  = math.radians(base_angle_deg + TWIST_DEG * z_frac)

    # Unit vectors
    cos_t  = math.cos(theta);  sin_t = math.sin(theta)
    # Radial outward (in XY)
    rx, ry = cos_t, sin_t
    # Tangential CCW (in XY)
    tx, ty = -sin_t, cos_t

    # Cone surface outward normal (3D)
    nx = nR_hat * cos_t
    ny = nR_hat * sin_t
    nz = nZ_hat

    # Blade protrusion (linear taper, clamped)
    zf_c   = max(0.0, min(1.0, z_frac))
    h      = BLADE_H_BOT + (BLADE_H_TOP - BLADE_H_BOT) * zf_c
    half_t = BLADE_T / 2.0

    # Centre of blade footprint on cone surface
    cx = r_cone * cos_t
    cy = r_cone * sin_t
    cz = z

    # BASE corners: push radially INWARD by EMBED_R (pure XY, no Z change)
    # This avoids the Z-folding that caused self-intersection in previous version
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

# ── Step 1: Hub frustum ───────────────────────────────────────────────────────
hub_solid = (
    cq.Workplane("XY")
    .circle(HUB_R_BASE)
    .workplane(offset=HUB_H)
    .circle(HUB_R_TOP)
    .loft()
    .val()
)

# ── Step 2: Central bore ──────────────────────────────────────────────────────
bore_solid = (
    cq.Workplane("XY")
    .workplane(offset=-2.0)
    .circle(BORE_R)
    .extrude(HUB_H + 4.0)
    .val()
)
hub_solid = hub_solid.cut(bore_solid)
print("Hub + bore complete.")

# ── Step 3: Build blade-0 using ruled=True loft ───────────────────────────────
# ruled=True creates only ruled surfaces (straight lines between sections)
# This CANNOT self-intersect as long as section wires don't cross each other
z_fracs  = [i / (N_SEC - 1) for i in range(N_SEC)]
wires_b0 = [make_blade_wire(zf, base_angle_deg=0.0) for zf in z_fracs]

# Use ruled=True to prevent Bezier overshoot / self-intersection
blade0 = cq.Solid.makeLoft(wires_b0, ruled=True)
print("Blade 0 lofted (ruled=True).")

# ── Step 4: Fuse all 7 blades ────────────────────────────────────────────────
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

# ── Step 5: Fillet junctions ──────────────────────────────────────────────────
final_solid = running
for r in [1.5, 1.0, 0.5]:
    try:
        final_solid = running.fillet(r)
        print(f"Fillet {r}mm OK.")
        break
    except Exception as ex:
        print(f"Fillet {r}mm failed: {ex}")
        final_solid = running

# ── Step 6: Wrap + centre on XY ──────────────────────────────────────────────
result_solid = cq.Workplane("XY").add(final_solid)
bb  = result_solid.val().BoundingBox()
result_solid = result_solid.translate(
    (-((bb.xmin+bb.xmax)/2), -((bb.ymin+bb.ymax)/2), 0)
)

bb2 = result_solid.val().BoundingBox()
print("\n=== Final Bounding Box ===")
print(f"X: {bb2.xmin:.2f} → {bb2.xmax:.2f}  ({bb2.xmax-bb2.xmin:.2f} mm, expect ~130)")
print(f"Y: {bb2.ymin:.2f} → {bb2.ymax:.2f}  ({bb2.ymax-bb2.ymin:.2f} mm, expect ~130)")
print(f"Z: {bb2.zmin:.2f} → {bb2.zmax:.2f}  ({bb2.zmax-bb2.zmin:.2f} mm, expect ~72)")
print(f"BLADE_T={BLADE_T} EMBED_R={EMBED_R} ruled=True N_SEC={N_SEC}")