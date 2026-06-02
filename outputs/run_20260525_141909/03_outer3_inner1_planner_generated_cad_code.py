import cadquery as cq
import math

# ═══════════════════════════════════════════
# BOUNDING BOX TARGET
# X: -300 to +300 = 600mm
# Y: -100 to +300 = 400mm
# Z:    0 to +800 = 800mm
# ═══════════════════════════════════════════

# ───────────────────────────────────────────
# 1. WALL
#    X: -300..+300, Y: -50..+50, Z: 0..800
# ───────────────────────────────────────────
wall = (cq.Workplane("XY")
          .box(600.0, 100.0, 800.0)
          .translate((0, 0, 400.0))
       )

# ───────────────────────────────────────────
# 2. OUTDOOR UNIT BODY
#    X: -250..+250 (500mm), Y: +50..+290 (240mm), Z: +50..+650 (600mm)
# ───────────────────────────────────────────
ou_w   = 500.0
ou_d   = 240.0
ou_h   = 600.0
ou_cy  = 50.0 + ou_d / 2.0    # = 170.0
ou_cz  = 50.0 + ou_h / 2.0    # = 350.0

outdoor_body = (cq.Workplane("XY")
                  .box(ou_w, ou_d, ou_h)
                  .translate((0.0, ou_cy, ou_cz))
               )

# Grille slots on +X side face — horizontal slots, depth 25mm in X
num_slots = 16
slot_h    = 10.0
slot_gap  = 22.0
for i in range(num_slots):
    z0 = 70.0 + i * (slot_h + slot_gap)
    if z0 + slot_h > 630.0:
        break
    s = (cq.Workplane("XY")
           .box(28.0, ou_d - 60.0, slot_h)
           .translate((ou_w / 2.0 - 12.0, ou_cy, z0 + slot_h / 2.0))
        )
    outdoor_body = outdoor_body.cut(s)

# Compressor bump — fused onto back-bottom of outdoor unit (Y side toward wall)
bump = (cq.Workplane("XY")
          .box(100.0, 40.0, 100.0)
          .translate((-80.0, 70.0, 100.0))
       )
outdoor_body = outdoor_body.union(bump)

# ───────────────────────────────────────────
# 3. OUTDOOR FAN ASSEMBLY
#    Strictly Y: +290 to +300 (10mm total depth)
#    Fan axis along Y. Center XZ = (0, 500)
#    Fan front face (visible) at Y = +290
#    Fan back (into unit body) at Y = +300 — NO, reversed:
#    The fan protrudes OUT from the unit face at Y=+290
#    So fan occupies Y = +290 to +300 (outward = decreasing Y... wait)
#    Outdoor unit front face = Y = +290 (max Y of outdoor body)
#    Fan protrudes in +Y direction: Y = +290 to +300
# ───────────────────────────────────────────
fan_y_start = 290.0   # flush with outdoor unit front face
fan_y_end   = 300.0   # absolute maximum Y allowed
fan_depth   = fan_y_end - fan_y_start   # = 10mm
fan_cx      = 0.0
fan_cz      = 500.0
fan_tip_r   = 120.0   # fits within ±250 X with margin
hub_r       = 30.0
ring_thick  = 12.0
n_blades    = 5

# Fan housing ring — thin annular disk, 10mm deep in Y
# Outer radius = fan_tip_r + ring_thick = 132mm (fits in ±250)
fan_ring_outer = (cq.Workplane("XZ")
                    .circle(fan_tip_r + ring_thick)
                    .extrude(fan_depth)
                    .translate((fan_cx, fan_y_start, fan_cz))
                 )
fan_ring_inner = (cq.Workplane("XZ")
                    .circle(fan_tip_r + 2.0)
                    .extrude(fan_depth + 0.2)
                    .translate((fan_cx, fan_y_start - 0.1, fan_cz))
                 )
fan_housing = fan_ring_outer.cut(fan_ring_inner)

# Hub — cylinder along Y, depth = fan_depth
fan_hub = (cq.Workplane("XZ")
             .circle(hub_r)
             .extrude(fan_depth)
             .translate((fan_cx, fan_y_start, fan_cz))
          )

# Blades — 5 simple flat boxes, each 6mm thick in Y, within fan_depth
# Blade local space: long axis=X (radial), thin=Y (axial=6mm), span=Z (40mm)
# After rotation around Y they stay within Y: fan_y_start to fan_y_end
blade_len   = fan_tip_r - hub_r   # 90mm radial
blade_thick = 6.0                  # Y thickness — well within 10mm fan depth
blade_span  = 40.0                 # Z span

# Blade Y center = fan_y_start + fan_depth/2 = 295.0
blade_y_center = fan_y_start + fan_depth / 2.0  # 295.0

blades_solid = None
for i in range(n_blades):
    spin_deg = i * (360.0 / n_blades)

    # Build blade: long in X, thin in Y, span in Z
    # Place so radial center is at X = hub_r + blade_len/2
    blade = (cq.Workplane("XY")
               .box(blade_len, blade_thick, blade_span)
               .translate((hub_r + blade_len / 2.0, 0.0, 0.0))
            )

    # Pitch 35° around X axis (airfoil angle, stays within Y budget since
    # max Y displacement from pitch = blade_span/2 * sin(35°) ≈ 11.5mm
    # but blade_thick=6 centers it, net Y excursion < fan_depth/2 = 5mm
    # Use smaller pitch: 20° → sin(20°)*20=6.8mm → within 5mm... use 15°
    # sin(15°)*20=5.17mm — marginal. Keep blades flat (0° pitch) to guarantee Y budget
    # Pitch = 0 for strict Y compliance; visual angle from spin is sufficient
    blade = blade.rotate((0, 0, 0), (0, 1, 0), spin_deg)

    # Translate to fan center in world
    blade = blade.translate((fan_cx, blade_y_center, fan_cz))

    if blades_solid is None:
        blades_solid = blade
    else:
        blades_solid = blades_solid.union(blade)

fan_assembly = fan_hub.union(blades_solid).union(fan_housing)

# ───────────────────────────────────────────
# 4. INDOOR UNIT
#    X: -225..+225 (450mm), Y: -50..-100 (50mm), Z: +550..+750 (200mm)
# ───────────────────────────────────────────
iu_w  = 450.0
iu_d  =  50.0
iu_h  = 200.0
iu_cy = -50.0 - iu_d / 2.0    # = -75.0
iu_cz = 550.0 + iu_h / 2.0    # = 650.0

indoor_body = (cq.Workplane("XY")
                 .box(iu_w, iu_d, iu_h)
                 .translate((0, iu_cy, iu_cz))
              )

# Louver slots on -Y face
l_slot_h   = 8.0
l_slot_gap = 12.0
l_slot_w   = 380.0
l_slot_d   = 14.0

for i in range(7):
    z0 = 558.0 + i * (l_slot_h + l_slot_gap)
    if z0 + l_slot_h > 742.0:
        break
    lv = (cq.Workplane("XY")
            .box(l_slot_w, l_slot_d, l_slot_h)
            .translate((0, iu_cy - iu_d / 2.0 + l_slot_d / 2.0, z0 + l_slot_h / 2.0))
         )
    indoor_body = indoor_body.cut(lv)

# Air intake on top
intake = (cq.Workplane("XY")
            .box(360.0, 30.0, 10.0)
            .translate((0, iu_cy, 745.0))
         )
indoor_body = indoor_body.cut(intake)

# ───────────────────────────────────────────
# 5. CONNECTING PIPES
#    Y: -100 to +290, X=±50, Z=710
# ───────────────────────────────────────────
pipe_r   = 10.0
pipe_y1  = -100.0
pipe_y2  =  290.0
pipe_len = pipe_y2 - pipe_y1   # 390mm
pipe_z   = 710.0

pipe1 = (cq.Workplane("XZ")
           .circle(pipe_r)
           .extrude(pipe_len)
           .translate((-50, pipe_y1, pipe_z))
        )
pipe2 = (cq.Workplane("XZ")
           .circle(pipe_r)
           .extrude(pipe_len)
           .translate(( 50, pipe_y1, pipe_z))
        )
pipes = pipe1.union(pipe2)

# Pipe holes through wall
for px in [-50, 50]:
    wall = wall.cut(
        cq.Workplane("XZ")
          .circle(pipe_r + 2.0)
          .extrude(104.0)
          .translate((px, -52.0, pipe_z))
    )

# ───────────────────────────────────────────
# 6. FINAL ASSEMBLY
# ───────────────────────────────────────────
result_solid = (wall
                .union(outdoor_body)
                .union(fan_assembly)
                .union(indoor_body)
                .union(pipes)
               )