import meshlib.mrmeshpy as mrmesh
import math

mp = mrmesh.MeshPart(mesh)

def analyze_slice(zLevel):
    contours = mrmesh.extractXYPlaneSections(mp, zLevel)
    radii = []
    for contour in contours:
        for ep in contour:
            pt = mesh.edgePoint(ep)
            r = math.hypot(pt.x, pt.y)
            radii.append(r)
    if not radii:
        return None, None
    return min(radii), max(radii)

z0 = analyze_slice(0.1)
z30 = analyze_slice(30)
z59 = analyze_slice(59.9)

check_results.append({
    "check_name": "slice_radii",
    "measured": f"Z=0.1: {z0}, Z=30: {z30}, Z=59.9: {z59}",
    "expected": "",
    "passed": True,
    "unit": "",
    "reason": ""
})
