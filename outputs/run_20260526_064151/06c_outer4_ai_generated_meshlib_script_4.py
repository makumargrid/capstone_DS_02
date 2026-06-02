
import meshlib.mrmeshpy as mrmesh
import math

# Test vertex access via vec_
pts = mesh.points
vec = pts.vec_
print(f"vec_ len: {len(vec)}")
print(f"first vert: {vec[0].x:.3f}, {vec[0].y:.3f}, {vec[0].z:.3f}")

# Test topology
topo = mesh.topology
valid_v = topo.getValidVerts()
vsize = topo.vertSize()
print(f"vertSize: {vsize}")

# Test iterating via VertId
vid = mrmesh.VertId(0)
v = pts[vid]
print(f"pts[VertId(0)]: {v.x:.3f}, {v.y:.3f}, {v.z:.3f}")

# Test holes
nh = topo.findNumHoles()
print(f"numHoles: {nh}")

check_results.append({"check_name": "api_probe", "measured": len(vec), "expected": 1505, "passed": len(vec) > 0, "unit": "count", "reason": f"vertex vec_ length={len(vec)}, vertSize={vsize}, numHoles={nh}"})
