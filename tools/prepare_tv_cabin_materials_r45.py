"""Original full-cube cabin material assets/exact after-images; no apply/JVM."""
from pathlib import Path
import copy,difflib,gzip,json,sys
sys.dont_write_bytecode=True
from PIL import Image,ImageDraw
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities
ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r45'
WORLD=ART/'composition_candidates/R45_source_candidate_20261004_tv_finish_v13_01/world'
OUT=ART/'lifts_doors_lifecycle_sol_v2/tv_door_lift_construction_v1/cabin_material_install_v1'
NAMES=['tv_staff_lift_panel_r45','tv_staff_lift_band_r45','tv_utility_lift_ceiling_r45']
def read(p):return json.loads(p.read_text('utf8'))
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode())
def main():
    assert not OUT.exists();OUT.mkdir();res=OUT/'resource_overlay';tex=res/'assets/projectseele/textures/block';tex.mkdir(parents=True)
    for name in NAMES[:2]:
        im=Image.new('RGB',(256,256),'#c5cbb7');d=ImageDraw.Draw(im);d.line((1,0,1,255),fill='#939f91',width=2);d.line((254,0,254,255),fill='#e0e3d2',width=2)
        if 'band'in name:d.rectangle((0,188,255,242),fill='#786479');d.line((0,242,255,242),fill='#514858',width=2)
        im.save(tex/(name+'.png'))
    im=Image.new('RGB',(512,512),'#293c38');d=ImageDraw.Draw(im)
    for x in range(0,512,128):
        for y in range(0,512,128):d.rectangle((x+7,y+7,x+120,y+120),fill='#18262b');d.line((x+7,y+7,x+120,y+7),fill='#586a68',width=3);d.line((x+7,y+7,x+7,y+120),fill='#475c58',width=3)
    im.save(tex/(NAMES[2]+'.png'))
    for name in NAMES:
        write(res/f'assets/projectseele/blockstates/{name}.json',{'variants':{'':{'model':'projectseele:block/'+name}}})
        model={'parent':'minecraft:block/cube_all','textures':{'all':'projectseele:block/'+name}}
        if name==NAMES[2]:model={'parent':'minecraft:block/cube','textures':{'particle':'projectseele:block/nerv_machine_edge','down':'projectseele:block/'+name,**{k:'projectseele:block/nerv_machine_edge'for k in ['up','north','south','east','west']}}}
        write(res/f'assets/projectseele/models/block/{name}.json',model);write(res/f'assets/projectseele/models/item/{name}.json',{'parent':'projectseele:block/'+name})
        write(res/f'data/projectseele/loot_tables/blocks/{name}.json',{'type':'minecraft:block','pools':[{'rolls':1,'conditions':[{'condition':'minecraft:survives_explosion'}],'entries':[{'type':'minecraft:item','name':'projectseele:'+name}]}]})
    write(OUT/'lang.additions.zh_cn.json',dict(zip(['block.projectseele.'+n for n in NAMES],['TV人员电梯浅绿壁板','TV人员电梯薄紫腰线壁板','TV勤务电梯顶棚格栅'])))
    write(OUT/'lang.additions.en_us.json',dict(zip(['block.projectseele.'+n for n in NAMES],['TV Staff Lift Wall Panel','TV Staff Lift Purple Datum Panel','TV Utility Lift Ceiling Grille'])))
    cars=read(ART/'tv_lifts_doors_sol_followup/all7_current_car_presence.json');styles=read(WORLD/'.projectseele_tv_lifts_r45.json')['styles'];schemas=read(ART/'tv_lifts_doors_sol_followup/shells_v1/all7_cabin_types.json');byid={r['id']:r for r in schemas};m=MeasuredWorld(WORLD)
    for c in cars:m.around(c['candidate_cars'][0]['centre'],c['radius']+3)
    m.load();tags=dict(iter_block_entities(WORLD,'projectseele:geofront',(-390,-590,-300),(170,110,785),selected_chunks=set(m.selected)));rows=[];protected=[];components=[]
    for car in cars:
        schema=byid[car['lift']];uid=schema['runtime_id'];staff=styles[uid].startswith('tv22');centre=car['candidate_cars'][0]['centre'];x,y,z=centre;r=car['radius'];h=car['height'];roof=y+h-2;doors={tuple(q)for q in schema['original_car_door_cells']};count=0
        for X in range(x-r,x+r+1):
            for Z in range(z-r,z+r+1):
                for Y in range(y,roof+1):
                    q=X,Y,Z;isroof=Y==roof
                    if not isroof and(not staff or(abs(X-x)!=r and abs(Z-z)!=r)or q in doors):continue
                    before=m.block(q);assert before is not None
                    if q in tags or before.partition('[')[0].endswith('_button')or before.startswith('movingelevators:'):
                        protected.append({'pos':list(q),'state':before,'full_nbt':tags[q].snbt()if q in tags else None});continue
                    assert before not in ['minecraft:air','minecraft:barrier'],'Never fill absent car/owned door'
                    after='projectseele:'+NAMES[0 if staff else 2]if isroof else'projectseele:'+NAMES[1 if Y-y==1 else 0]
                    rows.append(dict(pos=list(q),before=before,after=after,before_nbt=None,after_nbt=None,owner='tv_lift_material/'+uid,reason='Dedicated original full-cube skin; all original floor/roof height, doors and devices retained'));count+=1
        components.append(dict(runtime_id=uid,style=styles[uid],actual_car=centre,size=[r*2+1,h,r*2+1],rows=count,band_world_height=[y+1.0546875,y+1.265625]if staff else None,root_geometry_pending='Utility four small red luminaires within original ceiling face only; no headroom loss'))
    assert len(rows)==len({tuple(r['pos'])for r in rows})
    for name,inverse in [('forward',False),('inverse',True)]:
        with gzip.open(OUT/(name+'.jsonl.gz'),'wt',encoding='utf8')as f:
            for r in sorted(rows,key=lambda v:v['pos']):
                q=copy.deepcopy(r)
                if inverse:q['before'],q['after']=r['after'],r['before']
                f.write(json.dumps(q,ensure_ascii=False,separators=(',',':'))+'\n')
    write(OUT/'all7_current_style_full_material_components.json',components);write(OUT/'protected_actual_BEs_and_inputs.json',protected)
    patch=[]
    for path in [ROOT/'src/main/java/com/projectseele/registry/ModBlocks.java',ROOT/'src/main/java/com/projectseele/registry/ModItems.java',ROOT/'src/main/java/com/projectseele/world/TvLiftFinishR45.java',ROOT/'src/main/java/com/projectseele/world/S20MovingElevatorsAdapter.java']:
        before=path.read_text('utf8');after=before
        if path.stem=='ModBlocks':
            k=after.index('    public static final RegistryObject<Block> NERV_WALL_PANEL=');after=after[:k]+''.join(f'    public static final RegistryObject<Block> {n.upper()}=finish("{n}",Blocks.IRON_BLOCK,0);\n'for n in NAMES)+after[k:]
        elif path.stem=='ModItems':
            k=after.index('    public static final RegistryObject<Item> NERV_WALL_PANEL=');after=after[:k]+''.join(f'    public static final RegistryObject<Item> {n.upper()}=ITEMS.register("{n}",()->new BlockItem(ModBlocks.{n.upper()}.get(),new Item.Properties()));\n'for n in NAMES)+after[k:]
        elif path.stem=='TvLiftFinishR45':
            a='''        if(style.startsWith("tv22"))return heightAboveFeet==1
                ?Blocks.PURPLE_TERRACOTTA.defaultBlockState():ModBlocks.NERV_WALL_PANEL.get().defaultBlockState();'''
            b='''        if(style.startsWith("tv22"))return heightAboveFeet==1
                ?ModBlocks.TV_STAFF_LIFT_BAND_R45.get().defaultBlockState():ModBlocks.TV_STAFF_LIFT_PANEL_R45.get().defaultBlockState();''';assert after.count(a)==1;after=after.replace(a,b)
            a='    /** A single interior hole is distinct from an absent/misidentified platform. */';assert after.count(a)==1
            after=after.replace(a,'''    public static BlockState cabinRoof(ServerLevel level,S20PhysicalElevatorDirector.LiftSpec spec,BlockState original)
    {
        String style=styles(level).get(spec.id());if(style==null)return original;
        return (style.startsWith("tv22")?ModBlocks.TV_STAFF_LIFT_PANEL_R45.get():ModBlocks.TV_UTILITY_LIFT_CEILING_R45.get()).defaultBlockState();
    }

'''+a)
        else:
            a='''                    else if (dy == group.getCageSizeY() - 1)
                    {
                        state = Blocks.SMOOTH_QUARTZ.defaultBlockState();
                    }''';assert after.count(a)==1
            after=after.replace(a,'''                    else if (dy == group.getCageSizeY() - 1)
                    {
                        state = TvLiftFinishR45.cabinRoof(level,spec,Blocks.SMOOTH_QUARTZ.defaultBlockState());
                    }''')
        (OUT/(path.stem+'.before.txt')).write_bytes(path.read_bytes());(OUT/(path.stem+'.candidate.txt')).write_bytes(after.encode());rel=path.relative_to(ROOT).as_posix();patch.extend(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/'+rel,tofile='b/'+rel))
    (OUT/'root_register_materials_and_recurrence_producer.patch').write_bytes(''.join(patch).encode())
    write(OUT/'FROZEN.json',dict(actual_source_v13=str(WORLD),rows=len(rows),registered_full_cube_materials=NAMES,vanilla_cube_models_reused_no_custom_3D_geometry=True,all_floor_door_control_and_BE_preserved=True,Source_java_resource_or_world_written=False,registration_compile_install_native_shapes_visual_pending=True,public_or_operator_nav_install_mixed=False,all7_components=len(components),no_global_existing_material_override=True,official_pixels_or_audio_used=False))
    print(json.dumps(dict(directory=str(OUT),rows=len(rows),world_or_Java_or_root_resources_written=False),ensure_ascii=False))
if __name__=='__main__':main()
