import cadquery as cq
import math

# ─────────────────────────────────────────
# HELPER: rotate a shape about an axis
# ─────────────────────────────────────────
def rotate_about_center(shape, axis, angle_deg):
    return shape.rotate((0,0,0), axis, angle_deg)

# ═══════════════════════════════════════════
# 1. WALL SECTION
# ═══════════════════════════════════════════
wall_w  = 400.0   # X
wall_t  = 80.0    # Y (thickness)
wall_h  = 300.0   # Z

wall = (cq.Workplane("XY")
          .box(wall_w, wall_t, wall_h)
          .translate((0, 0, wall_h/2))
       )

# ═══════════════════════════════════════════
# 2. OUTDOOR UNIT BODY  (Y positive side)
# ═══════════════════════════════════════════
ou_w  = 300.0   # X
ou_d  = 200.0   # Y depth (away from wall)
ou_h  = 250.0   # Z

# Body sits on ground: Z=0 to Z=250, Y=+40 to Y=+240
ou_cx = 0.0
ou_cy = wall_t/2 + ou_d/2   # = 40 + 100 = 140
ou_cz = ou_h/2               # = 125

outdoor_body = (cq.Workplane("XY")
                  .box(ou_w, ou_d, ou_h)
                  .translate((ou_cx, ou_cy, ou_cz))
               )

# Compressor bump on bottom-back (small box on back face)
bump = (cq.Workplane("XY")
          .box(80, 40, 80)
          .translate((60, wall_t/2 + ou_d - 20, 40))
       )
outdoor_body = outdoor_body.union(bump)

# Grille cuts on the side face (+X face) — horizontal slots
grille_cuts = None
slot_h    = 4.0
slot_gap  = 10.0
slot_d    = 180.0   # depth into body (X direction) — actually cutting in X
num_slots = 14

for i in range(num_slots):
    z_pos = 20 + i * (slot_h + slot_gap)
    cut_box = (cq.Workplane("XY")
                 .box(20, slot_d, slot_h)
                 .translate((ou_w/2 - 5, ou_cy, z_pos + slot_h/2))
              )
    if grille_cuts is None:
        grille_cuts = cut_box
    else:
        grille_cuts = grille_cuts.union(cut_box)

outdoor_body = outdoor_body.cut(grille_cuts)

# ═══════════════════════════════════════════
# 3. OUTDOOR FAN  (on +Y face of outdoor unit)
# ═══════════════════════════════════════════
fan_face_y   = wall_t/2 + ou_d   # = 240
fan_cx       = 0.0
fan_cz       = 170.0             # center height on face
fan_r        = 70.0              # blade tip radius
hub_r        = 18.0
hub_d        = 28.0              # hub depth (Y direction)
n_blades     = 5
blade_w      = 20.0              # blade width (arc width at mid)
blade_thick  = 4.0               # blade thickness (min 2mm, using 4)
blade_len    = fan_r - hub_r     # = 52mm

# Fan housing ring (annular cylinder) — represented as outer cylinder cut by inner
fan_housing_outer = (cq.Workplane("XZ")
                       .circle(fan_r + 12)
                       .extrude(18)
                       .translate((fan_cx, fan_face_y, fan_cz))
                    )
fan_housing_inner = (cq.Workplane("XZ")
                       .circle(fan_r + 2)
                       .extrude(20)
                       .translate((fan_cx, fan_face_y - 1, fan_cz))
                    )
fan_housing = fan_housing_outer.cut(fan_housing_inner)

# Hub
fan_hub = (cq.Workplane("XZ")
             .circle(hub_r)
             .extrude(hub_d)
             .translate((fan_cx, fan_face_y, fan_cz))
          )

# Blades — simple twisted rectangular boxes rotated around Z (fan axis = Y)
blades = None
for i in range(n_blades):
    angle = i * (360.0 / n_blades)
    angle_rad = math.radians(angle)

    # Blade: thin box, length along radial direction, pitched 35deg for airfoil look
    # Blade sits from hub_r to fan_r along radius
    blade_mid_r = hub_r + blade_len / 2.0

    # Create blade as a box in local space, then rotate
    # Local: long axis = X (radial), thin axis = Y (axial depth), width = Z
    blade_box = (cq.Workplane("XY")
                   .box(blade_len, blade_thick, blade_w)
                   .translate((hub_r + blade_len/2, 0, 0))
                )

    # Pitch the blade 35° around X axis (twist for airfoil effect)
    blade_box = blade_box.rotate((0,0,0),(1,0,0), 35)

    # Rotate around Y axis to fan angle position
    blade_box = blade_box.rotate((0,0,0),(0,1,0), angle)

    # Move to fan center position: fan is in XZ plane, spinning around Y
    # So radial direction is in XZ plane; we need to re-map:
    # Fan hub center = (fan_cx, fan_face_y + hub_d/2, fan_cz)
    hub_center_y = fan_face_y + hub_d/2

    blade_box = blade_box.translate((fan_cx, hub_center_y, fan_cz))

    if blades is None:
        blades = blade_box
    else:
        blades = blades.union(blade_box)

fan_assembly = fan_hub.union(blades).union(fan_housing)

# ═══════════════════════════════════════════
# 4. INDOOR UNIT BODY  (Y negative side)
# ═══════════════════════════════════════════
iu_w  = 280.0
iu_d  =  80.0
iu_h  = 100.0

# Sits high on wall interior: Z=200 to Z=300
iu_cy = -(wall_t/2 + iu_d/2)   # = -40 - 40 = -80
iu_cz = 200 + iu_h/2           # = 250

indoor_body = (cq.Workplane("XY")
                 .box(iu_w, iu_d, iu_h)
                 .translate((0, iu_cy, iu_cz))
              )

# Louver slots on front face (-Y face) — horizontal slots
louver_cuts = None
l_slot_h   = 5.0
l_slot_gap = 8.0
l_slot_w   = 240.0
l_slot_d   = 12.0
num_louvers = 6

for i in range(num_louvers):
    z_pos = 200 + 10 + i * (l_slot_h + l_slot_gap)
    cut_box = (cq.Workplane("XY")
                 .box(l_slot_w, l_slot_d, l_slot_h)
                 .translate((0, iu_cy - iu_d/2 + l_slot_d/2, z_pos + l_slot_h/2))
              )
    if louver_cuts is None:
        louver_cuts = cut_box
    else:
        louver_cuts = louver_cuts.union(cut_box)

indoor_body = indoor_body.cut(louver_cuts)

# Air intake slot on top of indoor unit
intake = (cq.Workplane("XY")
            .box(220, 50, 8)
            .translate((0, iu_cy, 300 - 4))
          )
indoor_body = indoor_body.cut(intake)

# ═══════════════════════════════════════════
# 5. CONNECTING PIPES  (through wall)
# ═══════════════════════════════════════════
pipe_r    = 8.0
pipe_y1   = iu_cy - iu_d/2   # indoor far face
pipe_y2   = fan_face_y        # outdoor far face
pipe_z    = 245.0

pipe1 = (cq.Workplane("XZ")
           .circle(pipe_r)
           .extrude(pipe_y2 - pipe_y1)
           .translate((-20, pipe_y1, pipe_z))
        )

pipe2 = (cq.Workplane("XZ")
           .circle(pipe_r)
           .extrude(pipe_y2 - pipe_y1)
           .translate((20, pipe_y1, pipe_z))
        )

pipes = pipe1.union(pipe2)

# Pipe holes through wall
wall = wall.cut(
    cq.Workplane("XZ").circle(pipe_r + 1).extrude(wall_t + 2).translate((-20, -wall_t/2 - 1, pipe_z))
)
wall = wall.cut(
    cq.Workplane("XZ").circle(pipe_r + 1).extrude(wall_t + 2).translate((20, -wall_t/2 - 1, pipe_z))
)

# ═══════════════════════════════════════════
# 6. ASSEMBLE EVERYTHING
# ═══════════════════════════════════════════
result_solid = (wall
                .union(outdoor_body)
                .union(fan_assembly)
                .union(indoor_body)
                .union(pipes)
               )