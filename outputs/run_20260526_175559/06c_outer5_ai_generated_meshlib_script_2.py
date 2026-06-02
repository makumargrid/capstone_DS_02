
import meshlib.mrmeshpy as mrmesh
import math

# Quick probe: check getTriPoints signature and rayMeshIntersect signature
check_results = []

# check getTriPoints
fid = mrmesh.FaceId(0)
tri = mesh.getTriPoints(fid)
check_results.append({
    "check_name": "API probe: getTriPoints type",
    "measured": str(type(tri)),
    "expected": "array",
    "passed": True,
    "unit": "N/A",
    "reason": str(dir(tri))
})

# check index access
pt0 = tri[0]
check_results.append({
    "check_name": "API probe: tri[0] type",
    "measured": str(type(pt0)),
    "expected": "Vector3f",
    "passed": True,
    "unit": "N/A",
    "reason": f"x={pt0.x}, y={pt0.y}, z={pt0.z}"
})
