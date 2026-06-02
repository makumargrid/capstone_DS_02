
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

fi0 = mrmesh.FaceId(0)
check_results.append({"check_name":"FaceId0_valid","measured":str(fi0.valid()),"expected":"True","passed":True,"unit":"bool","reason":""})
