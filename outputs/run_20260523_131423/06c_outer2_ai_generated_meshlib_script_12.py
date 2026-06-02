import meshlib.mrmeshpy as mrmesh
import numpy as np

valid_faces = mesh.topology.getValidFaces()
points = mesh.points
mesh_part = mrmesh.MeshPart(mesh)

f_id = mrmesh.FaceId(0)
v_ids = mesh.topology.getTriVerts(f_id)
p0, p1, p2 = points[v_ids[0]], points[v_ids[1]], points[v_ids[2]]

arr0 = np.array([p0.x, p0.y, p0.z])
arr1 = np.array([p1.x, p1.y, p1.z])
arr2 = np.array([p2.x, p2.y, p2.z])
center = (arr0 + arr1 + arr2) / 3.0

v1 = arr1 - arr0
v2 = arr2 - arr0
normal = np.cross(v1, v2)
normal = normal / np.linalg.norm(normal)
inward_normal = -normal

line = mrmesh.Line3f(mrmesh.Vector3f(center[0], center[1], center[2]), 
                     mrmesh.Vector3f(inward_normal[0], inward_normal[1], inward_normal[2]))
res = mrmesh.rayMeshIntersect(mesh_part, line, 0.1, 100.0)

out = "type: " + str(type(res)) + " has distance: " + str(hasattr(res, 'distanceAlongLine'))
if hasattr(res, 'valid'):
    out += " has valid: " + str(type(res.valid))

check_results.append({
    "check_name": "dump",
    "measured": out,
    "expected": "",
    "passed": True,
    "unit": "",
    "reason": ""
})
