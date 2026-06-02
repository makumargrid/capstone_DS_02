
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

# FACE OVERHANG SCAN ONLY
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

ov_pct = round(100.0*ov_p/chk, 2) if chk else 0
check_results.append({"check_name":"FDM_overhang_pct","measured":ov_pct,"expected":"<15.0","passed":ov_pct<15.0,"unit":"%","reason":"prob="+str(ov_p)+"/"+str(chk)+" downfacing="+str(ov_d)+"/"+str(chk)})

for row in check_results:
    print(("PASS" if row["passed"] else "FAIL")+" "+row["check_name"]+": "+str(row["measured"])+" "+row["unit"])
