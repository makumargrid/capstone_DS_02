import meshlib.mrmeshpy as mrmesh
doc = mrmesh.Mesh.edgePoint.__doc__
check_results.append({
    "check_name": "edgePoint_doc",
    "measured": str(doc),
    "expected": "",
    "passed": True,
    "unit": "",
    "reason": ""
})
