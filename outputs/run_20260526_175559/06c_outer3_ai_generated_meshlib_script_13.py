
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

bb = mesh.getBoundingBox()
bmin = bb.min; bmax = bb.max
dx = bmax.x - bmin.x; dy = bmax.y - bmin.y; dz = bmax.z - bmin.z
zlo = bmin.z

vx=[]; vy=[]; vz_arr=[]
for vid in mesh.topology.getValidVerts():
    p = mesh.points.vec[vid.get()]
    vx.append(p.x); vy.append(p.y); vz_arr.append(p.z)
nv = len(vx)

# blade count at multiple Z heights
gr = math.radians(15.0)
blade_scan = []
for frac in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
    zt = zlo + frac*dz
    ag = sorted([math.atan2(vy[i],vx[i]) for i in range(nv)
                 if abs(vz_arr[i]-zt)<2.5 and 15.0<math.sqrt(vx[i]*vx[i]+vy[i]*vy[i])<90.0])
    if len(ag) < 5:
        blade_scan.append((0, 0, round(zt,1), frac))
        continue
    gaps = 0
    for k in range(1,len(ag)):
        if ag[k]-ag[k-1] > gr:
            gaps += 1
    wp = (ag[0]+2*math.pi) - ag[-1]
    if wp > gr:
        gaps += 1
    blade_scan.append((len(ag), gaps, round(zt,1), frac))

blade_scan.sort(reverse=True)
best_n, best_c, best_z, best_f = blade_scan[0]
check_results.append({"check_name":"blade_count_estimate","measured":best_c,"expected":7,"passed":abs(best_c-7)<=2,"unit":"count","reason":"best_z="+str(best_z)+"mm n="+str(best_n)+" scan="+str([(b[2],b[1]) for b in blade_scan])})

# Hub base cone surface: check pure cone portion (r < 50.5mm) at base
base_r_cone = [math.sqrt(vx[i]*vx[i]+vy[i]*vy[i]) for i in range(nv) if vz_arr[i]-zlo < 2.0]
hub_only_r = [r for r in base_r_cone if r <= 51.0]
hub_cone_diam = round(2.0*max(hub_only_r),3) if hub_only_r else 0
check_results.append({"check_name":"hub_cone_base_diam_only","measured":hub_cone_diam,"expected":100.0,"passed":abs(hub_cone_diam-100.0)<=5,"unit":"mm","reason":"hub surface at base: "+str(len(hub_only_r))+" verts, max_r="+str(round(max(hub_only_r) if hub_only_r else 0,3))})

# Hub top: look at pure hub without blade tips
# At Z_max (top of mesh), the hub should be there
z_near_top = bmax.z
top_slice_r = [math.sqrt(vx[i]*vx[i]+vy[i]*vy[i]) for i in range(nv) if abs(vz_arr[i]-z_near_top)<1.5]
if top_slice_r:
    check_results.append({"check_name":"top_slice_max_r","measured":round(2.0*max(top_slice_r),3),"expected":"info","passed":True,"unit":"mm","reason":"At Z_max="+str(round(z_near_top,2))+"mm: n="+str(len(top_slice_r))+" max_r="+str(round(max(top_slice_r),3))+" min_r="+str(round(min(top_slice_r),3))})

# For hub top diam: look at Z near zlo+60 but only hub cone portion (no blade tips)
# The cone at Z=60 has r=15mm, blades add 5mm -> blade tips at r=20mm
# Look for the tightest cluster near r=15 at Z=60
ztop_target = zlo + 60.0
top_all_r = sorted([math.sqrt(vx[i]*vx[i]+vy[i]*vy[i]) for i in range(nv) if abs(vz_arr[i]-ztop_target)<3.0])
if top_all_r:
    # hub cone surface: smallest r values (these ARE the bore inner wall/cone wall)
    # blade tips: largest r values
    hub_top_r_max = max(r for r in top_all_r if r <= 16.0) if any(r<=16.0 for r in top_all_r) else top_all_r[0]
    hub_top_diam = round(2.0*hub_top_r_max, 3)
    check_results.append({"check_name":"hub_top_cone_diam","measured":hub_top_diam,"expected":30.0,"passed":abs(hub_top_diam-30.0)<=5,"unit":"mm","reason":"Max r<=16mm at Z=60: "+str(round(hub_top_r_max,3))+"mm. Min r="+str(round(top_all_r[0],3))+" Max r="+str(round(top_all_r[-1],3))})

# Blade protrusion check
# At base (Z=0): blade tips should be at r=65mm (50+15)
blade_tip_base_r = max((math.sqrt(vx[i]*vx[i]+vy[i]*vy[i]) for i in range(nv) if vz_arr[i]-zlo<2.0), default=0)
check_results.append({"check_name":"blade_protrusion_base","measured":round(blade_tip_base_r,3),"expected":65.0,"passed":abs(blade_tip_base_r-65.0)<=12,"unit":"mm","reason":"max_r at base="+str(round(blade_tip_base_r,3))+" vs hub50+prot15=65"})

# At top (Z=60): blade tips should be at r=20mm (15+5) 
blade_tip_top_r = max((math.sqrt(vx[i]*vx[i]+vy[i]*vy[i]) for i in range(nv) if abs(vz_arr[i]-ztop_target)<3.0), default=0)
check_results.append({"check_name":"blade_protrusion_top","measured":round(blade_tip_top_r,3),"expected":20.0,"passed":abs(blade_tip_top_r-20.0)<=10,"unit":"mm","reason":"max_r at top="+str(round(blade_tip_top_r,3))+" vs hub15+prot5=20"})

# 7-fold symmetry
sec7=[0]*7
for i in range(nv):
    r2=math.sqrt(vx[i]*vx[i]+vy[i]*vy[i])
    if r2>16.0:
        sec7[int((math.atan2(vy[i],vx[i])%(2*math.pi))/(2*math.pi/7))%7]+=1
m7=sum(sec7)/7.0
v7=round((max(sec7)-min(sec7))/(m7+0.001),3)
check_results.append({"check_name":"7fold_symmetry","measured":v7,"expected":"<0.5","passed":v7<0.5,"unit":"ratio","reason":"sec="+str(sec7)+" var="+str(v7)})

check_results.append({"check_name":"avg_edge_length","measured":round(mesh.averageEdgeLength(),3),"expected":"<5.0","passed":mesh.averageEdgeLength()<5.0,"unit":"mm","reason":"avg="+str(round(mesh.averageEdgeLength(),3))})

for row in check_results:
    print(("PASS" if row["passed"] else "FAIL")+" "+row["check_name"]+": "+str(row["measured"])+" "+row["unit"])
