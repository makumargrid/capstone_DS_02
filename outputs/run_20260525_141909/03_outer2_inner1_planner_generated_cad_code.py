import cadquery as cq
import math

# ═══════════════════════════════════════════
# DIMENSIONS OVERVIEW
# X: -300 to +300  = 600mm
# Y: -100 to +300  = 400mm
# Z:    0 to +800  = 800mm
# ═══════════════════════════════════════════

# ───────────────────────────────────────────
# 1. WALL  (100mm thick, full height/width)
# ───────────────────────────────────────────
wall_w  = 600.0
wall_t  = 100.0
wall_h  = 800.0

wall = (cq.Workplane("XY")
          .box(wall_w, wall_t, wall_h)
          .translate((0, 0, wall_h / 2))
       )

# ───────────────────────────────────────────
# 2. OUTDOOR UNIT BODY
#    X: -250 to +250 (500mm wide)
#    Y: +50 to +300  (250mm deep)
#    Z: +50 to +650  (600mm tall)
# ───────────────────────────────────────────
ou_w  = 500.0
ou_d  = 250.0
ou_h  = 600.0
ou_cx = 0.0
ou_cy = 50.0 + ou_d / 2    # = 175.0
ou_cz = 50.0 + ou_h / 2    # = 350.0

outdoor_body = (cq.Workplane("XY")
                  .box(ou_w, ou_d, ou_h)
                  .translate((ou_cx, ou_cy, ou_cz))
               )

# Grille slots on +X side face — horizontal slots cut from outside
slot_h    = 10.0
slot_gap  = 18.0
slot_d    = 30.0   # how deep into body in X
num_slots = 18

grille_list = []
for i in range(num_slots):
    z_pos = 60.0 + i * (slot_h + slot_gap)
    if z_pos + slot_h > 640.0:
        break
    s = (cq.Workplane("XY")
           .box(slot_d + 2, ou_d - 40, slot_h)
           .translate((ou_w / 2 - slot_d / 2 + 1, ou_cy, z_pos + slot_h / 2))
        )
    grille_list.append(s)

for s in grille_list:
    outdoor_body = outdoor_body.cut(s)

# Compressor bump — small box on outdoor unit bottom-back interior side
bump = (cq.Workplane("XY")
          .box(120, 60, 120)
          .translate((-100, 50.0 + ou_d - 30, 110))
       )
outdoor_body = outdoor_body.union(bump)

# ───────────────────────────────────────────
# 3. OUTDOOR FAN  (on +Y face at Y=+300)
#    Fan axis = Y, face center = (0, 300, 500)
# ───────────────────────────────────────────
fan_face_y = 300.0
fan_cx     = 0.0
fan_cz     = 500.0      # fan center height (upper portion of outdoor unit)
fan_tip_r  = 140.0      # blade tip radius
hub_r      = 35.0
hub_depth  = 50.0       # hub extrudes outward in +Y
ring_thick = 15.0       # housing ring radial thickness
ring_depth = 25.0       # housing ring axial depth
n_blades   = 5

# Fan housing ring (annular) — in XZ plane, extruded in Y
fan_ring_outer = (cq.Workplane("XZ")
                    .circle(fan_tip_r + ring_thick)
                    .extrude(ring_depth)
                    .translate((fan_cx, fan_face_y, fan_cz))
                 )
fan_ring_inner = (cq.Workplane("XZ")
                    .circle(fan_tip_r + 2)
                    .extrude(ring_depth + 2)
                    .translate((fan_cx, fan_face_y - 1, fan_cz))
                 )
fan_housing = fan_ring_outer.cut(fan_ring_inner)

# Hub — cylinder along Y axis
fan_hub = (cq.Workplane("XZ")
             .circle(hub_r)
             .extrude(hub_depth)
             .translate((fan_cx, fan_face_y, fan_cz))
          )

# Blades — 5 blades, each a thin box rotated in XZ plane
# Each blade: length=105mm (hub_r to tip), thickness=6mm, width=50mm
# Pitched 40° around blade long axis for airfoil look
blade_len   = fan_tip_r - hub_r   # 105mm
blade_thick = 6.0
blade_width = 50.0

blades_solid = None
for i in range(n_blades):
    spin_angle = i * (360.0 / n_blades)   # rotation around Y (fan axis)

    # Create blade in local space:
    # Long axis along X (radial), thickness in Y (axial), width in Z
    blade = (cq.Workplane("XY")
               .box(blade_len, blade_thick, blade_width)
               .translate((hub_r + blade_len / 2.0, blade_thick / 2.0, 0))
            )

    # Pitch 40° around local X axis (creates airfoil sweep angle)
    blade = blade.rotate((hub_r, 0, 0), (hub_r + 1, 0, 0), 40)

    # Spin around Y axis to blade position
    blade = blade.rotate((0, 0, 0), (0, 1, 0), spin_angle)

    # Move to fan center in world space
    blade = blade.translate((fan_cx, fan_face_y + hub_depth / 2.0, fan_cz))

    if blades_solid is None:
        blades_solid = blade
    else:
        blades_solid = blades_solid.union(blade)

fan_assembly = fan_hub.union(blades_solid).union(fan_housing)

# ───────────────────────────────────────────
# 4. INDOOR UNIT
#    X: -225 to +225 (450mm wide)
#    Y: -50 to -100  (50mm deep)
#    Z: +550 to +750 (200mm tall)
# ───────────────────────────────────────────
iu_w  = 450.0
iu_d  =  50.0
iu_h  = 200.0
iu_cy = -50.0 - iu_d / 2    # = -75.0
iu_cz = 550.0 + iu_h / 2    # = 650.0

indoor_body = (cq.Workplane("XY")
                 .box(iu_w, iu_d, iu_h)
                 .translate((0, iu_cy, iu_cz))
              )

# Louver slots on -Y face (front of indoor unit facing room)
l_slot_h   = 8.0
l_slot_gap = 12.0
l_slot_w   = 380.0
l_slot_d   = 15.0
num_louvers = 8

louver_list = []
for i in range(num_louvers):
    z_pos = 555.0 + i * (l_slot_h + l_slot_gap)
    if z_pos + l_slot_h > 745.0:
        break
    lv = (cq.Workplane("XY")
            .box(l_slot_w, l_slot_d, l_slot_h)
            .translate((0, iu_cy - iu_d / 2.0 + l_slot_d / 2.0, z_pos + l_slot_h / 2.0))
         )
    louver_list.append(lv)

for lv in louver_list:
    indoor_body = indoor_body.cut(lv)

# Air intake slot on top face of indoor unit
intake = (cq.Workplane("XY")
            .box(360, 30, 10)
            .translate((0, iu_cy, 750.0 - 5.0))
          )
indoor_body = indoor_body.cut(intake)

# ───────────────────────────────────────────
# 5. CONNECTING PIPES
#    Full Y span: -100 to +300 = 400mm
#    At X=±50, Z=710
# ───────────────────────────────────────────
pipe_r  = 10.0
pipe_y1 = -100.0
pipe_y2 =  300.0
pipe_len = pipe_y2 - pipe_y1   # 400mm
pipe_z  = 710.0

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

# Cut pipe holes through wall
wall = wall.cut(
    cq.Workplane("XZ")
      .circle(pipe_r + 2)
      .extrude(wall_t + 4)
      .translate((-50, -wall_t / 2 - 2, pipe_z))
)
wall = wall.cut(
    cq.Workplane("XZ")
      .circle(pipe_r + 2)
      .extrude(wall_t + 4)
      .translate(( 50, -wall_t / 2 - 2, pipe_z))
)

# ───────────────────────────────────────────
# 6. ASSEMBLE
# ───────────────────────────────────────────
result_solid = (wall
                .union(outdoor_body)
                .union(fan_assembly)
                .union(indoor_body)
                .union(pipes)
               )