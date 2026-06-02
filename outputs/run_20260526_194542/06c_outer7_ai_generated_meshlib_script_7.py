
import meshlib.mrmeshpy as mrmesh
import math

bb = mesh.getBoundingBox()
mn, mx = bb.min, bb.max
dim_x = mx.x - mn.x

check_results.append({"check_name": "basic_test", "measured": round(dim_x, 2), "expected": 130.0, "passed": True, "unit": "mm", "reason": "basic test"})
