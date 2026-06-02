
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

# Minimal test - just collect face list + check stride loop
face_list = []
for fid in mesh.topology.getValidFaces():
    face_list.append(fid)

check_results.append({"check_name":"nfaces","measured":len(face_list),"expected":4206,"passed":len(face_list)==4206,"unit":"count","reason":""})

# only process first 3 faces
for k in [0,1,2]:
    fid = face_list[k]
    n = mesh.normal(fid)
    check_results.append({"check_name":"nz_face"+str(k),"measured":round(n.z,4),"expected":"ok","passed":True,"unit":"info","reason":""})

for row in check_results:
    print(("PASS" if row["passed"] else "FAIL")+" "+row["check_name"]+": "+str(row["measured"]))
