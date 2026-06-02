import cadquery as cq
import math
from OCC.Core.gp import gp_Ax3, gp_Pnt, gp_Dir, gp_Trsf, gp_Vec
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform

# ─────────────────────────────────────────
# PARAMETERS
# ─────────────────────────────────────────
HUB_BASE_R  = 50.0
HUB_TOP_R   = 15.0
HUB_H       = 60.0
BORE_R      = 7.5
N_BLADES    = 7
BLADE_TWIST = 60.0   # degrees total
BLADE_THICK = 2.0    # mm
PROT_BASE   = 15.0   # mm protrusion at base
PROT_TOP    = 5.0    # mm protrusion at top
N_SLABS     = 40     # slabs per blade for smooth solid

cone_slope  = (HUB_BASE_R - HUB_TOP_R) / HUB_H   # positive: 35/60
# Outward normal to cone surface (in r-z plane, pointing away from cone material)
# Cone wall goes direction: dr = -cone_slope*dz (inward as z rises), dz = +1
# Wall tangent (upward): (-cone_slope, +1) normalized
# Outward normal (rotate 90° CCW in rz-plane): (+1, +cone_slope) normalized
t_mag  = math.sqrt(cone_slope**2 + 1.0)
NR     = 1.0 / t_mag          # radial component of outward cone normal
NZ     = cone_slope / t_mag   # z component of outward cone normal

# ─────────────────────────────────────────
# 1. HUB — truncated cone
# ─────────────────────────────────────────
hub_wire = (
    cq.Workplane("XZ")
    .moveTo(BORE_R, 0.0)
    .lineTo(HUB_BASE_R, 0.0)
    .lineTo(HUB_TOP_R, HUB_H)
    .lineTo(BORE_R, HUB_H)
    .close()
)
hub = hub_wire.revolve(360, (0, 0, 0), (0, 0, 1))

# ─────────────────────────────────────────
# 2. CENTRAL BORE — already included in
#    hub profile (inner edge = BORE_R)
#    but let's cut cleanly just in case
# ─────────────────────────────────────────
bore_cyl = (
    cq.Workplane("XY")
    .workplane(offset=-1.0)
    .circle(BORE_R)
    .extrude(HUB_H + 2.0)
)
hub = hub.cut(bore_cyl)

# ─────────────────────────────────────────
# 3. SINGLE BLADE via transformed slabs
# ─────────────────────────────────────────
def make_single_blade(n_slabs=N_SLABS):
    """
    Build one blade as a union of thin oriented box slabs along the
    swept path on the cone surface, using OCC gp_Trsf for placement.
    """
    embed  = 1.2   # mm embed into cone surface for watertight union
    blade_shape = None

    dz_slab = HUB_H / (n_slabs - 1)

    for i in range(n_slabs):
        t = i / (n_slabs - 1)          # 0 → 1
        z = t * HUB_H
        twist_rad  = math.radians(BLADE_TWIST * t)
        cone_r     = HUB_BASE_R - cone_slope * z
        protrusion = PROT_BASE + (PROT_TOP - PROT_BASE) * t

        # ── Coordinate frame at this point on the cone surface ──
        # Origin: point ON the cone surface
        cos_a = math.cos(twist_rad)
        sin_a = math.sin(twist_rad)

        # Surface point
        sx = cone_r * cos_a
        sy = cone_r * sin_a
        sz = z

        # Outward cone normal in world coords
        onx = NR * cos_a
        ony = NR * sin_a
        onz = NZ

        # Tangential direction (circumferential, CCW)
        tx = -sin_a
        ty =  cos_a
        tz = 0.0

        # Third axis: along-blade-surface direction
        # = outward_normal × tangential  (right-hand)
        bx = ony * tz - onz * ty
        by = onz * tx - onx * tz
        bz = onx * ty - ony * tx
        # normalise b
        b_mag = math.sqrt(bx*bx + by*by + bz*bz)
        bx /= b_mag; by /= b_mag; bz /= b_mag

        # Box in local frame:
        #   local X = tangential  (width = BLADE_THICK)
        #   local Y = b dir       (slab depth, along cone surface / world-Z approx)
        #   local Z = outward normal (blade protrusion height)
        # Box origin (local 0,0,0) placed EMBED distance inside cone surface
        # so box runs from -embed to +protrusion along local Z

        total_z = protrusion + embed
        slab_depth = dz_slab * 1.8   # overlap between slabs
        slab_depth = max(slab_depth, 2.5)

        # Embed origin = surface point shifted inward along normal
        ox = sx - embed * onx
        oy = sy - embed * ony
        oz = sz - embed * onz

        # Build box at world origin in local frame:
        # centered in X (tangential), starts at Y=0 (slab_depth symmetric ±),
        # starts at Z=0 going +total_z along normal
        # We'll center in Y and X, starting at Z=0
        box_local = cq.Solid.makeBox(
            BLADE_THICK,   # length along local X
            slab_depth,    # length along local Y
            total_z,       # length along local Z (normal direction)
            pnt=cq.Vector(-BLADE_THICK/2, -slab_depth/2, 0.0)
        )

        # ── OCC Transformation ──
        # We want: local X→(tx,ty,tz), local Y→(bx,by,bz), local Z→(onx,ony,onz)
        # Origin at (ox, oy, oz)
        # gp_Ax3(origin, N=zDir, Vx=xDir)
        try:
            ax3 = gp_Ax3(
                gp_Pnt(ox, oy, oz),
                gp_Dir(onx, ony, onz),   # local Z → outward normal
                gp_Dir(tx,  ty,  tz)     # local X → tangential
            )
            trsf = gp_Trsf()
            trsf.SetTransformation(ax3)
            trsf.Invert()

            brep_trsf = BRepBuilderAPI_Transform(box_local.wrapped, trsf, True)
            brep_trsf.Build()
            transformed_shape = cq.Shape.cast(brep_trsf.Shape())

            if blade_shape is None:
                blade_shape = transformed_shape
            else:
                blade_shape = blade_shape.fuse(transformed_shape)

        except Exception as exc:
            print(f"  Slab {i} skipped: {exc}")
            continue

    return blade_shape


# Build blade 0 (at angle 0)
print("Building blade...")
blade_0 = make_single_blade()

# ─────────────────────────────────────────
# 4. REPLICATE BLADES & UNION WITH HUB
# ─────────────────────────────────────────
angle_step = 360.0 / N_BLADES

# Start with hub
result = hub.val()  # cq.Shape (Solid)

print("Unioning blades with hub...")
for i in range(N_BLADES):
    angle_deg = i * angle_step
    angle_rad = math.radians(angle_deg)

    if i == 0:
        blade_i = blade_0
    else:
        # Rotate blade_0 around Z axis
        rot_trsf = gp_Trsf()
        rot_trsf.SetRotation(
            __import__('OCC.Core.gp', fromlist=['gp_Ax1']).gp_Ax1(
                gp_Pnt(0, 0, 0),
                gp_Dir(0, 0, 1)
            ),
            angle_rad
        )
        brep_rot = BRepBuilderAPI_Transform(blade_0.wrapped, rot_trsf, True)
        brep_rot.Build()
        blade_i = cq.Shape.cast(brep_rot.Shape())

    result = result.fuse(blade_i)

# ─────────────────────────────────────────
# 5. WRAP INTO WORKPLANE & EXPORT
# ─────────────────────────────────────────
result_solid = cq.Workplane().newObject([result])