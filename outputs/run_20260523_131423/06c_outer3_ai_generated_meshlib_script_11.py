import meshlib.mrmeshpy as mrmesh

mp = mrmesh.MeshPart(mesh)
components = mrmesh.getAllComponents(mp)
num_components = len(components)

check_results.append({
    "check_name": "num_components",
    "measured": num_components,
    "expected": 1,
    "passed": num_components == 1,
    "unit": "components",
    "reason": "Ensure the final object is a single unified solid"
})
