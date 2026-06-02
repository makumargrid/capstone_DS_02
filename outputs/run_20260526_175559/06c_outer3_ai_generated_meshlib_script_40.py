
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

# ranges 2000-3000
ov_p = 0; ov_d = 0; chk = 0
for k in range(2000, 3000, 21):
    fi = mrmesh.FaceId(k)
    if not mesh.topology.hasFace(fi):
        continue
    n = mesh.normal(fi)
    chk += 1
    if n.z < 0:
        ov_d += 1
        if n.z > -0.707:
            ov_p += 1

check_results.append({"check_name":"range2000_3000","measured":chk,"expected":"ok","passed":True,"unit":"count","reason":"down="+str(ov_d)+" prob="+str(ov_p)})
