import meshlib.mrmeshpy as mrmesh
import numpy as np
import math

points = mesh.points
valid_verts = mesh.topology.getValidVerts()

vertices = []
for i in range(valid_verts.size()):
    if valid_verts.test(mrmesh.VertId(i)):
        p = points[mrmesh.VertId(i)]
        vertices.append([p.x, p.y, p.z])
vertices = np.array(vertices)

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
# taking a slice at Z=30
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
            
    # fill zeroes backwards and forwards
    for i in range(1, num_bins):
        if max_r_per_bin[i] == 0:
            max_r_per_bin[i] = max_r_per_bin[i-1]
    for i in range(num_bins-2, -1, -1):
        if max_r_per_bin[i] == 0:
            max_r_per_bin[i] = max_r_per_bin[i+1]
            
    # Simple peak finding
    peaks = []
    window = 10
    for i in range(num_bins):
        is_peak = True
        val = max_r_per_bin[i]
        for j in range(i - window, i + window + 1):
            idx = j % num_bins
            if max_r_per_bin[idx] > val:
                is_peak = False
                break
        if is_peak:
            # Check prominence
            min_in_window = min(max_r_per_bin[(i - window) % num_bins], max_r_per_bin[(i + window) % num_bins])
            if val - min_in_window > 2.0:
                if not peaks or min(abs(i - p) for p in peaks) > window:
                    peaks.append(i)
                    
    blade_count = len(peaks)

# 5. Wall Thickness (min wall > 2mm)
valid_faces = mesh.topology.getValidFaces()
mesh_part = mrmesh.MeshPart(mesh)

wall_thicknesses = []
for i in range(valid_faces.size()):
    if valid_faces.test(mrmesh.FaceId(i)):
        f_id = mrmesh.FaceId(i)
        v_ids = mesh.topology.getTriVerts(f_id)
        p0, p1, p2 = points[v_ids[0]], points[v_ids[1]], points[v_ids[2]]
        
        arr0 = np.array([p0.x, p0.y, p0.z])
        arr1 = np.array([p1.x, p1.y, p1.z])
        arr2 = np.array([p2.x, p2.y, p2.z])
        center = (arr0 + arr1 + arr2) / 3.0
        
        v1 = arr1 - arr0
        v2 = arr2 - arr0
        normal = np.cross(v1, v2)
        norm = np.linalg.norm(normal)
        if norm > 1e-6:
            normal = normal / norm
            inward_normal = -normal
            
            line = mrmesh.Line3f(mrmesh.Vector3f(center[0], center[1], center[2]), 
                                 mrmesh.Vector3f(inward_normal[0], inward_normal[1], inward_normal[2]))
            res = mrmesh.rayMeshIntersect(mesh_part, line, 0.1, 100.0) # start at 0.1 to avoid adjacent face hits
            if hasattr(res, 'distanceAlongLine'):
                wall_thicknesses.append(res.distanceAlongLine)

min_wall_mm = np.percentile(wall_thicknesses, 1) if wall_thicknesses else 0.0

check_results.append({
    "check_name": "Central Bore Diameter",
    "measured": round(float(bore_diameter), 2),
    "expected": 15.0,
    "passed": abs(bore_diameter - 15.0) < 1.0,
    "unit": "mm",
    "reason": "Measures the minimum distance from the Z axis to vertices."
})

check_results.append({
    "check_name": "Top Outer Diameter (Hub + Blades)",
    "measured": round(float(top_max_diameter), 2),
    "expected": 40.0,
    "passed": abs(top_max_diameter - 40.0) < 2.0,
    "unit": "mm",
    "reason": "Maximum diameter at Z=60 (30mm hub + 2*5mm blade protrusion)."
})

check_results.append({
    "check_name": "Base Outer Diameter (Hub + Blades)",
    "measured": round(float(base_max_diameter), 2),
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

check_results.append({
    "check_name": "Minimum Wall Thickness",
    "measured": round(float(min_wall_mm), 2),
    "expected": 2.0,
    "passed": float(min_wall_mm) >= 1.9,
    "unit": "mm",
    "reason": "1st percentile of ray-cast distances from face centers inward."
})
