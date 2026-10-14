"""Typed, explicit component transforms; unknown coordinate fields are not guessed."""
import copy
import nbtlib
from regional_voxels import canonical_state

OPPOSITE = {'north':'south','south':'north','east':'west','west':'east'}
RAIL_TURNS = {'ascending_north':'ascending_south','ascending_south':'ascending_north',
              'ascending_east':'ascending_west','ascending_west':'ascending_east',
              'north_east':'south_west','south_west':'north_east',
              'north_west':'south_east','south_east':'north_west'}


def state_in_frame(state,frame):
    if frame.turn == 0 or '[' not in state:
        return state
    assert frame.turn in (90,180,270)
    turns=frame.turn//90
    directions=['north','east','south','west']
    rotate=lambda v:directions[(directions.index(v)+turns)%4] if v in directions else v
    name, rest = state.split('[',1)
    props = dict(p.split('=',1) for p in rest[:-1].split(','))
    result = {}
    for key,value in props.items():
        target_key = rotate(key)
        if key == 'facing':
            value = rotate(value)
        elif key == 'rotation':
            value = str((int(value)+4*turns)%16)
        elif key == 'shape':
            if turns==2:value=RAIL_TURNS.get(value,value)
            elif value in ('east_west','north_south'):value={'east_west':'north_south','north_south':'east_west'}[value]
            elif value.startswith('ascending_'):value='ascending_'+rotate(value[len('ascending_'):])
            elif value in ('north_east','north_west','south_east','south_west'):
                pair={rotate(v) for v in value.split('_')}
                value=next(v for v in ('north_east','north_west','south_east','south_west') if set(v.split('_'))==pair)
        elif key=='axis' and value in ('x','z') and turns%2:value='z' if value=='x' else 'x'
        result[target_key] = value
    return canonical_state(name+'['+','.join(k+'='+v for k,v in result.items())+']')


def unpack_position(value):
    value = int(value) & ((1 << 64)-1)
    x,y,z = value>>38,value&4095,(value>>12)&((1 << 26)-1)
    return (x-(1 << 26) if x >= 1 << 25 else x,
            y-4096 if y >= 2048 else y,
            z-(1 << 26) if z >= 1 << 25 else z)


def pack_position(point):
    x,y,z = map(int,point)
    assert -(1 << 25)<=x<1 << 25 and -2048<=y<2048 and -(1 << 25)<=z<1 << 25
    value = ((x&((1 << 26)-1))<<38)|((z&((1 << 26)-1))<<12)|(y&4095)
    return nbtlib.Long(value if value < 1 << 63 else value-(1 << 64))


def block_entity_in_frame(before,frame,*,reference_positions=None):
    result = copy.deepcopy(before)
    for key,value in zip(('x','y','z'),frame.block(tuple(int(before[k]) for k in ('x','y','z')))):
        result[key] = type(before[key])(value)
    if str(before['id']) == 'projectseele:wall_artwork':
        result['Backing'] = pack_position(frame.block(unpack_position(before['Backing'])))
        if frame.turn:
            result['Facing'] = type(before['Facing'])((int(before['Facing'])+frame.turn//90)%4)
            x,z=float(before['OffsetX']),float(before['OffsetZ'])
            for _ in range(frame.turn//90):x,z=1-z,x
            result['OffsetX']=type(before['OffsetX'])(x);result['OffsetZ']=type(before['OffsetZ'])(z)
    if str(before['id']) == 'projectseele:nerv_access_reader':
        for key in ('Gate','Exit'):
            if key in before and int(before[key]) != 0:
                result[key] = pack_position(frame.block(unpack_position(before[key])))
    if str(before['id']) == 'projectseele:station_departure_board':
        if 'PlatformCentre' in before and int(before['PlatformCentre']) != 0:
            if reference_positions is None:
                raise ValueError('Explicit platform reference mapping required for native departure board')
            old = unpack_position(before['PlatformCentre'])
            if old not in reference_positions:
                raise ValueError(('Unmapped platform reference',old))
            result['PlatformCentre'] = pack_position(reference_positions[old])
    data = result.get('data')
    if str(before['id']).startswith('movingelevators:') and data is not None:
        if frame.turn and 'facing' in data:
            # Native remote buttons store Direction.get3DDataValue(), while
            # controller blocks and controllerFacing store the 2D value.
            value=int(data['facing'])
            if str(before['id'])=='movingelevators:button_tile':
                for _ in range(frame.turn//90):value={0:0,1:1,2:5,5:3,3:4,4:2}[value]
            else:
                value=(value+frame.turn//90)%4
            data['facing'] = type(data['facing'])(value)
        if 'controllerX' in data:
            old = tuple(int(data[k]) for k in ('controllerX','controllerY','controllerZ'))
            if reference_positions is None or old not in reference_positions:
                raise ValueError(('Explicit controller reference mapping required',old))
            for key,value in zip(('controllerX','controllerY','controllerZ'),reference_positions[old]):
                data[key] = type(data[key])(value)
            if frame.turn and 'controllerFacing' in data:
                data['controllerFacing'] = type(data['controllerFacing'])((int(data['controllerFacing'])+frame.turn//90)%4)
    return result


def actor_in_frame(before,frame):
    assert frame.turn in (0,180),'Actor migration only has the verified original component frames'
    result = copy.deepcopy(before)
    result['Pos'] = type(before['Pos'])([type(v)(p) for v,p in zip(before['Pos'],frame.point(tuple(map(float,before['Pos']))))])
    if frame.turn:
        result['Rotation'][0] = type(before['Rotation'][0])((float(before['Rotation'][0])+frame.turn+180)%360-180)
        if 'SeeleNervLogisticsYaw' in before:
            result['SeeleNervLogisticsYaw']=type(before['SeeleNervLogisticsYaw'])((float(before['SeeleNervLogisticsYaw'])+frame.turn+180)%360-180)
        if str(before['id'])=='projectseele:entry_plug_carrier' and bool(before.get('CanonicalPose',0)):
            # PoseQ is a world orientation; locked socket-to-plug Q is local
            # and must remain unchanged. Premultiply by the rigid Y half-turn.
            qx,qy,qz,qw=(float(before['PoseQ'+k]) for k in ('X','Y','Z','W'))
            for key,value in zip(('X','Y','Z','W'),(qz,qw,-qx,-qy)):
                result['PoseQ'+key]=type(before['PoseQ'+key])(value)
        if 'Motion' in result:
            for axis in (0,2):
                result['Motion'][axis] = type(before['Motion'][axis])(-float(before['Motion'][axis]))
    if str(before['id']) == 'projectseele:nerv_staff':
        result['StaffStation'] = pack_position(frame.block(unpack_position(before['StaffStation'])))
        if frame.turn:
            result['StaffStationYaw'] = type(before['StaffStationYaw'])((float(before['StaffStationYaw'])+frame.turn+180)%360-180)
    # Passengers use absolute saved positions too, while retaining their
    # original relation, UUID, inventory and all unrecognized typed state.
    if 'Passengers' in before:
        result['Passengers'] = type(before['Passengers'])([actor_in_frame(child,frame) for child in before['Passengers']])
    return result
