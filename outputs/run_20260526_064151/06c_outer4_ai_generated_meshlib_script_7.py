
import meshlib.mrmeshpy as mrmesh
import math

# Test full vertex loop via vec_
pts = mesh.points
topo = mesh.topology
vsize = topo.vertSize()
vec = pts.vec_

# Try a small loop first
radii = []
for i in range(min(10, vsize)):
    v = vec[i]
    r = math.sqrt(v.x**2 + v.y**2)
    radii.append(r)

check_results.append({"check_name": "small_loop", "measured": len(radii), "expected": 10, "passed": len(radii) == 10, "unit": "count", "reason": f"radii sample: {[round(r,2) for r in radii]}"})
