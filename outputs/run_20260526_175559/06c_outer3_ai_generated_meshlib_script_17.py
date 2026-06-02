
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

# Face-based checks: overhang ONLY (no findClosestPoint)
face_list = []
for fid in mesh.topology.getValidFaces():
    face_list.append(fid)

step = max(1, len(face_list)//200)
sampled = face_list[::step]
total_s = len(sampled)

ov_prob = 0
ov_down = 0
for fid in sampled:
    n = mesh.normal(fid)
    if n.z < 0:
        ov_down += 1
        if n.z > -0.707:
            ov_prob += 1

ov_pct = round(100.0*ov_prob/total_s, 2)
check_results.append({"check_name":"FDM_overhang_pct","measured":ov_pct,"expected":"<15.0","passed":ov_pct<15.0,"unit":"%","reason":"prob_overhangs="+str(ov_prob)+"/"+str(total_s)+" total_downfacing="+str(ov_down)+"/"+str(total_s)})

for row in check_results:
    print(("PASS" if row["passed"] else "FAIL")+" "+row["check_name"]+": "+str(row["measured"])+" "+row["unit"])
