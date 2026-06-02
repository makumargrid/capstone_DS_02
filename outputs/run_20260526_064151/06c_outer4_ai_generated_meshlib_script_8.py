
import meshlib.mrmeshpy as mrmesh
import math

# Test rayMeshIntersect API
origin = mrmesh.Vector3f()
origin.x = 0.0
origin.y = 0.0
origin.z = 30.0

direction = mrmesh.Vector3f()
direction.x = 1.0
direction.y = 0.0
direction.z = 0.0

line = mrmesh.Line3f()
line.p = origin
line.d = direction

result = mrmesh.rayMeshIntersect(mesh, line)
print(f"ray result type: {type(result)}")
print(f"result: {result}")
if result:
    print(f"has proj: {result.proj.point.x:.3f}, {result.proj.point.y:.3f}, {result.proj.point.z:.3f}")
    print(f"distanceAlongLine: {result.distanceAlongLine:.3f}")

check_results.append({"check_name": "ray_test", "measured": result is not None, "expected": True, "passed": result is not None, "unit": "bool", "reason": f"Ray from origin toward +X hit: {result.proj.point.x:.3f if result else 'none'}"})
