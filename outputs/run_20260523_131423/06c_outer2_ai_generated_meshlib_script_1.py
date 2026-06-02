import meshlib.mrmeshpy as mrmesh
import numpy as np
from scipy.signal import find_peaks

# mesh is already loaded
points = mesh.points()
vertices = np.array([[points[mrmesh.VertId(i)].x, points[mrmesh.VertId(i)].y, points[mrmesh.VertId(i)].z] for i in range(points.size())])

# 1. Bore diameter (min radius from Z axis at z > 5 and z < 55)
mid_verts = vertices[(vertices[:, 2] > 10) & (vertices[:, 2] < 50)]
if len(mid_verts) > 0:
    r_mid = np.sqrt(mid_verts[:, 0]**2 + mid_verts[:, 1]**2)
    min_r = np.min(r_mid)
    bore_diameter = min_r * 2
else:
    bore_diameter = 0.0

# 2. Hub Top dimensions
top_verts = vertices[vertices[:, 2] > 59.9]
if len(top_verts) > 0:
    r_top = np.sqrt(top_verts[:, 0]**2 + top_verts[:, 1]**2)
    top_max_r = np.max(r_top)
    top_max_diameter = top_max_r * 2
else:
    top_max_diameter = 0.0

# 3. Hub Base dimensions
base_verts = vertices[vertices[:, 2] < 0.1]
if len(base_verts) > 0:
    r_base = np.sqrt(base_verts[:, 0]**2 + base_verts[:, 1]**2)
    base_max_r = np.max(r_base)
    base_max_diameter = base_max_r * 2
else:
    base_max_diameter = 0.0

# 4. Blade Count
z_slice_verts = vertices[(vertices[:, 2] > 29.5) & (vertices[:, 2] < 30.5)]
blade_count = 0
if len(z_slice_verts) > 0:
    angles = np.arctan2(z_slice_verts[:, 1], z_slice_verts[:, 0])
    r_slice = np.sqrt(z_slice_verts[:, 0]**2 + z_slice_verts[:, 1]**2)
    
    num_bins = 360
    bins = np.linspace(-np.pi, np.pi, num_bins)
    bin_idx = np.digitize(angles, bins)
    
    max_r_per_bin = np.zeros(num_bins)
    for i in range(1, num_bins):
        pts_in_bin = r_slice[bin_idx == i]
        if len(pts_in_bin) > 0:
            max_r_per_bin[i] = np.max(pts_in_bin)
        else:
            max_r_per_bin[i] = max_r_per_bin[i-1] # primitive fill
            
    # fill zeroes backwards
    for i in range(num_bins-2, -1, -1):
        if max_r_per_bin[i] == 0:
            max_r_per_bin[i] = max_r_per_bin[i+1]
            
    max_r_extended = np.concatenate([max_r_per_bin[-30:], max_r_per_bin, max_r_per_bin[:30]])
    peaks, _ = find_peaks(max_r_extended, distance=20, prominence=2)
    valid_peaks = [p for p in peaks if 30 <= p < 30 + num_bins]
    blade_count = len(valid_peaks)

check_results.append({
    "check_name": "Central Bore Diameter",
    "measured": float(bore_diameter),
    "expected": 15.0,
    "passed": abs(bore_diameter - 15.0) < 1.0,
    "unit": "mm",
    "reason": "Measures the minimum distance from the Z axis to vertices."
})

check_results.append({
    "check_name": "Top Outer Diameter (Hub + Blades)",
    "measured": float(top_max_diameter),
    "expected": 40.0,
    "passed": abs(top_max_diameter - 40.0) < 2.0,
    "unit": "mm",
    "reason": "Maximum diameter at Z=60 (30mm hub + 2*5mm blade protrusion)."
})

check_results.append({
    "check_name": "Base Outer Diameter (Hub + Blades)",
    "measured": float(base_max_diameter),
    "expected": 130.0,
    "passed": abs(base_max_diameter - 130.0) < 2.0,
    "unit": "mm",
    "reason": "Maximum diameter at Z=0 (100mm hub + 2*15mm blade protrusion)."
})

check_results.append({
    "check_name": "Blade Count",
    "measured": int(blade_count),
    "expected": 7,
    "passed": int(blade_count) == 7,
    "unit": "count",
    "reason": "Detected number of radius peaks around the Z axis at Z=30."
})
