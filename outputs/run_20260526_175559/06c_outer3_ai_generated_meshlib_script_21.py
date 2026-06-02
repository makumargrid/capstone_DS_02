
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

# Build face list ONCE only and check capacity
face_list = []
for fid in mesh.topology.getValidFaces():
    face_list.append(fid)
nf = len(face_list)

check_results.append({"check_name":"face_list_len","measured":nf,"expected":"ok","passed":True,"unit":"count","reason":""})

# iterate FIRST 10 ONLY (not a second iterator)
ov5 = 0
for k in range(min(10,nf)):
    fid = face_list[k]
    n = mesh.normal(fid)
    if n.z < 0:
        ov5 += 1

check_results.append({"check_name":"overhang_first10","measured":ov5,"expected":"ok","passed":True,"unit":"count","reason":""})

# iterate LAST 10 ONLY
ov5b = 0
for k in range(nf-10, nf):
    fid = face_list[k]
    n = mesh.normal(fid)
    if n.z < 0:
        ov5b += 1
check_results.append({"check_name":"overhang_last10","measured":ov5b,"expected":"ok","passed":True,"unit":"count","reason":""})

for row in check_results:
    print(("PASS" if row["passed"] else "FAIL")+" "+row["check_name"]+": "+str(row["measured"])+" "+row["unit"])
