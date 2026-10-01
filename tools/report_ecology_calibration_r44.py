"""Summarize every native calibration origin, species and protection outcome."""
from pathlib import Path
from collections import Counter,defaultdict
import csv,gzip,json

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/rebuild_r44/ecology'

def main():
    job=json.loads((OUT/'calibration.json').read_text('utf8'));result=json.loads((OUT/'calibration.result.json').read_text('utf8'))
    assert result['native_preview_complete']
    trials=defaultdict(list)
    for row in result['feature_trials']:trials[row['chunk'],row['layer']].append(row)
    expected={(f"{r['x']},{r['z']}",r['layer']) for r in job['chunks']};assert expected==set(trials)
    rows=[json.loads(s) for s in gzip.open(OUT/'calibration.forward.jsonl.gz','rt',encoding='utf8')]
    inverse=[json.loads(s) for s in gzip.open(OUT/'calibration.inverse.jsonl.gz','rt',encoding='utf8')]
    fwd={tuple(r['pos']):r for r in rows};rev={tuple(r['pos']):r for r in inverse};assert fwd.keys()==rev.keys()
    assert all(r['before']==rev[q]['after'] and r['after']==rev[q]['before'] and r['before_nbt']==rev[q]['after_nbt'] and r['after_nbt']==rev[q]['before_nbt'] for q,r in fwd.items())
    per=[]
    for tile in sorted(job['chunks'],key=lambda r:(r['layer'],r['x'],r['z'])):
        key=f"{tile['x']},{tile['z']}",tile['layer'];ts=trials[key]
        own=[r for r in rows if r['pos'][0]//16==tile['x'] and r['pos'][2]//16==tile['z'] and (r['pos'][1]<0)==(tile['layer']=='geofront')]
        count=Counter(r['after'].partition('[')[0] for r in own)
        per.append(dict(chunk_x=tile['x'],chunk_z=tile['z'],layer=tile['layer'],biome=tile['biome'],features=len(ts),
            placed=sum(r['placed'] and not r['rolled_back_for_protection'] for r in ts),
            native_no_placement=sum(not r['placed'] and not r['rolled_back_for_protection'] for r in ts),
            protection_rollback=sum(r['rolled_back_for_protection'] for r in ts),
            final_owned_chunk_cells=len(own),leaves=sum(v for k,v in count.items() if k.endswith('_leaves')),logs=sum(v for k,v in count.items() if k.endswith('_log')),
            flowers=sum(v for k,v in count.items() if k in {'minecraft:dandelion','minecraft:cornflower','minecraft:oxeye_daisy','minecraft:allium'}),species=dict(count)))
    bio=json.loads((OUT/'calibration.biomes.forward.json').read_text('utf8'));back=json.loads((OUT/'calibration.biomes.inverse.json').read_text('utf8'))
    assert len(bio)==len(back) and all(a['before_snbt']==b['after_snbt'] and a['after_snbt']==b['before_snbt'] for a,b in zip(bio,back))
    report=dict(origin_tiles=len(expected),written_chunks=len({(r['pos'][0]//16,r['pos'][2]//16) for r in rows}),features=len(result['feature_trials']),
        effective_placements=sum(r['placed'] and not r['rolled_back_for_protection'] for r in result['feature_trials']),
        native_zero_placement=sum(not r['placed'] and not r['rolled_back_for_protection'] for r in result['feature_trials']),
        protected_rollbacks=[r for r in result['feature_trials'] if r['rolled_back_for_protection']],
        final_cells=len(rows),states=dict(Counter(r['after'].partition('[')[0] for r in rows)),
        biome_sections=len(bio),quart_cells=sum(len(r['quart_indices']) for r in bio),complete_inverse_verified=True,
        future_halo_note='Native placement writes into measured neighbour chunks; origin biome migration covers the 18 origins. Halo biome completion and full promotion require a further native audit; this is a calibration sample.',
        protection_reason_limit='This frozen epoch records rollback counts but not the rejected coordinate. No success is claimed for the two protected tree features; detailed per-coordinate reasons are a required next epoch improvement.',
        native_preview=True,world_changed_by_this_report=False,native_growth_reload=False,visual_self_review=False,user_approved=False,tiles=per)
    (OUT/'calibration_inspection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    with (OUT/'calibration_tiles.csv').open('w',newline='',encoding='utf-8-sig') as stream:
        keys=[k for k in per[0] if k!='species'];writer=csv.DictWriter(stream,fieldnames=keys);writer.writeheader();writer.writerows([{k:r[k] for k in keys} for r in per])
    print('All native origins/inverses inspected',len(per),'tiles',len(rows),'cells',len(bio),'biome sections',flush=True)

if __name__=='__main__':main()
