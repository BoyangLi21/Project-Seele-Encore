"""Read-only MTR conservation audit against the original delivered R51 archive.

Explicit rail replacement mappings only produce review rows. This tool never
accepts construction, rewrites MTR, starts a simulator or scans terrain.
"""
from pathlib import Path
import argparse,hashlib,json,struct,zipfile

ROOT=Path(__file__).resolve().parents[1]
ARCHIVE=Path('D:/eva/delivery/Project_SEELE_Encore_R51_20261009_Server.zip')
WORLD=Path('D:/eva/artifacts/r52_fresh_from_r51_20261009/WORLD_R52')
PREFIX='SEELE_R50_WORLD/'
HQ=9166787716217601435
PLATFORMS={0x910C703E8C195E14,0x5F8F651005220016,0x7503CEFA3D9A08FC}
OUT=ROOT/'artifacts/r52_hq_rail_boundary'
GEOMETRY={'position1','position2','angle1','angle2','shape','verticalRadius'}

class Reader:
    """The native loader consumes one MessagePack map; opaque tail bytes stay protected."""
    def __init__(self,raw):self.raw=raw;self.index=0
    def take(self,n):
        value=self.raw[self.index:self.index+n];self.index+=n
        if len(value)!=n:raise ValueError('Truncated native MTR record')
        return value
    def number(self,fmt):return struct.unpack(fmt,self.take(struct.calcsize(fmt)))[0]
    def read(self):
        code=self.number('>B')
        if code<0x80:return code
        if code>=0xe0:return code-256
        if 0xa0<=code<0xc0:return self.take(code&31).decode('utf8')
        if 0x90<=code<0xa0:return [self.read()for _ in range(code&15)]
        if 0x80<=code<0x90:return {self.read():self.read()for _ in range(code&15)}
        if code==0xc0:return None
        if code in (0xc2,0xc3):return code==0xc3
        formats={0xcc:'>B',0xcd:'>H',0xce:'>I',0xcf:'>Q',0xd0:'>b',0xd1:'>h',0xd2:'>i',0xd3:'>q',0xca:'>f',0xcb:'>d'}
        if code in formats:return self.number(formats[code])
        if code in (0xd9,0xda,0xdb):return self.take(self.number({0xd9:'>B',0xda:'>H',0xdb:'>I'}[code])).decode('utf8')
        if code in (0xc4,0xc5,0xc6):return {'$binary':self.take(self.number({0xc4:'>B',0xc5:'>H',0xc6:'>I'}[code])).hex()}
        if code in (0xdc,0xdd):return [self.read()for _ in range(self.number('>H'if code==0xdc else'>I'))]
        if code in (0xde,0xdf):return {self.read():self.read()for _ in range(self.number('>H'if code==0xde else'>I'))}
        if code in (0xc7,0xc8,0xc9,0xd4,0xd5,0xd6,0xd7,0xd8):
            size=self.number({0xc7:'>B',0xc8:'>H',0xc9:'>I'}[code])if code<0xd4 else{0xd4:1,0xd5:2,0xd6:4,0xd7:8,0xd8:16}[code]
            return {'$extension_type':self.number('>b'),'$extension_bytes':self.take(size).hex()}
        raise ValueError('Unsupported MessagePack code '+hex(code))

def digest(raw):return hashlib.sha256(raw).hexdigest()
def uid(value):return int(value)&0xffffffffffffffff
def hexid(value):return f'{uid(value):016X}'
def record(raw):
    decoder=Reader(raw);data=decoder.read()
    if not isinstance(data,dict):raise ValueError('Native MTR root map missing')
    return dict(sha256=digest(raw),bytes=len(raw),data=data,effective_bytes=decoder.index,
                opaque_tail_bytes=len(raw)-decoder.index,opaque_tail_sha256=digest(raw[decoder.index:]))
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n','utf8')
def baseline():
    result={}
    with zipfile.ZipFile(ARCHIVE)as archive:
        for name in archive.namelist():
            if name.startswith(PREFIX+'mtr/'):
                relative=name[len(PREFIX):];result[relative]=record(archive.read(name))
    return result
def geo_kind(name):
    return name.split('/')[3]if name.startswith('mtr/projectseele/geofront/')else'other_dimension'
def rail_id(name):return name.rsplit('/',1)[-1]
def rail_position_id(data):
    # Native Rail.getHexId uses Position.compareTo (X, Y, Z), even when the
    # serialized geometry keeps its original directed endpoint order.
    points=sorted(tuple(data[p][axis]for axis in ('x','y','z'))for p in ('position1','position2'))
    return '-'.join(hexid(value)for point in points for value in point)
def differences(before,after,path=''):
    if type(before)!=type(after):return [dict(field=path,before=before,after=after)]
    if isinstance(before,dict):
        output=[]
        for key in before.keys()|after.keys():
            pointer=path+'/'+str(key)
            if key not in before:output.append(dict(field=pointer,added=after[key]))
            elif key not in after:output.append(dict(field=pointer,removed=before[key]))
            else:output.extend(differences(before[key],after[key],pointer))
        return output
    if isinstance(before,list):
        if len(before)!=len(after):return [dict(field=path,before=before,after=after)]
        return [row for i,(a,b)in enumerate(zip(before,after))for row in differences(a,b,path+'/'+str(i))]
    return []if before==after else[dict(field=path,before=before,after=after)]
def vehicles(records):
    result={};errors=[]
    for name,r in records.items():
        if geo_kind(name)!='sidings':continue
        for value in r['data'].get('vehicles',[]):
            key=hexid(value['id'])
            if key in result:errors.append('Duplicate original vehicle identity '+key)
            result[key]=dict(siding_id=hexid(r['data']['id']),member=name,data=value)
    return result,errors
def manifest(original):
    rows=lambda group:[dict(member=n,**r)for n,r in original.items()if geo_kind(n)==group]
    station=[r for r in rows('stations')if uid(r['data']['id'])==HQ];assert len(station)==1
    other_stations=[r for r in rows('stations')if uid(r['data']['id'])!=HQ]
    other_platforms=[r for r in rows('platforms')if uid(r['data']['id'])not in PLATFORMS]
    fleet,errors=vehicles(original);assert not errors
    assert(len(other_stations),len(other_platforms),len(fleet),len(rows('routes')),len(rows('rails')))==(19,35,40,6,171)
    return dict(schema='projectseele.r52.hq-mtr-protection.v1',original_archive=str(ARCHIVE),
        headquarters_station_id=HQ,headquarters_station_hex=hexid(HQ),mutable_HQ_position_fields=['position1','position2'],
        HQ_platform_ids=[hexid(v)for v in sorted(PLATFORMS)],protected_stations=other_stations,
        protected_platforms=other_platforms,protected_vehicles=fleet,protected_all_routes=rows('routes'),
        original_rail_ids=[rail_id(r['member'])for r in rows('rails')],complete_original_records=original,
        explicit_rail_mapping_never_automatically_accepted=True,world_written=False)
def approval(path,original):
    if path is None:return set(),{}
    value=json.loads(path.read_text('utf8'));assert value.get('schema')=='projectseele.r52.hq-rail-review.v1'
    ids={str(v).upper()for v in value.get('approved_original_rail_ids',[])}
    known={rail_id(n)for n in original if geo_kind(n)=='rails'}
    assert ids<=known,'Unknown original rail ID in explicit Root list'
    mappings={str(old).upper():[str(v).upper()for v in new]for old,new in value.get('rail_replacements',{}).items()}
    assert set(mappings)<=ids and all(v for v in mappings.values()),'Replacement needs an explicitly listed original rail'
    return ids,mappings
def audit(world,original,approved,mappings):
    assert world.resolve()==WORLD.resolve(),'Only the explicit fresh Root WORLD_R52 source is an audit input'
    folder=world/'mtr';assert folder.is_dir()and not folder.is_symlink()
    current={};errors=[]
    for path in folder.rglob('*'):
        if not path.is_file():continue
        assert not path.is_symlink(),'MTR member may not be linked'
        name=path.relative_to(world).as_posix()
        try:
            first=path.stat();raw=path.read_bytes();last=path.stat()
            if(first.st_size,first.st_mtime_ns)!=(last.st_size,last.st_mtime_ns):raise ValueError('MTR source changed during read')
            current[name]=record(raw)
        except Exception as error:errors.append(dict(member=name,error=str(error)))
    issues=list(errors);review=[];protected_checks=0
    mutable_prefix={'stations':{HQ},'platforms':PLATFORMS}
    for name,before in original.items():
        group=geo_kind(name);after=current.get(name)
        if group=='rails'and rail_id(name)in approved:
            targets=mappings.get(rail_id(name),[rail_id(name)])
            matching=[dict(member=n,**r)for n,r in current.items()if geo_kind(n)=='rails'and rail_id(n)in targets]
            unchanged=after is not None and after['sha256']==before['sha256']and targets==[rail_id(name)]
            if not unchanged:
                row=dict(original_member=name,original=before,replacement_ids=targets,current_records=matching,
                         original_record_still_present=after is not None,pending_Root_review=True,automatically_accepted=False)
                for target in matching:
                    if rail_id(target['member'])!=rail_position_id(target['data']):issues.append(dict(member=target['member'],reason='Rail file ID differs from actual native endpoints'))
                    a={k:v for k,v in before['data'].items()if k not in GEOMETRY};b={k:v for k,v in target['data'].items()if k not in GEOMETRY}
                    invariant=differences(a,b)
                    if invariant:issues.append(dict(member=target['member'],reason='Approved geometry changed rail operating/unknown fields',fields=invariant))
                if len(matching)!=len(set(targets)):issues.append(dict(member=name,reason='Explicit replacement target missing/duplicated'))
                review.append(row)
            continue
        if group in mutable_prefix and uid(before['data']['id'])in mutable_prefix[group]:
            if after is None:issues.append(dict(member=name,reason='Original HQ station/platform ID removed'));continue
            before_fields={k:v for k,v in before['data'].items()if k not in ('position1','position2')}
            after_fields={k:v for k,v in after['data'].items()if k not in ('position1','position2')}
            changed=differences(before_fields,after_fields)
            if changed or before['opaque_tail_sha256']!=after['opaque_tail_sha256']:
                issues.append(dict(member=name,reason='HQ identity/operating/unknown field changed',fields=changed))
            coords=differences(before['data'],after['data'])
            if coords:review.append(dict(member=name,fields=coords,pending_Root_review=True,automatically_accepted=False))
            continue
        protected_checks+=1
        if after is None:issues.append(dict(member=name,reason='Protected original record missing'))
        elif after['sha256']!=before['sha256']:
            issues.append(dict(member=name,reason='Protected full original bytes changed',fields=differences(before['data'],after['data']),
                               opaque_tail_changed=before['opaque_tail_sha256']!=after['opaque_tail_sha256']))
    replacement_ids={v for values in mappings.values()for v in values}
    for name,row in current.items():
        if name not in original:
            if geo_kind(name)=='rails'and rail_id(name)in replacement_ids:
                if rail_id(name)!=rail_position_id(row['data']):issues.append(dict(member=name,reason='Rail file ID differs from actual native endpoints'))
            else:issues.append(dict(member=name,reason='Unapproved new MTR record'))
    for group,expected in [('stations',20),('platforms',38),('routes',6),('sidings',6),('depots',6)]:
        count=sum(geo_kind(n)==group for n in current)
        if count!=expected:issues.append(dict(group=group,reason='Original complete identity inventory count changed',expected=expected,actual=count))
    before_fleet,_=vehicles(original);after_fleet,duplicates=vehicles(current);issues.extend(dict(reason=s)for s in duplicates)
    for identifier,before in before_fleet.items():
        after=after_fleet.get(identifier)
        if after is None:issues.append(dict(vehicle=identifier,reason='Original vehicle missing'))
        elif before!=after:issues.append(dict(vehicle=identifier,reason='Full original identity/progress/unknown vehicle fields changed',fields=differences(before,after)))
    if set(after_fleet)!=set(before_fleet):issues.append(dict(reason='Original40 vehicle identity set changed'))
    return dict(schema='projectseele.r52.hq-mtr-protection-readback.v1',source_world=str(world.resolve()),
        baseline_archive=str(ARCHIVE),headquarters_station_id=HQ,protected_complete_record_checks=protected_checks,
        original_vehicle_count=40,current_vehicle_count=len(after_fleet),approved_original_rail_ids=sorted(approved),
        explicit_rail_replacements=mappings,protected_integrity_pass=not issues,issues=issues,
        station_and_rail_changes_require_Root_review=review,construction_automatically_accepted=False,
        status='PROTECTED_DIFFERENCE'if issues else'ROOT_REVIEW_REQUIRED'if review else'BASELINE_UNCHANGED',
        world_written=False,simulator_started=False,terrain_scanned=False)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--prepare',action='store_true');ap.add_argument('--world',type=Path,default=WORLD)
    ap.add_argument('--approved-rails',type=Path);ap.add_argument('--out',type=Path,default=OUT/'MTR_PROTECTION_READBACK.json');args=ap.parse_args()
    assert args.out.resolve().is_relative_to(ROOT.resolve()),'Diagnostic JSON must stay in the code worktree, never a world'
    original=baseline()
    if args.prepare:write(OUT/'HQ_PROTECTION_MANIFEST.json',manifest(original));print('Prepared original MTR protection manifest; world not read');return
    approved,mappings=approval(args.approved_rails,original);report=audit(args.world,original,approved,mappings);write(args.out,report)
    print(json.dumps(dict(status=report['status'],protected_integrity_pass=report['protected_integrity_pass'],issues=len(report['issues']),
        Root_review_items=len(report['station_and_rail_changes_require_Root_review']),report=str(args.out),world_written=False)))
    raise SystemExit(1 if report['issues']else 0)
if __name__=='__main__':main()
