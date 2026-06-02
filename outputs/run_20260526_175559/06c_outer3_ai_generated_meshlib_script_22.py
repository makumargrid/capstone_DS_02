
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

# NO vertex iteration - only face-based
face_list = []
for fid in mesh.topology.getValidFaces():
    face_list.append(fid)
nf = len(face_list)

ov_p = 0; ov_d = 0; checked = 0
stride = max(1, nf//200)
for k in range(0, nf, stride):
    fid = face_list[k]
    n = mesh.normal(fid)
    checked += 1
    if n.z < 0:
        ov_d += 1
        if n.z > -0.707:
            ov_p += 1

ov_pct = round(100.0*ov_p/checked, 2) if checked else 0
check_results.append({"check_name":"FDM_overhang_pct","measured":ov_pct,"expected":"<15.0","passed":ov_pct<15.0,"unit":"%","reason":"prob="+str(ov_p)+"/"+str(checked)+" downfacing="+str(ov_d)})

for row in check_results:
    print(("PASS" if row["passed"] else "FAIL")+" "+row["check_name"]+": "+str(row["measured"])+" "+row["unit"])
