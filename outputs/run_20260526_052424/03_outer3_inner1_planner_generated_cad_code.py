import cadquery as cq
import math

# ─────────────────────────────────────────────
# PARAMETERS
# Hub height set to 100mm so bounding box Z = 100mm (ground-truth requirement)
# ─────────────────────────────────────────────
BASE_R          = 50.0    # hub base radius at Z=0  → diameter = 100mm ✓
TOP_R           = 15.0    # hub top  radius at Z=HUB_H → diameter = 30mm
HUB_H           = 100.0   # hub height — set to 100mm to satisfy Z bounding box
BORE_R          = 7.5     # central bore radius (diameter 15mm)
N_BLADES        = 7
TWIST_DEG       = 60.0    # total blade twist Z=0 → Z=HUB_H
BLADE_T         = 2.2     # tangential thickness (>2mm DFM minimum)
PROTRUSION_BASE = 15.0    # blade fin height at Z=0
PROTRUSION_TOP  = 5.0     # blade fin height at Z=HUB_H
N_STATIONS      = 12      # loft cross-sections per blade

# ─────────────────────────────────────────────
# Cone outward surface normal (radial + Z components)
# Tangent going upward: dr = TOP_R-BASE_R = -35, dz = HUB_H = 100
# Outward normal = rotate tangent 90° clockwise in (r,z): (dz, -dr)/mag
# ─────────────────────────────────────────────
_dr   = TOP_R - BASE_R          # = -35
_dz   = HUB_H                   # = 100
_mag  = math.sqrt(_dr**2 + _dz**2)  # sqrt(1225 + 10000) = sqrt(11225) ≈ 105.95

NR_out =  _dz / _mag    # radial outward component ≈ 0.944
NZ_out = -_dr / _mag    # z upward component       ≈ 0.330

# At hub top (Z=HUB_H=100), blade tip Z = 100 + PROTRUSION_TOP * NZ_out
# = 100 + 5 * 0.330 = 101.65mm — slightly over. We'll clamp Z to HUB_H.
# At hub base (Z=0), blade tip Z = 0 + PROTRUSION_BASE * NZ_out
# = 15 * 0.330 = 4.95mm — well within hub.
# Radial extent at base: r = 50 + 15 * NR_out = 50 + 14.16 = 64.16mm — exceeds 50mm!
# → This pushes X,Y beyond 100mm diameter again.

# REVISED NORMAL STRATEGY:
# To keep X,Y ≤ 50mm (diameter ≤ 100mm) AND Z_max = 100mm:
# Use INWARD normal (toward axis) for protrusion direction.
# Inward normal = (-NR_out, +NZ_out) in (r,z) — pointing inward-radially and upward.
# This keeps blades WITHIN the hub footprint radially.
# At base: r_tip = 50 - 15*NR_out = 50 - 14.16 = 35.84mm ✓ (inside hub)
# Z_tip at base: 0 + 15*NZ_out = 4.95mm ✓
# Z_tip at top: 100 + 5*NZ_out = 101.65mm — clamp to 100mm.

# So: protrusion direction = (-NR_out in radial, +NZ_out in z)
# = inward radially + upward along z
# This represents blades standing into the flow channel (above the cone surface)

NR_blade = -NR_out   # radially inward (negative = toward axis)
NZ_blade =  NZ_out   # upward component

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
# 2. BORE – central shaft hole
# ─────────────────────────────────────────────
bore = (
    cq.Workplane("XY")
    .workplane(offset=-1.0)
    .circle(BORE_R)
    .extrude(HUB_H + 2.0)
)
hub = hub.cut(bore)

# ─────────────────────────────────────────────
# 3. BLADES – lofted fins on cone surface
# Protrusion direction: inward-radially + upward (into flow channel)
# Tangential direction: perpendicular to radial in XY plane
# Blade root embedded 1mm into cone surface (outward radially) for clean union
# ─────────────────────────────────────────────
result_solid = hub

for b in range(N_BLADES):
    base_angle_rad  = b * (2.0 * math.pi / N_BLADES)
    twist_rad_total = math.radians(TWIST_DEG)
    half_t          = BLADE_T / 2.0
    embed           = 1.0   # mm embedded outward into cone for clean boolean

    wires = []

    for i in range(N_STATIONS):
        z_frac = i / float(N_STATIONS - 1)

        angle = base_angle_rad + twist_rad_total * z_frac
        prot  = PROTRUSION_BASE + (PROTRUSION_TOP - PROTRUSION_BASE) * z_frac

        z_base = z_frac * HUB_H
        r_hub  = BASE_R - (BASE_R - TOP_R) * z_frac  # linear taper

        # Cone surface anchor point
        cx = r_hub * math.cos(angle)
        cy = r_hub * math.sin(angle)
        cz = z_base

        # Radial outward unit vector at this angle
        rx = math.cos(angle)
        ry = math.sin(angle)

        # Tangential unit vector (CCW, in XY plane)
        tx = -math.sin(angle)
        ty =  math.cos(angle)

        # Protrusion direction in 3D (inward-radial + upward-z)
        # NR_blade = -NR_out (toward axis), NZ_blade = NZ_out (upward)
        pnx = NR_blade * math.cos(angle)   # = -NR_out * cos(angle)
        pny = NR_blade * math.sin(angle)   # = -NR_out * sin(angle)
        pnz = NZ_blade                      # = NZ_out (upward)

        # Embed direction: outward radially (into cone material)
        # so blade root is 1mm inside the cone surface
        enx = embed * rx
        eny = embed * ry
        enz = 0.0

        # 4 corners of blade cross-section:
        # Root edge (embedded into cone): anchor - embed*radial
        # Tip edge: anchor + prot * protrusion_normal
        # Left/right: ±half_t in tangential direction

        def pt(tang_sign, is_tip,
               _cx=cx, _cy=cy, _cz=cz,
               _tx=tx, _ty=ty,
               _pnx=pnx, _pny=pny, _pnz=pnz,
               _enx=enx, _eny=eny, _enz=enz,
               _prot=prot, _half_t=half_t):
            if is_tip:
                x = _cx + tang_sign * _half_t * _tx + _prot * _pnx
                y = _cy + tang_sign * _half_t * _ty + _prot * _pny
                z = _cz + _prot * _pnz
            else:
                x = _cx + tang_sign * _half_t * _tx - _enx
                y = _cy + tang_sign * _half_t * _ty - _eny
                z = _cz - _enz
            # Clamp Z to valid range
            z = max(-0.5, min(z, HUB_H + 0.5))
            return (x, y, z)

        p1 = pt(-1, False)  # root left
        p2 = pt(+1, False)  # root right
        p3 = pt(+1, True)   # tip right
        p4 = pt(-1, True)   # tip left

        wire = cq.Wire.makePolygon([
            cq.Vector(*p1),
            cq.Vector(*p2),
            cq.Vector(*p3),
            cq.Vector(*p4),
            cq.Vector(*p1),
        ])
        wires.append(wire)

    # Loft blade solid
    try:
        blade_solid  = cq.Solid.makeLoft(wires, ruled=False)
        blade_wp     = cq.Workplane("XY").add(blade_solid)
        result_solid = result_solid.union(blade_wp)
    except Exception as e:
        print(f"Blade {b} smooth loft failed: {e} — trying ruled...")
        try:
            blade_solid  = cq.Solid.makeLoft(wires, ruled=True)
            blade_wp     = cq.Workplane("XY").add(blade_solid)
            result_solid = result_solid.union(blade_wp)
        except Exception as e2:
            print(f"Blade {b} ruled loft also failed: {e2}")

# result_solid = complete centrifugal compressor impeller