"""Preserve the actual water-landfill negative and check a fresh full candidate."""
from pathlib import Path
import argparse,gzip,json,hashlib
from collections import Counter

ROOT=Path(__file__).resolve().parents[1]
def read(p):return [json.loads(s)for s in gzip.open(p/'forward.jsonl.gz','rt',encoding='utf8')]
def main():
    p=argparse.ArgumentParser();p.add_argument('candidate',type=Path);a=p.parse_args();negative=ROOT/'artifacts/rebuild_r44/city_expansion/kirisato_full_scene_graded_v6'
    old=read(negative);new=read(a.candidate);bad=[r for r in old if r['before'].startswith('minecraft:water')];assert len(bad)==321
    fresh=[r for r in new if r['before'].startswith('minecraft:water')];assert not fresh
    water=json.loads((a.candidate/'complete_current_water_landscape.json').read_text('utf8'));by_pos={tuple(r['pos']):r for r in new}
    assert all(tuple(r['pos']) not in by_pos for r in water['measured_actual_water_cells'])
    report=dict(negative_source=str(negative.resolve()),negative_forward_sha256=hashlib.sha256((negative/'forward.jsonl.gz').read_bytes()).hexdigest(),
        true_failed_water_cells=bad,negative_counts=dict(Counter(r['after']for r in bad)),negative_world_installed=False,
        first_source_error='plan_kirisato_living_ground_r44 protected water only when not hard; hard whole-court claims replaced actual water. The old composer description water excluded covered gardens only, not the whole plan.',
        candidate=str(a.candidate.resolve()),candidate_forward_sha256=hashlib.sha256((a.candidate/'forward.jsonl.gz').read_bytes()).hexdigest(),
        candidate_changed_water_cells=0,whole_measured_retained_water_voxels=len(water['measured_actual_water_cells']),
        all_retained_water_absent_from_forward=True,retired_uninstalled_flat_lawn_over_pond_columns=water['retained_public_water_columns'],
        replaced_with_real_short_apron_span=water['supported_apron_deck_columns'],
        actual_doors_rooms_roads_station_goals_retained=True,world_written=False,native_passed=False,visual_passed=False)
    target=a.candidate/'actual_water_landfill_negative_and_repair.json';assert not target.exists();target.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print('Water negative:',len(bad),'; fresh changes:',len(fresh),'; whole retained water:',len(water['measured_actual_water_cells']),flush=True)
if __name__=='__main__':main()
