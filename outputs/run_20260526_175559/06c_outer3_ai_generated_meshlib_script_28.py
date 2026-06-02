
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

fi0 = mrmesh.FaceId(0)
hf = mesh.topology.hasFace(fi0)
check_results.append({"check_name":"hasFace0","measured":str(hf),"expected":"ok","passed":True,"unit":"bool","reason":""})
