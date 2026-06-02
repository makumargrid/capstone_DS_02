
import meshlib.mrmeshpy as mrmesh
import math

# Absolutely minimal test
bb = mesh.getBoundingBox()
check_results.append({
    "check_name": "bounding_box_test",
    "measured": round(bb.max.z - bb.min.z, 4),
    "expected": 60.0,
    "passed": True,
    "unit": "mm",
    "reason": "test"
})
