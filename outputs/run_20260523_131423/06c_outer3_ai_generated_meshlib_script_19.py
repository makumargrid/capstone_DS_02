import meshlib.mrmeshpy as mrmesh
import math

mp = mrmesh.MeshPart(mesh)

def get_blade_angles(zLevel, threshold_r):
    contours = mrmesh.extractXYPlaneSections(mp, zLevel)
    outer_contour = None
    for contour in contours:
        pts = [mesh.edgePoint(ep) for ep in contour]
        r_max = max((math.hypot(p.x, p.y) for p in pts))
        if r_max > 20:
            outer_contour = pts
            break
            
    radii = [math.hypot(p.x, p.y) for p in outer_contour]
    n = len(radii)
    angles = []
    for i in range(n):
        prev_r = radii[i-1]
        curr_r = radii[i]
        next_r = radii[(i+1)%n]
        if curr_r > prev_r and curr_r > next_r and curr_r > threshold_r:
            pt = outer_contour[i]
            a = math.degrees(math.atan2(pt.y, pt.x))
            if a < 0: a += 360
            angles.append(a)
            
    # merge close peaks (within 10 deg)
    angles.sort()
    merged = []
    if angles:
        curr_grp = [angles[0]]
        for a in angles[1:]:
            if a - curr_grp[-1] < 10:
                curr_grp.append(a)
            else:
                merged.append(sum(curr_grp)/len(curr_grp))
                curr_grp = [a]
        # check wrap-around
        if merged and (360 - curr_grp[-1] + merged[0]) < 10:
            merged[0] = (merged[0] + curr_grp[-1] - 360) / 2
        else:
            merged.append(sum(curr_grp)/len(curr_grp))
    return sorted(merged)

angles_15 = get_blade_angles(15.0, 48.0)
angles_45 = get_blade_angles(45.0, 25.0)

diffs = []
for a1, a2 in zip(angles_15, angles_45):
    diff = a2 - a1
    if diff < -180: diff += 360
    elif diff > 180: diff -= 360
    diffs.append(diff)

avg_diff = sum(diffs)/len(diffs) if diffs else 0
total_twist_est = avg_diff * (60.0 / 30.0)

check_results.append({
    "check_name": "blade_twist",
    "measured": abs(total_twist_est),
    "expected": 60.0,
    "passed": abs(abs(total_twist_est) - 60.0) < 10.0,
    "unit": "degrees",
    "reason": f"Measured {avg_diff:.1f} deg twist between Z=15 and Z=45. Extrapolated to 60mm."
})
