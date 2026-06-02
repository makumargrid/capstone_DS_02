import meshlib.mrmeshpy as mrmesh
try:
    p = mrmesh.Vector3f(0, 0, 0)
    d = mrmesh.Vector3f(1, 0, 0)
    line = mrmesh.Line3f(p, d)
    res = mrmesh.rayMeshIntersect(mrmesh.MeshPart(mesh), line)
    out = "success" if res else "failed"
except Exception as e:
    out = str(e)
check_results.append({
    "check_name": "dump",
    "measured": out,
    "expected": "",
    "passed": True,
    "unit": "",
    "reason": ""
})
