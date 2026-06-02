
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

# Probe rayMeshIntersect signature
org = mrmesh.Vector3f()
org.x = 0.0
org.y = 0.0
org.z = 30.0

direction = mrmesh.Vector3f()
direction.x = 1.0
direction.y = 0.0
direction.z = 0.0

line = mrmesh.Line3f()
line.p = org
line.d = direction

# Try calling with just mesh and line
result = mrmesh.rayMeshIntersect(mesh, line)
check_results.append({
    "check_name": "API probe: rayMeshIntersect result type",
    "measured": str(type(result)),
    "expected": "result",
    "passed": True,
    "unit": "N/A",
    "reason": str(result) if result else "None/empty"
})
if result:
    check_results.append({
        "check_name": "API probe: rayMeshIntersect distanceAlongLine",
        "measured": result.distanceAlongLine,
        "expected": ">0",
        "passed": True,
        "unit": "mm",
        "reason": str(dir(result))
    })
