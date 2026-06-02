
import meshlib.mrmeshpy as mrmesh
import math

# Test vertex iteration step by step
pts = mesh.points
topo = mesh.topology
vsize = topo.vertSize()

# Try vec_ access
vec = pts.vec_
v0 = vec[0]
x0 = v0.x
y0 = v0.y
z0 = v0.z

check_results.append({"check_name": "vec_access", "measured": f"{x0:.3f},{y0:.3f},{z0:.3f}", "expected": "some vertex", "passed": True, "unit": "mm", "reason": "test"})
