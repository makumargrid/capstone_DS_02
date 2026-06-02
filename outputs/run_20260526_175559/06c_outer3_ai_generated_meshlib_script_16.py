
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

def vec3f(x,y,z):
    v = mrmesh.Vector3f(); v.x=x; v.y=y; v.z=z; return v

# Face-based checks: wall thickness + overhang
face_list = []
for fid in mesh.topology.getValidFaces():
    face_list.append(fid)

step = max(1, len(face_list)//150)
sampled = face_list[::step]

thick = []
ov_prob = 0
ov_down = 0
total_s = len(sampled)

for fid in sampled:
    n = mesh.normal(fid)
    tri = mesh.getTriPoints(fid)
    p0=tri[0]; p1=tri[1]; p2=tri[2]
    cx=(p0.x+p1.x+p2.x)/3.0
    cy=(p0.y+p1.y+p2.y)/3.0
    cz=(p0.z+p1.z+p2.z)/3.0
    
    # overhang
    if n.z < 0:
        ov_down += 1
        if n.z > -0.707:
            ov_prob += 1
    
    # wall thickness - shoot inward
    probe = vec3f(cx-n.x*0.1, cy-n.y*0.1, cz-n.z*0.1)
    res = mesh.findClosestPoint(probe)
    if res and res.valid():
        hp = res.proj.point
        d = math.sqrt((hp.x-cx)**2+(hp.y-cy)**2+(hp.z-cz)**2)
        if 0.1 < d < 50.0:
            thick.append(d)

if thick:
    thick.sort()
    mn_t = thick[0]
    p5_t = thick[max(0,int(0.05*len(thick)))]
    avg_t = sum(thick)/len(thick)
    check_results.append({"check_name":"wall_thickness_5pct","measured":round(p5_t,3),"expected":2.0,"passed":p5_t>=2.0,"unit":"mm","reason":"5pct="+str(round(p5_t,3))+" min="+str(round(mn_t,3))+" avg="+str(round(avg_t,3))+" n="+str(len(thick))})

ov_pct = round(100.0*ov_prob/total_s, 2)
check_results.append({"check_name":"FDM_overhang_pct","measured":ov_pct,"expected":"<15.0","passed":ov_pct<15.0,"unit":"%","reason":"prob_ov="+str(ov_prob)+"/"+str(total_s)+" down="+str(ov_down)+"/"+str(total_s)})

for row in check_results:
    print(("PASS" if row["passed"] else "FAIL")+" "+row["check_name"]+": "+str(row["measured"])+" "+row["unit"])
