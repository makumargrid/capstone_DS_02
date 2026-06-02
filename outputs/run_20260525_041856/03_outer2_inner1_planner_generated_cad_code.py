import cadquery as cq

# 1. THE WALL
# Acts as structural separator and precisely sets the Y=800, Z=650 bounds.
wall = (
    cq.Workplane("XY")
    .box(100, 800, 650, centered=(True, True, False))
    .edges("|Y and >Z").chamfer(10)
)

# 2. INDOOR UNIT (X < 0)
# Loft ensures exactly 45-degree slopes for safe, support-free printing.
indoor = (
    cq.Workplane("YZ")
    .workplane(offset=-40) # Embeds 10mm into the wall (X=-50)
    .center(0, 500)
    .rect(700, 200) # Rear face: Y [-350, 350], Z [400, 600]
    .workplane(offset=-160) # Moves to X=-200
    .center(0, 80)
    .rect(380, 40) # Front face: Y [-190, 190], Z [560, 600]
    .loft()
)

# Display panel on the front face
display = (
    cq.Workplane("XY")
    .workplane(offset=580)
    .center(-195, 0)
    .box(20, 100, 20, centered=(True, True, True))
)
indoor = indoor.union(display)

# 3. OUTDOOR UNIT (X > 0)
# Sits flush on the ground (Z=0) avoiding huge support gaps.
outdoor = (
    cq.Workplane("XY")
    .center(225, 0)
    .box(250, 700, 550, centered=(True, True, False)) # X [100, 350]
    .edges("|Z").chamfer(20)
)

# Fan Cutout (Diamond shape explicitly avoids flat unprintable ceilings)
fan_cutout = (
    cq.Workplane("YZ")
    .workplane(offset=350)
    .center(0, 300)
    .polygon(4, 380) # Diamond with 380mm diameter
    .extrude(-30)
)
outdoor = outdoor.cut(fan_cutout)

# 4. FAN ASSEMBLY
# Pyramidal Hub sweeps to a point to avoid horizontal cantilevers
hub = (
    cq.Workplane("YZ")
    .workplane(offset=319) # Embed 1mm into floor of cutout
    .center(0, 300)
    .polygon(4, 100)
    .workplane(offset=31) # Extrudes to X=350
    .polygon(4, 1) # Tiny tip
    .loft()
)

# Horizontal blade (Chamfered underneath for DFM printability)
blade1 = (
    cq.Workplane("YZ")
    .workplane(offset=319)
    .center(0, 300)
    .rect(360, 20)
    .extrude(20) # Extrudes to X=339
    .edges("<Z and >X")
    .chamfer(19) # Transforms the bottom into a safe 45-degree slope
)

# Vertical blade (Inherently safe since it builds up the back wall)
blade2 = (
    cq.Workplane("YZ")
    .workplane(offset=319)
    .center(0, 300)
    .rect(20, 360)
    .extrude(20)
)

# Vertical Grille Bars (Towers that embed into solid top/bottom to avoid bridges)
bars = None
for y_pos in [-120, -60, 0, 60, 120]:
    bar = (
        cq.Workplane("YZ")
        .workplane(offset=341)
        .center(y_pos, 300)
        .rect(10, 440) # Overextends in Z to anchor into the solid body
        .extrude(9) # Flush to X=350
    )
    if bars is None:
        bars = bar
    else:
        bars = bars.union(bar)

fan_assembly = hub.union(blade1).union(blade2).union(bars)
outdoor = outdoor.union(fan_assembly)

# 5. CONNECTING PIPE
# Diamond profile bridge connecting indoor and outdoor perfectly
pipe = (
    cq.Workplane("YZ")
    .workplane(offset=-100) # Starts inside indoor unit
    .center(0, 500)
    .polygon(4, 60)
    .extrude(250) # Ends securely inside outdoor unit at X=150
)

# 6. FINAL ASSEMBLY
result_solid = (
    wall
    .union(indoor)
    .union(outdoor)
    .union(pipe)
)