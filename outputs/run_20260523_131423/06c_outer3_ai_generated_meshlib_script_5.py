import meshlib.mrmeshpy as mrmesh
doc = mrmesh.extractXYPlaneSections.__doc__
doc2 = mrmesh.extractPlaneSections.__doc__
check_results.append({
    "check_name": "extract_docs",
    "measured": str(doc) + "\n---\n" + str(doc2),
    "expected": "",
    "passed": True,
    "unit": "",
    "reason": ""
})
