import meshlib.mrmeshpy as mrmesh
import numpy as np

mesh_part = mrmesh.MeshPart(mesh)

# ray that does NOT intersect
line = mrmesh.Line3f(mrmesh.Vector3f(1000, 1000, 1000), mrmesh.Vector3f(1, 0, 0))
res = mrmesh.rayMeshIntersect(mesh_part, line, 0.1, 100.0)

out = "dist: " + str(res.distanceAlongLine) + " bool: " + str(bool(res)) + " proj: " + str(res.proj)

check_results.append({
    "check_name": "dump",
    "measured": out,
    "expected": "",
    "passed": True,
    "unit": "",
    "reason": ""
})
