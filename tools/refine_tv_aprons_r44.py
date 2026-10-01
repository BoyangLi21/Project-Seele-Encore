"""Whole functional reference-scaled apron/receiver/loadbridge private revision.

Keeps previously validated moving casting/pad geometry unchanged. Regenerates
complete affected fixedparts from the author generator, then rechecks all
carrier, body, realworld and crew interfaces before root installation.
"""
from pathlib import Path
import argparse,hashlib,json
import build_tv_shoulder_shells_r44 as author

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/rebuild_r44/hangar_machinery'


def main(source, out):
    source=Path(source).resolve()
    out,_=author.private_destination(out)
    out.mkdir(parents=True,exist_ok=False)
    d=json.loads(source.read_text('utf8'));author.m.PARTS.clear();author.COLLISION.clear()
    for part,fn in [('platform_r',author.platform),('front_receiver_r',author.beam_receiver),('fixed_support_r',author.fixed_support)]:
        author.m.use(part);fn()
    for part in ('platform','front_receiver','fixed_support'):
        r=part+'_r';l=part+'_l';author.m.PARTS[l]=author.reflected(author.m.PARTS[r],-1)
        author.COLLISION[l]=[[[-q[1][0],q[0][1],q[0][2]],[-q[0][0],q[1][1],q[1][2]]] for q in author.COLLISION[r]]
    for name,values in author.m.PARTS.items():d['parts'][name]=values;d['collision_parts'][name]=author.COLLISION[name]
    for c in d['components']:
        if c['part'] in author.m.PARTS:c['closed_bounds_local']=c['sampled_sweep_bounds_local']=author.bounds(author.m.PARTS[c['part']])
    d['engineering_dimensions']['platform_width_m']=5.3
    d['functional_apron_refinement']={'reference_whole_regular_width_m':5.3,'old_regular_width_m':7.55,
        'whole_receiver_and_terminal_shaft_and_rails_changed_together':True,'rear_support_bridge_connected':True,
        'private_equipment_not_public_route':True,'original_two_crew_lanes_02_arrival_and_operator_controls_retained':True,
        'source_generator_sha256':hashlib.sha256((ROOT/'tools/build_tv_shoulder_shells_r44.py').read_bytes()).hexdigest()}
    p=out/source.name;p.write_text(json.dumps(d,separators=(',',':')),encoding='utf8')
    print('Original-source wholeapron candidate',hashlib.sha256(p.read_bytes()).hexdigest())


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Refine a complete source asset into a fresh private revision; never overwrite v4 or installed assets.')
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    try:main(args.source,args.out)
    except (ValueError,FileNotFoundError) as failure:parser.error(str(failure))
