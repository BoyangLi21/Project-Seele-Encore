"""Root-only finite Dock sockets from an explicitly selected, clear mechanical source."""
import argparse,collections,gzip,hashlib,json
from pathlib import Path
from query_blocks import iter_selected_sections,iter_block_entities
from r52_spatial_plan import BASE
import regional_voxels as vox


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text('utf8'))
def states_at(world,points):
    selected=collections.defaultdict(set);wanted=collections.defaultdict(list);result={}
    for x,y,z in points:selected[x//16,z//16].add(y//16);wanted[x//16,y//16,z//16].append((x,y,z))
    for cx,cz,sy,palette,indices in iter_selected_sections(world,'projectseele:geofront',selected):
        a=indices.reshape(16,16,16)
        for x,y,z in wanted[cx,sy,cz]:result[x,y,z]=palette[int(a[y%16,z%16,x%16])]
    assert set(result)==set(points),'Every source cell must be measured'
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--packet',type=Path,required=True);ap.add_argument('--proof',type=Path,required=True);ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    packet=read(args.packet);proof=read(args.proof);source=packet['dock_source_sha256']
    assert source==proof['station_source']
    stations=proof['candidate_stations'];assert len(stations)==12 and len({s['leg']for s in stations})==12
    assert all(not s['source_hits']for s in stations),'Known mechanism intersections must be fixed before civil work'
    assert len(packet['stations'])==12 and {s['leg']for s in stations}=={s['leg']for s in packet['stations']}
    world=BASE/'WORLD_R52';gates=read(BASE/'runtime_directory/gates/ROOT_GATES.json')['gates']
    owned_gates=set();protected=set()
    for gate in gates:
        f=BASE/'runtime_directory/gates'/gate['collision_steps']['cells_file'];assert sha(f)==gate['collision_steps']['sha256']
        for group in json.loads(gzip.decompress(f.read_bytes())):
            owned_gates.update(tuple(cell['position'])for cell in group)
        protected.update(tuple(row['position'])for row in gate['supports'])
    basis={tuple(q)for row in packet['stations']for q in row['native_foundation_cells']}
    shell={tuple(q)for row in packet['stations']for q in row['actual_source_shell_sample_cells']}
    assert not basis&owned_gates,'Native pads cannot replace gate cells'
    assert not basis&shell,('Moving mechanism intersects its required native bearing blocks; revise the mechanism before civil installation',sorted(basis&shell)[:12])
    neighbours={(x+dx,y+dy,z+dz)for x,y,z in basis for dx in range(-3,4)for dz in range(-3,4)for dy in(-1,0)}
    # Root measured these six existing shaft-skin fixtures independently.
    # Keep the two lights on the same wall beyond the station hardware's
    # maximum Z=128.196; only the four trim cells inside the slot are retired.
    lamps={(48,-558,124):(48,-558,130),(6,-558,124):(6,-558,130)}
    trim={(54,-550,-795),(54,-550,-794),(12,-550,-795),(12,-550,-794)}
    actual=states_at(world,shell|basis|neighbours|set(lamps.values()))
    air={'minecraft:air','minecraft:cave_air','minecraft:void_air'}
    removable={'minecraft:stone','projectseele:nerv_shaft_panel','projectseele:nerv_structural_panel','projectseele:nerv_machine_edge','projectseele:nerv_strip_light[lit=true]'}
    clear={q for q in shell-basis-owned_gates if actual[q]not in air}
    assert not clear&protected,'Declared gate supports cannot be carved'
    assert trim|set(lamps)<=clear,'Measured fixture scope changed'
    assert all(actual[q]=='minecraft:black_concrete'for q in trim)
    assert all(actual[q]=='minecraft:sea_lantern'for q in lamps)
    assert all(actual[q]in removable or q in trim or q in lamps for q in clear),[(q,actual[q])for q in clear if actual[q]not in removable and q not in trim and q not in lamps][:12]
    assert not set(lamps.values())&(shell|basis|owned_gates|protected)
    assert all(actual[q]=='projectseele:nerv_shaft_panel'for q in lamps.values())
    # All existing fixed-rail iron anchors are protected by the whitelist too.
    pad={q for q in basis if actual[q]in air}
    solid={'minecraft:stone','minecraft:iron_block','projectseele:nerv_structural_panel','projectseele:nerv_shaft_panel'}
    assert all(actual[q]in solid|air for q in basis),'Native bearing blocks must be solid or explicitly filled'
    # The underside parking slot passes under part of the existing floor.
    # Preserve the actual one-block-thick floor beam: at most three horizontal
    # full-block joins to an uncut, directly founded rim. Do not leave isolated
    # pads and do not silently refill a slot that the mechanism needs.
    load_paths=[]
    for start in sorted(basis):
        todo=collections.deque([(start,[start])]);seen={start};found=None
        while todo:
            q,path=todo.popleft();below=(q[0],q[1]-1,q[2])
            if below not in clear and actual.get(below)in solid:
                found=path+[below];break
            if len(path)>3:continue
            for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
                n=(q[0]+dx,q[1],q[2]+dz)
                if n not in seen and n not in clear and (actual.get(n)in solid or n in basis):
                    seen.add(n);todo.append((n,path+[n]))
        assert found,('Finite native floor-beam load path missing',start)
        load_paths.append(found)
    changes={q:'minecraft:air'for q in clear};changes.update({q:'projectseele:nerv_structural_panel'for q in pad})
    changes.update({q:'minecraft:sea_lantern'for q in lamps.values()})
    for cx,cz in {(x//16,z//16)for x,y,z in changes}:
        tags=dict(iter_block_entities(world,'projectseele:geofront',(cx*16,-960,cz*16),(cx*16+15,319,cz*16+15)))
        assert not set(tags)&set(changes),'Never carve a block entity from source surface samples'
    vox.WORLD=world;vox.OUT=BASE/'mechanical_foundations/final_dock';vox.DIM='projectseele:geofront'
    p=vox.Painter(vertical_bounds=(-960,320));stage='dock_'+source[:12];assert not list((vox.OUT/stage).glob('applied_*'))
    for q,state in changes.items():p.exact((*q,*q),actual[q],state,'R52_actual_mechanical_source_socket')
    p.meta.update(root_author=True,source_sha256=source,packet_sha256=sha(args.packet),proof_sha256=sha(args.proof),
        real_bearing_cells=[list(q)for q in sorted(basis)],new_bearing_cells=len(pad),source_intersecting_civil_cells=len(clear),
        preserved_native_load_paths=load_paths,maximum_floor_beam_horizontal_joins=max(len(v)-2 for v in load_paths),
        gate_cells_preserved=len(shell&owned_gates),existing_gate_supports_preserved=True,
        shaft_lamps_relocated=[dict(before=a,after=b)for a,b in lamps.items()],retired_slot_trim_cells=sorted(trim),
        sample_shell_scope=True,native_verified=False,requires_installed_source_clearance=True)
    out=p.save_plan(stage)
    if args.apply:p.apply(stage)
    (out/'PLAN.json').write_text(json.dumps(dict(p.meta,world_written=args.apply),indent=2),'utf8')
    print(json.dumps(dict(stage=str(out),clearance_cells=len(clear),new_supports=len(pad),world_written=args.apply)))


if __name__=='__main__':main()
