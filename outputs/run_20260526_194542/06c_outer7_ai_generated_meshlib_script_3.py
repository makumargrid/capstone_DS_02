
import meshlib.mrmeshpy as mrmesh
import math

# Probe face centroid via topology + point access
faces = mesh.topology.getValidFaces()
face_list = list(faces)
fid = face_list[0]

# Use topology to get 3 vertices of a face
verts_of_face = []
e = mesh.topology.edgeWithLeft(fid)
e0 = e
for _ in range(3):
    v = mesh.topology.org(e)
    verts_of_face.append(v)
    e = mesh.topology.next(e)

print("Vertices of face:", verts_of_face)
p0 = mesh.points[verts_of_face[0]]
p1 = mesh.points[verts_of_face[1]]
p2 = mesh.points[verts_of_face[2]]
print(f"p0=({p0.x:.2f},{p0.y:.2f},{p0.z:.2f})")
cx_test = (p0.x + p1.x + p2.x) / 3.0
print("centroid x:", cx_test)

# Test face normal
n = mesh.normal(fid)
print(f"normal=({n.x:.3f},{n.y:.3f},{n.z:.3f})")

check_results.append({"check_name": "API probe v2", "measured": "ok", "expected": "ok", "passed": True, "unit": "N/A", "reason": f"centroid_x={cx_test:.2f}"})
