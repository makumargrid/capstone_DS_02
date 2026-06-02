import meshlib.mrmeshpy as mrmesh

comp_funcs = [d for d in dir(mrmesh) if 'component' in d.lower()]
check_results.append({
    "check_name": "comp_funcs",
    "measured": str(comp_funcs),
    "expected": "",
    "passed": True,
    "unit": "",
    "reason": ""
})
