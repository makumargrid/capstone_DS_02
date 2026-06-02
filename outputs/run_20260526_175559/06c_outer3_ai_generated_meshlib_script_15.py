
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

bb = mesh.getBoundingBox()
bmin = bb.min; bmax = bb.max
dx = bmax.x - bmin.x; dy = bmax.y - bmin.y; dz = bmax.z - bmin.z
zlo = bmin.z

vx=[]; vy=[]; vz_arr=[]
for vid in mesh.topology.getValidVerts():
    p = mesh.points.vec[vid.get()]
    vx.append(p.x); vy.append(p.y); vz_arr.append(p.z)
nv = len(vx)

# Blade count - SIMPLIFIED: just one Z level
gr = math.radians(15.0)
zt = zlo + 0.5*dz
ag = []
for i in range(nv):
    ri = math.sqrt(vx[i]*vx[i]+vy[i]*vy[i])
    if abs(vz_arr[i]-zt)<2.5 and 15.0<ri<90.0:
        ag.append(math.atan2(vy[i],vx[i]))
ag.sort()
gaps2 = 0
for k in range(1,len(ag)):
    if ag[k]-ag[k-1] > gr:
        gaps2 += 1
if ag:
    wp = (ag[0]+2*math.pi) - ag[-1]
    if wp > gr:
        gaps2 += 1
check_results.append({"check_name":"blade_count_midZ","measured":gaps2,"expected":7,"passed":abs(gaps2-7)<=2,"unit":"count","reason":"Z="+str(round(zt,1))+" n_verts="+str(len(ag))})

check_results.append({"check_name":"cp1","measured":1,"expected":1,"passed":True,"unit":"info","reason":"blade_count done"})
