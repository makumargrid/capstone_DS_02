
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

# Range 0 to 500 (small range to find crash point)
ov_p = 0; ov_d = 0; chk = 0
for k in range(0, 500, 21):
    fi = mrmesh.FaceId(k)
    if not mesh.topology.hasFace(fi):
        continue
    n = mesh.normal(fi)
    chk += 1
    if n.z < 0:
        ov_d += 1
        if n.z > -0.707:
            ov_p += 1

check_results.append({"check_name":"range0_500","measured":chk,"expected":"ok","passed":True,"unit":"count","reason":"down="+str(ov_d)+" prob="+str(ov_p)})
