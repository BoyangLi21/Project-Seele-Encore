"""Generate/bind the finite, fractional personnel-return graph; never write a world.

The old public graph is an input to the regression, not the universe of nodes.
Only the 202 metadata-owned decks and the six measured gate approaches enter
the operator extension. A fresh root cold lease is mandatory for runtime use.
"""
from __future__ import annotations
import argparse, difflib, gzip, heapq, json, math, sys
from pathlib import Path
sys.dont_write_bytecode=True
from audit_pyramid_components_r45 import ROOT,WORLD,BASELINE,read,write,sha
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities
from prepare_school_hakone_native_r45 import ActualGeometry

ART=ROOT/'artifacts/rebuild_r45/pyramid_components_sol_v1'
FROZEN=ART/'boarding417_semantics_v4'
JAVA=ROOT/'src/main/java/com/projectseele/world/OperatorNavigationR45.java'
SCHEMA='projectseele.r45-operator-return-graph.v1'

def distances(nodes,edges,target):
    adjacent=[[]for _ in nodes]
    for e in edges:
        a,b=e['a'],e['b'];cost=math.dist(nodes[a]['feet'],nodes[b]['feet'])
        adjacent[a].append((b,cost));adjacent[b].append((a,cost))
    cost=[math.inf]*len(nodes);nxt=[-1]*len(nodes);cost[target]=0;nxt[target]=target;q=[(0,target)]
    while q:
        d,i=heapq.heappop(q)
        if d!=cost[i]:continue
        for n,w in adjacent[i]:
            if d+w<cost[n]:cost[n]=d+w;nxt[n]=i;heapq.heappush(q,(d+w,n))
    assert all(math.isfinite(d)for d in cost),'A declared scope contains a disconnected node'
    return [dict(next=n,metres=d)for n,d in zip(nxt,cost)]

def prepare(args):
    out=args.out.resolve();assert not out.exists() and not out.is_relative_to(WORLD)
    source=read(FROZEN/'scoped_operator_graph_extension_UNBOUND.json')
    owners=read(FROZEN/'all427_current_owned_installation_readback.json')
    gate_rows=read(FROZEN/'all6_gate_pairs_and_real_same_floor_lift_paths.json')
    metadata=read(WORLD/'r44_tv_personnel_platforms.json')
    expected={r['relative']:r['sha256']for r in read(BASELINE)['files']};assert len(expected)==1736
    def inventory():
        assert {p.relative_to(WORLD).as_posix()for p in WORLD.rglob('*')if p.is_file()}==set(expected)
        value={k:sha(WORLD/k)for k in sorted(expected)};assert value==expected;return value
    before=inventory()
    assert sha(WORLD/'r44_tv_personnel_platforms.json')==source['source_metadata_sha256']
    assert sha(WORLD/'native_collision_shapes.json')==source['native_collision_sha256']
    with gzip.open(WORLD/'nerv_routes_r24.json.gz','rt',encoding='utf8')as f:old_graph=json.load(f)
    old_nodes={tuple(r[:3])for r in old_graph['nodes']};assert len(old_nodes)==143080
    legacy=read(FROZEN/'all417_current_semantics_and_full_columns.json')
    legacy_xz={(r['legacy_pos'][0],r['legacy_pos'][2])for r in legacy}
    m=MeasuredWorld(WORLD);m.box((-46,-405,-298),(114,-385,-42));m.load()
    assert all(v=='full'for v in m.status.values())
    tags=dict(iter_block_entities(WORLD,'projectseele:geofront',(-46,-405,-298),(114,-385,-42),selected_chunks=set(m.selected)))
    g=ActualGeometry(m);scopes=[];regressions=[];gateway_proofs=[]
    for case,gate_row in zip(source['cases'],gate_rows):
        gate=gate_row['contract'];v,side=gate['variant'],gate['side']
        nodes=[];index={};edges=[];edge_seen=set()
        opened={tuple(q)for p in gate['lower_positions']for q in(p,[p[0],p[1]+1,p[2]])}
        def add(feet,kind,owner=None):
            feet=tuple(map(float,feet));key=(feet,kind)
            if key in index:return index[key]
            q=tuple(owner['position'])if owner else(math.floor(feet[0]),math.floor(feet[1]-.04),math.floor(feet[2]))
            assert q not in tags,'A route must not invent ownership of a block entity'
            row=dict(feet=list(feet),kind=kind,support=list(q),state=m.block(q),full_nbt=None)
            if owner:
                assert row['state']==owner['after'];row['variant']=v;row['side']=side
            else:assert g.standing(feet,opened)=='STATIC_STANDING',('Unproven fixed gate/public bearing',row,g.standing(feet,opened))
            assert g.clear(feet,opened)=='CLEAR',('Blocked declared endpoint',row)
            n=len(nodes);nodes.append(row);index[key]=n;return n
        def edge(a,b,kind):
            if a==b:return
            key=tuple(sorted((a,b)))
            if key in edge_seen:return
            pa,pb=nodes[a]['feet'],nodes[b]['feet'];assert math.hypot(pa[0]-pb[0],pa[2]-pb[2])<=1.001
            y=max(pa[1],pb[1]);assert g.clear([pa[0],y,pa[2]],opened,[pb[0],y,pb[2]])=='CLEAR'
            edge_seen.add(key);edges.append(dict(a=a,b=b,kind=kind,native_walk_proven=False))
        fixed={}
        for d in case['current202_exact_native_floor_subset']:
            q=tuple(d['actual']['pos']);assert(q[0],q[2])not in legacy_xz
            p=d['actual_fixed_world_body_probe'];n=add(p,'fixed_operator',d['owner']);fixed[q]=n
            regressions.append(dict(scope=case['id'],node=n,owner=list(q),exact_feet=p,
                old_integer_graph_exact_datum_present=(q[0],p[1],q[2])in old_nodes,
                old_Java_getAsInt_feet_y=int(p[1]),new_loader_double_feet_y=p[1],native_pass=False))
        for e in case['all_current_adjacent_fixed_floor_edge_proposals']:
            edge(fixed[tuple(e['a'])],fixed[tuple(e['b'])],'fixed_operator')
        public_paths={}
        for name,path in case['real_same_floor_lift_public_paths'].items():
            ids=[add(p,'public')for p in path]
            for a,b in zip(ids,ids[1:]):edge(a,b,'public')
            public_paths[name]=ids
        for lower in gate['lower_positions']:
            x,y,z=lower
            if v==2 and side==1:inside=(x-1,z);outside=[x+1.5,float(y),z+.5]
            else:inside=(x,z+1);outside=[x+.5,float(y),z-.5]
            # Gate approaches can be the native .9375 MTR tread. Do not
            # resurrect the integer nominal datum in the new producer.
            support=(math.floor(outside[0]),y-1,math.floor(outside[2]));boxes=g.boxes(support,opened)
            assert boxes is not None
            tops=sorted({b[4]for b in boxes},reverse=True)
            actual=[support[1]+top for top in tops if all(any(b[0]<=a<=b[3]and b[2]<=c<=b[5]and abs(b[4]-top)<.001 for b in boxes)for a in(.25,.5,.75)for c in(.25,.5,.75))]
            assert actual,'A registered gate has no full fixed public bearing'
            outside[1]=actual[0]
            inside_id=next(n for q,n in fixed.items()if(q[0],q[2])==inside)
            gate_id=add([x+.5,float(y),z+.5],'gate');outside_id=add(outside,'public')
            edge(inside_id,gate_id,'gate');edge(gate_id,outside_id,'gate')
            for n in list(public_paths['real_west_lift'])+list(public_paths['real_compact_lift']):
                p=nodes[n]['feet']
                if abs(p[1]-outside[1])<=.063 and 0<math.hypot(p[0]-outside[0],p[2]-outside[2])<=1.001:edge(n,outside_id,'public')
            gateway_proofs.append(dict(scope=case['id'],actual_lower=lower,inside=nodes[inside_id],gate=nodes[gate_id],outside=nodes[outside_id],
                static_full_0p6m_body_sweep_with_complete_pair_open=True,actual_native_gate_and_stair_walk_pass=False))
        target=public_paths['real_west_lift'][0]
        table=distances(nodes,edges,target)
        assert all(nodes[table[i]['next']]['kind']=='public'for i,n in enumerate(nodes)if n['kind']=='public'),'A public return may not enter a private lane'
        scopes.append(dict(id=case['id'],variant=v,side=side,gate_lower=gate['lower_positions'],nodes=nodes,edges=edges,
            default_target='real_west_lift',target=target,return_table=table,public_paths=public_paths,
            compact_car_usable=False,compact_known_foreign_floor_corner_repair_installed=False))
    assert sum(len(c['current202_exact_native_floor_subset'])for c in source['cases'])==202
    assert sum(len(c['all_current_adjacent_fixed_floor_edge_proposals'])for c in source['cases'])==291
    assert sum(not r['old_integer_graph_exact_datum_present']for r in regressions)==172
    after=inventory();assert before==after
    document=dict(schema=SCHEMA,bound=False,dimension='projectseele:geofront',ordinary_public_floor=False,native_walk_proven=False,
        metadata_sha256=source['source_metadata_sha256'],native_shapes_sha256=source['native_collision_sha256'],
        source_contract_file=str((FROZEN/'scoped_operator_graph_extension_UNBOUND.json').resolve()),source_contract_sha256=sha(FROZEN/'scoped_operator_graph_extension_UNBOUND.json'),
        original_public_graph_sha256=sha(WORLD/'nerv_routes_r24.json.gz'),fixed_count=202,fixed_edge_count=291,gate_count=6,
        owners=[dict(position=r['actual']['pos'],state=r['actual']['state'],full_nbt=r['actual']['full_nbt'])for r in owners],scopes=scopes,
        dynamic_inspection=dict(bound=False,provider='TvCageCollisionR44 + actual no-save gantry',required_flags=['projectseele.r44TvPersonnelPlatformsReview','projectseele.r44TvCageReview'],
            reason='Nominal model waypoints are not an actual native route; never substitute the 417 old air nodes'),installed=False)
    out.mkdir(parents=True);write(out/'operator_return_graph.UNBOUND.json',document)
    write(out/'same202_old_failure_and_new_precision_regression.json',regressions);write(out/'all12_gateway_static_proofs.json',gateway_proofs)
    write(out/'runtime_negative_cases.UNBOUND.json',dict(schema='projectseele.r45-operator-navigation-regression.v1',bound=False,
        positive_cases=regressions,edge_cases=[dict(scope=s['id'],edge=e)for s in scopes for e in s['edges']],
        required_negative_states=['unbound','changed_graph_hash','wrong_world_path_uuid_seed','different_server','missing_or_changed_metadata','changed_427_owner_or_foreign_BE',
            'unloaded_chunk_or_entity_section','closed_pair','split_open_pair','broken_half','fleet_not_PARKED','no_gantry','duplicate_gantry','mid_motion_clock',
            'occupied_next_sweep','missing_support','changed_fractional_shape','riding_or_spectator','legacy417_air','dynamic_inspection_flag_disabled','dynamic_inspection_route_unbound'],native_pass=False))
    # The root applies this small dispatch after compiling the independent provider.
    consumer=ROOT/'src/main/java/com/projectseele/world/NervWayfindingR24.java';old=consumer.read_bytes().decode('utf8');new=old
    already_registered='OperatorNavigationR45.start(player,goal)'in old
    if not already_registered:new=new.replace('"low_plant","nearest_lift");','"low_plant","nearest_lift","operator_nearest_lift","operator_inspection_exit");')
    anchor='        var selections=ACTIVE.computeIfAbsent(player.server,key->new HashMap<>());'
    newline='\r\n'if'\r\n'in old else'\n'
    addition=anchor+newline+'        if(OperatorNavigationR45.GOALS.contains(goal)){selections.remove(player.getUUID());return OperatorNavigationR45.start(player,goal);}'+newline+'        OperatorNavigationR45.stop(player);'
    assert old.count(anchor)==1
    if not already_registered:new=new.replace(anchor,addition)
    assert new.count('OperatorNavigationR45.')==3 and ('"operator_nearest_lift","operator_inspection_exit"'in new)
    patch=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/src/main/java/com/projectseele/world/NervWayfindingR24.java',tofile='b/src/main/java/com/projectseele/world/NervWayfindingR24.java'))
    (out/'root_operator_dispatch.patch').write_bytes(patch.encode('utf8'));(out/'NervWayfindingR24.before.java.txt').write_bytes(consumer.read_bytes())
    write(out/'report.json',dict(fixed_nodes=202,fixed_edges=291,scopes=6,all_fixed_nodes_have_same_scope_gate_and_original_west_lift_return=True,
        old_same202_exact_datum_missing=172,new_same202_precision_lost=0,legacy417_registered_as_private_or_public_nodes=0,
        public_graph_replaced=False,full1736_inventory_SHA_before_after_equal=True,graph_bound=False,registration_patch_applied=already_registered,
        source_contract_sha256=document['source_contract_sha256'],graph_sha256=sha(out/'operator_return_graph.UNBOUND.json'),
        consumer_before_sha256=sha(consumer),world_written=False,Java_Gradle_MC_started=False,native_pass=False,installed=False))
    print(json.dumps(read(out/'report.json'),ensure_ascii=False),flush=True)

def bind(args):
    out=args.out.resolve();assert not out.exists() and not out.is_relative_to(WORLD)
    job=read(args.graph);assert job['schema']==SCHEMA and not job['bound']
    lease=read(args.binding)
    assert lease['schema']in('projectseele.city-atomic-native-binding-r45.v2','projectseele.city-atomic-native-binding-r45.v3')
    assert lease['qa_copy'] and lease['composition_complete'] and lease['installed_disabled'] and not lease['runtime_enabled']
    assert not Path(lease['preworld_receipt_output']).exists(),'Consumed leases cannot bind another operator run'
    epoch={str(Path(r['path']).resolve()).lower():r['sha256']for r in lease['source_epoch']}
    consumer=JAVA.with_name('NervWayfindingR24.java')
    # Review uses its own diagnostic/driver API. Never require installing its
    # temporary goals in the production player's public menu.
    for source in(JAVA,consumer):assert epoch.get(str(source.resolve()).lower())==sha(source),'Fresh root lease must include current provider and dispatch source'
    package=ROOT/'build/classes/java/main/com/projectseele/world'
    classes=sorted(list(package.glob('OperatorNavigationR45*.class'))+list(package.glob('NervWayfindingR24*.class')))
    assert classes and any(p.name=='OperatorNavigationR45.class'for p in classes),'Root must compile this provider before binding'
    runtime=[]
    for p in classes:
        assert epoch.get(str(p.resolve()).lower())==sha(p),'Lease lacks a current provider/record class'
        runtime.append(dict(resource='/com/projectseele/world/'+p.name,sha256=sha(p)))
    files={r['relative']:r['sha256']for r in lease['world_files']}
    assert files['r44_tv_personnel_platforms.json']==job['metadata_sha256']
    assert files['native_collision_shapes.json']==job['native_shapes_sha256']
    assert files['nerv_routes_r24.json.gz']==job['original_public_graph_sha256'],'Keep exact original public graph authority'
    assert sha(job['source_contract_file'])==job['source_contract_sha256']
    job.update(bound=True,world=lease['world'],world_id=lease['world_id'],world_seed=lease['world_seed'],
        candidate_binding=str(args.binding.resolve()),candidate_binding_sha256=sha(args.binding),runtime_classes=runtime,
        binding_mode='GUIDANCE_REVIEW_ONLY_NO_NATIVE_MOVE_PASS',native_walk_proven=False,installed=False)
    out.mkdir(parents=True);path=out/'operator_return_graph.bound.json';write(path,job)
    write(out/'root_properties.json',dict(properties=[f'-Dprojectseele.r45OperatorNavigationGraph={path}',f'-Dprojectseele.r45OperatorNavigationGraphSHA256={sha(path)}',
        f'-Dprojectseele.nativeCandidateBindingR45={args.binding.resolve()}',f'-Dprojectseele.nativeCandidateBindingR45SHA256={sha(args.binding)}',
        f'-Dprojectseele.nativeCandidateAdmissionR45={lease["preworld_receipt_output"]}',
        '-Dprojectseele.r44TvPersonnelPlatformsReview=true','-Dprojectseele.r44TvCageReview=true'],
        bound=True,world_written=False,process_started=False,native_pass=False,public_goal_registration_required=False,
        review_entry='OperatorNavigationR45.diagnostic(player, false/true); controlled root driver only'))
    print('Prepared one fresh-lease operator graph outside the world; no process started, no native pass.',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('prepare');a.add_argument('--out',type=Path,required=True)
    b=s.add_parser('bind');b.add_argument('--graph',type=Path,required=True);b.add_argument('--binding',type=Path,required=True);b.add_argument('--out',type=Path,required=True)
    args=p.parse_args();prepare(args)if args.action=='prepare'else bind(args)
