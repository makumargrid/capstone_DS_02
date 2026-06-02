
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

# blade count 
gr = math.radians(15.0)
bc_list = []
for frac in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
    zt = zlo + frac*dz
    ag = []
    for i in range(nv):
        ri = math.sqrt(vx[i]*vx[i]+vy[i]*vy[i])
        if abs(vz_arr[i]-zt)<2.5 and 15.0<ri<90.0:
            ag.append(math.atan2(vy[i],vx[i]))
    if len(ag) < 5:
        bc_list.append((0, 0, round(zt,1)))
        continue
    ag.sort()
    gaps = 0
    for k in range(1,len(ag)):
        if ag[k]-ag[k-1] > gr:
            gaps += 1
    wp = (ag[0]+2*math.pi) - ag[-1]
    if wp > gr:
        gaps += 1
    bc_list.append((len(ag), gaps, round(zt,1)))

bc_list.sort(reverse=True)
best_n2 = bc_list[0][0]
best_c2 = bc_list[0][1]
best_z2 = bc_list[0][2]
check_results.append({"check_name":"blade_count_estimate","measured":best_c2,"expected":7,"passed":abs(best_c2-7)<=2,"unit":"count","reason":"best_z="+str(best_z2)+"mm n="+str(best_n2)+" all="+str([(b[2],b[1]) for b in bc_list])})

# blade twist angle: compare angle histogram at base vs top
ang_base_list = []
for i in range(nv):
    ri = math.sqrt(vx[i]*vx[i]+vy[i]*vy[i])
    if vz_arr[i]-zlo < 2.0 and ri > 52.0:
        ang_base_list.append(math.atan2(vy[i],vx[i]))

ang_top_list = []
ztop60 = zlo + 60.0
for i in range(nv):
    ri = math.sqrt(vx[i]*vx[i]+vy[i]*vy[i])
    if abs(vz_arr[i]-ztop60) < 3.0 and ri > 17.0:
        ang_top_list.append(math.atan2(vy[i],vx[i]))

def get_peaks(ang_list, nbins):
    if not ang_list:
        return []
    cnt = [0]*nbins
    for a in ang_list:
        idx = int(((a % (2*math.pi)) / (2*math.pi)) * nbins) % nbins
        cnt[idx] += 1
    pks = []
    for i in range(nbins):
        if cnt[i]>0 and cnt[i]>=cnt[(i-1)%nbins] and cnt[i]>=cnt[(i+1)%nbins]:
            pks.append((i*360.0/nbins, cnt[i]))
    pks.sort(key=lambda t: -t[1])
    top7 = sorted([p[0] for p in pks[:7]])
    return top7

pb2 = get_peaks(ang_base_list, 72)
pt2 = get_peaks(ang_top_list, 72)
if pb2 and pt2:
    mean_b = sum(pb2)/len(pb2)
    mean_t = sum(pt2)/len(pt2)
    tw2 = mean_t - mean_b
    if tw2 > 180: tw2 -= 360
    if tw2 < -180: tw2 += 360
    ta2 = round(abs(tw2), 2)
    check_results.append({"check_name":"blade_twist_angle","measured":ta2,"expected":60.0,"passed":abs(ta2-60.0)<=35,"unit":"degrees","reason":"shift="+str(ta2)+"deg base="+str([round(p,1) for p in pb2])+" top="+str([round(p,1) for p in pt2])})
else:
    check_results.append({"check_name":"blade_twist_angle","measured":-1,"expected":60.0,"passed":False,"unit":"degrees","reason":"insufficient data base_n="+str(len(ang_base_list))+" top_n="+str(len(ang_top_list))})

# hub top cone diam (strip blade tips)
ztop60 = zlo+60.0
top_cone_r = []
for i in range(nv):
    ri = math.sqrt(vx[i]*vx[i]+vy[i]*vy[i])
    if abs(vz_arr[i]-ztop60) < 3.0 and ri <= 16.0:
        top_cone_r.append(ri)
if top_cone_r:
    hub_top_d = round(2.0*max(top_cone_r),3)
    check_results.append({"check_name":"hub_top_cone_diam","measured":hub_top_d,"expected":30.0,"passed":abs(hub_top_d-30.0)<=5,"unit":"mm","reason":"max_r(r<=16mm)="+str(round(max(top_cone_r),3))+" n="+str(len(top_cone_r))})

# 7-fold symmetry
sec7=[0]*7
ssz7 = 2*math.pi/7
for i in range(nv):
    ri=math.sqrt(vx[i]*vx[i]+vy[i]*vy[i])
    if ri>16.0:
        ai=(math.atan2(vy[i],vx[i]))%(2*math.pi)
        sec7[int(ai/ssz7)%7]+=1
m7=sum(sec7)/7.0
v7=round((max(sec7)-min(sec7))/(m7+0.001),3)
check_results.append({"check_name":"7fold_symmetry","measured":v7,"expected":"<0.5","passed":v7<0.5,"unit":"ratio","reason":"sectors="+str(sec7)+" var="+str(v7)})

# avg edge
ae = round(mesh.averageEdgeLength(),3)
check_results.append({"check_name":"avg_edge_length","measured":ae,"expected":"<5.0","passed":ae<5.0,"unit":"mm","reason":"avg_edge="+str(ae)+"mm"})

for row in check_results:
    print(("PASS" if row["passed"] else "FAIL")+" "+row["check_name"]+": "+str(row["measured"])+" "+row["unit"])
