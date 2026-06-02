import meshlib.mrmeshpy as mrmesh
import math

mp = mrmesh.MeshPart(mesh)

contours = mrmesh.extractXYPlaneSections(mp, 0.1)

contour_info = []
for i, contour in enumerate(contours):
    pts = [mesh.edgePoint(ep) for ep in contour]
    r_min = min((math.hypot(p.x, p.y) for p in pts))
    r_max = max((math.hypot(p.x, p.y) for p in pts))
    contour_info.append(f"C{i}: {len(pts)} pts, R_min={r_min:.2f}, R_max={r_max:.2f}")

check_results.append({
    "check_name": "z0_contours_info",
    "measured": " | ".join(contour_info),
    "expected": "2 contours",
    "passed": len(contours) == 2,
    "unit": "",
    "reason": ""
})
