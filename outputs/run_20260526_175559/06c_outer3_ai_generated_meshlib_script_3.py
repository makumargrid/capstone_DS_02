
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

# ── helpers ─────────────────────────────────────────────────────────────────
def vec3(x, y, z):
    v = mrmesh.Vector3f()
    v.x = x; v.y = y; v.z = z
    return v

# Probe getTriPoints structure
face_list = []
for f_id in mesh.topology.getValidFaces():
    face_list.append(f_id)

tri_pts = mesh.getTriPoints(face_list[0])
attrs = [a for a in dir(tri_pts) if not a.startswith('_')]
# Store in check_results so we can see the output
check_results.append({
    "check_name": "api_probe_getTriPoints",
    "measured": str(attrs[:20]),
    "expected": "attribute names",
    "passed": True,
    "unit": "info",
    "reason": f"type={type(tri_pts).__name__}"
})
