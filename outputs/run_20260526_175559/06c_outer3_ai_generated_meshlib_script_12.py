
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

bb = mesh.getBoundingBox()
bmin = bb.min
bmax = bb.max
dx = bmax.x - bmin.x
dy = bmax.y - bmin.y
dz = bmax.z - bmin.z
zlo = bmin.z

check_results.append({"check_name":"bbox_x","measured":round(dx,3),"expected":160.4,"passed":abs(dx-160.4)<=15,"unit":"mm","reason":"delta="+str(round(abs(dx-160.4),3))})
check_results.append({"check_name":"bbox_y","measured":round(dy,3),"expected":160.4,"passed":abs(dy-160.4)<=15,"unit":"mm","reason":"delta="+str(round(abs(dy-160.4),3))})
check_results.append({"check_name":"bbox_z","measured":round(dz,3),"expected":71.5,"passed":abs(dz-71.5)<=15,"unit":"mm","reason":"delta="+str(round(abs(dz-71.5),3))})

vx=[]; vy=[]; vz_arr=[]
for vid in mesh.topology.getValidVerts():
    p = mesh.points.vec[vid.get()]
    vx.append(p.x); vy.append(p.y); vz_arr.append(p.z)
nv = len(vx)

# base slice
base_r = [math.sqrt(vx[i]*vx[i]+vy[i]*vy[i]) for i in range(nv) if vz_arr[i]-zlo < 2.0]
max_base_r = max(base_r) if base_r else 0.0
base_diam = round(2.0*max_base_r, 3)
check_results.append({"check_name":"hub_base_outer_diam","measured":base_diam,"expected":100.0,"passed":abs(base_diam-100.0)<=15,"unit":"mm","reason":"max_r="+str(round(max_base_r,3))})

# top slice
ztop = zlo+60.0
top_r = [math.sqrt(vx[i]*vx[i]+vy[i]*vy[i]) for i in range(nv) if abs(vz_arr[i]-ztop)<3.0]
max_top_r = max(top_r) if top_r else 0.0
min_top_r = min(top_r) if top_r else 0.0
top_diam = round(2.0*max_top_r, 3)
check_results.append({"check_name":"hub_top_outer_diam","measured":top_diam,"expected":30.0,"passed":abs(top_diam-30.0)<=15,"unit":"mm","reason":"max_r="+str(round(max_top_r,3))+" min_r="+str(round(min_top_r,3))})
check_results.append({"check_name":"hub_height","measured":round(dz,3),"expected":60.0,"passed":abs(dz-60.0)<=15,"unit":"mm","reason":"Z="+str(round(zlo,2))+" to "+str(round(bmax.z,2))})

# bore
all_r_sorted = sorted([math.sqrt(vx[i]*vx[i]+vy[i]*vy[i]) for i in range(nv)])
inner_r_vals = [r for r in all_r_sorted if r < 12.0]
if inner_r_vals:
    bore_diam = round(2.0*inner_r_vals[-1], 3)
    bore_note = str(len(inner_r_vals))+" verts r<12mm max="+str(round(inner_r_vals[-1],4))
else:
    bore_diam = round(2.0*all_r_sorted[0], 3)
    bore_note = "no_verts_r<12 min_global="+str(round(all_r_sorted[0],4))
check_results.append({"check_name":"central_bore_diam","measured":bore_diam,"expected":15.0,"passed":abs(bore_diam-15.0)<=5,"unit":"mm","reason":bore_note})

check_results.append({"check_name":"checkpoint_A","measured":len(check_results),"expected":"ok","passed":True,"unit":"count","reason":"all checks up to bore done"})
