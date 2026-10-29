"""Capture the actual UN campus for component relocation, without writing the save.

Compact section arrays include original air, complete block states and bounds.
Entity and block-entity archives retain full NBT, including inventories and UUIDs.
The output is an input to the terrain/component installer, not an installed map.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

import nbtlib
import numpy as np
from install_r53_carrier_trays import stopped_world
from query_blocks import chunk_statuses, dimension_dir, iter_block_entities, iter_selected_sections, AIR
from transplant_s22_authority import read_region, parse_chunk

DIMENSION = "projectseele:geofront"
METADATA = (
    "r07_installations.json", "r07_commissioned.json", "military_readiness_r23.json",
    "un01_annex_r20.json", "un_hangars_r31.json", "un_air_reception_r40.json",
    "un_commission_r21.json", "un_models_r21.json", "un_models_r30.json",
    "nerv_staff_r15.json", "regional_plan.json", "ROOT_RUNTIME_DIRECTORY.json",
)


def contains(bounds, point):
    return len(point) == 3 and all(bounds[i] <= point[i] < bounds[i+3]+1 for i in range(3))


def identities(entity):
    if "UUID" in entity:
        yield tuple(map(int, entity["UUID"]))
    for passenger in entity.get("Passengers", []):
        yield from identities(passenger)


def capture_blocks(world, bounds, out):
    x0,y0,z0,x1,y1,z1=bounds
    selected={(x,z):set(range(y0//16,y1//16+1))
              for x in range(x0//16,x1//16+1) for z in range(z0//16,z1//16+1)}
    statuses=chunk_statuses(world,DIMENSION,selected)
    regions=defaultdict(dict)
    for p,sections in selected.items():
        if statuses[p] == "full":regions[p[0]//32,p[1]//32][p]=sections
    files=[];counts=Counter();states_count=Counter()
    # Plan view records actual authored columns; terrain is still archived.
    authored=np.zeros((z1-z0+1,x1-x0+1),dtype=np.uint8)
    terrain={"minecraft:air","minecraft:cave_air","minecraft:void_air","minecraft:stone",
             "minecraft:dirt","minecraft:grass_block","minecraft:water","minecraft:sand",
             "minecraft:gravel","minecraft:bedrock","minecraft:deepslate"}
    for (rx,rz),chunks in sorted(regions.items()):
        states=[];lookup={};coords=[];blocks=[]
        for cx,cz,sy,palette,indices in iter_selected_sections(world,DIMENSION,chunks):
            code=[]
            for state in palette:
                if state not in lookup:lookup[state]=len(states);states.append(state)
                code.append(lookup[state])
            coords.append((cx,sy,cz))
            blocks.append(np.asarray(code,dtype=np.uint32)[indices].astype(np.uint16))
            if len(states)>65535:raise ValueError("Region palette overflow")
            local=indices.reshape(16,16,16)
            xs=slice(max(x0,cx*16)-cx*16,min(x1+1,cx*16+16)-cx*16)
            zs=slice(max(z0,cz*16)-cz*16,min(z1+1,cz*16+16)-cz*16)
            ys=slice(max(y0,sy*16)-sy*16,min(y1+1,sy*16+16)-sy*16)
            cropped=local[ys,zs,xs]
            n=np.bincount(cropped.ravel(),minlength=len(palette))
            states_count.update({state:int(n[i]) for i,state in enumerate(palette) if n[i]})
            artificial=np.asarray([s.split("[")[0] not in terrain for s in palette])[cropped]
            target=(slice(max(z0,cz*16)-z0,min(z1+1,cz*16+16)-z0),
                    slice(max(x0,cx*16)-x0,min(x1+1,cx*16+16)-x0))
            authored[target]|=artificial.any(axis=0)
        name=f"blocks/r.{rx}.{rz}.npz"
        np.savez_compressed(out/name,coordinates=np.asarray(coords,dtype=np.int32),
                            palette=np.asarray(states),blocks=np.asarray(blocks,dtype=np.uint16))
        files.append(dict(path=name,sections=len(coords),palette=len(states)))
        counts["sections"]+=len(coords)
        print(f"Captured UN blocks {len(files)}/{len(regions)} regions",flush=True)
    tags=[tag for _,tag in iter_block_entities(world,DIMENSION,tuple(bounds[:3]),tuple(bounds[3:]),selected_chunks=selected)]
    nbtlib.File({"BlockEntities":nbtlib.List[nbtlib.Compound](tags)}).save(out/"block-entities.nbt",gzipped=True)
    np.savez_compressed(out/"authored-columns.npz",bounds=np.asarray(bounds),authored=authored)
    counts.update(block_entities=len(tags),non_air_cells=sum(n for s,n in states_count.items() if s not in AIR))
    return dict(files=files,counts=dict(counts),chunk_statuses=dict(Counter(statuses.values())),
                unavailable_chunks=[[*p,status] for p,status in statuses.items() if status!="full"],
                block_entity_types=dict(Counter(str(t.get("id"))for t in tags)),
                block_states=dict(states_count))


def capture_entities(world,bounds,out):
    folder=dimension_dir(world,DIMENSION)/"entities"
    records=[];ids=set();counts=Counter()
    for rx in range(bounds[0]//512,bounds[3]//512+1):
        for rz in range(bounds[2]//512,bounds[5]//512+1):
            path=folder/f"r.{rx}.{rz}.mca"
            if not path.exists() or path.stat().st_size==0:continue
            _,blobs=read_region(path)
            for slot,blob in enumerate(blobs):
                if blob is None:continue
                for entity in parse_chunk(blob).get("Entities",[]):
                    if not contains(bounds,list(map(float,entity.get("Pos",[])))):continue
                    current=list(identities(entity))
                    if len(current)!=len(set(current)) or ids.intersection(current):
                        raise ValueError("An original actor occurs twice in the selected campus")
                    ids.update(current);counts[str(entity.get("id"))]+=1
                    records.append(nbtlib.Compound(Region=nbtlib.IntArray([rx,rz]),Slot=nbtlib.Int(slot),Entity=entity))
    nbtlib.File({"Records":nbtlib.List[nbtlib.Compound](records)}).save(out/"entities.nbt",gzipped=True)
    return dict(roots=len(records),identities=len(ids),types=dict(counts))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("world","plan","out"):parser.add_argument("--"+name,type=Path,required=True)
    args=parser.parse_args();world=args.world.resolve();out=args.out.resolve()
    plan=json.loads(args.plan.read_text("utf8"));bounds=plan["source_bounds"]
    if out.exists():raise ValueError("Use a new capture directory; do not overwrite a frozen baseline")
    if out==world or world in out.parents:raise ValueError("Capture must stay outside the actual save")
    with stopped_world(world):
        (out/"blocks").mkdir(parents=True);(out/"baseline").mkdir()
        blocks=capture_blocks(world,bounds,out);actors=capture_entities(world,bounds,out)
        metadata=[]
        data=dimension_dir(world,DIMENSION)/"data"
        sources=[world/name for name in METADATA]
        sources.extend(data/name for name in (
            "projectseele_military_r07.dat","projectseele_un01_annex_r20.dat",
            "projectseele_un_airlift_r29.dat","projectseele_un_locations_r22.dat",
            "projectseele_facility_sites.dat"))
        for source in sources:
            if not source.is_file():continue
            relative=source.relative_to(world);target=out/"baseline"/relative
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
            metadata.append(relative.as_posix())
        report=dict(schema="projectseele.hakone.component-source.v1",world=str(world),dimension=DIMENSION,
                    captured_utc=datetime.now(timezone.utc).isoformat(),world_written=False,
                    source_bounds=bounds,proposed_delta=plan["delta"],blocks=blocks,actors=actors,
                    metadata=metadata,
                    remaining=["component placement around mapped water and trunk roads",
                               "explicit NBT coordinate transforms and traffic references",
                               "destination measured delta and inverse; installation not performed"])
        (out/"manifest.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
        print(json.dumps(dict(block_counts=blocks["counts"],chunk_statuses=blocks["chunk_statuses"],actors=actors),ensure_ascii=False),flush=True)


if __name__=="__main__":main()
