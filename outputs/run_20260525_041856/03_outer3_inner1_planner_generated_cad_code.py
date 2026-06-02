import cadquery as cq

# 1. THE WALL (Exactly hits Y=800 and Z=650 limits)
wall = (
    cq.Workplane("XY")
    .box(200, 800, 650, centered=(True, True, False))
)

# 2. INDOOR UNIT (Extruded wedge perfectly reaching exactly X=-425)
indoor = (
    cq.Workplane("XZ")
    .polyline([(-50, 200), (-425, 600), (-50, 600)])
    .close()
    .extrude(300, both=True) # Extrudes symmetrically to Y [-300, 300]
)

# 3. OUTDOOR UNIT BODY (Perfectly reaching exactly X=425)
outdoor = (
    cq.Workplane("XY")
    .center(237.5, 0)
    .box(375, 700, 500, centered=(True, True, False)) # X spans [50, 425]
)

# Cutout: Diamond hole avoids flat ceilings for robust FDM
cutout = (
    cq.Workplane("YZ")
    .workplane(offset=425)
    .center(0, 250)
    .polygon(4, 400) # 4 sides = Diamond (radius 200)
    .extrude(-75)    # Cuts deep back to X=350
)
outdoor = outdoor.cut(cutout)

# 4. FAN ASSEMBLY
# Pyramidal Hub
hub = (
    cq.Workplane("YZ")
    .workplane(offset=349) # Embed 1mm deep into back face to avoid coplanar errors
    .center(0, 250)
    .polygon(4, 120)
    .workplane(offset=51)  # Reaches to X=400
    .polygon(4, 2)
    .loft()
)

# Horizontal Fin (Sketched directly with a 45-degree slope underneath)
h_fin = (
    cq.Workplane("XZ")
    .polyline([(340, 200), (380, 240), (380, 260), (340, 260)])
    .close()
    .extrude(190, both=True) # Y spans [-190, 190]
)

# Vertical Fin (Simple straight tower structure)
v_fin = (
    cq.Workplane("XZ")
    .center(360, 250)
    .rect(40, 400)          # X width 40, Z height 400
    .extrude(10, both=True) # Y thickness 20
)

# Grille Bars (Sub-flush bounds to categorically prevent face self-intersections)
bars = None
for y_pos in [-120, -60, 0, 60, 120]:
    bar = (
        cq.Workplane("XZ")
        .center(414, 250)       # Sub-flush front face (X=424 instead of 425)
        .rect(20, 420)          # Avoids sharing Z=0 or Z=500 planes (Z=[40, 460])
        .extrude(5, both=True)  # Y thickness 10
    )
    # Offset each bar into its correct Y position by translating
    bar = bar.translate((0, y_pos, 0))
    
    if bars is None:
        bars = bar
    else:
        bars = bars.union(bar)

# Merge all outdoor components safely
outdoor = outdoor.union(hub).union(h_fin).union(v_fin).union(bars)

# 5. CONNECTING PIPE
# Central diamond pipe bridges components natively
pipe = (
    cq.Workplane("YZ")
    .workplane(offset=-150)
    .center(0, 400)
    .polygon(4, 100) # Diamond to avoid overhead overhang
    .extrude(300)    # Runs through entire wall from X=-150 to X=150
)

# 6. FINAL ASSEMBLY
result_solid = wall.union(indoor).union(outdoor).union(pipe)