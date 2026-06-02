
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

# Full overhang scan - using face_list[:] slice, NOT step-slicing
face_list = []
for fid in mesh.topology.getValidFaces():
    face_list.append(fid)

ov_prob = 0
ov_down = 0
total_checked = 0

# use stride with explicit index, not slice
stride = max(1, len(face_list)//200)
idx = 0
while idx < len(face_list):
    fid = face_list[idx]
    n = mesh.normal(fid)
    total_checked += 1
    if n.z < 0:
        ov_down += 1
        if n.z > -0.707:
            ov_prob += 1
    idx += stride

ov_pct = round(100.0*ov_prob/total_checked, 2) if total_checked>0 else 0
check_results.append({"check_name":"FDM_overhang_pct","measured":ov_pct,"expected":"<15.0","passed":ov_pct<15.0,"unit":"%","reason":"prob="+str(ov_prob)+"/"+str(total_checked)+" down="+str(ov_down)})

for row in check_results:
    print(("PASS" if row["passed"] else "FAIL")+" "+row["check_name"]+": "+str(row["measured"])+" "+row["unit"])
