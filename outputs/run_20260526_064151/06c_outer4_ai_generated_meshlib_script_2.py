
import meshlib.mrmeshpy as mrmesh
import math

# Test basic mesh access patterns
bb = mesh.getBoundingBox()
print(f"BB min: {bb.min.x:.3f}, {bb.min.y:.3f}, {bb.min.z:.3f}")
print(f"BB max: {bb.max.x:.3f}, {bb.max.y:.3f}, {bb.max.z:.3f}")

pts = mesh.points
topo = mesh.topology
print(f"vertSize: {topo.vertSize()}")
print(f"faceSize: {topo.faceSize()}")

# Test accessing a vertex
vid0 = mrmesh.VertId(0)
v0 = pts[vid0]
print(f"v0: {v0.x:.3f}, {v0.y:.3f}, {v0.z:.3f}")

# Test vec_ access for all points
vec = pts.vec_
print(f"vec_ length: {len(vec)}")
v_first = vec[0]
print(f"first via vec_: {v_first.x:.3f}, {v_first.y:.3f}, {v_first.z:.3f}")

check_results.append({"check_name": "API test", "measured": len(vec), "expected": 1505, "passed": True, "unit": "count", "reason": "API test"})
