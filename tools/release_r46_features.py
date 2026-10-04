"""R46 production deployment checks on selected final JAR/config bytes; no native execution."""
import hashlib,json,struct
from pathlib import Path

def _calls(data,method,target_class,target_method):
    pos=10;count=struct.unpack_from('>H',data,8)[0];cp={};i=1
    widths={3:4,4:4,5:8,6:8,7:2,8:2,9:4,10:4,11:4,12:4,15:3,16:2,17:4,18:4,19:2,20:2}
    while i<count:
        tag=data[pos];pos+=1
        if tag==1:
            size=struct.unpack_from('>H',data,pos)[0];pos+=2;cp[i]=(tag,data[pos:pos+size].decode('utf8',errors='replace'));pos+=size
        elif tag in (7,8):cp[i]=(tag,struct.unpack_from('>H',data,pos)[0]);pos+=2
        elif tag in (9,10,11,12):cp[i]=(tag,*struct.unpack_from('>HH',data,pos));pos+=4
        elif tag in widths:pos+=widths[tag];i+=int(tag in (5,6))
        else:raise ValueError('Unknown JVM constant tag')
        i+=1
    def utf(index):return cp[index][1]
    targets=[]
    for index,row in cp.items():
        if row[0] not in (10,11):continue
        owner=cp[row[1]];name_type=cp[row[2]]
        if utf(owner[1])==target_class and utf(name_type[1])==target_method:targets.append(index)
    pos+=6;interfaces=struct.unpack_from('>H',data,pos)[0];pos+=2+2*interfaces
    for fields in (True,False):
        members=struct.unpack_from('>H',data,pos)[0];pos+=2
        for _ in range(members):
            _,name,_,attrs=struct.unpack_from('>HHHH',data,pos);pos+=8
            for _ in range(attrs):
                attr,size=struct.unpack_from('>HI',data,pos);pos+=6
                if not fields and utf(name)==method and utf(attr)=='Code':
                    code_size=struct.unpack_from('>I',data,pos+4)[0];code=data[pos+8:pos+8+code_size]
                    if any(bytes([0xb8])+struct.pack('>H',index) in code for index in targets):return True
                pos+=size
    return False

def check_r46_features(archive,runtime_files,recipe_source):
    runtime={r['destination']:r for r in runtime_files}
    config=Path(runtime['config/projectseele-runtime-r45.properties']['source']).read_text('utf8')
    values={line.split('=',1)[0].strip():line.split('=',1)[1].strip() for line in config.splitlines() if '=' in line and not line.lstrip().startswith(('#','!'))}
    if values.get('tv_cage')!='true' or values.get('personnel_platforms')!='true':raise ValueError('R46 production cage/personnel owners must both be enabled')
    for owner,method,cls,name in [
        ('com/projectseele/world/TvCageCollisionR44.class','enabled','com/projectseele/config/PortableRuntimeOwnersR45','tvCage'),
        ('com/projectseele/world/TvPersonnelPlatformInterlockR44.class','enabled','com/projectseele/config/PortableRuntimeOwnersR45','personnelPlatforms'),
        ('com/projectseele/client/render/TvCageEnclosureR44.class','render','com/projectseele/world/TvCageCollisionR44','enabled'),
        ('com/projectseele/client/ClientEvents.class','lambda$onClientSetup$0','com/projectseele/client/LocalPrivateShaderBootstrapR46','installAndSelect')]:
        if not _calls(archive.read(owner),method,cls,name):raise ValueError('R46 final bytecode invocation missing: '+owner+'#'+method+' -> '+cls+'#'+name)
    recipe=json.loads(Path(recipe_source).read_text('utf8'))
    if not recipe['output_filename'].startswith('SEELE_Local_Cavern_R46_') or 'SEELE_INTERIOR_LIGHT=180' not in recipe['settings']:
        raise ValueError('R46 actual personal shader selection / Interior Light180 missing')
    if recipe['input_sha256']!='66061b3c5b4843e31bc9a7562a7ac697a51bb77c73defc7071f996b783efacce':raise ValueError('Unexpected original shader')
    if not {'shaders/block.properties','shaders/lib/lighting/mainLighting.glsl','shaders/lib/materials/specificMaterials/translucents/water.glsl'}<={f['path'] for f in recipe['files']}:
        raise ValueError('R46 LCL/illumination recipe targets missing')
    audio=json.loads(archive.read('assets/projectseele/audio/hangar_pa_reverb_r46.json'))
    sounds=json.loads(archive.read('assets/projectseele/sounds.json'))
    if len(audio)!=18:raise ValueError('Incomplete independent hangar PA')
    for row in audio:
        event=row['name'];raw=archive.read('assets/projectseele/sounds/'+event+'.ogg')
        if hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError('Hangar PA actual asset differs: '+event)
        if sounds[event]['sounds'][0]['name']!='projectseele:'+event or sounds[event]['sounds'][0]['attenuation_distance']!=220:
            raise ValueError('Hangar PA event has no matched positional clip: '+event)
    if not _calls(archive.read('com/projectseele/world/FacilityPaR31.class'),'announce','com/projectseele/world/FacilityPaR31','hangar'):
        raise ValueError('Dedicated room audio routing not called by final production announce')
    return dict(scope='FINAL_PRODUCTION_BYTECODE_AND_SELECTED_PAYLOAD_NOT_NATIVE',
        enabled_paired_facility_owners=True,actual_static_invocation_sites_checked=5,
        personal_shader_first_setup_hook=True,explicit_interior_light=180,independent_PA_assets=18)
