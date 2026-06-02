
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

# 7-fold symmetry ONLY
sec7=[0]*7; ssz7=2*math.pi/7
for i in range(nv):
    ri=math.sqrt(vx[i]*vx[i]+vy[i]*vy[i])
    if ri>16.0:
        ai=(math.atan2(vy[i],vx[i]))%(2*math.pi)
        sec7[int(ai/ssz7)%7]+=1
m7=sum(sec7)/7.0
v7=round((max(sec7)-min(sec7))/(m7+0.001),3)
check_results.append({"check_name":"7fold_symmetry","measured":v7,"expected":"<0.5","passed":v7<0.5,"unit":"ratio","reason":"sectors="+str(sec7)+" var="+str(v7)})

for row in check_results:
    print(("PASS" if row["passed"] else "FAIL")+" "+row["check_name"]+": "+str(row["measured"])+" "+row["unit"])
