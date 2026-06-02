import cadquery as cq
import math

# ─────────────────────────────────────────────
# PARAMETERS
# ─────────────────────────────────────────────
BASE_R          = 50.0    # hub base radius at Z=0  → diameter = 100mm
TOP_R           = 15.0    # hub top  radius at Z=60 → diameter =  30mm
HUB_H           = 60.0    # hub height (Z=0 to Z=60)
BORE_R          = 7.5     # central bore radius (diameter 15mm)
N_BLADES        = 7
TWIST_DEG       = 60.0    # total blade twist from Z=0 to Z=HUB_H
BLADE_T         = 2.2     # blade tangential thickness (>2mm for DFM)
PROTRUSION_BASE = 15.0    # blade fin height at Z=0 (off cone surface)
PROTRUSION_TOP  = 5.0     # blade fin height at Z=60
N_STATIONS      = 12      # loft cross-section count per blade

# ─────────────────────────────────────────────
# Cone geometry
# Cone surface tangent (going upward from base to top):
#   delta_r = TOP_R - BASE_R = -35,  delta_z = HUB_H = 60
# Unit tangent: t = (-35, 60) / mag
# Normal pointing INTO flow space (away from solid, toward axis/above):
#   Rotate tangent 90° counter-clockwise in (r,z) plane:
#   n = (-60, -35) / mag  →  nr=-60/mag (inward), nz=-35/mag (downward) ← wrong direction
#   Rotate tangent 90° clockwise in (r,z) plane:
#   n = (60, 35) / mag  → nr=+60/mag (outward), nz=+35/mag  ← this is outward normal (away from axis)
#
# We want the normal that points AWAY from the cone solid surface toward the open space.
# The cone solid occupies the region BELOW the slanted surface.
# The open flow space is ABOVE/INSIDE the slanted surface.
# Correct inward-flow normal = rotate tangent CCW:  n = (-dz, dr_upward) / mag
#   = (-60, -35)/mag  but that points inward-and-downward
#
# Let's think differently: at base (r=50, z=0), the cone surface slopes inward going up.
# A blade "standing up" from this surface into the flow channel goes:
#   - radially inward (toward axis) AND upward
# So the correct protrusion direction: blend of (-r_hat) and (+z_hat)
# Specifically the inward surface normal:
#   tangent_up = normalize(-35, +60) in r-z
#   inward_normal = rotate CCW 90°: (r,z) → (-z, r) applied to tangent
#   = normalize(-60, -35)  ← points inward-radially and downward ... still wrong
#
# Actually for the flow-side normal on a cone that narrows upward:
# The OUTWARD normal (away from axis, into material below) = (60, 35)/mag
# The INWARD normal (into flow space above cone) = (-60, -35)/mag
# This inward normal points inward AND downward which makes blades go down — wrong.
#
# PRACTICAL SOLUTION: Use pure Z-upward protrusion for blades.
# Blades stand straight up from the cone surface in the +Z direction.
# This guarantees X,Y stay within hub footprint (R≤50mm) and
# Z extends upward (max Z = 60 + 15 = 75mm at base, but base protrusion=15mm, top=5mm).
# Wait: at base Z=0, blade protrudes +15mm in Z → Z goes to 15mm (fine, within hub)
# At intermediate stations the blade tip Z = z_station + protrusion... but hub is already
# at that Z so the blade tip is at z_station + protrusion which may exceed 60mm.
# At z=0, tip at z=15 (fine). At z=45, tip at z=45+8.75=53.75 (fine). At z=60, tip=60+5=65mm.
# So Z_max ≈ 65mm. That's acceptable.
# X,Y: blades sit ON the cone surface, never extending beyond r_hub at each station.
# The blade is thin (2.2mm tangential) centered on the cone surface point.
# X_max = r_hub * cos(angle) + half_t * |sin(angle)| ≤ 50 + 1.1 = 51.1mm ... still >50
# Hmm, tangential offset adds ~1.1mm → diameter ~102mm. Very close.
# FINAL FIX: Place blade profile INSIDE the hub surface (entirely within r_hub).
# ─────────────────────────────────────────────

# Cone surface outward normal components (radial outward, z upward)
_dr = TOP_R - BASE_R      # = -35 (r decreases going up)
_dz = HUB_H               # = +60
_mag = math.sqrt(_dr**2 + _dz**2)   # sqrt(35^2 + 60^2) = sqrt(1225+3600) = sqrt(4825) ≈ 69.46

# Outward normal (away from cone axis, into surrounding air — this is OUTSIDE the impeller)
# = rotate tangent (_dr, _dz) by -90° (clockwise) in r-z plane: (dz, -dr)/mag
NR_out =  _dz / _mag    # ≈ +0.864 (radially outward)
NZ_out = -_dr / _mag    # ≈ +0.504 (upward)

# For blades on a centrifugal impeller, blades stand on the cone surface
# and protrude in the direction AWAY from the cone surface toward the flow.
# On a centrifugal compressor, the flow channel is ABOVE the hub cone.
# The inward (flow-side) normal = -outward normal = (-NR_out, -NZ_out)
# But this points inward-radially and downward → blade goes into hub. Wrong.
#
# CORRECT INTERPRETATION for centrifugal impeller:
# Blades are fins that stick up from the cone surface. "Up" means away from the 
# solid cone, toward the open space. For a cone narrowing upward, the open space
# is both above AND outward at the base, but inward at the top.
# The blades should protrude along the OUTWARD normal but the X,Y extent must be capped.
#
# ROOT CAUSE OF ORIGINAL FAILURE: blades extended to r = 50 + 15*NR_out ≈ 63mm (radius)
# → diameter 126mm >> 100mm spec.
#
# TRUE FIX: Scale protrusion so max radius stays ≤ 50mm.
# At base: r_hub=50, radial protrusion = prot * NR_out.
# Allowed radial protrusion = 50 - 50 = 0 at base (no outward extension at base!).
# So at base, blades can only protrude UPWARD, not outward.
#
# FINAL APPROACH: Protrusion direction = pure +Z (upward off cone surface).
# This is actually correct for many centrifugal impeller designs where blades
# are defined by their height above the hub in the axial direction.

# We'll use PURE +Z protrusion direction.
# Blade profile at each station:
#   - Anchor point ON the cone surface (r_hub, angle, z)
#   - Profile extends from z_anchor to z_anchor + protrusion in Z
#   - Profile width = BLADE_T in tangential direction
#   - Profile is offset INWARD from cone surface by small amount (so blade is within r_hub)

# ─────────────────────────────────────────────
# 1. HUB – truncated cone via revolve
# ─────────────────────────────────────────────
hub_profile = (
    cq.Workplane("XZ")
    .moveTo(0.0, 0.0)
    .lineTo(BASE_R, 0.0)
    .lineTo(TOP_R, HUB_H)
    .lineTo(0.0, HUB_H)
    .close()
)
hub = hub_profile.revolve(360, (0, 0, 0), (0, 0, 1))

# ─────────────────────────────────────────────
# 2. BORE
# ─────────────────────────────────────────────
bore = (
    cq.Workplane("XY")
    .workplane(offset=-1.0)
    .circle(BORE_R)
    .extrude(HUB_H + 2.0)
)
hub = hub.cut(bore)

# ─────────────────────────────────────────────
# 3. BLADES
# Strategy: Each blade profile is a thin rectangle on the cone surface.
# The rectangle sits ON the cone surface and protrudes in +Z direction.
# Tangential width = BLADE_T. Z-height = protrusion at that station.
# The blade is positioned so its outer edge is flush with r_hub (or slightly inside).
# ─────────────────────────────────────────────

result_solid = hub

for b in range(N_BLADES):
    base_angle_rad  = b * (2.0 * math.pi / N_BLADES)
    twist_rad_total = math.radians(TWIST_DEG)
    half_t          = BLADE_T / 2.0

    wires = []

    for i in range(N_STATIONS):
        z_frac = i / float(N_STATIONS - 1)

        angle = base_angle_rad + twist_rad_total * z_frac
        prot  = PROTRUSION_BASE + (PROTRUSION_TOP - PROTRUSION_BASE) * z_frac

        z_base = z_frac * HUB_H
        r_hub  = BASE_R - (BASE_R - TOP_R) * z_frac

        # Cone surface point (the anchor — on the cone surface)
        cx = r_hub * math.cos(angle)
        cy = r_hub * math.sin(angle)
        cz = z_base

        # Tangential direction (in XY plane, perpendicular to radial)
        tx = -math.sin(angle)
        ty =  math.cos(angle)

        # Radial inward direction (toward axis) — to keep blade within hub footprint
        # We place the blade so it doesn't extend beyond r_hub radially
        # The blade is centered on the cone surface point radially
        # Radial outward unit vector
        rx = math.cos(angle)
        ry = math.sin(angle)

        # 4 corners of blade cross-section profile:
        # The profile sits on the cone surface and protrudes upward (+Z)
        # Corners in (tangential, Z) space centered on (cx, cy, cz):
        #   bottom edge: z = cz (on cone surface, embedded 0mm — we'll union clean)
        #   top edge:    z = cz + prot
        #   left/right:  ±half_t in tangential direction
        # To embed into hub for clean union: bottom edge goes to cz - 0 (cone surface)
        # We embed radially inward by a tiny amount to ensure connectivity
        embed_r = 1.0  # mm inward from cone surface

        # Bottom-left, bottom-right, top-right, top-left
        # "bottom" = on cone surface (z=cz), "top" = z=cz+prot
        # Radially: centered at r_hub, so x=cx,y=cy but shifted ±half_t tangentially
        # We also shift inward by embed_r/2 so blade root is inside cone surface
        p1 = (cx - half_t*tx - embed_r*rx, cy - half_t*ty - embed_r*ry, cz)
        p2 = (cx + half_t*tx - embed_r*rx, cy + half_t*ty - embed_r*ry, cz)
        p3 = (cx + half_t*tx - embed_r*rx, cy + half_t*ty - embed_r*ry, cz + prot)
        p4 = (cx - half_t*tx - embed_r*rx, cy - half_t*ty - embed_r*ry, cz + prot)

        wire = cq.Wire.makePolygon([
            cq.Vector(*p1),
            cq.Vector(*p2),
            cq.Vector(*p3),
            cq.Vector(*p4),
            cq.Vector(*p1),
        ])
        wires.append(wire)

    # Loft blade
    try:
        blade_solid = cq.Solid.makeLoft(wires, ruled=False)
        blade_wp    = cq.Workplane("XY").add(blade_solid)
        result_solid = result_solid.union(blade_wp)
    except Exception as e:
        print(f"Blade {b} smooth loft failed ({e}), trying ruled...")
        try:
            blade_solid = cq.Solid.makeLoft(wires, ruled=True)
            blade_wp    = cq.Workplane("XY").add(blade_solid)
            result_solid = result_solid.union(blade_wp)
        except Exception as e2:
            print(f"Blade {b} ruled loft also failed: {e2}")

# result_solid = complete impeller (hub cone + bore + 7 twisted blades)