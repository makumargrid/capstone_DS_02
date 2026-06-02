
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

# Bounding box
bb = mesh.getBoundingBox()
mn = bb.min; mx = bb.max
dim_x = mx.x - mn.x
dim_y = mx.y - mn.y
dim_z = mx.z - mn.z
z_min = mn.z

check_results.append({"check_name":"bbox_x","measured":round(dim_x,3),"expected":160.4,"passed":abs(dim_x-160.4)<=15,"unit":"mm","reason":"delta="+str(round(abs(dim_x-160.4),3))+"mm"})
check_results.append({"check_name":"bbox_y","measured":round(dim_y,3),"expected":160.4,"passed":abs(dim_y-160.4)<=15,"unit":"mm","reason":"delta="+str(round(abs(dim_y-160.4),3))+"mm"})
check_results.append({"check_name":"bbox_z","measured":round(dim_z,3),"expected":71.5,"passed":abs(dim_z-71.5)<=15,"unit":"mm","reason":"delta="+str(round(abs(dim_z-71.5),3))+"mm"})

# Vertices
all_v = []
for vid in mesh.topology.getValidVerts():
    p = mesh.points.vec[vid.get()]
    all_v.append((p.x, p.y, p.z))

# Hub base diameter
vb = [(x,y,z) for x,y,z in all_v if z - z_min < 2.0]
rb = [math.sqrt(x*x+y*y) for x,y,z in vb]
bd = round(2.0*max(rb),3) if rb else 0
check_results.append({"check_name":"hub_base_outer_diameter","measured":bd,"expected":100.0,"passed":abs(bd-100.0)<=15,"unit":"mm","reason":"max_r="+str(round(max(rb),3))+"mm, "+str(len(vb))+" verts in base slice"})

# Hub top diameter
z_top = z_min+60.0
vt = [(x,y,z) for x,y,z in all_v if abs(z-z_top)<3.0]
rt = [math.sqrt(x*x+y*y) for x,y,z in vt]
td = round(2.0*max(rt),3) if rt else 0
check_results.append({"check_name":"hub_top_outer_diameter","measured":td,"expected":30.0,"passed":abs(td-30.0)<=15,"unit":"mm","reason":"max_r="+str(round(max(rt),3))+"mm, min_r="+str(round(min(rt),3))+"mm, "+str(len(vt))+" verts"})

# Height
check_results.append({"check_name":"hub_total_height","measured":round(dim_z,3),"expected":60.0,"passed":abs(dim_z-60.0)<=15,"unit":"mm","reason":"Z range "+str(round(mn.z,3))+" to "+str(round(mx.z,3))+"mm"})

# Central bore
all_r = sorted([math.sqrt(x*x+y*y) for x,y,z in all_v])
inner_r = [r for r in all_r if r < 12.0]
zone20  = [r for r in all_r if r < 20.0]
if inner_r:
    bd2 = round(2.0*max(inner_r),3)
    note2 = str(len(inner_r))+" verts r<12mm; max_r="+str(round(max(inner_r),4))+"mm"
elif zone20:
    bd2 = round(2.0*min(zone20),3)
    note2 = "No verts r<12mm; min_r_in_zone20="+str(round(min(zone20),4))+"mm - bore may be solid"
else:
    bd2 = round(2.0*all_r[0],3)
    note2 = "Min r globally="+str(round(all_r[0],4))+"mm - bore absent"
check_results.append({"check_name":"central_bore_diameter","measured":bd2,"expected":15.0,"passed":abs(bd2-15.0)<=5,"unit":"mm","reason":note2})

# Blade count
def bc_at(z_tgt):
    gap_r = math.radians(15.0)
    angles = sorted([math.atan2(y,x) for x,y,z in all_v
                     if abs(z-z_tgt)<2.5 and 15.0<math.sqrt(x*x+y*y)<90.0])
    if len(angles)<5: return 0, 0
    gaps=[angles[i]-angles[i-1] for i in range(1,len(angles)) if angles[i]-angles[i-1]>gap_r]
    wrap=(angles[0]+2*math.pi)-angles[-1]
    if wrap>gap_r: gaps.append(wrap)
    return len(gaps), len(angles)

scores = []
for frac in [0.2,0.3,0.4,0.5,0.6,0.7,0.8]:
    c, n = bc_at(z_min+frac*60.0)
    scores.append((n, c, round(z_min+frac*60.0,1)))
best_n, best_c, best_z = max(scores, key=lambda x: x[0])
check_results.append({"check_name":"blade_count_estimate","measured":best_c,"expected":7,"passed":abs(best_c-7)<=2,"unit":"count","reason":"best at Z="+str(best_z)+"mm: "+str(best_c)+" blades from "+str(best_n)+" verts. scores="+str([(s[1],s[0]) for s in scores])})

# Blade tip at base
if rb:
    max_rb = round(max(rb),3)
    check_results.append({"check_name":"blade_tip_radius_at_base","measured":max_rb,"expected":65.0,"passed":abs(max_rb-65.0)<=12,"unit":"mm","reason":"max_r="+str(max_rb)+"mm vs expected 65mm (hub50+protrusion15)"})

# Blade tip at top
if rt:
    max_rt = round(max(rt),3)
    check_results.append({"check_name":"blade_tip_radius_at_top","measured":max_rt,"expected":20.0,"passed":abs(max_rt-20.0)<=10,"unit":"mm","reason":"max_r="+str(max_rt)+"mm vs expected 20mm (hub15+protrusion5)"})

# Blade twist
ang_b = [math.atan2(y,x) for x,y,z in vb if math.sqrt(x*x+y*y)>52.0]
ang_t = [math.atan2(y,x) for x,y,z in vt if math.sqrt(x*x+y*y)>17.0]
def hist_peaks(angles, n=72):
    if not angles: return []
    cnt=[0]*n
    for a in angles:
        cnt[int(((a%(2*math.pi))/(2*math.pi))*n)%n] += 1
    pks=[]
    for i in range(n):
        if cnt[i]>0 and cnt[i]>=cnt[(i-1)%n] and cnt[i]>=cnt[(i+1)%n]:
            pks.append((round(i/n*360.0,1), cnt[i]))
    pks.sort(key=lambda p:-p[1])
    return sorted([p[0] for p in pks[:7]])
pb=hist_peaks(ang_b); pt=hist_peaks(ang_t)
if pb and pt:
    tw=sum(pt)/len(pt)-sum(pb)/len(pb)
    if tw>180: tw-=360
    if tw<-180: tw+=360
    ta=round(abs(tw),2)
    check_results.append({"check_name":"blade_twist_angle","measured":ta,"expected":60.0,"passed":abs(ta-60.0)<=35,"unit":"degrees","reason":"peak_shift="+str(ta)+"deg vs 60deg+-35. base="+str(pb)+" top="+str(pt)})

# 7-fold symmetry
sec=[0]*7; ssz=2*math.pi/7
for x,y,z in all_v:
    r=math.sqrt(x*x+y*y)
    if r>16.0:
        a=math.atan2(y,x)%(2*math.pi)
        sec[int(a/ssz)%7]+=1
msec=sum(sec)/7.0
var=round((max(sec)-min(sec))/(msec+1e-9),3)
check_results.append({"check_name":"7fold_rotational_symmetry","measured":var,"expected":"<0.5","passed":var<0.5,"unit":"ratio","reason":"sector_counts="+str(sec)+" var="+str(var)})

# Avg edge length
avg_e=round(mesh.averageEdgeLength(),3)
check_results.append({"check_name":"avg_edge_length","measured":avg_e,"expected":"<5.0","passed":avg_e<5.0,"unit":"mm","reason":"avg_edge="+str(avg_e)+"mm"})

for r in check_results:
    print(("PASS" if r["passed"] else "FAIL")+" "+r["check_name"]+": "+str(r["measured"])+" "+r["unit"])
