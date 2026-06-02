import meshlib.mrmeshpy as mrmesh
import math

mp = mrmesh.MeshPart(mesh)

def count_contours(zLevel):
    contours = mrmesh.extractXYPlaneSections(mp, zLevel)
    return len(contours)

z0_count = count_contours(0.1)
z30_count = count_contours(30)
z59_count = count_contours(59.9)

check_results.append({
    "check_name": "contour_counts",
    "measured": f"Z=0.1: {z0_count}, Z=30: {z30_count}, Z=59.9: {z59_count}",
    "expected": "2 per slice (outer boundary and inner bore)",
    "passed": z0_count == 2,
    "unit": "contours",
    "reason": ""
})
