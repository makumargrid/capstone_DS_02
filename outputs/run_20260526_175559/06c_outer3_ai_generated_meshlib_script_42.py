
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

bb = mesh.getBoundingBox()
bmin = bb.min; bmax = bb.max
dz = bmax.z - bmin.z; zlo = bmin.z

vx=[]; vy=[]; vz_arr=[]
for vid in mesh.topology.getValidVerts():
    p = mesh.points.vec[vid.get()]
    vx.append(p.x); vy.append(p.y); vz_arr.append(p.z)
nv = len(vx)

# 7-fold symmetry
sec7=[0]*7; ssz7=2*math.pi/7
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
check_results.append({"check_name":"avg_edge_length","measured":ae,"expected":"<5.0","passed":ae<5.0,"unit":"mm","reason":"avg="+str(ae)+"mm"})

# blade twist: outer verts at base vs top
ang_b=[]; ang_t=[]
ztop60 = zlo+60.0
for i in range(nv):
    ri=math.sqrt(vx[i]*vx[i]+vy[i]*vy[i])
    if vz_arr[i]-zlo < 2.0 and ri>52.0:
        ang_b.append(math.atan2(vy[i],vx[i]))
    if abs(vz_arr[i]-ztop60)<3.0 and ri>17.0:
        ang_t.append(math.atan2(vy[i],vx[i]))

def peaks7(angles, nb=72):
    if not angles: return []
    cnt=[0]*nb
    for a in angles:
        cnt[int(((a%(2*math.pi))/(2*math.pi))*nb)%nb]+=1
    pks=[]
    for i in range(nb):
        if cnt[i]>0 and cnt[i]>=cnt[(i-1)%nb] and cnt[i]>=cnt[(i+1)%nb]:
            pks.append((i*360.0/nb,cnt[i]))
    pks.sort(key=lambda t:-t[1])
    return sorted([p[0] for p in pks[:7]])

pb=peaks7(ang_b); pt=peaks7(ang_t)
if pb and pt:
    mb=sum(pb)/len(pb); mt=sum(pt)/len(pt)
    tw=mt-mb
    if tw>180: tw-=360
    if tw<-180: tw+=360
    ta=round(abs(tw),2)
    check_results.append({"check_name":"blade_twist_angle","measured":ta,"expected":60.0,"passed":abs(ta-60.0)<=35,"unit":"degrees","reason":"shift="+str(ta)+"deg base="+str([round(p,1) for p in pb])+" top="+str([round(p,1) for p in pt])})
else:
    check_results.append({"check_name":"blade_twist_angle","measured":-1,"expected":60.0,"passed":False,"unit":"degrees","reason":"base_n="+str(len(ang_b))+" top_n="+str(len(ang_t))})

# hub top cone diam (only vertices r<=16mm near Z=60)
top_cone=[math.sqrt(vx[i]*vx[i]+vy[i]*vy[i]) for i in range(nv) if abs(vz_arr[i]-ztop60)<3.0 and math.sqrt(vx[i]*vx[i]+vy[i]*vy[i])<=16.0]
if top_cone:
    htd=round(2.0*max(top_cone),3)
    check_results.append({"check_name":"hub_top_cone_diam","measured":htd,"expected":30.0,"passed":abs(htd-30.0)<=5,"unit":"mm","reason":"max_r(r<=16)="+str(round(max(top_cone),3))+"mm n="+str(len(top_cone))})

for row in check_results:
    print(("PASS" if row["passed"] else "FAIL")+" "+row["check_name"]+": "+str(row["measured"])+" "+row["unit"])
