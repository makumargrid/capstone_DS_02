
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

# Try calling mesh.normal with FaceId(int)
fi0 = mrmesh.FaceId(0)
n0 = mesh.normal(fi0)
check_results.append({"check_name":"normal_FaceId0","measured":round(n0.z,4),"expected":"ok","passed":True,"unit":"info","reason":str(round(n0.x,4))+","+str(round(n0.y,4))+","+str(round(n0.z,4))})
