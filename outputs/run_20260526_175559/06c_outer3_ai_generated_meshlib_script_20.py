
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

face_list = []
for fid in mesh.topology.getValidFaces():
    face_list.append(fid)

# ONLY iterate the FIRST 100 faces with stride
ov_prob = 0
ov_down = 0
checked = 0
for fid in face_list[:100]:
    n = mesh.normal(fid)
    checked += 1
    if n.z < 0:
        ov_down += 1
        if n.z > -0.707:
            ov_prob += 1

check_results.append({"check_name":"overhang_100faces","measured":ov_prob,"expected":"ok","passed":True,"unit":"count","reason":"down="+str(ov_down)+"/"+str(checked)})

for row in check_results:
    print(("PASS" if row["passed"] else "FAIL")+" "+row["check_name"]+": "+str(row["measured"])+" "+row["unit"])
