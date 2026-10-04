"""Finite existing clinic examination/wash bay, preserving its doctor PC.

Uses a complete measured old workstation, real native bed constructor records,
and caller-owned exact state/NBT writer. No world I/O or clinical game rules.
"""
import copy
import nbtlib

FOOT='minecraft:white_bed[facing=south,occupied=false,part=foot]'
HEAD='minecraft:white_bed[facing=south,occupied=false,part=head]'
SINK='minecraft:water_cauldron[level=3]'


def captured_bed_defaults(records):
    result={}
    for row in records:
        if row.get('after') not in (FOOT,HEAD) or not row.get('after_full_nbt'):continue
        tag=nbtlib.parse_nbt(row['after_full_nbt'])
        if str(tag.get('id',''))!='minecraft:bed' or set(tag)-{'id','x','y','z','keepPacked'}:continue
        result.setdefault(row['after'],tag)
    return result


def author_clinic_exam_bay(building,state,put,bed_defaults,protected=lambda positions:False):
    if building.get('style')!='office' or building['id'].startswith('airport/'):
        return dict(status='NOT_ORDINARY_CLINIC',changes=[],treatment_system_claimed=False)
    (x,y,z),(X,Y,Z)=building['planned_bounds'];feet=building['planned_floor_feet'][0];xx,zz=x+11,z+5
    check=[(xx,feet,zz),(xx+1,feet,zz),(xx+2,feet,zz),(xx+1,feet+1,zz),(xx,feet,zz+1),
           (xx,feet+1,zz),(xx,feet+1,zz+1),(xx,feet-1,zz),(xx,feet-1,zz+1)]
    expected=['minecraft:smooth_quartz']*3+['minecraft:black_stained_glass','minecraft:air','minecraft:air','minecraft:air','minecraft:smooth_stone','minecraft:smooth_stone']
    actual=[state(p) for p in check]
    if actual!=expected or protected(check):
        return dict(status='HOLD_WHOLE_HUMAN_BE_CREATE_OR_NON_TEMPLATE_BAY',positions=check,actual=actual,treatment_system_claimed=False)
    if FOOT not in bed_defaults or HEAD not in bed_defaults:
        return dict(status='NATIVE_COMPLETE_BED_DEFAULTS_REQUIRED',positions=check,changes=[],treatment_system_claimed=False)
    changes=[];owner=building['id']+'/actual_exam_wash_bay'
    for pos,after in [((xx,feet,zz),FOOT),((xx,feet,zz+1),HEAD),((xx+2,feet,zz),SINK)]:
        tag=None
        if after in (FOOT,HEAD):
            tag=copy.deepcopy(bed_defaults[after]);tag['x'],tag['y'],tag['z']=[nbtlib.Int(v) for v in pos]
            tag=tag.snbt()
        put(pos,after,owner,'Finite existing clinic ground-floor examination bed/washing bay; real1993 clinic adjacency, doctor PC/counter/chair and original storage kept; no treatment/medication/NPC changes',tag)
        changes.append(dict(pos=pos,state=after,complete_new_bed_nbt=tag))
    return dict(status='COMPLETE_EXAM_WASH_BAY_CANDIDATE',changes=changes,doctor_pc_and_counter=[xx+1,feet+1,zz],
        preserved_existing_doctor_seat=[xx+1,feet,zz+1],legal_bedside_point=[xx-.5,feet,zz+1.5],
        sleep_or_treatment_or_interaction_verified=False,treatment_system_claimed=False,upper_floor_changes=0,new_items=0,new_actors=0,
        reference='1993-08 own clinic plan/photographs by Nomura; https://www.asahi-net.or.jp/~mf4n-nmr/MyDesign.html',
        layout_and_cauldron_are_original_voxel_adaptation=True,closed_private_treatment_room_claimed=False)
