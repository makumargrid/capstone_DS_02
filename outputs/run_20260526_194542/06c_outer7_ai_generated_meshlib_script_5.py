
import meshlib.mrmeshpy as mrmesh
import math

# Inspect getTriVerts signature more carefully via help
faces = mesh.topology.getValidFaces()
face_list = list(faces)
fid = face_list[0]

print("getTriVerts:", help(mesh.topology.getTriVerts))
print("getAllTriVerts:", help(mesh.topology.getAllTriVerts))

check_results.append({"check_name": "probe", "measured": "ok", "expected": "ok", "passed": True, "unit": "N/A", "reason": "help called"})
