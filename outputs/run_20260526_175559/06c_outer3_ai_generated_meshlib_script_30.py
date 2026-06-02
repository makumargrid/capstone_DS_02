
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

# Test a range loop calling mesh.normal
chk = 0; ov_d = 0
for k in range(0, 20, 1):
    fi = mrmesh.FaceId(k)
    n = mesh.normal(fi)
    chk += 1
    if n.z < 0:
        ov_d += 1

check_results.append({"check_name":"loop20_normal","measured":chk,"expected":20,"passed":chk==20,"unit":"count","reason":"down="+str(ov_d)})
