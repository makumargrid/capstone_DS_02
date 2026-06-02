import meshlib.mrmeshpy as mrmesh
import math

mp = mrmesh.MeshPart(mesh)

contour_info = []
for z in [30, 59.9]:
    contours = mrmesh.extractXYPlaneSections(mp, z)
    info = []
    for i, contour in enumerate(contours):
        pts = [mesh.edgePoint(ep) for ep in contour]
        r_min = min((math.hypot(p.x, p.y) for p in pts))
        r_max = max((math.hypot(p.x, p.y) for p in pts))
        info.append(f"C{i}: {len(pts)} pts, R_min={r_min:.2f}, R_max={r_max:.2f}")
    contour_info.append(f"Z={z}: " + " | ".join(info))

check_results.append({
    "check_name": "upper_contours_info",
    "measured": "\n".join(contour_info),
    "expected": "",
    "passed": True,
    "unit": "",
    "reason": ""
})
