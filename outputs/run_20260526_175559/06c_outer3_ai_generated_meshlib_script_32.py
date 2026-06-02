
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

# Let's probe where the crash happens step by step
nf = mesh.topology.faceSize()
check_results.append({"check_name":"nf","measured":nf,"expected":"ok","passed":True,"unit":"count","reason":""})

stride = 21  # exactly nf//200
check_results.append({"check_name":"stride","measured":stride,"expected":"ok","passed":True,"unit":"count","reason":""})

# Test just range(0, 100, 21) 
ov_d = 0; chk = 0
for k in range(0, 100, 21):
    fi = mrmesh.FaceId(k)
    hf = mesh.topology.hasFace(fi)
    if not hf:
        continue
    n = mesh.normal(fi)
    chk += 1
    if n.z < 0:
        ov_d += 1

check_results.append({"check_name":"loop_100","measured":chk,"expected":"ok","passed":True,"unit":"count","reason":"down="+str(ov_d)})
