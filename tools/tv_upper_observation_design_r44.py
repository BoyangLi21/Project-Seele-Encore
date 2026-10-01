"""Shared commissioned upper-gallery geometry; no reader, writer or world inference."""
FRONT_X=(-33,93);OLD_FACE=-275;NEW_FACE=-267;FEET=-367
FLOOR='projectseele:nerv_floor_panel';STRUCT='projectseele:nerv_structural_panel'
GLASS='projectseele:clear_glass';LIGHT='projectseele:nerv_strip_light'
STEP='minecraft:polished_blackstone_slab[type=bottom,waterlogged=false]'


def lift_negative(q):
    return -33<=q[0]<=-25 and -376<=q[1]<=-360 and -284<=q[2]<=-274


def members():
    for x in range(FRONT_X[0],FRONT_X[1]+1):
        for y in range(-367,-362):yield (x,y,OLD_FACE),'minecraft:air','retire_complete_old_front_glazing'
    for x in range(FRONT_X[0],FRONT_X[1]+1):
        for z in range(OLD_FACE+1,NEW_FACE+1):
            yield (x,-369,z),GLASS if z==NEW_FACE else STRUCT,'continuous_deck_foundation_on_original_beam'
            yield (x,-368,z),GLASS if z==NEW_FACE else FLOOR,'complete_original_level_front_observation_floor'
            for y in range(-367,-362):
                boundary=x in FRONT_X or z==NEW_FACE
                after=(STRUCT if x in FRONT_X else GLASS) if boundary else 'minecraft:air'
                if z==NEW_FACE-1 and x not in FRONT_X and y==-367:after=STEP
                yield (x,y,z),after,'whole_extended_pressure_glazing' if boundary else ('continuous_half_metre_raised_window_view_stand' if after==STEP else 'whole_declared_new_public_headroom')
            yield (x,-362,z),LIGHT if (x+24)%12==0 and z in (-273,-270) else STRUCT,'attached_complete_observer_ceiling_and_strip_lights'


def author_source(scene,block_entities):
    """Called after the copied R20 programme, before its final exact delta."""
    allowed={'minecraft:air','minecraft:void_air','minecraft:cave_air',FLOOR,STRUCT,GLASS,LIGHT,STEP,
        'projectseele:nerv_wall_panel','projectseele:nerv_machine_edge','projectseele:nerv_shaft_panel','minecraft:light_gray_stained_glass'}
    for q,state,purpose in members():
        index=scene.index((*q,*q));before=scene.palette[int(scene.after[index].reshape(-1)[0])]
        if lift_negative(q) or q in block_entities or scene.protected[index].any():continue
        if before not in allowed:raise RuntimeError(('Other whole original owner in future upper gallery source',q,before))
        scene.fill((*q,*q),state)
    scene.descriptions.append({'kind':'complete_upper_observer_r44','bounds':[-33,-369,-275,93,-362,-267],
        'original_public_feet_y':FEET,'real_raised_view_stand_feet_y':FEET+.5,'retained_beam_z':-271,
        'authority':'R44 explicitly authorised whole upper gallery; original native r25-west-observation interface and all three copied upper rooms retained'})
