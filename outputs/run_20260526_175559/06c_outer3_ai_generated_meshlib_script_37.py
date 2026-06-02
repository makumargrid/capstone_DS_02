
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

# PART 1: All three ranges combined into one scan, no intermediate appends
ov_p = 0; ov_d = 0; chk = 0
for k in range(0, 4206, 21):
    fi = mrmesh.FaceId(k)
    if not mesh.topology.hasFace(fi):
        continue
    n = mesh.normal(fi)
    chk += 1
    if n.z < 0:
        ov_d += 1
        if n.z > -0.707:
            ov_p += 1

# NO intermediate check_results append - just compute the value
ov_pct_val = round(100.0*ov_p/chk, 2) if chk else 0

# Then do PART 2: 7-fold symmetry (vertex-only)
vx2=[]; vy2=[]
for vid in mesh.topology.getValidVerts():
    p = mesh.points.vec[vid.get()]
    vx2.append(p.x); vy2.append(p.y)
nv2 = len(vx2)

sec7=[0]*7; ssz7=2*math.pi/7
for i in range(nv2):
    ri=math.sqrt(vx2[i]*vx2[i]+vy2[i]*vy2[i])
    if ri>16.0:
        ai=(math.atan2(vy2[i],vx2[i]))%(2*math.pi)
        sec7[int(ai/ssz7)%7]+=1
m7=sum(sec7)/7.0
v7=round((max(sec7)-min(sec7))/(m7+0.001),3)

# avg edge
ae = round(mesh.averageEdgeLength(),3)

# NOW append all results at once
check_results.append({"check_name":"FDM_overhang_pct","measured":ov_pct_val,"expected":"<15.0","passed":ov_pct_val<15.0,"unit":"%","reason":"prob="+str(ov_p)+"/"+str(chk)+" down="+str(ov_d)})
check_results.append({"check_name":"7fold_symmetry","measured":v7,"expected":"<0.5","passed":v7<0.5,"unit":"ratio","reason":"sec="+str(sec7)})
check_results.append({"check_name":"avg_edge_length","measured":ae,"expected":"<5.0","passed":ae<5.0,"unit":"mm","reason":"avg="+str(ae)})

for row in check_results:
    print(("PASS" if row["passed"] else "FAIL")+" "+row["check_name"]+": "+str(row["measured"])+" "+row["unit"])
