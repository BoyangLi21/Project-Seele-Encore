"""Read-only FULL/unfinished classification for real world-generation cases."""
from pathlib import Path
import json
from query_blocks import chunk_statuses

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW';OUT=ROOT/'artifacts/rebuild_r44/ecology'

def main():
    config=json.loads((OUT/'biome_source.completed.json').read_text('utf8'));reserved=config['reserved_bounds']+config['underground_reserved_bounds']
    # Existing unfinished outer-dome cells exercise the same real generator
    # path that the last four forest photos reached, including zero-arg height.
    positions={(x,z) for x in range(80,110) for z in range(55,90)
        if not any(x*16-20<=r[2] and x*16+35>=r[0] and z*16-20<=r[3] and z*16+35>=r[1] for r in reserved)}
    statuses=chunk_statuses(WORLD,'projectseele:geofront',positions)
    before_features={'empty','structure_starts','structure_references','biomes','noise','surface','carvers'}
    cases=[dict(x=x,z=z,measured_status=s,scope='Actual existing pre-feature chunk, surface and cavern production generator')
        for (x,z),s in sorted(statuses.items()) if s in before_features][:4]
    assert cases,'Inspect current unfinished regions rather than generating a guessed empty area'
    job=dict(world=WORLD.resolve().as_posix(),seed=config['seed'],chunks=cases,world_write_authority='Root only, explicit native source generation fixture; no client/agent launch',
        native_property='projectseele.r44EcologyFutureJob',reversible_basis='Root must back up the selected complete region files before native generation; no player/entity/transport progress copied')
    (OUT/'future_generation_cases.json').write_text(json.dumps(job,indent=2),'utf8');print(cases,flush=True)

if __name__=='__main__':main()
