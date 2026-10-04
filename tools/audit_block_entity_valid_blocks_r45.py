"""Read-only all-dimension BE/block audit on the explicitly frozen R45 source."""
from pathlib import Path
import argparse,collections,gzip,hashlib,io,json,re,struct,zlib
import nbtlib,numpy as np
from inspect_map_assets import decode_modern_section,palette_state
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'artifacts/rebuild_r45/composition_candidates/R45_source_candidate_20261003_v4_01/world'
DEFAULT_OUT=ROOT/'artifacts/rebuild_r45/be_state_mismatch_sol_v15'
MASK=(1<<64)-1

def sha_bytes(data):return hashlib.sha256(data).hexdigest()
def packed_xyz(value):
 v=int(value)&MASK;x=v>>38;z=(v>>12)&0x3ffffff;y=v&0xfff
 return (x-(1<<26) if x&(1<<25) else x,y-4096 if y&2048 else y,z-(1<<26) if z&(1<<25) else z)

def valid_blocks():
 a=ROOT/'src/main/java/com/projectseele/registry/ModBlockEntities.java';b=ROOT/'src/main/java/com/projectseele/registry/ModBlocks.java'
 text=b.read_text('utf-8-sig');blocks={name:'projectseele:'+ident for name,ident in re.findall(r'RegistryObject<Block>\s+(\w+)\s*=\s*(?:BLOCKS\.register|finish|structuralFinish|equipment)\s*\(\s*"([^"]+)"',text)}
 declarations=[];source=a.read_text('utf-8-sig')
 for m in re.finditer(r'BLOCK_ENTITY_TYPES\.register\("([^"]+)"\s*,\s*\(\)\s*->\s*BlockEntityType\.Builder\.of\((.*?)\)\.build\(null\)\)',source,re.S):
  symbols=re.findall(r'ModBlocks\.(\w+)\.get\(\)',m[2]);names=[blocks.get(s) for s in symbols]
  declarations.append({'be_id':'projectseele:'+m[1],'valid_blocks':names,'symbols':symbols,'fully_resolved':bool(names) and None not in names,
   'registry_line':source.count('\n',0,m.start())+1,'declaration':m[0]})
 return {d['be_id']:set(d['valid_blocks']) for d in declarations if d['fully_resolved']},{'declarations':declarations,'source_sha256':{str(a):sha_bytes(a.read_bytes()),str(b):sha_bytes(b.read_bytes())}}

def dimensions():
 pairs=[('minecraft:overworld',SOURCE),('minecraft:the_nether',SOURCE/'DIM-1'),('minecraft:the_end',SOURCE/'DIM1')]
 base=SOURCE/'dimensions'
 if base.exists():
  for region in base.rglob('region'):
   if region.is_dir():
    parts=region.parent.relative_to(base).parts
    if len(parts)>=2:pairs.append((parts[0]+':'+('/'.join(parts[1:])),region.parent))
 return [(name,path) for name,path in pairs if (path/'region').is_dir()]

def strict_chunks(region,errors,counter,file_records):
 before=region.stat();data=region.read_bytes();file_records.append({'path':str(region.relative_to(SOURCE)),'sha256':sha_bytes(data),'bytes':len(data),'mtime_ns':before.st_mtime_ns})
 if len(data)==0:counter['zero_byte_empty_region_placeholders']+=1;return
 if len(data)<8192:errors.append({'file':str(region),'reason':'short nonempty Anvil header'});return
 rx,rz=map(int,region.stem.split('.')[1:]);occupied={}
 for index in range(1024):
  loc=struct.unpack_from('>I',data,index*4)[0];sector=loc>>8;sectors=loc&255
  if not sector:continue
  cx,cz=rx*32+index%32,rz*32+index//32;counter['header_nonempty']+=1
  try:
   if sector<2 or sectors<1 or sector*4096+5>len(data):raise ValueError('invalid sector location')
   for s in range(sector,sector+sectors):
    if s in occupied:raise ValueError('overlapping sectors')
    occupied[s]=index
   pos=sector*4096;length=struct.unpack_from('>I',data,pos)[0];kind=data[pos+4];external=kind&128;kind&=127
   if not external and (length<1 or length>sectors*4096-4 or pos+4+length>len(data)):raise ValueError('chunk length beyond allocated sectors')
   if external:
    path=region.parent/f'c.{cx}.{cz}.mcc';raw=path.read_bytes();file_records.append({'path':str(path.relative_to(SOURCE)),'sha256':sha_bytes(raw),'bytes':len(raw),'mtime_ns':path.stat().st_mtime_ns})
   else:raw=data[pos+5:pos+4+length]
   if kind==1:raw=gzip.decompress(raw)
   elif kind==2:raw=zlib.decompress(raw)
   elif kind!=3:raise ValueError(f'unsupported compression {kind}')
   tag=nbtlib.File.parse(io.BytesIO(raw));chunk=tag.get('Level',tag)
   if int(chunk.get('xPos',cx))!=cx or int(chunk.get('zPos',cz))!=cz:raise ValueError('chunk coordinate differs from Anvil slot')
   counter['decoded']+=1;yield cx,cz,chunk
  except Exception as e:errors.append({'file':str(region.relative_to(SOURCE)),'chunk':[cx,cz],'reason':str(e)})
 after=region.stat()
 if before.st_size!=after.st_size or before.st_mtime_ns!=after.st_mtime_ns:errors.append({'file':str(region),'reason':'source changed during read'})

def state_at(chunk,pos,cache):
 y=pos[1]//16
 if y not in cache:
  section=next((s for s in chunk.get('sections',[]) if int(s['Y'])==y),None)
  if section is None:cache[y]=None
  else:cache[y]=decode_modern_section(section)
 data=cache[y]
 if data is None:return 'minecraft:air','MISSING_SECTION_AIR'
 palette,indices=data
 if not palette:return None,'MISSING_PALETTE_UNKNOWN'
 index=((pos[1]&15)<<8)|((pos[2]&15)<<4)|(pos[0]&15)
 return palette_state(palette[int(indices[index])]),'SAME_CHUNK_SECTION_PALETTE'

def classify(be_id,state,valid):
 if be_id not in valid:return 'UNKNOWN_REGISTRATION'
 if state is None:return 'UNKNOWN_STATE'
 return 'VALID_DECLARED_BLOCK' if state.split('[')[0] in valid[be_id] else 'DECLARED_TYPE_MISMATCH'

def main(out):
 if SOURCE.resolve()!=Path(r'D:/eva/artifacts/rebuild_r45/composition_candidates/R45_source_candidate_20261003_v4_01/world').resolve():raise ValueError('Frozen source authority differs')
 if out.exists():raise ValueError('Use a new report epoch; never overwrite')
 if not out.resolve().is_relative_to(DEFAULT_OUT.resolve()):raise ValueError('Report must stay in owned artifact directory')
 out.mkdir(parents=True);valid,declarations=valid_blocks();errors=[];files=[];rows=[];counts=collections.Counter();missing=[];dim_stats=[]
 reverse={block:be for be,names in valid.items() for block in names}
 registry=ROOT/'artifacts/rebuild_r45/transport_controls_agent/prepared_v1/all50_current_live_boards.json'
 registered={tuple(b['position']) for b in json.loads(registry.read_text('utf-8'))['boards']}
 for dimension,path in dimensions():
  c=collections.Counter();start=len(rows)
  for region in sorted((path/'region').glob('r.*.*.mca')):
   c['regions']+=1
   for cx,cz,chunk in strict_chunks(region,errors,c,files):
    status=str(chunk.get('Status','')).removeprefix('minecraft:');c['status_'+status]+=1
    cache={};present=collections.defaultdict(list)
    for index,be in enumerate(chunk.get('block_entities',chunk.get('TileEntities',[]))):
     pos=tuple(int(be[k]) for k in ('x','y','z')) if all(k in be for k in ('x','y','z')) else None
     be_id=str(be.get('id',''));state=None;state_origin='MISSING_BE_POSITION'
     if pos:
      present[pos].append(be_id)
      if (pos[0]//16,pos[2]//16)==(cx,cz):state,state_origin=state_at(chunk,pos,cache)
      else:state_origin='BE_POSITION_OUTSIDE_CONTAINER_CHUNK'
     full=be.snbt();classification=classify(be_id,state,valid)
     row={'dimension':dimension,'position':list(pos) if pos else None,'be_id':be_id,'state':state,'state_origin':state_origin,'classification':classification,
      'chunk':[cx,cz],'chunk_status':status,'region':str(region.relative_to(SOURCE)),'be_index':index,'full_nbt':full,'nbt_snbt_sha256':sha_bytes(full.encode()),
      'in_declared_live50':dimension=='projectseele:geofront' and pos in registered,'valid_block_names':sorted(valid.get(be_id,[])),'native_pass':False}
     rows.append(row);counts[be_id,classification]+=1;c['block_entities']+=1
    for pos,ids in present.items():
     if len(ids)>1:errors.append({'dimension':dimension,'chunk':[cx,cz],'position':pos,'reason':'multiple block entities at same coordinates','ids':ids})
    if status=='full':
     for section in chunk.get('sections',[]):
      palette=section.get('block_states',{}).get('palette',[])
      wanted={i for i,p in enumerate(palette) if str(p.get('Name','')) in reverse}
      if not wanted:continue
      pal,ids=decode_modern_section(section);cache[int(section['Y'])]=(pal,ids)
      for index in np.flatnonzero(np.isin(ids,list(wanted))):
       pos=(cx*16+(int(index)&15),int(section['Y'])*16+(int(index)>>8),cz*16+((int(index)>>4)&15));state=palette_state(pal[int(ids[index])]);expected=reverse[state.split('[')[0]]
       if expected not in present.get(pos,[]):missing.append({'dimension':dimension,'position':pos,'state':state,'expected_be':expected,'present_be_types':present.get(pos,[]),'classification':'DECLARED_BE_BLOCK_WITHOUT_MATCHING_BE','region':str(region.relative_to(SOURCE))})
   if c['regions']%20==0:print(json.dumps({'dimension':dimension,'regions':c['regions'],'decoded':c['decoded'],'be':c['block_entities']},ensure_ascii=False),flush=True)
  dim_stats.append({'dimension':dimension,'root':str(path.relative_to(SOURCE)),'counts':dict(c),'be_rows':len(rows)-start})
 with gzip.open(out/'all_world_block_entities.jsonl.gz','wt',encoding='utf-8') as f:
  for row in rows:f.write(json.dumps(row,ensure_ascii=False)+'\n')
 boards=[r for r in rows if r['be_id']=='projectseele:station_departure_board']
 mismatches=[r for r in rows if r['classification']=='DECLARED_TYPE_MISMATCH']
 for name,value in [('valid_blocks_source',declarations),('all_departure_boards',boards),('declared_mismatches',mismatches),('missing_declared_be_blocks',missing),('read_errors',errors),('source_region_files',files)]:
  (out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),'utf-8')
 report={'schema':'projectseele.be-state-audit-r45.v15','source_world':str(SOURCE),'dimensions':dim_stats,'be_count':len(rows),'departure_board_be_count':len(boards),
  'declared_mismatch_count':len(mismatches),'missing_declared_be_count':len(missing),'unknown_registration_count':sum(r['classification']=='UNKNOWN_REGISTRATION' for r in rows),
  'type_classification_counts':[{'be_id':k[0],'status':k[1],'count':n} for k,n in sorted(counts.items())],
  'read_complete':not errors,'errors':len(errors),'source_world_written':False,'java_mc_started':False,'native_pass':False,
  'limits':'Unknown mod registry relations stay UNKNOWN; SavedData/cargo/journal payloads are separate from world block_entities and will be audited in a separate report.'}
 (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8');print(json.dumps({k:report[k] for k in ('be_count','departure_board_be_count','declared_mismatch_count','missing_declared_be_count','unknown_registration_count','read_complete','errors')},ensure_ascii=False),flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True);args=parser.parse_args();main(args.out)
