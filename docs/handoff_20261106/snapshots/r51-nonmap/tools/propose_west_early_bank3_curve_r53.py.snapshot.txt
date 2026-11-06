"""One minimal west-early bank3 proposal; never authoritative design or WORLD."""
import argparse
import copy
import json
import math
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from build_continuous_upright_directory_r52 import corner, segment, sample, verify_segments, reversed_curve
from audit_current_anchor_complete_motion_r53 import chords
from upright_native_anchor_selection_r53 import sha, require


def bounded_points(segments):
    out = []
    for s in segments:
        for a, b, error in chords(np.asarray(s['controls'])):
            count = max(1, math.ceil(np.linalg.norm(b-a)))
            out.extend(a+(b-a)*t for t in np.linspace(0, 1, count+1))
    return np.array(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--design', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'One fresh Root-review proposal required')
    original = json.loads(args.design.read_text('utf8')); proposal = copy.deepcopy(original)
    legs = {l['id']: l for l in proposal['legs']}; reports = []; points = {}
    # Existing designer parameters: UP96/FAN112/NORTH120, first radius10,
    # second radius20. Reuse its zero-curvature-end quintic control convention.
    for v in range(3):
        name = f'unit{v}/exit3/upright_continuous'; leg = legs[name]
        old = copy.deepcopy(leg['centre_curve']['segments'])
        start = np.asarray(old[0]['controls'][0]); up = start+np.array([0, 96., 0])
        fan = start+np.array([-28.*v, 112., -120.])
        first = np.asarray(corner(start, up, fan, 10.))
        incoming = (fan-up)/np.linalg.norm(fan-up)
        main_start, main_end = np.asarray(old[4]['controls'])
        direction = (main_end-main_start)/np.linalg.norm(main_end-main_start)
        # Twelve metres is the smallest integral setback exceeding the
        # original radius20's two outgoing 8m controls in all three lanes.
        join_x = fan[0]-12.
        join = main_start+direction*((join_x-main_start[0])/direction[0])
        controls = np.array([first[-1], first[-1]+8*incoming, first[-1]+16*incoming,
                             join-16*direction, join-8*direction, join])
        require(np.all(np.diff(controls, axis=0)[:, 0] <= 1e-10), 'No eastward early control allowed')
        pieces = [old[0], segment(first), segment(controls), segment([join, main_end]), *old[5:]]
        length = verify_segments(pieces)
        require(pieces[0] == old[0] and pieces[-4:] == old[-4:], 'V86 and main far/receiver controls must remain exact')
        require(all(np.all(np.diff(s['controls'], axis=0)[:, 1] > 0) for s in pieces), 'Every control derivative must rise')
        leg['centre_curve']['segments'] = pieces
        legs[name+'/reverse']['centre_curve']['segments'] = reversed_curve(pieces)
        points[v] = bounded_points(pieces)
        reports.append(dict(variant=v, fan=fan.tolist(), unchanged_vertical_metres=86,
            new_main_join=join.tolist(), first_blend_controls=first.tolist(), west_early_controls=controls.tolist(),
            original_main_line_retained_from_join=True, unchanged_far_receiver_segments=4,
            length_m=length, original_length_m=verify_segments(old), early_maximum_x=float(controls[:, 0].max())))
    pair_results = []
    for a, b in ((0, 1), (0, 2), (1, 2)):
        # 1m chord samples have <=0.502m continuous cover distance each.
        # These 34x70x34 bounds include the whole 31.7m carried footprint and
        # the sample/cone error, and reject arbitrary unequal route clocks.
        tree = cKDTree(points[b]/np.array([34., 70., 34.]))
        hits = tree.query_ball_point(points[a]/np.array([34., 70., 34.]), 1., p=np.inf)
        pair_results.append(dict(a=a, b=b, conservative_complete_body_pairs=sum(map(len, hits))))
        if any(hits):
            i = next(i for i, h in enumerate(hits) if h)
            print('lane broad candidate', a, b, points[a][i].tolist(), points[b][hits[i][0]].tolist(), flush=True)
    require(all(r['conservative_complete_body_pairs'] == 0 for r in pair_results), 'Three complete lane envelopes overlap')
    proposal['root_review_proposal'] = dict(status='NOT_AUTHORITY_NOT_INSTALLABLE',
        original_design_sha256=sha(args.design), scope='Only bank3 early blends/main joins and their exact reverse curves',
        unchanged='All nodes/ports/V86/other six ascent curves/all far receiver controls/whole original carrier/EVA/head source',
        source_parameters='design_monotone_launch_complete.py UP96,FAN112,NORTH120,R10,R20; existing quintic zero-end-curvature convention',
        reports=reports, complete_lane_pair_check=pair_results, world_written=False, native_admission=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(proposal, indent=2)+'\n', encoding='utf8')
    print(json.dumps(dict(output=str(args.output), sha256=sha(args.output),
        main_joins=[r['new_main_join'] for r in reports], length_delta_m=[r['length_m']-r['original_length_m'] for r in reports],
        conservative_complete_lane_pairs=pair_results)), flush=True)


if __name__ == '__main__':
    main()
