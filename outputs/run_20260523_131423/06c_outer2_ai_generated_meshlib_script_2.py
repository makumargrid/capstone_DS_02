import meshlib.mrmeshpy as mrmesh
ray_funcs = [d for d in dir(mrmesh) if 'ray' in d.lower()]
check_results.append({
    "check_name": "dump",
    "measured": ", ".join(ray_funcs),
    "expected": "",
    "passed": True,
    "unit": "",
    "reason": ""
})
