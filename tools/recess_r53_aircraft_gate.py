"""Plan the authorized retirement of the visible aircraft well.

The lower door keeps its resource identity but becomes a recessed ceiling hatch.
Only recorded shaft construction may be restored to the pre-construction terrain;
the new cassette has an explicit envelope inside the surveyed armored ceiling.
"""
from pathlib import Path
import argparse, collections, copy, gzip, hashlib, json, subprocess
import numpy as np


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode(value):
    return (json.dumps(value,ensure_ascii=False,separators=(",",":"))+"\n").encode()


def plan_metadata(world, work, output, java, classpath):
    destination=output/"candidate"
    assert not destination.exists(), "Preserve the existing metadata proposal"
    destination.mkdir()
    filenames=["ROOT_RUNTIME_DIRECTORY.json","ROOT_MECHANICAL_OWNER.json",
               "ROOT_AIR_TRANSPORT.json","ROOT_ASSEMBLY_BUNDLE.json",
               "personnel_lifts_r52.json","r52/headquarters_command_doors.json",
               "r52/headquarters.json","r52/travel.json"]
    docs={n:json.loads((world/n).read_bytes()) for n in filenames}
    original=copy.deepcopy(docs)
    oldfp=docs["ROOT_ASSEMBLY_BUNDLE.json"]["directory_fingerprint"]
    def fingerprint(path):
        return subprocess.check_output([str(java),"-cp",classpath,"JsonDocumentFingerprintR53",str(path)],text=True).strip()
    def save(name):
        p=destination/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(encode(docs[name]))
    assert fingerprint(world/"ROOT_RUNTIME_DIRECTORY.json")==oldfp
    bindings=docs["ROOT_RUNTIME_DIRECTORY.json"]["runtime"]["bindings"]
    match=[b for b in bindings if b["resource"]=="remote_airshaft_south"]
    assert len(match)==1 and match[0]["expected_type"]=="projectseele:nerv_hangar_door"
    match[0]["expected_type"]="projectseele:nerv_silo_door"
    save("ROOT_RUNTIME_DIRECTORY.json")
    newfp=fingerprint(destination/"ROOT_RUNTIME_DIRECTORY.json")
    def replace(value):
        if isinstance(value,dict):return {k:replace(v) for k,v in value.items()}
        if isinstance(value,list):return [replace(v) for v in value]
        return newfp if value==oldfp else value
    docs={n:replace(v) for n,v in docs.items()}
    gates=docs["ROOT_MECHANICAL_OWNER.json"]["gates"]
    index=next(i for i,g in enumerate(gates) if g["resource"]=="remote_airshaft_south")
    oldgate=copy.deepcopy(gates[index])
    newgate=json.loads((work/"gate-recessed/ROOT_TYPED_GATES_CANDIDATE.json").read_bytes())["gates"][0]
    assert oldgate["visual"]==newgate["visual"]==match[0]["entity_uuid"]
    source=work/"gate-recessed"/newgate["collision_steps"]["cells_file"]
    target=destination/oldgate["collision_steps"]["cells_file"]
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read_bytes())
    newgate["collision_steps"]["cells_file"]=oldgate["collision_steps"]["cells_file"]
    gates[index]=newgate
    docs["ROOT_MECHANICAL_OWNER.json"]["commissioning_receipt_sha256"]=digest(output/"geometry-check/GATE14_CURRENT_WORLD_HITS.json")
    changed=[]
    for corridor in docs["ROOT_AIR_TRANSPORT.json"]["corridors"]:
        ends={corridor["from"],corridor["to"]}
        if ends=={"shaft_south_approach","shaft_bottom"}:
            assert corridor["gates"]==["remote_airshaft_south"]
            corridor["gates"]=[];changed.append(corridor["id"])
        elif ends=={"shaft_bottom","shaft_top"}:
            assert corridor["gates"]==["remote_airshaft_surface"]
            corridor["gates"]=["remote_airshaft_south","remote_airshaft_surface"];changed.append(corridor["id"])
    assert len(changed)==4
    # Every original frame, duration, cargo rig and mission itinerary is retained.
    checked=copy.deepcopy(docs["ROOT_AIR_TRANSPORT.json"])
    checked["directory_fingerprint"]=oldfp
    for a,b in zip(checked["corridors"],original["ROOT_AIR_TRANSPORT.json"]["corridors"]):
        a["gates"]=b["gates"]
    assert checked==original["ROOT_AIR_TRANSPORT.json"]
    for name in filenames:
        if name not in ("ROOT_ASSEMBLY_BUNDLE.json","r52/headquarters.json"):save(name)
    docs["r52/headquarters.json"]["command_door_sha256"]=digest(destination/"r52/headquarters_command_doors.json")
    save("r52/headquarters.json")
    bundle=docs["ROOT_ASSEMBLY_BUNDLE.json"]
    for key in ("directory","mechanical_owner","air_transport","personnel_lifts"):
        bundle[key]["sha256"]=digest(destination/bundle[key]["file"])
    save("ROOT_ASSEMBLY_BUNDLE.json")
    pairs={oldfp:newfp}
    for name in filenames:
        pairs[digest(world/name)]=digest(destination/name)
        pairs[fingerprint(world/name)]=fingerprint(destination/name)
    pairs={k:v for k,v in pairs.items() if k!=v}
    frozen={n:digest(world/n) for n in filenames+[oldgate["collision_steps"]["cells_file"]]}
    result=dict(old_directory=oldfp,new_directory=newfp,reference_pairs=pairs,
                frozen_sources=frozen,old_gate=oldgate,new_gate=newgate,
                changed_corridor_gate_lists=changed,route_frames_durations_rigs_missions_unchanged=True,
                original_three_eva_routes_unchanged=True)
    (output/"METADATA_PLAN.json").write_bytes(encode(result))
    print("Metadata ready",newfp,"reference pairs",len(pairs),flush=True)


def install(world, work, output):
    import io, msvcrt, shutil, uuid
    import nbtlib
    import regional_voxels as vox
    from prepare_terminal_move_r52 import runs
    from expand_r53_natural_lake import verify_envelope
    from query_blocks import iter_block_entities
    from apply_s20_approved_semantic_repairs import parse_state, atomic_replace, decompress_chunk
    from transplant_s22_authority import read_region, parse_chunk, build_region, chunk_blob

    assert not (output/"INSTALLED.json").exists()
    assert not (output/"install-before").exists(), "Inspect any interrupted installation first"
    meta=json.loads((output/"METADATA_PLAN.json").read_bytes())
    hit=json.loads((output/"geometry-check/GATE14_CURRENT_WORLD_HITS.json").read_bytes())
    assert len(hit["gates"])==1 and not hit["gates"][0]["part_cell_hits"]
    source=np.load(output/"EXACT_BEFORE_AFTER.npz")
    before,after=source["before"],source["after"];names=source["palette"].tolist();origin=source["origin"].tolist()
    if "UNMEASURED" not in names:names.append("UNMEASURED")
    end=(origin[0]+before.shape[2]-1,origin[1]+before.shape[0]-1,origin[2]+before.shape[1]-1)
    dimension="projectseele:geofront";data=world/"dimensions/projectseele/geofront/data"
    native=nbtlib.parse_nbt((work/"NEW_GATE_NATIVE_READY.snbt").read_text("utf8"))
    def identity(tag):
        return str(uuid.UUID(int=sum((int(v)&0xffffffff)<<(96-32*i) for i,v in enumerate(tag))))
    gateid=meta["new_gate"]["visual"]
    assert identity(native["UUID"])==gateid and str(native["id"])=="projectseele:nerv_silo_door"
    assert list(map(float,native["Pos"]))==meta["new_gate"]["frame"]["position"]
    assert float(native["R52DeclaredHatch"]["Raw"])==0
    assert np.isfinite(float(native["R52DeclaredHatch"]["ClockGoal"]))
    rows={};changes=[];pairs=meta["reference_pairs"]
    def rewrite(tag, path, addresses):
        if not isinstance(tag,(nbtlib.Compound,nbtlib.List)):return
        for key in list(tag) if isinstance(tag,nbtlib.Compound) else range(len(tag)):
            if isinstance(tag[key],nbtlib.String) and str(tag[key]) in pairs:
                old=str(tag[key]);tag[key]=nbtlib.String(pairs[old]);addresses.append((path+(key,),old))
            else:rewrite(tag[key],path+(key,),addresses)
    def references(tag,label):
        old=copy.deepcopy(tag);addresses=[];rewrite(tag,(),addresses)
        if not addresses:return False
        inverse=copy.deepcopy(tag)
        for address,value in addresses:
            parent=inverse
            for k in address[:-1]:parent=parent[k]
            parent[address[-1]]=nbtlib.String(value)
        assert inverse.snbt()==old.snbt(), "Only exact source references may migrate"
        changes.append(dict(file=label,fields=[list(a) for a,v in addresses]))
        return True
    def binary(tag):
        stream=io.BytesIO();tag.write(stream);return gzip.compress(stream.getvalue(),mtime=0)
    with (world/"session.lock").open("r+b") as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        for rel,h in meta["frozen_sources"].items():assert digest(world/rel)==h,rel
        runtime=data/"projectseele_nerv_routes_r52.dat"
        ground=nbtlib.load(runtime)["data"]
        assert str(ground["DirectoryFingerprint"])==meta["old_directory"] and not str(ground["Fault"])
        assert all(str(j["Phase"])=="PARKED" for j in ground["Jobs"])
        air=nbtlib.load(data/"projectseele_nerv_air_transport_r52.dat")["data"]
        assert all(str(j["Phase"]) in {"COMPLETE","CANCELLED"} for j in air["Jobs"])
        verify_envelope(world,origin,before,names)
        assert not list(iter_block_entities(world,dimension,tuple(origin),end)), "Preserve every device NBT"
        # Full progress is retained; only source fingerprints and this authorized
        # machine's observed chunk change. No mission is reset or advanced.
        for path in world.rglob("*.dat"):
            raw=path.read_bytes();unpacked=gzip.decompress(raw) if raw[:2]==b"\x1f\x8b" else raw
            if path!=runtime and not any(k.encode() in unpacked for k in pairs):continue
            tag=nbtlib.load(path);changed=references(tag,path.relative_to(world).as_posix())
            if path==runtime:
                entries=[e for e in tag["data"]["InstallationActorChunks"] if identity(e["Actor"])==gateid]
                assert len(entries)==1
                x,z=int(native["Pos"][0])//16,int(native["Pos"][2])//16
                packed=((z&0xffffffff)<<32)|(x&0xffffffff)
                if packed>=1<<63:packed-=1<<64
                entries[0]["Chunk"]=nbtlib.Long(packed);changed=True
            if changed:rows[path]=(raw,binary(tag))
        retired=[];target_chunk=(int(native["Pos"][0])//16,int(native["Pos"][2])//16)
        target_region=world/"dimensions/projectseele/geofront/entities"/f"r.{target_chunk[0]//32}.{target_chunk[1]//32}.mca"
        target_slot=(target_chunk[0]&31)+32*(target_chunk[1]&31);inserted=False
        for folder in [world/"entities",*(world/"dimensions").glob("*/*/entities")]:
            if not folder.exists():continue
            for path in folder.glob("r.*.*.mca"):
                raw=path.read_bytes()
                if not raw:continue
                stamps,blobs=read_region(path);dirty=False
                for index,blob in enumerate(blobs):
                    if blob is None:continue
                    size=int.from_bytes(blob[:4],"big");unpacked=decompress_chunk(blob[4],blob[5:4+size])
                    target=path==target_region and index==target_slot
                    has_gate=bytes.fromhex(gateid.replace("-","")) in unpacked
                    if not target and not has_gate and not any(k.encode() in unpacked for k in pairs):continue
                    tag=parse_chunk(blob);changed=references(tag,path.relative_to(world).as_posix()+"/"+str(index))
                    entities=tag["Entities"]
                    for i in range(len(entities)-1,-1,-1):
                        entity=entities[i]
                        if identity(entity["UUID"])!=gateid:continue
                        assert str(entity["id"])=="projectseele:nerv_hangar_door"
                        assert list(map(float,entity["Pos"]))==meta["old_gate"]["frame"]["position"]
                        assert not entity.get("Passengers"), "Occupied equipment cannot retire"
                        retired.append(copy.deepcopy(entity));del entities[i];changed=True
                    if target:
                        entities.append(copy.deepcopy(native));inserted=True;changed=True
                    if changed:blobs[index]=chunk_blob(tag);dirty=True
                if dirty:rows[path]=(raw,build_region(stamps,blobs))
        assert len(retired)==1 and inserted, "Exactly one authorized gate controller must change"
        (output/"OLD_GATE_FULL.snbt").write_text(retired[0].snbt(),"utf8")
        # Derived maintenance cells must not restore the retired well on load.
        headers=list(data.glob("projectseele_city_rigid_topology_r45_*.dat"));assert len(headers)==1
        folder=data/str(nbtlib.load(headers[0])["data"]["GenerationFolder"])/"chunks"
        vox.WORLD=world;vox.OUT=output;vox.DIM=dimension
        painter=vox.Painter(vertical_bounds=(-1440,320))
        count=runs(painter,origin,before,after,names,"R53_retire_visible_aircraft_well")
        cache_cells=0
        for cx,cz in painter.by_chunk:
            path=folder/f"{cx}_{cz}.dat"
            if not path.exists():continue
            tag=nbtlib.load(path);palette=tag["Palette"];lookup={v.snbt():i for i,v in enumerate(palette)};dirty=False
            for entry in tag["Static"]:
                value=int(entry["Pos"]);x=value>>38;y=value&4095;z=(value>>12)&67108863
                if y>=2048:y-=4096
                if z>=33554432:z-=67108864
                q=(y-origin[1],z-origin[2],x-origin[0])
                if not all(0<=q[i]<before.shape[i] for i in range(3)) or before[q]==after[q]:continue
                assert palette[int(entry["StateId"])]==parse_state(names[int(before[q])]),(x,y,z,"Static source differs")
                s=parse_state(names[int(after[q])]);key=s.snbt()
                if key not in lookup:lookup[key]=len(palette);palette.append(s)
                entry["StateId"]=nbtlib.Int(lookup[key]);cache_cells+=1;dirty=True
            if dirty:rows[path]=(path.read_bytes(),binary(tag))
        for path in (output/"candidate").rglob("*"):
            if path.is_file():
                target=world/path.relative_to(output/"candidate")
                rows[target]=(target.read_bytes(),path.read_bytes())
        # Freeze complete region and metadata preimages before the first write.
        backup=output/"install-before";backup.mkdir()
        regions={world/"dimensions/projectseele/geofront/region"/f"r.{cx//32}.{cz//32}.mca" for cx,cz in painter.by_chunk}
        for path in set(rows)|regions:
            target=backup/path.relative_to(world);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
        progress={p:digest(p) for p in [world/"level.dat",*list((world/"playerdata").glob("*.dat")),world/"nerv_routes_r24.json.gz",world/"nearest_lift_paths_r44.json.gz",world/"r53_personnel_walking_graph.json.gz"]}
        print("Installing",count,"cells",len(rows),"metadata/cache files",cache_cells,"maintained cells",flush=True)
        try:
            receipt=painter.apply("recessed_aircraft_gate",session_lock=lock)
            for path,(old,new) in rows.items():
                assert path.read_bytes()==old,path
                atomic_replace(path,new);assert path.read_bytes()==new
            verify_envelope(world,origin,after,names)
            expected_progress={p:hashlib.sha256(rows[p][1]).hexdigest() if p in rows else h for p,h in progress.items()}
            assert expected_progress=={p:digest(p) for p in progress}
            assert not list(iter_block_entities(world,dimension,tuple(origin),end))
        except BaseException:
            for path in set(rows)|regions:atomic_replace(path,(backup/path.relative_to(world)).read_bytes())
            (output/"ROLLED_BACK.json").write_bytes(encode(dict(reason="Installation failed; full file preimages restored")))
            raise
        result=dict(changed_cells=count,maintained_static_cells=cache_cells,retired_gate=gateid,
                    exact_full_envelope_readback=True,device_nbt_unchanged=True,
                    preserved_player_navigation={str(p.relative_to(world)):h for p,h in progress.items()},
                    source_reference_changes=changes,native_visual="pending",lod_refresh="pending",
                    files=[dict(path=p.relative_to(world).as_posix(),before=hashlib.sha256(a).hexdigest(),after=hashlib.sha256(b).hexdigest()) for p,(a,b) in rows.items()],receipt=receipt)
        (output/"INSTALLED.json").write_bytes(encode(result))
        print("Installed; exact readback passed",count,flush=True)


def plan(work, original, output):
    assert not (output/"EXACT_BEFORE_AFTER.npz").exists(), "Preserve the existing frozen proposal"
    output.mkdir(parents=True,exist_ok=True)
    data = np.load(work / "old.npz")
    before = data["states"]; names = data["palette"].tolist()
    origin = data["origin"].astype(int); after = before.copy()
    source = np.load(original / "SOURCE_EXTENDED.npz")
    terrain = source["states"]; terrain_names = source["palette"].tolist()
    so = source["origin"].astype(int)

    def state(name):
        if name not in names: names.append(name)
        return names.index(name)

    def bounds(box):
        x, y, z, X, Y, Z = box
        assert origin[0] <= x <= X < origin[0] + before.shape[2]
        assert origin[1] <= y <= Y < origin[1] + before.shape[0]
        assert origin[2] <= z <= Z < origin[2] + before.shape[1]
        return (slice(y-origin[1], Y-origin[1]+1),
                slice(z-origin[2], Z-origin[2]+1), slice(x-origin[0], X-origin[0]+1))

    owned = np.zeros(before.shape, dtype=bool)
    expected = np.full(before.shape, 65535, dtype=np.uint16)
    operations = [original / p / "ops.json.gz" for p in (
        "remote_164m_aircraft_shaft", "actual_machine_bearings_and_cassettes",
        "south_leaf_collision_alignment/align_measured_south_leaf")]
    for path in operations:
        for row in json.loads(gzip.decompress(path.read_bytes())):
            box = list(row["box"])
            if box[1] >= -90: continue
            box[4] = min(-91, box[4])
            s = bounds(box); owned[s] = True; expected[s] = state(row["state"])
    mismatch = owned & (expected != before)
    variants = collections.Counter((names[int(a)], names[int(b)])
                                   for a, b in zip(expected[mismatch], before[mismatch]))
    assert set(variants) <= {
        ("projectseele:nerv_shaft_panel", "projectseele:nerv_structural_panel"),
        ("projectseele:nerv_shaft_panel", "minecraft:black_concrete")}, variants

    # Stop the old walls at the measured original ceiling in every column.
    # Keeping the excavated opening above that surface preserves the air route.
    roof = np.full(before.shape[1:], -32768, dtype=np.int16)
    restored = 0
    stone = terrain_names.index("minecraft:stone")
    for iz, ix in np.argwhere(owned.any(axis=0)):
        x, z = int(ix+origin[0]), int(iz+origin[2])
        tx, tz = x-so[0], z-so[2]
        assert 0 <= tx < terrain.shape[2] and 0 <= tz < terrain.shape[1]
        col = terrain[:, tz, tx]
        ceiling = np.flatnonzero((col == stone) & (np.arange(len(col))+so[1] > -350))
        assert len(ceiling), (x, z, "No original ceiling")
        yroof = int(ceiling[0]+so[1]); roof[iz, ix] = yroof
        ys = np.flatnonzero(owned[:, iz, ix] & (np.arange(before.shape[0])+origin[1] < yroof))
        target = [state(terrain_names[int(v)]) for v in col[ys+origin[1]-so[1]]]
        restored += int(np.count_nonzero(after[ys, iz, ix] != target))
        after[ys, iz, ix] = target
        # The exposed mouth is armor, including the cut end of former black ribs.
        for y in range(yroof, yroof+3):
            q = (y-origin[1], iz, ix)
            if owned[q] and names[int(after[q])].startswith("projectseele:nerv_"):
                after[q] = state("projectseele:nerv_structural_panel")

    cassette = [-1227, -94, -807, -1013, -81, -633]
    permitted = {"minecraft:air", "minecraft:stone", "minecraft:barrier",
                 "minecraft:black_concrete", "projectseele:nerv_structural_panel",
                 "projectseele:nerv_shaft_panel", "projectseele:nerv_wall_panel",
                 "projectseele:nerv_machine_edge", "projectseele:nerv_strip_light[lit=true]"}
    assert {names[int(i)] for i in np.unique(before[bounds(cassette)])} <= permitted
    # The cassette is wholly above the original cave ceiling. Two-block armor
    # encloses the machinery; the existing 164 m vertical route remains open.
    for z in range(cassette[2], cassette[5]+1):
        for x in range(cassette[0], cassette[3]+1):
            col = terrain[:, z-so[2], x-so[0]]
            ys = np.flatnonzero((col == stone) & (np.arange(len(col))+so[1] > -350))
            assert int(ys[0]+so[1]) <= cassette[1]-6, (x, z)
    armor = state("projectseele:nerv_structural_panel"); air = state("minecraft:air")
    after[bounds(cassette)] = armor
    after[bounds([-1225, -92, -805, -1015, -83, -635])] = air
    after[bounds([-1202, -94, -802, -1039, -81, -639])] = air

    gate = json.loads((work/"gate-recessed/ROOT_TYPED_GATES_CANDIDATE.json").read_bytes())["gates"][0]
    assert gate["resource"] == "remote_airshaft_south" and gate["kind"] == "SILO"
    assert gate["frame"]["position"] == [-1120, -89.99, -720]
    for support in gate["supports"]:
        x,y,z = support["position"]
        after[y-origin[1],z-origin[2],x-origin[0]] = state(support["state"])
    collision = work/"gate-recessed"/gate["collision_steps"]["cells_file"]
    assert digest(collision) == gate["collision_steps"]["sha256"]
    steps = json.loads(gzip.decompress(collision.read_bytes()))
    for cell in steps[0]:
        x,y,z = cell["position"]
        q = (y-origin[1],z-origin[2],x-origin[0])
        assert after[q] == air, (cell, names[int(after[q])])
        after[q] = state(cell["closed"])
    changed = before != after
    assert not np.any(changed[-1]) and not np.any(changed[:,:,0]) and not np.any(changed[:,:,-1])
    np.savez_compressed(output/"EXACT_BEFORE_AFTER.npz", before=before, after=after,
                        palette=names, origin=origin, original_ceiling=roof)
    report = dict(changed_cells=int(changed.sum()), retired_exposed_cells=restored,
                  source_hashes={str(p):digest(p) for p in operations+[original/"SOURCE_EXTENDED.npz",work/"old.npz"]},
                  recorded_material_upgrades={str(k):v for k,v in variants.items()},
                  cassette=cassette, frame=gate["frame"], gate_resource=gate["resource"],
                  original_routes_unchanged=True, surface_exit_unchanged=True,
                  full_gate_geometry="pending", native_visual="pending", installed=False)
    (output/"PLAN.json").write_text(json.dumps(report,indent=2),"utf8")
    print(json.dumps(report),flush=True)


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--work",type=Path,required=True)
    p.add_argument("--original",type=Path)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--world",type=Path)
    p.add_argument("--java",type=Path)
    p.add_argument("--classpath")
    p.add_argument("--metadata",action="store_true")
    p.add_argument("--apply",action="store_true")
    a=p.parse_args()
    if a.apply:install(a.world,a.work,a.output)
    elif a.metadata:plan_metadata(a.world,a.work,a.output,a.java,a.classpath)
    else:plan(a.work,a.original,a.output)
