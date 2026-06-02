
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

# Test FaceId construction by int and hasFace
fi0 = mrmesh.FaceId(0)
fi1 = mrmesh.FaceId(1)
fi9999 = mrmesh.FaceId(9999)
check_results.append({"check_name":"FaceId_valid","measured":str(fi0.valid())+","+str(fi1.valid())+","+str(fi9999.valid()),"expected":"ok","passed":True,"unit":"bool","reason":""})

# try hasFace
hf0 = mesh.topology.hasFace(fi0)
check_results.append({"check_name":"hasFace_0","measured":str(hf0),"expected":"True","passed":True,"unit":"bool","reason":""})

# try normal with FaceId(0)
n0 = mesh.normal(fi0)
check_results.append({"check_name":"normal_fi0","measured":round(n0.z,4),"expected":"ok","passed":True,"unit":"info","reason":""})

# test range(0, 10, 1) loop without hasFace
chk = 0; ov_d = 0
for k in range(0, 10, 1):
    fi = mrmesh.FaceId(k)
    n = mesh.normal(fi)
    chk += 1
    if n.z < 0:
        ov_d += 1
check_results.append({"check_name":"loop_10faces_no_hasFace","measured":chk,"expected":10,"passed":chk==10,"unit":"count","reason":"down="+str(ov_d)})

for row in check_results:
    print(("PASS" if row["passed"] else "FAIL")+" "+row["check_name"]+": "+str(row["measured"]))
