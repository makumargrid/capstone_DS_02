import meshlib.mrmeshpy as mrmesh
check_results.append({
    "check_name": "rayMeshIntersect_doc",
    "measured": str(mrmesh.rayMeshIntersect.__doc__),
    "expected": "",
    "passed": True,
    "unit": "",
    "reason": ""
})
