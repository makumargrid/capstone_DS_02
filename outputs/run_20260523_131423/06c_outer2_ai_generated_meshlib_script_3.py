import meshlib.mrmeshpy as mrmesh
doc = mrmesh.rayMeshIntersect.__doc__
check_results.append({
    "check_name": "dump",
    "measured": str(doc),
    "expected": "",
    "passed": True,
    "unit": "",
    "reason": ""
})
