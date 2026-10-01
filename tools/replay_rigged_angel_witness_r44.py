"""Independent readback of actual parsed weighted resource and emit vertices.

Consumes only the opt-in native witness. It does not substitute the DCC mesh,
guessed resource path, or LocalTriangle fallback for the actual weighted layer.
"""
from pathlib import Path
import argparse, json
import numpy as np


def product(a,b):
    return np.concatenate((a[...,:1]*b[...,:1]-(a[...,1:]*b[...,1:]).sum(-1,keepdims=True),
        a[...,:1]*b[...,1:]+b[...,:1]*a[...,1:]+np.cross(a[...,1:],b[...,1:])),axis=-1)


def skin(points,ids,weights,real,dual,matrices,scaled,rule):
    q=real[ids]; d=dual[ids]
    if rule=='first-slot':reference=q[:,0]
    elif rule=='dominant':
        # The production helper breaks equal positive weights by stable bone
        # identity, not by storage slot; use the same explicit contract.
        maximum=weights.max(1);owners=np.where(weights==maximum[:,None],ids,np.iinfo(np.int32).max).min(1)
        reference=real[owners]
    else:reference=None
    if reference is None:
        accumulator=np.zeros((len(points),4));sign=np.empty(weights.shape)
        for k in range(4):
            sign[:,k]=np.where((q[:,k]*accumulator).sum(1)<0,-1.,1.)
            accumulator+=q[:,k]*(weights[:,k]*sign[:,k])[:,None]
    else:sign=np.where((q*reference[:,None]).sum(2)<0,-1.,1.)
    qr=(q*(weights*sign)[...,None]).sum(1);qd=(d*(weights*sign)[...,None]).sum(1)
    length=np.linalg.norm(qr,axis=1);qr/=length[:,None];qd/=length[:,None]
    qd-=qr*(qr*qd).sum(1)[:,None]
    translation=2*product(qd,qr*np.array([1,-1,-1,-1]))[:,1:]
    v=2*np.cross(qr[:,1:],points)
    result=points+qr[:,:1]*v+np.cross(qr[:,1:],v)+translation
    use_lbs=(scaled[ids]&(weights>0)).any(1)
    if use_lbs.any():
        selected=matrices[ids[use_lbs]];p=points[use_lbs]
        posed=np.einsum('nkij,nj->nki',selected[:,:,:3,:3],p)+selected[:,:,:3,3]
        result[use_lbs]=(posed*weights[use_lbs,:,None]).sum(1)
    return result, length, use_lbs


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--witness',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();resources={};samples=[];fallback=[];skipped=[]
    for number,line in enumerate(args.witness.read_text('utf8').splitlines(),1):
        row=json.loads(line);kind=row.get('kind')
        if kind=='actual-parsed-weighted-resource':
            required=('decoded_vertices','parsed_indices','parsed_weights','bones')
            if not all(k in row for k in required):raise ValueError('Native witness predates independent geometry readback')
            resources[row['resource']]=row
        elif kind=='actual-weighted-fallback-dispatch':fallback.append(row)
        elif kind=='actual-weighted-emit-vertices':
            if row['branch']=='wrap-cache':skipped.append(dict(line=number,reason='Authored wrap cache bypasses skinning, classified separately'));continue
            if row['resource'] not in resources:raise ValueError('Actual parsed bytes identity missing before emit')
            identity=resources[row['resource']];source=np.asarray(identity['decoded_vertices'],dtype=np.float32).reshape(-1,8)
            points=source[:,:3].astype(float)*[-1/16,1/16,1/16]
            ids=np.asarray(identity['parsed_indices'],int).reshape(-1,4);weights=np.asarray(identity['parsed_weights'],dtype=np.float32).reshape(-1,4).astype(float)
            palette=row['actual_palette'];matrices=np.asarray([p['actual_root_relative_matrix_column_major'] for p in palette]).reshape(-1,4,4).transpose(0,2,1)
            real=np.asarray([p['actual_real_quaternion_xyzw'] for p in palette])[:,[3,0,1,2]]
            dual=np.asarray([p['actual_dual_quaternion_xyzw'] for p in palette])[:,[3,0,1,2]]
            scaled=np.asarray([p['scaled_lbs_branch'] for p in palette],bool)
            if [p['bone'] for p in palette]!=identity['bones']:raise ValueError('Native decoded and actual palette orders differ')
            world=np.asarray(row['actual_emit_to_world_matrix_column_major']).reshape(4,4).T
            lift=np.asarray(row.get('actual_ground_support_translation_emit_xyz',[0,0,0]))
            actual=np.asarray(row['vertices_world_xyz']).reshape(-1,3)
            rule='running-sum' if row.get('running_sum_review',False) else 'dominant' if row['dominant_review'] else 'first-slot'
            metrics={};predictions={}
            for label in ('first-slot','dominant','running-sum'):
                local,norm,lbs=skin(points,ids,weights,real,dual,matrices,scaled,label)
                predicted=(local+lift)@world[:3,:3].T+world[:3,3];predictions[label]=predicted
                errors=np.linalg.norm(predicted-actual,axis=1);worst=int(np.argmax(errors))
                metrics[label]=dict(maximum_world_error_blocks=float(errors[worst]),rms_world_error_blocks=float(np.sqrt(np.mean(errors**2))),
                    worst_vertex=worst,minimum_blended_real_norm=float(norm.min()),scaled_lbs_vertices=int(lbs.sum()))
            worst=metrics[rule]['worst_vertex'];permutations=[]
            for order in ([3,0,1,2],[1,2,3,0],[2,3,0,1]):
                p,_,_=skin(points,ids[:,order],weights[:,order],real,dual,matrices,scaled,rule)
                p=(p+lift)@world[:3,:3].T+world[:3,3]
                error=np.linalg.norm(p-predictions[rule],axis=1)
                permutations.append(dict(order=order,maximum_deformation_change_blocks=float(error.max()),changed_vertices_over_1mm=int((error>.001).sum())))
            samples.append(dict(line=number,entity_uuid=row['entity_uuid'],game_time=row['game_time'],frame=row['frame'],branch=row['branch'],actual_rule=rule,
                comparisons=metrics,storage_permutation=permutations,actual_rule_worst_vertex=dict(index=worst,decoded_indices=ids[worst].tolist(),decoded_weights=weights[worst].tolist(),
                actual_world=actual[worst].tolist(),independent_world=predictions[rule][worst].tolist())))
    if not samples:raise ValueError('No independently replayable actual weighted draws captured')
    maximum=max(r['comparisons'][r['actual_rule']]['maximum_world_error_blocks'] for r in samples)
    report=dict(native_recorded=True,actual_weighted_draw_samples=len(samples),maximum_actual_rule_replay_error_blocks=maximum,
        actual_rule_numeric_readback_pass=maximum<.002,identities=[{k:v for k,v in r.items() if k not in ('decoded_vertices','parsed_indices','parsed_weights')} for r in resources.values()],
        actual_fallback_dispatches=fallback,classified_bypasses=skipped,samples=samples,
        scope='Actual loaded bytes/decoded geometry/weights, actual JOML DQ palette and actual final emitted vertices; independently replayed. GPU pixels, limb binding quality and artistic acceptance remain unverified.',
        artistic_acceptance=False)
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('samples','identities','actual_fallback_dispatches','classified_bypasses')},indent=2))


if __name__=='__main__':main()
