import meshlib.mrmeshpy as mrmesh
slice_funcs = [d for d in dir(mrmesh) if 'cut' in d.lower() or 'slice' in d.lower() or 'cross' in d.lower()]
check_results.append({
    "check_name": "slice_funcs",
    "measured": str(slice_funcs),
    "expected": "",
    "passed": True,
    "unit": "",
    "reason": ""
})
