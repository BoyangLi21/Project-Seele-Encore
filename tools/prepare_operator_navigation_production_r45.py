"""Prepare installed semantic files/consumer patch offline; never install or launch.

Production input has no developer paths, class hashes or one-shot QA admission.
Sealing requires an actual same202/291/six-gate native receipt; no template pass.
"""
from __future__ import annotations
import argparse,copy,difflib,gzip,hashlib,json,math,sys
from pathlib import Path
sys.dont_write_bytecode=True
import nbtlib
from audit_pyramid_components_r45 import ROOT,WORLD,BASELINE,read,write,sha
from measure_world_r40 import MeasuredWorld
from prepare_school_hakone_native_r45 import ActualGeometry

ART=ROOT/'artifacts/rebuild_r45/pyramid_components_sol_v1'
DEFAULT=ART/'operator_navigation_integration_v2/operator_return_graph.UNBOUND.json'
SEMANTIC='R45_FIXED_PERSONNEL_V1';MODEL='R44_TV_PERSONNEL_4639_2A789'
MODEL_SHA='2a789960d2649118b12505be8d6c93888ed8e1cabe6beaef0c20f498b12551a3'
NAMES=('operator_return_routes_r45.json.gz','operator_navigation_acceptance_r45.json','operator_navigation_manifest_r45.json')
IDENTITY='dimensions/projectseele/geofront/data/projectseele_tokyo3_building_world_id_r44.dat'
NEGATIVES={'wrong_world_uuid_seed','changed_owner_or_BE','unloaded_chunk_or_entity_section','closed_pair','split_pair','occupied','moving',
           'no_gantry','duplicate_gantry','changed_support_or_fractional_shape','legacy417_air','disabled_provider','dynamic_inspection_unbound'}

def patch_file(path,new):
    old=path.read_bytes().decode('utf8')
    return ''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/'+path.relative_to(ROOT).as_posix(),tofile='b/'+path.relative_to(ROOT).as_posix()))

def main(args):
    out=args.out.resolve();assert not out.exists() and not out.is_relative_to(WORLD) and 'saves'not in{p.lower()for p in out.parts}
    old=read(args.graph);assert old['schema']=='projectseele.r45-operator-return-graph.v1' and not old['bound']
    baseline=read(BASELINE);plan={r['relative']:r['sha256']for r in baseline['files']}
    def inventory():
        assert len(plan)==1736 and {p.relative_to(WORLD).as_posix()for p in WORLD.rglob('*')if p.is_file()}==set(plan)
        values={k:sha(WORLD/k)for k in sorted(plan)};assert values==plan;return values
    before=inventory()
    assert sha(WORLD/IDENTITY)==plan[IDENTITY] and sha(WORLD/'r44_tv_personnel_platforms.json')==old['metadata_sha256']
    identity=str(nbtlib.load(WORLD/IDENTITY)['data']['WorldUUID']);assert identity==baseline['world_id']
    assert sha(ROOT/'src/main/resources/assets/projectseele/mesh/tv_shoulder_shells_r44.json')==MODEL_SHA,'Root model epoch changed; obtain a fresh semantic/native proof'
    graph=copy.deepcopy(old)
    for key in('source_contract_file','bound','installed','native_shapes_sha256'):graph.pop(key,None)
    graph.update(schema='projectseele.operator-return-semantic-graph.v1',semantic_revision=SEMANTIC,world_id=identity,world_seed=baseline['world_seed'],
        model_revision=MODEL,model_sha256=MODEL_SHA,source_semantics_sha256=old['source_contract_sha256'])
    for scope in graph['scopes']:
        scope.pop('compact_car_usable',None);scope.pop('compact_known_foreign_floor_corner_repair_installed',None);scope['compact_target_enabled']=False
    plain=(json.dumps(graph,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf8');compressed=gzip.compress(plain,mtime=0)
    graph_sha=hashlib.sha256(compressed).hexdigest()
    fixed=[dict(scope=s['id'],node=i,feet=n['feet'])for s in graph['scopes']for i,n in enumerate(s['nodes'])if n['kind']=='fixed_operator']
    edges=[dict(scope=s['id'],a=e['a'],b=e['b'])for s in graph['scopes']for e in s['edges']if e['kind']=='fixed_operator']
    assert len(fixed)==202 and len(edges)==291 and len(graph['scopes'])==6
    # Strict production width/height, independent of the older .58/1.77 proxy.
    m=MeasuredWorld(WORLD);m.box((-46,-405,-298),(114,-385,-42));m.load();assert all(s=='full'for s in m.status.values())
    geometry=ActualGeometry(m);body_proofs=[]
    def full_clear(a,b,opened):
        y=max(a[1],b[1]);lo=[min(a[0],b[0])-.3,y+.001,min(a[2],b[2])-.3];hi=[max(a[0],b[0])+.3,y+1.8,max(a[2],b[2])+.3]
        for x in range(math.floor(lo[0]),math.floor(hi[0])+1):
            for Y in range(math.floor(lo[1]),math.floor(hi[1])+1):
                for z in range(math.floor(lo[2]),math.floor(hi[2])+1):
                    q=(x,Y,z);boxes=geometry.boxes(q,opened)
                    if boxes is None:return 'UNKNOWN_NATIVE_SHAPE'
                    if any(all(q[k]+box[k]<hi[k] and q[k]+box[k+3]>lo[k]for k in range(3))for box in boxes):return 'BODY_OBSTRUCTION'
        return 'CLEAR'
    for scope in graph['scopes']:
        opened={tuple(q)for p in scope['gate_lower']for q in(p,[p[0],p[1]+1,p[2]])}
        for i,n in enumerate(scope['nodes']):body_proofs.append(dict(scope=scope['id'],node=i,kind=n['kind'],status=full_clear(n['feet'],n['feet'],opened)))
        for e in scope['edges']:body_proofs.append(dict(scope=scope['id'],edge=e,kind=e['kind'],status=full_clear(scope['nodes'][e['a']]['feet'],scope['nodes'][e['b']]['feet'],opened)))
    assert all(r['status']=='CLEAR'for r in body_proofs),'Strict .6 x1.8 production body finds a blocked or unknown route; preserve failure and repair its owner'
    assert inventory()==before
    proof=dict(schema='projectseele.operator-navigation-installed-acceptance.v1',passed=False,world_id=identity,world_seed=baseline['world_seed'],
        semantic_revision=SEMANTIC,graph_sha256=graph_sha,metadata_sha256=old['metadata_sha256'],model_sha256=MODEL_SHA,
        actual_fixed_cells_passed=0,actual_fixed_edges_passed=0,actual_gate_scopes_passed=0,actual_runtime_negative_states_passed=False,source_native_receipt_sha256=None)
    if args.acceptance:
        raw=read(args.acceptance)
        assert raw['schema']=='projectseele.r45-operator-native-acceptance.v1' and raw['passed'] and raw['actual_native_execution'] and not raw.get('synthetic_fixture',False)
        assert raw['source_graph_sha256']==sha(args.graph) and raw['metadata_sha256']==old['metadata_sha256'] and raw['model_sha256']==MODEL_SHA
        assert raw['world_id']==identity and int(raw['world_seed'])==int(baseline['world_seed'])
        observed={(r['scope'],r['node']):r for r in raw['fixed_cells']};assert len(observed)==202
        for row in fixed:
            r=observed[row['scope'],row['node']]
            assert r['executed'] and r['passed'] and r['no_teleport_during_measurement'] and math.dist(r['actual_end_feet'],row['feet'])<.1
        seen={(r['scope'],min(r['a'],r['b']),max(r['a'],r['b'])):r for r in raw['fixed_edges']};assert len(seen)==291
        for e in edges:
            r=seen[e['scope'],min(e['a'],e['b']),max(e['a'],e['b'])];assert r['executed'] and r['passed'] and r['no_teleport_during_measurement'] and r['both_width_lanes_actual_passed']
        gates={r['scope']:r for r in raw['gate_scopes']};assert set(gates)=={s['id']for s in graph['scopes']}
        for r in gates.values():assert all(r[k]for k in('executed','open_pair_walk_passed','closed_pair_refused','split_pair_refused','occupied_refused','moving_refused','missing_duplicate_gantry_refused'))
        negatives={r['state']:r for r in raw['negative_cases']};assert set(negatives)==NEGATIVES
        assert all(r['executed'] and r['passed']for r in negatives.values())
        proof.update(passed=True,actual_fixed_cells_passed=202,actual_fixed_edges_passed=291,actual_gate_scopes_passed=6,
            actual_runtime_negative_states_passed=True,source_native_receipt_sha256=sha(args.acceptance))
    proof_bytes=(json.dumps(proof,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    manifest=dict(schema='projectseele.operator-navigation-manifest.v1',installed_semantic_contract=True,fixed_navigation_accepted=proof['passed'],
        semantic_revision=SEMANTIC,dimension='projectseele:geofront',world_id=identity,world_seed=baseline['world_seed'],
        graph_file=NAMES[0],graph_sha256=graph_sha,acceptance_file=NAMES[1],acceptance_sha256=hashlib.sha256(proof_bytes).hexdigest(),
        metadata_file='r44_tv_personnel_platforms.json',metadata_sha256=old['metadata_sha256'],identity_file=IDENTITY,
        model_revision=MODEL,model_sha256=MODEL_SHA,dynamic_inspection_bound=False)
    # Review patch remains uninstalled. Production goals are offered dynamically,
    # only after a valid installed contract and actual facility enablement.
    nav=ROOT/'src/main/java/com/projectseele/world/NervWayfindingR24.java';nav_old=nav.read_bytes().decode('utf8');nl='\r\n'if'\r\n'in nav_old else'\n'
    assert 'OperatorNavigationR45.start(player,goal)'not in nav_old,'Do not mix the QA goal dispatch into production'
    anchor='        var selections=ACTIVE.computeIfAbsent(player.server,key->new HashMap<>());'
    addition=anchor+nl+'        if(goal.equals("operator_nearest_lift")){selections.remove(player.getUUID());return OperatorNavigationProductionR45.start(player);}'+nl+'        OperatorNavigationProductionR45.stop(player);'
    new=nav_old if'OperatorNavigationProductionR45.start(player)'in nav_old else nav_old.replace(anchor,addition)
    assert new.count('OperatorNavigationProductionR45.')==2 and '"operator_nearest_lift"'not in new.split('public static final List<String> GOALS=',1)[1].split(';',1)[0]
    command=ROOT/'src/main/java/com/projectseele/visual/NervStaffCommands.java';cmd_old=command.read_bytes().decode('utf8')
    expression='java.util.stream.Stream.concat(com.projectseele.world.NervWayfindingR24.GOALS.stream(),java.util.stream.Stream.of("stop"))'
    replacement='java.util.stream.Stream.concat(java.util.stream.Stream.concat(com.projectseele.world.NervWayfindingR24.GOALS.stream(),com.projectseele.world.OperatorNavigationProductionR45.availableGoals(c.getSource().getPlayer()).stream()),java.util.stream.Stream.of("stop"))'
    cmd_new=cmd_old if'OperatorNavigationProductionR45.availableGoals'in cmd_old else cmd_old.replace(expression,replacement)
    assert 'OperatorNavigationProductionR45.availableGoals'in cmd_new
    out.mkdir(parents=True);(out/NAMES[0]).write_bytes(compressed);(out/NAMES[1]).write_bytes(proof_bytes);write(out/NAMES[2],manifest)
    write(out/'all_full0p6x1p8_body_and_higher_datum_sweeps.json',body_proofs)
    (out/'root_production_navigation_dispatch.patch').write_bytes((patch_file(nav,new)+patch_file(command,cmd_new)).encode('utf8'))
    template=dict(schema='projectseele.r45-operator-native-acceptance.v1',passed=False,actual_native_execution=False,world_id=identity,world_seed=baseline['world_seed'],
        source_graph_sha256=sha(args.graph),metadata_sha256=old['metadata_sha256'],model_sha256=MODEL_SHA,
        fixed_cells=[dict(**r,executed=False,passed=False,no_teleport_during_measurement=False,actual_end_feet=None)for r in fixed],
        fixed_edges=[dict(**r,executed=False,passed=False,no_teleport_during_measurement=False,both_width_lanes_actual_passed=False)for r in edges],
        gate_scopes=[dict(scope=s['id'],executed=False,open_pair_walk_passed=False,closed_pair_refused=False,split_pair_refused=False,occupied_refused=False,moving_refused=False,missing_duplicate_gantry_refused=False)for s in graph['scopes']],
        negative_cases=[dict(state=k,executed=False,passed=False)for k in sorted(NEGATIVES)])
    write(out/'actual_native_acceptance_INPUT_TEMPLATE_false.json',template)
    assert all(not(WORLD/name).exists()for name in NAMES),'Preserve earlier installed files; prepare an explicit version migration instead'
    write(out/'root_semantic_install_recipe.json',dict(schema='projectseele.operator-navigation-install-proposal.v1',world=str(WORLD),installed=False,
        install_allowed=proof['passed'],files=[dict(target_relative=name,candidate=str(out/name),candidate_sha256=sha(out/name),before_absent=True,before_bytes=None)for name in NAMES],
        inverse='Only remove newly installed files whose complete SHA equals this recipe; retain all old graphs, metadata, ownership/progress and world files',
        world_block_mask=[],entity_mask=[],public_graph_replaced=False,requires_actual_facility_enablement_wiring_by_root=True))
    write(out/'report.json',dict(production_graph_has_development_path_or_QA_lease_or_class_SHA=False,fixed_count=202,fixed_edges=291,scope_count=6,
        native_accepted=proof['passed'],installed=False,consumer_patch_applied=False,ordinary_public_GOALS_unchanged=True,
        available_goal_when_manifest_absent_or_not_accepted_or_real_provider_disabled=[],no_dynamic_inspection_goal=True,
        graph_sha256=graph_sha,source_review_graph_sha256=sha(args.graph),full0p6x1p8_static_probes=len(body_proofs),all_full_width_native_shape_static_probes_clear=True,
        full1736_inventory_SHA_before_after_equal=True,world_written=False,Java_Gradle_MC_started=False))
    print(json.dumps(read(out/'report.json'),ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--graph',type=Path,default=DEFAULT);p.add_argument('--acceptance',type=Path);p.add_argument('--out',type=Path,required=True);main(p.parse_args())
