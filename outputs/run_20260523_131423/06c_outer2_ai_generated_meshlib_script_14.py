import meshlib.mrmeshpy as mrmesh
import numpy as np

valid_verts = mesh.topology.getValidVerts()
points = mesh.points
vertices = []
for i in range(valid_verts.size()):
    if valid_verts.test(mrmesh.VertId(i)):
        p = points[mrmesh.VertId(i)]
        vertices.append([p.x, p.y, p.z])
vertices = np.array(vertices)

z_slice = vertices[(vertices[:, 2] > 29.5) & (vertices[:, 2] < 30.5)]
r_slice = np.sqrt(z_slice[:, 0]**2 + z_slice[:, 1]**2)

min_r = np.min(r_slice) if len(r_slice) > 0 else 0
max_r = np.max(r_slice) if len(r_slice) > 0 else 0

out = f"min_r={min_r:.2f}, max_r={max_r:.2f}"

check_results.append({
    "check_name": "dump",
    "measured": out,
    "expected": "",
    "passed": True,
    "unit": "",
    "reason": ""
})
