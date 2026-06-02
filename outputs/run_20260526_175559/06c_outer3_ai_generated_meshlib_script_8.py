
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

def vec3(x, y, z):
    v = mrmesh.Vector3f()
    v.x = x; v.y = y; v.z = z
    return v

# Phase 1: Bounding box + vertex collection
bb = mesh.getBoundingBox()
mn = bb.min;  mx = bb.max
dim_x = mx.x - mn.x
dim_y = mx.y - mn.y
dim_z = mx.z - mn.z
z_min = mn.z

check_results.append({"check_name":"bbox_x","measured":round(dim_x,3),"expected":160.4,"passed":abs(dim_x-160.4)<=15,"unit":"mm","reason":f"delta={abs(dim_x-160.4):.3f}mm"})
check_results.append({"check_name":"bbox_y","measured":round(dim_y,3),"expected":160.4,"passed":abs(dim_y-160.4)<=15,"unit":"mm","reason":f"delta={abs(dim_y-160.4):.3f}mm"})
check_results.append({"check_name":"bbox_z","measured":round(dim_z,3),"expected":71.5,"passed":abs(dim_z-71.5)<=15,"unit":"mm","reason":f"delta={abs(dim_z-71.5):.3f}mm"})

all_v = []
for vid in mesh.topology.getValidVerts():
    p = mesh.points.vec[vid.get()]
    all_v.append((p.x, p.y, p.z))

check_results.append({"check_name":"phase1_done","measured":len(all_v),"expected":"ok","passed":True,"unit":"verts","reason":""})
