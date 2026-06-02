import cadquery as cq
import math

# ─────────────────────────────────────────
# PARAMETERS
# ─────────────────────────────────────────
HUB_BASE_R  = 50.0   # radius at Z=0
HUB_TOP_R   = 15.0   # radius at Z=60
HUB_H       = 60.0   # total height
BORE_R      = 7.5    # bore radius (15mm dia)
N_BLADES    = 7
BLADE_TWIST = 60.0   # degrees total twist bottom to top
BLADE_THICK = 2.0    # mm tangential thickness
PROT_BASE   = 15.0   # mm protrusion at Z=0
PROT_TOP    = 5.0    # mm protrusion at Z=60
N_SLABS     = 35     # slabs per blade

# Cone geometry
cone_slope = (HUB_BASE_R - HUB_TOP_R) / HUB_H  # = 35/60 ≈ 0.5833

# Outward normal to cone surface in the r-z plane:
# Wall tangent going upward: direction (-cone_slope, 1) in (r, z)
# Outward normal (rotate 90 deg CW in rz plane): (1, cone_slope) normalized
t_mag = math.sqrt(cone_slope**2 + 1.0)
NR = 1.0 / t_mag          # radial component of outward cone normal
NZ = cone_slope / t_mag   # z component of outward cone normal

# ─────────────────────────────────────────
# 1. HUB — truncated cone via revolve
#    Profile includes the bore wall so it
#    is already a hollow frustum
# ─────────────────────────────────────────
hub = (
    cq.Workplane("XZ")
    .moveTo(BORE_R, 0.0)
    .lineTo(HUB_BASE_R, 0.0)
    .lineTo(HUB_TOP_R, HUB_H)
    .lineTo(BORE_R, HUB_H)
    .close()
    .revolve(360, (0, 0, 0), (0, 0, 1))
)

# Extra clean bore cut (handles any revolve seam artifacts)
bore_cyl = (
    cq.Workplane("XY")
    .workplane(offset=-1.0)
    .circle(BORE_R)
    .extrude(HUB_H + 2.0)
)
hub = hub.cut(bore_cyl)

# ─────────────────────────────────────────
# 2. BLADE SLAB HELPER
# ─────────────────────────────────────────
def make_oriented_box(
    ox, oy, oz,       # origin (embed point on/in cone surface)
    nx, ny, nz,       # local Z = outward cone normal (unit)
    ux, uy, uz,       # local X = tangential direction (unit)
    box_w,            # width  along local X (BLADE_THICK)
    box_d,            # depth  along local Y (slab thickness)
    box_h             # height along local Z (protrusion + embed)
):
    """
    Build a box in local frame then place it in world space using
    cq.Plane(origin, xDir, normal) → cq.Location.
    Local axes:
      X = tangential (ux, uy, uz)
      Z = outward normal (nx, ny, nz)
      Y = Z cross X (computed automatically by CadQuery Plane)
    The box runs:
      X: -box_w/2 → +box_w/2  (centered)
      Y: -box_d/2 → +box_d/2  (centered)
      Z:  0       → +box_h    (from embed point outward)
    """
    # Build box centered in X and Y, extending +Z
    local_box = cq.Solid.makeBox(
        box_w,
        box_d,
        box_h,
        pnt=cq.Vector(-box_w / 2.0, -box_d / 2.0, 0.0)
    )

    # Define the world-space coordinate frame using CadQuery Plane
    # origin = embed point, xDir = tangential, normal = outward cone normal
    plane = cq.Plane(
        origin=(ox, oy, oz),
        xDir=(ux, uy, uz),
        normal=(nx, ny, nz)
    )

    # Get the Location from the Plane and apply to the box
    loc = cq.Location(plane)
    placed_box = local_box.located(loc)

    return placed_box


# ─────────────────────────────────────────
# 3. BUILD ONE BLADE
# ─────────────────────────────────────────
def make_single_blade(n_slabs=N_SLABS):
    """
    Build one blade (at angular start = 0) as a fused set of
    oriented box slabs along the swept cone-surface path.
    Returns a cq.Shape (Solid).
    """
    embed     = 1.5    # mm embedded into cone surface
    dz_slab   = HUB_H / (n_slabs - 1)
    slab_depth_factor = 2.0  # overlap multiplier for slab depth

    blade_shape = None

    for i in range(n_slabs):
        t          = i / (n_slabs - 1)
        z          = t * HUB_H
        twist_rad  = math.radians(BLADE_TWIST * t)
        cone_r     = HUB_BASE_R - cone_slope * z
        protrusion = PROT_BASE + (PROT_TOP - PROT_BASE) * t

        cos_a = math.cos(twist_rad)
        sin_a = math.sin(twist_rad)

        # ── Point on cone surface ──
        sx = cone_r * cos_a
        sy = cone_r * sin_a
        sz = z

        # ── Outward cone normal in world coords ──
        onx = NR * cos_a
        ony = NR * sin_a
        onz = NZ

        # ── Tangential direction (circumferential CCW) ──
        tx = -sin_a
        ty =  cos_a
        tz = 0.0

        # ── Embed origin: step inward along normal ──
        ox = sx - embed * onx
        oy = sy - embed * ony
        oz = sz - embed * onz

        # ── Slab dimensions ──
        total_h   = protrusion + embed          # along normal
        slab_d    = max(dz_slab * slab_depth_factor, 3.0)  # along Y (overlap)

        # ── Build and place the slab ──
        try:
            placed = make_oriented_box(
                ox, oy, oz,
                onx, ony, onz,
                tx,  ty,  tz,
                BLADE_THICK,
                slab_d,
                total_h
            )

            if blade_shape is None:
                blade_shape = placed
            else:
                blade_shape = blade_shape.fuse(placed)

        except Exception as exc:
            print(f"  Slab {i} failed: {exc}")
            continue

    return blade_shape


# ─────────────────────────────────────────
# 4. BUILD ALL 7 BLADES & UNION WITH HUB
# ─────────────────────────────────────────
print("Building blade 0...")
blade_0 = make_single_blade()

angle_step = 360.0 / N_BLADES

# Start accumulating from the hub
result = hub.val()   # cq.Solid (Shape)

print("Fusing blades into hub...")
for i in range(N_BLADES):
    angle_deg = i * angle_step

    if i == 0:
        blade_i = blade_0
    else:
        # Rotate blade_0 around Z axis using CadQuery Shape.rotate()
        blade_i = blade_0.rotate(
            cq.Vector(0, 0, 0),
            cq.Vector(0, 0, 1),
            angle_deg
        )

    result = result.fuse(blade_i)

# ─────────────────────────────────────────
# 5. FINAL RESULT
# ─────────────────────────────────────────
result_solid = cq.Workplane().newObject([result])

print("Done. result_solid is ready.")