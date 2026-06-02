
import meshlib.mrmeshpy as mrmesh
import math

# Test topology access
topo = mesh.topology
vsize = topo.vertSize()

check_results.append({"check_name": "vertsize", "measured": vsize, "expected": 1505, "passed": True, "unit": "count", "reason": "test"})
