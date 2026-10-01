"""All 20 station areas: real gate palettes, 276 boards and every APG pair.

Reader reach/visibility and per-door route-map coverage are distinct from a
native boarding result. No world or block-entity mutations are performed.
"""
from pathlib import Path
from collections import Counter
import copy,json,math
from audit_facility_transit_r44 import Geometry,NORMAL
from measure_world_r40 import MeasuredWorld,properties
from query_blocks import iter_block_entities,iter_selected_sections,AIR
from station_sign_readers_r44 import reader_visibility

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/"run/saves/SEELE_FIELD_R44_REVIEW";OUT=ROOT/"artifacts/rebuild_r44/facility_transit_r44/station_signs"


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    catalogue=json.loads((ROOT/"artifacts/repair_r43/facility_catalogue/catalogue.json").read_text(encoding="utf8"))
    platforms=json.loads((ROOT/"artifacts/rebuild_r44/facility_transit_r44/platform_interfaces/interfaces.json").read_text(encoding="utf8"))["platforms"]
    tags={};w=MeasuredWorld(WORLD);gate_states=Counter()
    for s in catalogue["stations"]:
        lo,hi=map(tuple,s["bounds"]);w.box(lo,hi)
        for q,t in iter_block_entities(WORLD,"projectseele:geofront",lo,hi):
            if str(t.get("id",""))=="projectseele:station_departure_board":tags[q]=copy.deepcopy(t)
    w.load();g=Geometry(w)
    # Scan actual palettes, including MTR's ticket_barrier names. A catalogue
    # keyword count alone cannot decide that no physical gates are installed.
    for cx,cz,sy,palette,indices in iter_selected_sections(WORLD,"projectseele:geofront",w.selected,skip_unfinished=True):
        for k,state in enumerate(palette):
            if any(name in state for name in ("ticket_barrier","ticket_gate","fare_gate","turnstile","nerv_access_reader","city_personnel_door")):
                gate_states[state]+=int((indices==k).sum())
    boards=[]
    for q,t in sorted(tags.items()):
        state=w.block(q);face=properties(state or "").get("facing");reader=None
        if face in NORMAL:
            dx,dz=NORMAL[face]
            for fy in range(q[1]+1,q[1]-8,-1):
                for distance in (3,2,4,5):
                    a=(q[0]+distance*dx,fy,q[2]+distance*dz)
                    if g.standing(a)["status"]!="STATIC_STANDING":continue
                    proof=reader_visibility(w.block,g.boxes,q,face,a,direction=bool(t.get('Wayfinding',False)),compact=state.startswith('projectseele:nerv_direction_panel'),route_map='MapRows' in t)
                    if proof['clear']:reader=a;break
                if reader:break
        boards.append({"position":q,"state":state,"facing":face,"reader":reader,"native_platform_id":int(t.get("NativePlatformId",-1)),
            "kind":"route_map" if "MapRows" in t else "wayfinding" if bool(t.get("Wayfinding",False)) else "live_departure",
            "nbt":t.snbt(),"status":"STATIC_FRONT_READER" if reader else "UNRESOLVED_READER"})
    maps={}
    for b in boards:
        if b["kind"]=="route_map" and b["reader"]:maps.setdefault(b["native_platform_id"],[]).append(b)
    coverage=[]
    for p in platforms:
        pid=int(p["id"]);pairs=[]
        # Left/right lower door halves belong to one physical boarding mouth.
        seen=set()
        for gate in p["gates"]:
            q=tuple(gate["pos"]);state=w.get(q[0],q[1]+1,q[2]);prop=properties(state or "")
            if prop.get("side")!="left":continue
            reader=tuple(gate["approach"])
            candidates=[]
            for board in maps.get(pid,[]):
                a=tuple(board["reader"])
                if abs(a[1]-reader[1])>.15 or math.dist(a,reader)>12:continue
                route=g.flat_path(reader,a,radius=20)
                if route:candidates.append((len(route)-1,board))
            best=min(candidates,key=lambda a:a[0]) if candidates else None
            pairs.append({"door_lower":q,"actual_door_state":state,"approach":reader,
                "map":best[1]["position"] if best else None,"map_walk_distance":best[0] if best else None,
                "near_and_reachable":best is not None and best[0]<=8})
        coverage.append({"platform":p["id"],"station":p["station"],"door_pairs":pairs,
            "covered_pairs":sum(x["near_and_reachable"] for x in pairs),"total_pairs":len(pairs),
            "stage":"Saved exact physical/reader geometry; live door/ride and text legibility are separately unverified"})
    report={"world":str(WORLD),"station_areas":20,"actual_gate_palette_counts":dict(gate_states),"boards":boards,
        "counts":dict(Counter(b["kind"] for b in boards)),"unresolved_board_readers":sum(b["reader"] is None for b in boards),
        "door_coverage":coverage,"unknown_shapes":sorted(g.unknown),"reader_method":"Standing eye plus nine rays over real lettering span; same-floor wall boards included. Conservatively treats measured collision solids as optical obstructions.","status":"INCOMPLETE per-object signs/gate function/legibility audit, not whole-station acceptance"}
    (OUT/"full_sign_audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
    print("Gate palettes",report["actual_gate_palette_counts"],"boards",report["counts"],"unresolved",report["unresolved_board_readers"],
        "APG pairs",sum(p["total_pairs"] for p in coverage),"covered",sum(p["covered_pairs"] for p in coverage),flush=True)
    return report


if __name__=="__main__":main()
