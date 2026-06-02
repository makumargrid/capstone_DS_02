import meshlib.mrmeshpy as mrmesh
section_funcs = [d for d in dir(mrmesh) if 'section' in d.lower() or 'contour' in d.lower()]
check_results.append({
    "check_name": "section_funcs",
    "measured": str(section_funcs),
    "expected": "",
    "passed": True,
    "unit": "",
    "reason": ""
})
