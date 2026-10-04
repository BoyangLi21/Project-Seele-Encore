"""Ground-floor use and coherent book displays in original owned office bays.

No world I/O. Existing households/upper floors/actors/storage/stairs are kept.
The caller supplies an exact current-state/full-NBT writer and whole-object
protection veto; non-template workstations are rejected intact.
"""

BOOKSHELF='minecraft:bookshelf'


def source_owned_sign_text(current,reference):
    if current is None or reference is None:return False
    import copy
    actual=copy.deepcopy(current);actual.pop('keepPacked',None)
    return actual==reference


def create_owned_envelopes(topology):
    result=[]
    for row in topology['records']:
        s=row['source'];cx,cy,cz=s.get('source_center',s.get('center'));half=s['half'];height=s['height'];low=s.get('retracted_base_y',19-height)
        result.append(([cx-half-5,low-2,cz-half-5],[cx+half+5,cy+height+4,cz+half+5]))
    return result


def intersects_create(points,envelopes):
    return any(all(lo[k]<=p[k]<=hi[k] for k in range(3)) for p in points for lo,hi in envelopes)


def resolve_ground_floor_use(identity,label,style):
    if style=='residential':return 'residential_lobby','住宅入口'
    if style=='office' and identity=='residential_lobby':return 'local_office','办公楼入口'
    return identity,label


def author_bookshop_displays(building,state,put,protected=lambda positions:False):
    if building.get('style')!='office':return dict(complete_displays=[],held=[],scope='Existing office-style bookstore ground floor only')
    (x,y,z),(X,Y,Z)=building['planned_bounds'];feet=building['planned_floor_feet'][0];made=[];held=[]
    for xx in range(x+11,X-2,6):
        for zz in range(z+5,Z-3,7):
            ident=building['id']+f'/ground_book_display/{xx}/{zz}'
            positions=[(xx,feet,zz),(xx+1,feet,zz),(xx+2,feet,zz),(xx+1,feet+1,zz)]
            expected=['minecraft:smooth_quartz']*3+['minecraft:black_stained_glass'];actual=[state(p) for p in positions]
            if all(s==BOOKSHELF for s in actual):made.append(dict(id=ident,positions=positions,status='EXISTING_COMPLETE_DISPLAY_KEPT'));continue
            if actual!=expected or protected(positions):
                held.append(dict(id=ident,positions=positions,actual=actual,reason='Complete human/non-template/BE/Create protected workstation preserved'));continue
            for p in positions:put(p,BOOKSHELF,ident,'Ground-floor bookshop display replaces one complete obsolete office quartz/monitor component; same exact full-block collision, original chair/storage/stairs/upper floors preserved')
            made.append(dict(id=ident,positions=positions,status='COMPLETE_DISPLAY_CANDIDATE',original_states=actual,
                existing_reading_seat_position=[xx+1,feet,zz+1],new_actor_or_inventory_created=False))
    return dict(complete_displays=made,held=held,ground_floor_only=True,upper_floor_edits=0,actual_trade_or_reading_UI_claimed=False)
