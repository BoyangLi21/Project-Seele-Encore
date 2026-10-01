"""Replay every original actual native palette against a new binding."""
from pathlib import Path
import argparse,itertools,json
import numpy as np
from replay_rigged_angel_witness_r44 import skin


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--witness',type=Path,required=True);ap.add_argument('--candidate',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    mesh=json.loads(args.candidate.read_text('utf8'));ids=np.asarray(mesh['skin']['indices']).reshape(-1,4);weights=np.asarray(mesh['skin']['weights']).reshape(-1,4)
    identity=None;samples=[];permutation=[]
    for line in args.witness.open('r',encoding='utf8'):
        row=json.loads(line)
        if row['kind']=='actual-parsed-weighted-resource':
            identity=row
            if mesh['skin']['bones']!=row['bones']:raise ValueError('Actual native palette bones differ')
            decoded=np.asarray(row['decoded_vertices'],dtype=np.float32).reshape(-1,8)
            if not np.array_equal(np.asarray(mesh['parts']['root']['vertices'],dtype=np.float32),decoded.reshape(-1)):raise ValueError('Candidate changes actual decoded render geometry')
            points=decoded[:,:3].astype(float)*[-1/16,1/16,1/16]
        elif row['kind']=='actual-weighted-emit-vertices'and row['branch']!='wrap-cache':
            if identity is None:raise ValueError('Missing actually parsed resource')
            palette=row['actual_palette'];real=np.asarray([p['actual_real_quaternion_xyzw']for p in palette])[:,[3,0,1,2]];dual=np.asarray([p['actual_dual_quaternion_xyzw']for p in palette])[:,[3,0,1,2]]
            matrices=np.asarray([p['actual_root_relative_matrix_column_major']for p in palette]).reshape(-1,4,4).transpose(0,2,1);scaled=np.asarray([p['scaled_lbs_branch']for p in palette])
            first=skin(points,ids,weights,real,dual,matrices,scaled,'first-slot')[0]
            running=skin(points,ids,weights,real,dual,matrices,scaled,'running-sum')[0]
            error=np.linalg.norm(first-running,axis=1);worst=int(error.argmax())
            samples.append(dict(actual_frame=row['frame'],first_vs_running_maximum_emit_delta=float(error[worst]),worst_vertex=worst,focus_emit_deltas={str(v):float(error[v])for v in(11388,17952)}))
            # All positive/padded four-slot permutations for the actually
            # inspected wrist points on every captured native palette.
            chosen=np.asarray([11388,17952]);wanted=first[chosen];maximum=0.
            for order in itertools.permutations(range(4)):
                value=skin(points[chosen],ids[chosen][:,order],weights[chosen][:,order],real,dual,matrices,scaled,'first-slot')[0]
                maximum=max(maximum,float(np.linalg.norm(value-wanted,axis=1).max()))
            permutation.append(dict(actual_frame=row['frame'],inspected_wrist_maximum_slot_permutation_emit_delta=maximum))
    if not samples:raise ValueError('No actual complete native skin samples')
    report=dict(samples=samples,inspected_wrist_slot_permutations=permutation,
        actual_samples=len(samples),maximum_first_vs_running_emit_delta=max(r['first_vs_running_maximum_emit_delta']for r in samples),
        maximum_inspected_wrist_permutation_emit_delta=max(r['inspected_wrist_maximum_slot_permutation_emit_delta']for r in permutation),
        scope='Every recorded original native palette and exact decoded geometry. New candidate binding is replayed offline; its native emit, fullbody art and actual combat contact remain unverified.',artistic_acceptance=False,native_candidate_run=False)
    args.out.mkdir(parents=True,exist_ok=True);(args.out/'all_original_native_palette_readback.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items()if k not in('samples','inspected_wrist_slot_permutations')},indent=2))


if __name__=='__main__':main()
