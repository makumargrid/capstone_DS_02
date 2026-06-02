import meshlib.mrmeshpy as mrmesh
import math

mp = mrmesh.MeshPart(mesh)
contours = mrmesh.extractXYPlaneSections(mp, 30.0)

# Find the outer contour (not the bore)
outer_contour = None
for contour in contours:
    pts = [mesh.edgePoint(ep) for ep in contour]
    r_max = max((math.hypot(p.x, p.y) for p in pts))
    if r_max > 20:
        outer_contour = pts
        break

# Smooth R values slightly to avoid noise, then count peaks
radii = [math.hypot(p.x, p.y) for p in outer_contour]
peaks = 0
n = len(radii)
for i in range(n):
    prev_r = radii[i-1]
    curr_r = radii[i]
    next_r = radii[(i+1)%n]
    if curr_r > prev_r and curr_r > next_r and curr_r > 38.0:  # Peak must be near R_max
        peaks += 1

check_results.append({
    "check_name": "blade_count",
    "measured": peaks,
    "expected": 7,
    "passed": peaks == 7,
    "unit": "blades",
    "reason": "Counted radial peaks at mid-height (Z=30)"
})
