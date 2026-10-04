from pathlib import Path
import gzip,json,copy,hashlib,importlib.util,sys,collections
sys.dont_write_bytecode=True
R=Path('D:/eva');A=R/'artifacts/rebuild_r45';O=A/'lifts_doors_lifecycle_sol_v2/tv_door_lift_construction_v1/root_v14_cabin558_entry_v1';M=A/'lifts_doors_lifecycle_sol_v2/tv_door_lift_construction_v1/cabin_material_install_v4_source_v14';W=A/'composition_candidates/R45_source_candidate_20261004_station_finish_v14_01/world';P=A/'terrain_global_agent/stream_exact_install_r45_v2.py'
sys.path.insert(0,str(R/'tools'));spec=importlib.util.spec_from_file_location('cabin_shared_codec',P);c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c);rows=[json.loads(l)for l in gzip.open(M/'forward.jsonl.gz','rt',encoding='utf8')];state={s:i for i,s in enumerate(sorted({r[k]for r in rows for k in ['before','after']}))};reverse={i:s for s,i in state.items()};by=collections.defaultdict(list)
for r in rows:
 x,y,z=r['pos'];by[x//16,z//16].append((y//16,(x&15)+(z&15)*16+(y&15)*256,state[r['before']],state[r['after']],r['before_nbt'],r['after_nbt']))
regions={};be=0;chunks=[];negative=False
for (cx,cz),changes in sorted(by.items()):
 key=(cx//32,cz//32)
 if key not in regions:regions[key]=c.read_region(W/'dimensions/projectseele/geofront/region'/f'r.{key[0]}.{key[1]}.mca')[1]
 blob=regions[key][(cx&31)+(cz&31)*32];before=c.parse_chunk(blob);before_tags=copy.deepcopy(c.block_tags(before));guard=c.chunk_guard_hash(before,changes,True);projected=copy.deepcopy(before)
 c.validate_chunk(projected,changes,reverse)
 if not negative:
  bad=list(changes);sy,off,b,a,bn,an=bad[0];bad[0]=(sy,off,a,a,bn,an)
  try:c.validate_chunk(copy.deepcopy(before),bad,reverse)
  except RuntimeError:negative=True
  else:raise AssertionError('Wrong whole-state preimage accepted')
 c.mutate_chunk(projected,changes,reverse,True);after=c.parse_chunk(c.chunk_blob(projected));c.validate_chunk(after,changes,reverse,after=True);assert c.block_tags(after)==before_tags and c.chunk_guard_hash(after,changes,True)==guard
 inv=[(sy,off,a,b,an,bn)for sy,off,b,a,bn,an in changes];c.mutate_chunk(after,inv,reverse,True);restored=c.parse_chunk(c.chunk_blob(after));c.validate_chunk(restored,changes,reverse);assert c.block_tags(restored)==before_tags and c.chunk_guard_hash(restored,changes,True)==guard
 be+=len(before_tags);chunks.append(dict(chunk=[cx,cz],rows=len(changes),complete_BE_records_preserved=len(before_tags),forward_serialized_exact=True,inverse_serialized_exact=True,all_non_target_chunk_tags_equal=True))
assert negative and len(chunks)==13 and sum(r['rows']for r in chunks)==558
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();d=dict(schema='projectseele.tv-cabin558-v14-shared-codec-ram-projection.v1',source=str(W),source_receipt_sha256=sha(W.parent/'composition_station_finish_readback.json'),forward_sha256=sha(M/'forward.jsonl.gz'),inverse_sha256=sha(M/'inverse.jsonl.gz'),shared_codec_sha256=sha(P),regions=len(regions),chunks=chunks,all_touched_BE_preserved=be,typedNBT_forward_and_inverse_exact=True,wrong_preimage_rejected=True,derivative_relight_not_actor_or_device_NBT=True,actual_registered3_capture_reference=str(O/'native_actual_binding_v1/catalog.BOUND.json'),world_or_Java_or_class_or_shared_source_written=False,native_function_or_visual_pass=False)
q=O/'native_registered558_codec_RAM_projection.json';assert not q.exists();q.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'chunks':13,'rows':558,'all_touched_BE':be,'negative_preimage':True,'world_or_Java_written':False,'receipt':str(q)},indent=2))
