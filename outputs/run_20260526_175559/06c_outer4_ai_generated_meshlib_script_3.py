
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

coords = mesh.points
bb = mesh.getBoundingBox()
z_base = bb.min.z
z_top  = bb.max.z

def r_hub(z_frac):
    return 50.0 - (50.0 - 15.0) * z_frac

def vec3f(x, y, z):
    v = mrmesh.Vector3f(); v.x = x; v.y = y; v.z = z
    return v

# ── Test getTriPoints indexing ────────────────────────────────────────────────
fid0 = mrmesh.FaceId(0)
pts = mesh.getTriPoints(fid0)
# Try index-based access
p0 = pts[0]
p1 = pts[1]
p2 = pts[2]
cx = (p0.x + p1.x + p2.x) / 3.0
cy = (p0.y + p1.y + p2.y) / 3.0
cz = (p0.z + p1.z + p2.z) / 3.0
check_results.append({
    "check_name": "_debug_tri_access",
    "measured": round(cx, 2),
    "expected": "any",
    "passed": True,
    "unit": "mm",
    "reason": f"TriPoints[0] index access works. Center={round(cx,2)},{round(cy,2)},{round(cz,2)}"
})
