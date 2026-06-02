
import meshlib.mrmeshpy as mrmesh
import math

# Use getAllTriVerts to get all face vertex triples at once
all_tri_verts = mesh.topology.getAllTriVerts()
print("type:", type(all_tri_verts))
print("len:", len(all_tri_verts))
first = all_tri_verts[0]
print("first type:", type(first))
print("first dir:", [x for x in dir(first) if not x.startswith('_')])

# Try indexing
print("first[0]:", first[0])
print("first[0] type:", type(first[0]))

# Get vertex positions
v0 = first[0]
v1 = first[1]  
v2 = first[2]
p0 = mesh.points[v0]
p1 = mesh.points[v1]
p2 = mesh.points[v2]
print(f"p0=({p0.x:.2f},{p0.y:.2f},{p0.z:.2f})")

check_results.append({"check_name": "getAllTriVerts probe", "measured": len(all_tri_verts), "expected": "positive", "passed": len(all_tri_verts) > 0, "unit": "count", "reason": "getAllTriVerts works"})
