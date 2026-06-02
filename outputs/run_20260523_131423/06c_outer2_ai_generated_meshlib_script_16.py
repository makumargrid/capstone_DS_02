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

z_slice = vertices[(vertices[:, 2] > 29.0) & (vertices[:, 2] < 31.0)]
angles = np.arctan2(z_slice[:, 1], z_slice[:, 0])
r_slice = np.sqrt(z_slice[:, 0]**2 + z_slice[:, 1]**2)

min_r = np.min(r_slice)
max_r = np.max(r_slice)
threshold = (min_r + max_r) / 2

sort_idx = np.argsort(angles)
sorted_r = r_slice[sort_idx]
sorted_angles = angles[sort_idx]

window = max(1, len(sorted_r) // 10)
smoothed_r = np.convolve(np.pad(sorted_r, (window, window), mode='wrap'), np.ones(window)/window, mode='valid')

crossings = 0
for i in range(len(sorted_r)):
    if smoothed_r[i] > threshold and smoothed_r[i-1] <= threshold:
        crossings += 1

out = f"crossings={crossings}, points={len(sorted_r)}"
check_results.append({
    "check_name": "dump",
    "measured": out,
    "expected": "",
    "passed": True,
    "unit": "",
    "reason": ""
})
