
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

# ── helpers ─────────────────────────────────────────────────────────────────
def vec3(x, y, z):
    v = mrmesh.Vector3f()
    v.x = x; v.y = y; v.z = z
    return v

# ── explore getTriPoints return type ─────────────────────────────────────────
face_list = []
for f_id in mesh.topology.getValidFaces():
    face_list.append(f_id)
    break

tri_pts = mesh.getTriPoints(face_list[0])
print(type(tri_pts))
print(dir(tri_pts))
# try indexing
try:
    p0 = tri_pts[0]
    print("indexing works:", p0.x, p0.y, p0.z)
except Exception as e:
    print("indexing failed:", e)
