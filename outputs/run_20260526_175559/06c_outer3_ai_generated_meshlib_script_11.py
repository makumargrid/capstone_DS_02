
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

check_results.append({"check_name":"bbox_x","measured":round(dx,3),"expected":160.4,"passed":abs(dx-160.4)<=15,"unit":"mm","reason":"delta "+str(round(abs(dx-160.4),3))})
check_results.append({"check_name":"bbox_y","measured":round(dy,3),"expected":160.4,"passed":abs(dy-160.4)<=15,"unit":"mm","reason":"delta "+str(round(abs(dy-160.4),3))})
check_results.append({"check_name":"bbox_z","measured":round(dz,3),"expected":71.5,"passed":abs(dz-71.5)<=15,"unit":"mm","reason":"delta "+str(round(abs(dz-71.5),3))})

vx=[]; vy=[]; vz_arr=[]
for vid in mesh.topology.getValidVerts():
    p = mesh.points.vec[vid.get()]
    vx.append(p.x); vy.append(p.y); vz_arr.append(p.z)
nv = len(vx)

# Hub base: Z in [zlo, zlo+2)
base_idx = [i for i in range(nv) if vz_arr[i]-zlo < 2.0]
base_r   = [math.sqrt(vx[i]*vx[i]+vy[i]*vy[i]) for i in base_idx]
max_base_r = max(base_r) if base_r else 0.0
base_diam  = round(2.0*max_base_r, 3)
check_results.append({"check_name":"hub_base_outer_diam","measured":base_diam,"expected":100.0,"passed":abs(base_diam-100.0)<=15,"unit":"mm","reason":"max_r="+str(round(max_base_r,3))+"mm n="+str(len(base_idx))})

# Hub top: Z near zlo+60
ztop = zlo+60.0
top_idx = [i for i in range(nv) if abs(vz_arr[i]-ztop)<3.0]
top_r   = [math.sqrt(vx[i]*vx[i]+vy[i]*vy[i]) for i in top_idx]
max_top_r = max(top_r) if top_r else 0.0
min_top_r = min(top_r) if top_r else 0.0
top_diam  = round(2.0*max_top_r, 3)
check_results.append({"check_name":"hub_top_outer_diam","measured":top_diam,"expected":30.0,"passed":abs(top_diam-30.0)<=15,"unit":"mm","reason":"max_r="+str(round(max_top_r,3))+" min_r="+str(round(min_top_r,3))+" n="+str(len(top_idx))})

# Height
check_results.append({"check_name":"hub_height","measured":round(dz,3),"expected":60.0,"passed":abs(dz-60.0)<=15,"unit":"mm","reason":"Z="+str(round(zlo,2))+".."+str(round(bmax.z,2))})

# Bore
all_r2 = sorted([math.sqrt(vx[i]*vx[i]+vy[i]*vy[i]) for i in range(nv)])
cnt_inner = sum(1 for r2 in all_r2 if r2 < 12.0)
if cnt_inner > 0:
    max_inner = max(r2 for r2 in all_r2 if r2 < 12.0)
    bore_diam = round(2.0*max_inner, 3)
    bore_note = str(cnt_inner)+" verts r<12 max_r="+str(round(max_inner,4))
else:
    min_all = all_r2[0]
    bore_diam = round(2.0*min_all, 3)
    bore_note = "no verts r<12 min_r_global="+str(round(min_all,4))
check_results.append({"check_name":"central_bore_diam","measured":bore_diam,"expected":15.0,"passed":abs(bore_diam-15.0)<=5,"unit":"mm","reason":bore_note})

# Blade count at multiple Z levels
def blade_cnt(z_tgt):
    gr = math.radians(15.0)
    ag = []
    for i in range(nv):
        r2 = math.sqrt(vx[i]*vx[i]+vy[i]*vy[i])
        if abs(vz_arr[i]-z_tgt)<2.5 and 15.0<r2<90.0:
            ag.append(math.atan2(vy[i],vx[i]))
    if len(ag)<5:
        return 0, 0
    ag.sort()
    gaps=0
    for k in range(1,len(ag)):
        if ag[k]-ag[k-1]>gr:
            gaps+=1
    wp=(ag[0]+2*math.pi)-ag[-1]
    if wp>gr:
        gaps+=1
    return gaps, len(ag)

zfracs = [0.2,0.3,0.4,0.5,0.6,0.7,0.8]
blade_results = []
for frac in zfracs:
    bc, bn = blade_cnt(zlo+frac*60.0)
    blade_results.append((bn, bc, round(zlo+frac*60.0,1)))
blade_results.sort(reverse=True)
best_bc_n  = blade_results[0][0]
best_bc    = blade_results[0][1]
best_bc_z  = blade_results[0][2]
check_results.append({"check_name":"blade_count","measured":best_bc,"expected":7,"passed":abs(best_bc-7)<=2,"unit":"count","reason":"best_z="+str(best_bc_z)+" n="+str(best_bc_n)+" results="+str([(b[1],b[0]) for b in blade_results])})

# Blade tip radii
check_results.append({"check_name":"blade_tip_r_base","measured":round(max_base_r,3),"expected":65.0,"passed":abs(max_base_r-65.0)<=12,"unit":"mm","reason":"max_r_at_base="+str(round(max_base_r,3))+" exp=65"})
check_results.append({"check_name":"blade_tip_r_top","measured":round(max_top_r,3),"expected":20.0,"passed":abs(max_top_r-20.0)<=10,"unit":"mm","reason":"max_r_at_top="+str(round(max_top_r,3))+" exp=20"})

# 7-fold symmetry
sec7=[0,0,0,0,0,0,0]
ssz7=2*math.pi/7
for i in range(nv):
    r2=math.sqrt(vx[i]*vx[i]+vy[i]*vy[i])
    if r2>16.0:
        ang=(math.atan2(vy[i],vx[i]))%(2*math.pi)
        idx=int(ang/ssz7)%7
        sec7[idx]+=1
msec7=sum(sec7)/7.0
var7=round((max(sec7)-min(sec7))/(msec7+0.001),3)
check_results.append({"check_name":"7fold_symmetry","measured":var7,"expected":"<0.5","passed":var7<0.5,"unit":"ratio","reason":"sec="+str(sec7)})

# Avg edge
avg_e = round(mesh.averageEdgeLength(),3)
check_results.append({"check_name":"avg_edge_length","measured":avg_e,"expected":"<5.0","passed":avg_e<5.0,"unit":"mm","reason":"avg="+str(avg_e)})

for row in check_results:
    print(str(row["passed"])+" "+row["check_name"]+" "+str(row["measured"]))
