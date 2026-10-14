"""Merge independent exact three-variant surveys, requiring matching overlaps."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np


def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True)
    p.add_argument('--inputs',type=Path,nargs=3,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    directory=json.loads(a.directory.read_text('utf8'));digest=hashlib.sha256(a.directory.read_bytes()).hexdigest()
    wanted={l['id'] for l in directory['legs'] if 'centre_curve' in l and not l['id'].endswith('/reverse')}
    assert len(wanted)==9
    names=[];codes={};before={};core={};shell={};banks={};lane_bits={};all_legs=set();sources=[];reports=[]
    for variant,folder in enumerate(a.inputs):
        report=json.loads((folder/'MEASURED_REPORT.json').read_text('utf8'));reports.append(report)
        assert report['measured'] and report['directory_sha256']==digest and report['measured_height_range_m'] is None
        legs=set(report['measured_legs']);assert len(legs)==3 and not all_legs&legs
        assert all(f'unit{variant}/' in k for k in legs);all_legs.update(legs)
        source=folder/'MEASURED_SOURCE.npz';d=np.load(source);mapping=[]
        for state in map(str,d['palette']):
            if state not in codes:codes[state]=len(names);names.append(state)
            mapping.append(codes[state])
        mapping=np.asarray(mapping,np.uint16);old=mapping[d['before']];cc=d['core'];ss=d['shell'];bb=d['banks']
        for i,k in enumerate(d['section_keys']):
            key=tuple(map(int,k))
            if key in before:
                assert np.array_equal(before[key],old[i]),('Concurrent actual World source changed',key)
                core[key]|=cc[i];shell[key]|=ss[i];banks[key]|=bb[i];lane_bits[key]|=cc[i].astype(np.uint8)*(1<<variant)
            else:
                before[key]=old[i].copy();core[key]=cc[i].copy();shell[key]=ss[i].copy();banks[key]=bb[i].copy()
                lane_bits[key]=cc[i].astype(np.uint8)*(1<<variant)
        sources.append(dict(path=folder.as_posix(),report_sha256=hashlib.sha256((folder/'MEASURED_REPORT.json').read_bytes()).hexdigest(),
                            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
    assert all_legs==wanted and len({r['hulls_sha256'] for r in reports})==1
    keys=sorted(before);a.output.mkdir(parents=True,exist_ok=True)
    assert not (a.output/'MEASURED_SOURCE.npz').exists(),'Preserve prior immutable source surveys'
    np.savez_compressed(a.output/'MEASURED_SOURCE.npz',section_keys=np.array(keys,np.int32),
        before=np.array([before[k] for k in keys],np.uint16),core=np.array([core[k] for k in keys]),
        shell=np.array([shell[k] for k in keys]),banks=np.array([banks[k] for k in keys]),palette=names)
    overlap=sum(int(np.count_nonzero((v&(v-1))!=0)) for v in lane_bits.values())
    result=dict(reports[0],measured_legs='all_actual_forward_continuous_legs',parts=sum(r['parts'] for r in reports),
                sections=len(keys),chunks=len({k[:2] for k in keys}),core_cells=sum(int(v.sum()) for v in core.values()),
                shell_cells=sum(int(v.sum()) for v in shell.values()),multiple_lane_core_cells=overlap,
                independent_variant_sources=sources,overlap_before_states_identical=True,world_written=False,clearance_passed=False)
    (a.output/'MEASURED_REPORT.json').write_text(json.dumps(result,indent=2),'utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='independent_variant_sources'}),flush=True)


if __name__=='__main__':main()
