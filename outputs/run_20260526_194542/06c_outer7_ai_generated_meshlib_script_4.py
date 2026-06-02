
import meshlib.mrmeshpy as mrmesh
import math

# Test getLeftTriVerts and getTriVerts
faces = mesh.topology.getValidFaces()
face_list = list(faces)
fid = face_list[0]

# Try getLeftTriVerts - takes an edge
e = mesh.topology.edgeWithLeft(fid)
print("edgeWithLeft:", e)

# Try getTriVerts
v0 = mrmesh.VertId()
v1 = mrmesh.VertId()
v2 = mrmesh.VertId()
mesh.topology.getTriVerts(fid, v0, v1, v2)
print("v0:", v0, "v1:", v1, "v2:", v2)

p0 = mesh.points[v0]
p1 = mesh.points[v1]
p2 = mesh.points[v2]
print(f"p0=({p0.x:.2f},{p0.y:.2f},{p0.z:.2f})")
print(f"p1=({p1.x:.2f},{p1.y:.2f},{p1.z:.2f})")
print(f"p2=({p2.x:.2f},{p2.y:.2f},{p2.z:.2f})")
cx_test = (p0.x + p1.x + p2.x) / 3.0
print("centroid x:", cx_test)

n = mesh.normal(fid)
print(f"normal=({n.x:.3f},{n.y:.3f},{n.z:.3f})")

check_results.append({"check_name": "API probe v3", "measured": "ok", "expected": "ok", "passed": True, "unit": "N/A", "reason": "getTriVerts works"})
