
import meshlib.mrmeshpy as mrmesh
import math
import statistics as stats

check_results = []

def vec3(x, y, z):
    v = mrmesh.Vector3f()
    v.x = x; v.y = y; v.z = z
    return v

# ── Bounding box ─────────────────────────────────────────────────────────────
bb = mesh.getBoundingBox()
mn = bb.min; mx = bb.max
dim_x = mx.x - mn.x
dim_y = mx.y - mn.y
dim_z = mx.z - mn.z
z_min = mn.z

check_results.append({"check_name":"bbox_x","measured":round(dim_x,3),"expected":160.4,"passed":abs(dim_x-160.4)<=15,"unit":"mm","reason":f"Δ={abs(dim_x-160.4):.3f}mm vs tol 15mm"})
check_results.append({"check_name":"bbox_y","measured":round(dim_y,3),"expected":160.4,"passed":abs(dim_y-160.4)<=15,"unit":"mm","reason":f"Δ={abs(dim_y-160.4):.3f}mm vs tol 15mm"})
check_results.append({"check_name":"bbox_z","measured":round(dim_z,3),"expected":71.5,"passed":abs(dim_z-71.5)<=15,"unit":"mm","reason":f"Δ={abs(dim_z-71.5):.3f}mm vs tol 15mm"})

# ── All vertices ──────────────────────────────────────────────────────────────
all_v = []
for vid in mesh.topology.getValidVerts():
    p = mesh.points.vec[vid.get()]
    all_v.append((p.x, p.y, p.z))

# ── Hub base diameter ────────────────────────────────────────────────────────
vb = [(x,y,z) for x,y,z in all_v if z - z_min < 2.0]
rb = [math.sqrt(x*x+y*y) for x,y,z in vb]
bd = 2.0*max(rb) if rb else 0
check_results.append({
    "check_name":"hub_base_outer_diameter",
    "measured":round(bd,3),"expected":100.0,
    "passed":abs(bd-100.0)<=15,
    "unit":"mm",
    "reason":f"Max r={max(rb):.3f}mm at Z∈[{z_min:.2f},{z_min+2:.2f}]mm, {len(vb)} verts. Note: blade tips included."
})

# ── Hub top diameter ──────────────────────────────────────────────────────────
z_top = z_min+60.0
vt = [(x,y,z) for x,y,z in all_v if abs(z-z_top)<3.0]
rt = [math.sqrt(x*x+y*y) for x,y,z in vt]
td = 2.0*max(rt) if rt else 0
check_results.append({
    "check_name":"hub_top_outer_diameter",
    "measured":round(td,3),"expected":30.0,
    "passed":abs(td-30.0)<=15,
    "unit":"mm",
    "reason":f"Max r={max(rt):.3f}mm at Z≈{z_top:.1f}mm, {len(vt)} verts. Min r={min(rt):.3f}mm."
})

# ── Total height ──────────────────────────────────────────────────────────────
check_results.append({
    "check_name":"hub_total_height","measured":round(dim_z,3),"expected":60.0,
    "passed":abs(dim_z-60.0)<=15,
    "unit":"mm","reason":f"Z range [{mn.z:.2f},{mx.z:.2f}]mm. Blade tips add ~{dim_z-60:.1f}mm above hub body."
})

# ── Central bore diameter ──────────────────────────────────────────────────────
all_r = sorted([math.sqrt(x*x+y*y) for x,y,z in all_v])
inner_r = [r for r in all_r if r < 12.0]
zone20  = [r for r in all_r if r < 20.0]
if inner_r:
    bd2 = 2.0*max(inner_r)
    note2 = f"{len(inner_r)} verts in r<12mm, max_r={max(inner_r):.4f}mm → Ø{bd2:.3f}mm"
elif zone20:
    bd2 = 2.0*min(zone20)
    note2 = f"No verts in r<12mm; smallest r in r<20mm = {min(zone20):.4f}mm → bore may be solid"
else:
    bd2 = 2.0*all_r[0]
    note2 = f"Min r globally = {all_r[0]:.4f}mm — bore absent"
check_results.append({
    "check_name":"central_bore_diameter","measured":round(bd2,3),"expected":15.0,
    "passed":abs(bd2-15.0)<=5,
    "unit":"mm","reason":note2
})

# ── Blade count (angular gap method) ─────────────────────────────────────────
def blade_count_at(z_tgt, z_tol=2.5, rmin=15.0, rmax=90.0, gap_deg=15.0):
    gap_r = math.radians(gap_deg)
    angles = sorted([math.atan2(y,x) for x,y,z in all_v
                     if abs(z-z_tgt)<z_tol and rmin<math.sqrt(x*x+y*y)<rmax])
    if len(angles)<5:
        return 0, 0
    gaps=[angles[i]-angles[i-1] for i in range(1,len(angles)) if angles[i]-angles[i-1]>gap_r]
    wrap=(angles[0]+2*math.pi)-angles[-1]
    if wrap>gap_r: gaps.append(wrap)
    return len(gaps), len(angles)

results_per_z = {}
for frac in [0.2,0.3,0.4,0.5,0.6,0.7,0.8]:
    zz = z_min + frac*60.0
    c, n = blade_count_at(zz)
    results_per_z[frac] = (c, n, zz)

best = max(results_per_z.values(), key=lambda t: t[1])
best_c, best_n, best_z = best
check_results.append({
    "check_name":"blade_count_estimate",
    "measured":best_c,"expected":7,
    "passed":abs(best_c-7)<=2,
    "unit":"count",
    "reason":f"Best at Z={best_z:.1f}mm: {best_c} blades ({best_n} verts). Per-Z: "+
             ", ".join([f"Z{int(f*100)}%={v[0]}b/{v[1]}v" for f,v in sorted(results_per_z.items())])
})

# ── Blade tip radius at base ───────────────────────────────────────────────────
if rb:
    max_rb = max(rb)
    check_results.append({
        "check_name":"blade_tip_radius_at_base","measured":round(max_rb,3),"expected":65.0,
        "passed":abs(max_rb-65.0)<=12,
        "unit":"mm","reason":f"Max r at base = {max_rb:.3f}mm (expected hub50+protrusion15=65mm). Δ={abs(max_rb-65):.3f}mm"
    })

# ── Blade tip radius at top ────────────────────────────────────────────────────
if rt:
    max_rt = max(rt)
    check_results.append({
        "check_name":"blade_tip_radius_at_top","measured":round(max_rt,3),"expected":20.0,
        "passed":abs(max_rt-20.0)<=10,
        "unit":"mm","reason":f"Max r at top = {max_rt:.3f}mm (expected hub15+protrusion5=20mm). Δ={abs(max_rt-20):.3f}mm"
    })

# ── Blade twist angle ─────────────────────────────────────────────────────────
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
            pks.append((i/n*360.0, cnt[i]))
    pks.sort(key=lambda p:-p[1])
    return sorted([p[0] for p in pks[:7]])

pb=hist_peaks(ang_b); pt=hist_peaks(ang_t)
if pb and pt:
    tw=stats.mean(pt)-stats.mean(pb)
    if tw>180: tw-=360
    if tw<-180: tw+=360
    ta=abs(tw)
    check_results.append({
        "check_name":"blade_twist_angle_base_to_top","measured":round(ta,2),"expected":60.0,
        "passed":abs(ta-60.0)<=35,
        "unit":"degrees",
        "reason":f"Peak shift {tw:.2f}° (|{ta:.2f}°| vs 60°±35°). Base: {[round(p,1) for p in pb]}, Top: {[round(p,1) for p in pt]}"
    })

# ── 7-fold symmetry ───────────────────────────────────────────────────────────
sec=[0]*7; ssz=2*math.pi/7
for x,y,z in all_v:
    r=math.sqrt(x*x+y*y)
    if r>16.0:
        a=math.atan2(y,x)%(2*math.pi)
        sec[int(a/ssz)%7]+=1
msec=sum(sec)/7.0
var=(max(sec)-min(sec))/(msec+1e-9)
check_results.append({
    "check_name":"7fold_rotational_symmetry","measured":round(var,3),"expected":"<0.5",
    "passed":var<0.5,
    "unit":"ratio","reason":f"Sector counts: {sec}; (max-min)/mean={var:.3f}"
})

# ── Avg edge length ────────────────────────────────────────────────────────────
avg_e=mesh.averageEdgeLength()
check_results.append({
    "check_name":"avg_edge_length","measured":round(avg_e,3),"expected":"<5.0",
    "passed":avg_e<5.0,
    "unit":"mm","reason":f"Avg edge {avg_e:.3f}mm. {'Sufficient' if avg_e<5 else 'Coarse'} to resolve 2mm features."
})

for r in check_results:
    print(f"[{'PASS' if r['passed'] else 'FAIL'}] {r['check_name']}: {r['measured']} {r['unit']}")
