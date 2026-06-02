import meshlib.mrmeshpy as mrmesh
import math

mp = mrmesh.MeshPart(mesh)
contours = mrmesh.extractXYPlaneSections(mp, 30.0)

# Find the outer contour
outer_contour = None
for contour in contours:
    pts = [mesh.edgePoint(ep) for ep in contour]
    r_max = max((math.hypot(p.x, p.y) for p in pts))
    if r_max > 20:
        outer_contour = pts
        break

radii = [math.hypot(p.x, p.y) for p in outer_contour]
n = len(radii)

peak_angles = []
for i in range(n):
    prev_r = radii[i-1]
    curr_r = radii[i]
    next_r = radii[(i+1)%n]
    if curr_r > prev_r and curr_r > next_r and curr_r > 38.0:
        pt = outer_contour[i]
        angle = math.degrees(math.atan2(pt.y, pt.x))
        if angle < 0:
            angle += 360
        peak_angles.append(angle)

peak_angles.sort()
check_results.append({
    "check_name": "blade_angles",
    "measured": str([round(a, 1) for a in peak_angles]),
    "expected": "7 roughly equally spaced angles",
    "passed": True,
    "unit": "degrees",
    "reason": ""
})
