"""Repair measured interfaces from R41's pre-edit negative controls and census."""
from pathlib import Path
import argparse,json,shutil
import regional_voxels as v
from measure_world_r40 import MeasuredWorld,properties
from query_blocks import AIR,iter_block_entities

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/spatial_repair_r41'
WORLD=ROOT/'run/saves/SEELE_FIELD_R41_REVIEW'


def main(apply=False):
    assert json.loads((ART/'negative_controls.json').read_text('utf8'))['passed']
    if not WORLD.exists():
        shutil.copytree(ART/'source_world_backup',WORLD)
        (WORLD/'session.lock').write_bytes(bytes([0xe2,0x98,0x83]))
    v.WORLD=WORLD;v.OUT=ART/'interfaces';p=v.Painter();w=MeasuredWorld(WORLD)
    boxes=[((89,-447,-51),(108,-385,-32)),((83,-396,-273),(89,-387,-266)),
           ((71,-437,303),(76,-386,315)),((-336,-468,722),(-328,-460,730)),
           ((6468,75,-6249),(6475,83,-6242)),((6416,75,-6230),(6425,83,-6225))]
    for lo,hi in boxes:w.box(lo,hi)
    w.load();tags={}
    for lo,hi in boxes:tags.update(iter_block_entities(WORLD,v.DIM,lo,hi))
    changes={};reasons=[]
    def put(q,after,why,allowed):
        before=w.block(q)
        if before==after:return
        assert q not in tags,('Do not remove a block entity',q)
        assert before is not None and before.partition('[')[0] in allowed,(q,before,why)
        changes[q]=(after,why)
    panel={'projectseele:nerv_wall_panel','projectseele:nerv_structural_panel','projectseele:clear_glass','projectseele:nerv_wall_datum'}
    shell=panel|AIR|{'minecraft:polished_deepslate','minecraft:polished_blackstone_bricks'}
    # The existing foyer has a south edge over a retired track-bed depression.
    # Keep its present walking width and close the edge against its two jambs.
    for x in range(93,97):
        for y in range(-442,-437):
            put((x,y,-43),'projectseele:nerv_wall_panel' if y in (-442,-438) else 'projectseele:clear_glass','foyer/continuous_south_guard',AIR)
    for z in range(-41,-33):
        for y in range(-395,-388):put((105,y,z),'minecraft:air','old_moving_walk/retire_attached_wall_with_device',shell)
    # Open the missing half of an existing two-wide doorway, up to its header.
    for y in range(-394,-390):put((86,y,-270),'minecraft:air','hangar/correct_full_width_lane_exit',panel)
    # Four stacked junctions share the same accidental cross-wall geometry.
    for foot in (-434,-420,-406,-392):
        for z in (307,311):
            for x in (73,74):
                for y in range(foot,foot+3):put((x,y,z),'minecraft:air','east_pyramid/open_both_lane_halves_at_junction',panel)
    # These lanes intentionally turn inside the vestibule. Provide a real
    # stationary landing before its retained enclosing wall, on both halves.
    for x in (-332,-331,-330):
        for z in (724,725,727,728):
            put((x,-467,z),'projectseele:nerv_floor_panel','arrival/three_metre_lane_landing',{'mtr:escalator_step'})
    for x in (6471,6472):
        for z in (-6247,-6246):
            put((x,76,z),'projectseele:nerv_floor_panel','un_control_room/two_metre_turn_landing',{'mtr:escalator_step'})
    # The through-walk predates this concrete partition. Its intact floor
    # continues on both sides; form a five-wide doorway and preserve the posts.
    for x in range(6418,6423):
        for y in range(77,80):put((x,y,-6227),'minecraft:air','un_through_walk/open_partition_port',AIR|{'minecraft:gray_concrete'})
    for y in range(77,80):put((6419,y,-6228),'minecraft:air','un_through_walk/retire_doorway_spur',{'minecraft:gray_concrete'})
    for q,(after,why) in sorted(changes.items()):p.match((*q,*q),w.block(q),after,'r41/'+why)
    p.meta.update(negative_control_source='negative_controls.json',old_world='source_world_backup',
                  source_scope='All 60261 FULL GeoFront chunks; whole-width exits, attached sheets and unguarded floor boundaries',
                  preserved=['Original lift car and call hardware','Live rail and trains','Original command hall layout','All entity and player identities'],
                  implementation='Open verified existing doorways or shorten a belt to a supported landing; no new route used to bypass a reported obstruction')
    p.save_plan('measured_interfaces')
    if apply:p.apply('measured_interfaces')
    (ART/'interfaces/contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),'utf8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');main(p.parse_args().apply)
