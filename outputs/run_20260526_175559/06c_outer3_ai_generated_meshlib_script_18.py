
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

# Test ONLY face list collection
face_list = []
cnt = 0
for fid in mesh.topology.getValidFaces():
    face_list.append(fid)
    cnt += 1

check_results.append({"check_name":"face_count","measured":cnt,"expected":"ok","passed":True,"unit":"count","reason":""})

# test normal on first face
if face_list:
    n0 = mesh.normal(face_list[0])
    check_results.append({"check_name":"normal_test","measured":str(round(n0.x,3))+","+str(round(n0.y,3))+","+str(round(n0.z,3)),"expected":"ok","passed":True,"unit":"info","reason":""})

# test overhang on FIRST 5 faces only
ov_count = 0
down_count = 0
for fid in face_list[:5]:
    n = mesh.normal(fid)
    if n.z < 0:
        down_count += 1
        if n.z > -0.707:
            ov_count += 1
check_results.append({"check_name":"overhang_5faces","measured":ov_count,"expected":"ok","passed":True,"unit":"count","reason":"down="+str(down_count)})
