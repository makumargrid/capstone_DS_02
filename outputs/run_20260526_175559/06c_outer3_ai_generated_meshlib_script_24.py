
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

# Store face IDs as integers
face_ids_int = []
for fid in mesh.topology.getValidFaces():
    face_ids_int.append(fid.get())

check_results.append({"check_name":"face_int_list","measured":len(face_ids_int),"expected":"ok","passed":True,"unit":"count","reason":"first="+str(face_ids_int[0])+" last="+str(face_ids_int[-1])})

# Now call normal using FaceId constructed from int
fi = mrmesh.FaceId(face_ids_int[100])
n = mesh.normal(fi)
check_results.append({"check_name":"normal_from_int","measured":round(n.z,4),"expected":"ok","passed":True,"unit":"info","reason":""})

# overhang with integer approach
stride = max(1, len(face_ids_int)//200)
ov_p = 0; ov_d = 0; chk = 0
for k in range(0, len(face_ids_int), stride):
    fi2 = mrmesh.FaceId(face_ids_int[k])
    n2 = mesh.normal(fi2)
    chk += 1
    if n2.z < 0:
        ov_d += 1
        if n2.z > -0.707:
            ov_p += 1

ov_pct = round(100.0*ov_p/chk, 2) if chk else 0
check_results.append({"check_name":"FDM_overhang_pct","measured":ov_pct,"expected":"<15.0","passed":ov_pct<15.0,"unit":"%","reason":"prob="+str(ov_p)+"/"+str(chk)+" down="+str(ov_d)})

for row in check_results:
    print(("PASS" if row["passed"] else "FAIL")+" "+row["check_name"]+": "+str(row["measured"])+" "+row["unit"])
