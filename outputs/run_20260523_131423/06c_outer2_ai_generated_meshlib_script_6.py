import meshlib.mrmeshpy as mrmesh
valid_faces = mesh.topology().getValidFaces()
for i in range(valid_faces.size()):
    if valid_faces.test(mrmesh.FaceId(i)):
        f_id = mrmesh.FaceId(i)
        verts = mesh.topology().getFv(f_id) if hasattr(mesh.topology(), 'getFv') else mesh.topology().getTriVerts(f_id)
        out = type(verts).__name__
        break
check_results.append({
    "check_name": "dump",
    "measured": out,
    "expected": "",
    "passed": True,
    "unit": "",
    "reason": ""
})
