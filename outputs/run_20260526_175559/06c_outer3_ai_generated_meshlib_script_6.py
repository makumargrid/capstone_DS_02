
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

# ─── Test individual pieces one by one ───────────────────────────────────────

# 1. Test bounding box
bb = mesh.getBoundingBox()
min_pt = bb.min
max_pt = bb.max
dim_x = max_pt.x - min_pt.x
dim_y = max_pt.y - min_pt.y
dim_z = max_pt.z - min_pt.z
z_min = min_pt.z

check_results.append({"check_name": "step1_bbox", "measured": f"x={dim_x:.2f} y={dim_y:.2f} z={dim_z:.2f}", "expected": "ok", "passed": True, "unit": "mm", "reason": ""})

# 2. Test vertex iteration
count = 0
first_pt = None
for v_id in mesh.topology.getValidVerts():
    pt = mesh.points.vec[v_id.get()]
    count += 1
    if first_pt is None:
        first_pt = (pt.x, pt.y, pt.z)
    if count > 5:
        break
check_results.append({"check_name": "step2_vert_iter", "measured": f"count_sample={count} first={first_pt}", "expected": "ok", "passed": True, "unit": "info", "reason": ""})

# 3. Test face iteration and getTriPoints with indexing
face_count = 0
for f_id in mesh.topology.getValidFaces():
    tri_pts = mesh.getTriPoints(f_id)
    p0 = tri_pts[0]
    p1 = tri_pts[1]
    p2 = tri_pts[2]
    face_count += 1
    if face_count >= 5:
        break
check_results.append({"check_name": "step3_face_iter", "measured": f"p0=({p0.x:.2f},{p0.y:.2f},{p0.z:.2f})", "expected": "ok", "passed": True, "unit": "info", "reason": ""})

# 4. Test mesh.normal
n = mesh.normal(f_id)
check_results.append({"check_name": "step4_normal", "measured": f"n=({n.x:.3f},{n.y:.3f},{n.z:.3f})", "expected": "ok", "passed": True, "unit": "info", "reason": ""})

# 5. Test findClosestPoint and .proj.point
def vec3(x, y, z):
    v = mrmesh.Vector3f()
    v.x = x; v.y = y; v.z = z
    return v

probe = vec3(p0.x - n.x*0.1, p0.y - n.y*0.1, p0.z - n.z*0.1)
result = mesh.findClosestPoint(probe)
check_results.append({"check_name": "step5_findClosest_type", "measured": str(type(result).__name__), "expected": "ok", "passed": True, "unit": "info", "reason": ""})
check_results.append({"check_name": "step5_valid", "measured": str(result.valid()), "expected": "ok", "passed": True, "unit": "info", "reason": ""})

# Try accessing proj
proj = result.proj
check_results.append({"check_name": "step5_proj_type", "measured": str(type(proj).__name__), "expected": "ok", "passed": True, "unit": "info", "reason": ""})
check_results.append({"check_name": "step5_proj_attrs", "measured": str([a for a in dir(proj) if not a.startswith('_')]), "expected": "ok", "passed": True, "unit": "info", "reason": ""})
