import meshlib.mrmeshpy as mrmesh
import math

mp = mrmesh.MeshPart(mesh)

contours = mrmesh.extractXYPlaneSections(mp, 15.0)

info = []
for i, contour in enumerate(contours):
    pts = [mesh.edgePoint(ep) for ep in contour]
    r_min = min((math.hypot(p.x, p.y) for p in pts))
    r_max = max((math.hypot(p.x, p.y) for p in pts))
    info.append(f"C{i}: R_min={r_min:.2f}, R_max={r_max:.2f}")

check_results.append({
    "check_name": "z15_contours_info",
    "measured": " | ".join(info),
    "expected": "",
    "passed": True,
    "unit": "",
    "reason": ""
})
