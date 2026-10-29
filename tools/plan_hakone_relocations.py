"""Preserve object identity while proposing a cross city and Odawara UN site.

Reads current SavedData and GIS design inputs. This is deliberately a migration
plan, not an installer: cargo, fixed supports, controllers, entities and traffic
must move together in a later reversible transaction.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import nbtlib
import numpy as np


def unpack(value):
    value=int(value)&((1<<64)-1)
    x,z,y=value>>38,(value>>12)&0x3ffffff,value&4095
    return [x-(1<<26) if x>=1<<25 else x,y-4096 if y>=2048 else y,z-(1<<26) if z>=1<<25 else z]


def intersects(a,b):
    return not(a[2]<b[0] or b[2]<a[0] or a[3]<b[1] or b[3]<a[1])


def footprint(tower,centre,margin=4):
    p=tower.get("Footprint",{});half=int(tower["Half"]);x,_,z=centre
    return [x+int(p.get("MinX",-half))-margin,z+int(p.get("MinZ",-half))-margin,
            x+int(p.get("MaxX",half))+margin,z+int(p.get("MaxZ",half))+margin]


def city_plan(world):
    folder=world/"dimensions/projectseele/geofront/data"
    sources=list(folder.glob("projectseele_city_rigid_topology_r45_*.dat"))
    if len(sources)!=1:
        raise ValueError("One authoritative city topology is required")
    data=nbtlib.load(sources[0])["data"]
    origin=unpack(data["Origin"]);ox,oy,oz=origin
    towers=list(data["Towers"])
    arm_half_width=104;arm_reach=344
    cross=[[ox-arm_half_width,oz-arm_reach,ox+arm_half_width,oz+arm_reach],
           [ox-arm_reach,oz-arm_half_width,ox+arm_reach,oz+arm_half_width]]
    # The original three private-building centres remain outside the indexed
    # generated tower list. Read their actual archive anchors, not templates.
    private=[]
    reserved=[dict(name="existing EVA launch exits and transfer apron",box=[-80,-100,140,8])]
    for file in sorted(folder.glob("projectseele_city_private_cargo_r45_*.dat")):
        root=nbtlib.load(file);tag=root.get("data",root)
        for building in tag.get("Buildings",[]):
            centre=unpack(building["Centre"])
            spec=dict(Half=building["Half"],Footprint=building.get("R45Footprint",{}))
            box=footprint(spec,centre)
            private.append(dict(file=file.name,centre=centre,bounds_xz=box,status="retain complete original archive in place"))
            reserved.append(dict(name=file.name,box=box))
    def inside(box):
        return any(box[0]>=c[0] and box[1]>=c[1] and box[2]<=c[2] and box[3]<=c[3] for c in cross)
    rows=[];occupied=[];pending=[]
    for index,tower in enumerate(towers):
        centre=unpack(tower["Centre"]);box=footprint(tower,centre)
        row=dict(index=index,kind=str(tower["Kind"]),source_centre=centre,source_footprint=box,
                 retained_retracted_base_y=int(tower.get("RetractedBaseY",19-int(tower["Height"]))),
                 height=int(tower["Height"]))
        if inside(box):
            row.update(target_centre=centre,delta=[0,0,0],status="retain")
            occupied.append(box)
        else:
            pending.append((row,tower))
        rows.append(row)
    candidates=[(ox+x,oy,oz+z) for x in range(-320,321,40) for z in range(-320,321,40)
                if abs(x)<=80 or abs(z)<=80]
    # Native line identities stay in place. Move a new building slot instead
    # of cutting an elevated railway when the complete component is installed.
    transit=json.loads((world/'native_transit_r28.json').read_text(encoding='utf-8'))
    rails=np.asarray([p for curve in transit['curves'] if curve['mode']=='TRAIN'
                      for p in curve['points'] if ox-400<=p[0]<=ox+400 and oz-400<=p[2]<=oz+400],dtype=float)
    def occupies_rail(tower,centre):
        if not len(rails):return False
        box=footprint(tower,centre,margin=7)
        base=int(tower.get('RetractedBaseY',19-int(tower['Height'])))
        return bool(np.any((rails[:,0]>=box[0])&(rails[:,0]<=box[2])
            &(rails[:,2]>=box[1])&(rails[:,2]<=box[3])
            &(rails[:,1]+8>=base-1)&(rails[:,1]-3<=centre[1]+int(tower['Height'])+3)))
    # Largest existing footprints get first choice; retained towers are fixed.
    pending.sort(key=lambda item:-(item[0]["source_footprint"][2]-item[0]["source_footprint"][0])
                                  *(item[0]["source_footprint"][3]-item[0]["source_footprint"][1]))
    for row,tower in pending:
        old=row["source_centre"]
        choices=sorted(candidates,key=lambda c:(c[0]-old[0])**2+(c[2]-old[2])**2)
        for candidate in choices:
            candidate=[candidate[0],old[1],candidate[2]]
            box=footprint(tower,candidate)
            if not inside(box) or any(intersects(box,p) for p in occupied) or any(intersects(box,p["box"]) for p in reserved) or occupies_rail(tower,candidate):
                continue
            row.update(target_centre=candidate,delta=[candidate[i]-old[i] for i in range(3)],status="relocate complete existing tower")
            occupied.append(box)
            break
        else:
            raise ValueError(f"No complete cross slot for tower {row['index']}")
    # Geometric checks concern an offline plan only; never gate game ticks.
    if len(rows)!=len(towers) or len({tuple(r['target_centre']) for r in rows})!=len(rows):
        raise ValueError("Each original tower must retain exactly one target")
    return dict(status="placement proposal only; not installed",source_topology=str(sources[0]),origin=origin,
                shape="two intersecting arms; ordinary surrounding districts remain irregular",
                cross_rectangles_xz=cross,retained_towers=sum(r["status"]=="retain" for r in rows),
                moved_towers=sum(r["status"]!="retain" for r in rows),towers=rows,private_archives=private,
                reserved_interfaces=reserved,
                mandatory_migration=["complete current cargo with inventories and NBT","fixed supports, shaft liners and street covers",
                "controller positions and native references","topology and control SavedData preserving state and identity",
                "attached effects and local street connections","underground maintenance access"],
                reference_status="User-requested cross layout; reference setting-drawing repost inspected. Exact original publication and arm proportions remain to be resolved.")


def un_plan(world,gis):
    design=np.load(gis/"terrain-design.npz")
    # Includes the R23 north flight line, R31 western annex and R40 aprons.
    source=[6208,64,-7088,6896,176,-5944]
    delta=[-2608,-150,5812]
    target=[source[i]+delta[i%3] for i in range(6)]
    xs,zs=design["x"],design["z"]
    ix=np.where((xs>=target[0])&(xs<=target[3]))[0];iz=np.where((zs>=target[2])&(zs<=target[5]))[0]
    selection=np.ix_(iz,ix);height=design["height_y"][selection]
    sea=design["sea"][selection];water=design["inland_water"][selection]
    installation=json.loads((world/"r07_installations.json").read_text("utf8"))
    readiness=json.loads((world/"military_readiness_r23.json").read_text("utf8"))
    assigned=[entry["key"] for entry in installation["entities"]+readiness["vehicles"] if entry["position"][0]>6000]
    return dict(status="Odawara northern plain siting proposal; not installed",source_bounds=source,target_bounds=target,delta=delta,
                old_floor=74,target_floor=74+delta[1],
                terrain_y_percentiles=list(map(float,np.nanpercentile(height,[0,25,50,75,100]))),
                sea_fraction=float(sea.mean()),inland_water_fraction=float(water.mean()),
                registered_original_entities=assigned,
                siting_constraint="Preserve the mapped Sakawa river and public trunk routes; reshape the site boundary/grade rather than burying the river. This is a fictional UN installation within real regional geography.",
                mandatory_migration=["R07 and annex entities with original UUIDs and current state","all building/device NBT and inventories",
                "wet cells, gantries, reception decks and current repair phase","runtime legacy coordinates replaced with a world-owned site frame",
                "aircraft routes, boarding points, public road and rail connections","staff waypoints and station signage",
                "retire the old fixed base footprint and former route endpoints after the new site is operational"])


def plot_city(plan,out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle,Patch
    plt.rcParams["font.sans-serif"]=["Microsoft YaHei","SimHei","DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"]=False
    fig,axes=plt.subplots(1,2,figsize=(13,7),constrained_layout=True)
    ox,_,oz=plan["origin"]
    for target,ax in enumerate(axes):
        for x0,z0,x1,z1 in plan["cross_rectangles_xz"]:
            ax.add_patch(Rectangle((x0,z0),x1-x0,z1-z0,fc="#f1e8ce",ec="none",alpha=.5))
        for row in plan["towers"]:
            c=row["target_centre"] if target else row["source_centre"]
            box=row["source_footprint"];dx=c[0]-row["source_centre"][0];dz=c[2]-row["source_centre"][2]
            color="#d2853d" if row["status"]!="retain" else "#607d83"
            ax.add_patch(Rectangle((box[0]+dx,box[1]+dz),box[2]-box[0],box[3]-box[1],fc=color,ec="white",lw=.5))
        for p in plan["private_archives"]:
            x0,z0,x1,z1=p["bounds_xz"]
            ax.add_patch(Rectangle((x0,z0),x1-x0,z1-z0,fc="#6d5d96",ec="white",lw=.5))
        x0,z0,x1,z1=plan["reserved_interfaces"][0]["box"]
        ax.add_patch(Rectangle((x0,z0),x1-x0,z1-z0,fill=False,ec="#b33b50",lw=1.2,ls="--"))
        ax.text((x0+x1)/2,z0-12,"原 EVA 出口",ha="center",fontsize=9,color="#a52e43")
        ax.set_xlim(ox-390,ox+390);ax.set_ylim(oz+390,oz-390);ax.set_aspect("equal")
        ax.set_xlabel("X / 东");ax.set_ylabel("Z / 南")
        ax.set_title("当前方形楼阵" if not target else "十字形排布候选",fontsize=14)
    axes[1].legend(handles=[Patch(color="#607d83",label="70 座原位保留"),Patch(color="#d2853d",label="30 座整体迁移"),
                            Patch(color="#6d5d96",label="3 座私有楼体原位保留")],loc="lower right",fontsize=9)
    fig.suptitle("保留原楼体与升降身份，重组城区轮廓",fontsize=18)
    fig.text(.012,.006,"当前存档 SavedData → 布局候选；尚未迁移方块、控制器或实体。轴向与臂宽仍需结合原设定和街区深化。",fontsize=9)
    fig.savefig(out/"city-cross-plan.png",dpi=150);plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world",type=Path,required=True);parser.add_argument("--gis",type=Path,required=True)
    args=parser.parse_args()
    city=city_plan(args.world)
    for name,result in [("city-cross-relocation",city),("un-odawara-relocation",un_plan(args.world,args.gis))]:
        (args.gis/(name+".json")).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
        print(name,{k:v for k,v in result.items() if k in ("status","retained_towers","moved_towers","target_bounds","target_floor","terrain_y_percentiles","sea_fraction","inland_water_fraction")})
    plot_city(city,args.gis)


if __name__=="__main__":main()
