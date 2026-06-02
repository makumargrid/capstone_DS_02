
import meshlib.mrmeshpy as mrmesh
import math

# Probe getTriPoints return type
faces = mesh.topology.getValidFaces()
face_list = list(faces)
fid = face_list[0]
tri = mesh.getTriPoints(fid)
print(type(tri))
print(dir(tri))
# Try indexing
try:
    print("tri[0]:", tri[0])
    print("tri[0].x:", tri[0].x)
except Exception as e:
    print("Index error:", e)
# Try as ThreePoints
try:
    print("tri.a:", tri.a)
except:
    pass

check_results.append({"check_name": "API probe", "measured": str(type(tri)), "expected": "array", "passed": True, "unit": "N/A", "reason": str(dir(tri))[:200]})
