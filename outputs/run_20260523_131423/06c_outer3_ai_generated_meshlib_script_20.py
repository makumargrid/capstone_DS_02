import meshlib.mrmeshpy as mrmesh
import math

mp = mrmesh.MeshPart(mesh)
contours = mrmesh.extractXYPlaneSections(mp, 30.0)

outer_contour = None
for contour in contours:
    pts = [mesh.edgePoint(ep) for ep in contour]
    r_max = max((math.hypot(p.x, p.y) for p in pts))
    if r_max > 20:
        outer_contour = pts
        break

widths = []
radii = [math.hypot(p.x, p.y) for p in outer_contour]
n = len(radii)

for i in range(n):
    if radii[i] > 38.0 and radii[i-1] <= 38.0:
        # rising edge
        j = i
        while radii[j] > 38.0:
            j = (j + 1) % n
            if j == i: break
        # falling edge is j-1
        pt_start = outer_contour[i]
        pt_end = outer_contour[(j-1)%n]
        w = math.hypot(pt_end.x - pt_start.x, pt_end.y - pt_start.y)
        widths.append(w)

check_results.append({
    "check_name": "blade_thickness_z30",
    "measured": sum(widths)/len(widths) if widths else 0,
    "expected": 2.0,
    "passed": widths and abs((sum(widths)/len(widths)) - 2.0) < 0.5,
    "unit": "mm",
    "reason": "Measured blade chord width at R=38 on Z=30 slice"
})
