"""Root-owned R52 component frames; no world writes or inferred excavation rights.

Coordinates are block indices. Continuous actor coordinates rotate around block
centres, so the 180-degree translation differs by one on X/Z. This distinction
is deliberate: using the block transform for actors offsets every socket.
"""
from dataclasses import dataclass
from pathlib import Path
import json

BASE = Path('D:/eva/artifacts/r52_fresh_from_r51_20261009')


@dataclass(frozen=True)
class Frame:
    turn: int
    dx: int
    dy: int
    dz: int

    def block(self, p):
        x, y, z = p
        if self.turn == 180:
            x, z = -x, -z
        elif self.turn == 90:
            x, z = -z, x
        elif self.turn == 270:
            x, z = z, -x
        elif self.turn != 0:
            raise ValueError('Only exact orthogonal facility frames')
        return (x + self.dx, y + self.dy, z + self.dz)

    def point(self, p):
        x, y, z = p
        if self.turn == 180:
            x, z = 1 - x, 1 - z
        elif self.turn == 90:
            x,z=1-z,x
        elif self.turn == 270:
            x,z=z,1-x
        return (x + self.dx, y + self.dy, z + self.dz)

    def box(self, lo, hi):
        a, b = self.block(lo), self.block(hi)
        return [list(map(min, zip(a, b))), list(map(max, zip(a, b)))]


PYRAMID = Frame(0, 0, -93, 0)
HANGAR = Frame(180, 60, -236, 88)
TERMINAL = Frame(0, 0, -280, -7)
HQ_STATION = PYRAMID
BANK_CENTRES_Z = (124.5, -328.5, -781.5)


def document():
    # Boxes are component survey envelopes, NOT permission to clear every cell.
    components = {}
    for name, frame, lo, hi in (
        ('pyramid', PYRAMID, (-90, -470, 207), (150, -291, 447)),
        ('hangar', HANGAR, (-48, -470, -302), (114, -338, -192)),
        ('terminal', TERMINAL, (-56, -647, 232), (116, -516, 420)),
        ('hq_station', HQ_STATION, (-22, -482, 466), (82, -449, 542)),
    ):
        components[name] = dict(frame=frame.__dict__, source_envelope=[lo, hi],
                                destination_envelope=frame.box(lo, hi))
    cages = [HANGAR.point((x + .5, -442, -239.5)) for x in (-12, 30, 72)]
    original_transfer_end = [HANGAR.point((x + .5, -410, -35.5)) for x in (-12, 30, 72)]
    assert all(b[1] - a[1] == 32 and a[2] - b[2] == 204
               for a, b in zip(cages, original_transfer_end))
    assert components['pyramid']['destination_envelope'][0][1] > components['hangar']['destination_envelope'][1][1]
    assert components['hangar']['destination_envelope'][0][1] > components['terminal']['destination_envelope'][1][1]
    assert HANGAR.block((30, -443, -240)) == (30, -679, 328)
    assert HANGAR.point((30.5, -442, -239.5)) == (30.5, -678, 328.5)
    return dict(
        schema='projectseele.r52.root-spatial-plan.v1', source_commit='6f2d35c',
        source='R51-delivered original R50 world', map_author='root',
        status='Root construction in progress; installed stages have separate exact APPLIED receipts, runtime not yet commissioned',
        components=components, cage_feet_by_original_variant=cages,
        aligned_room_cores=dict(pyramid_centre_xz=[30,327],
                                hangar_core=HANGAR.box((-38,-470,-285),(98,-351,-192)),
                                terminal_core=TERMINAL.box((-38,-630,265),(98,-529,403)),
                                note='Full core rooms align under headquarters; the original crucifix stays against its south wall, not moved into the room centre.'),
        original_transfer_end_by_original_variant=original_transfer_end,
        original_transfer=dict(yaw=180, keep_original_shape=True, upright=True,
                               rise=32, horizontal_length=204),
        launch_banks=[dict(id=i + 1, lane_count=3, longitudinal_centre_z=z,
                           carrier_foot_y=-646, lane_x=[-11.5, 30.5, 72.5])
                      for i, z in enumerate(BANK_CENTRES_Z)],
        launch_topology=['hangar -> original inclined transfer -> bank_1',
                         'bank_1 -> rear pressure gate -> tracked transfer -> bank_2',
                         'bank_2 -> rear pressure gate -> tracked transfer -> bank_3'],
        launch_exits=dict(bank_1='short vertical / incline / original surface wells',
                          bank_2='vertical / GeoFront floor',
                          bank_3='short vertical / Hakone incline / surface wells'),
        launch_centre_preflight=dict(
            bank_1=dict(body_reference_path=[[30.5,-646,124.5],[30.5,-554,124.5],
                                   [30.5,-530,-35.5],[30.5,81,-35.5]],
                        note='Connection civil installed. Final deployment head needs explicit carrier-to-support handoff; these are body reference origins, not measured sole pivots.'),
            bank_2=dict(body_reference_path=[[30.5,-646,-328.5],[30.5,-475,-328.5]],
                        note='Vertical civil installed at apron floor -476. Final handoff terminal root is independently measured with full carrier.'),
            bank_3=dict(short_vertical_top_y=-556, incline_destination_y=-516,
                        body_reference_path=[[30.5,-646,-781.5],[30.5,-556,-781.5],[-1169.5,-516,1150.5],[-1169.5,72,1150.5]],
                        surface_apron_floor_y=68,all_three_inclines_parallel=True,
                        note='Final third bank is equally spaced 453m behind bank2. Earlier -448.5 bank/near-Hakone and converging drafts are superseded; only the exact stage receipts authorize installed geometry.')),
        water_level=-473, artificial_lake_side='west', reference_bank_point=[-75, -467, 342],
        roof_beacon=PYRAMID.block((30, -291, 327)),
        exterior_logo=dict(source_bounds=[[-6, -406, 356], [66, -335, 405]],
                           target_front_xy_bounds=[[14, -462], [46, -430]],
                           project_to_original_front_shell=True,
                           preserve_glazed_band=True),
        shared_lift_reference=[109, -553, 403], original_entrance_destination=[31, -560, 447],
        required_dimension_min_y=-960, unchanged_dimension_max_y=320,
        protected=['all 678 original actors and original player/mission progress',
                   'all 19 non-HQ stations, 35 non-HQ platforms, 40 MTR vehicles and 6 routes',
                   'original surface lift x126..134,z269..277 upper column',
                   'original compact personnel lift and surviving experimental station/lab',
                   'all four original NERV/tree artwork anchors with full typed NBT'],
        pending_before_map_writes=['component masks incl. roof/foundation/doors and furnishings',
                                  'complete original and destination occupancy readback',
                                  'native MTR approach curves with unchanged external endpoints',
                                  'whole-device NBT and runtime-frame rebinding',
                                  'full side/overhead support and launch swept-clearance checks'])


if __name__ == '__main__':
    out = BASE / 'ROOT_SPATIAL_PLAN.json'
    out.write_text(json.dumps(document(), ensure_ascii=False, indent=2) + '\n', 'utf8')
    print(out)
