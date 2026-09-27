"""Rebuild the delivered navigation file from the actual R42 geometry."""
from pathlib import Path
import json,gzip,hashlib
import export_facility_navigation_r40 as previous

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R42_REVIEW'
OUT=ROOT/'artifacts/rebuild_r42/navigation'


def main():
    previous.WORLD=WORLD;previous.OUT=OUT;previous.main()
    file=WORLD/'nerv_routes_r24.json.gz'
    with gzip.open(file,'rt',encoding='utf8') as f:data=json.load(f)
    data['source']='R42 exact current floor/portal graph, rebuilt from the repaired preview; derived navigation must be included in the static delivery manifest.'
    with gzip.open(file,'wt',encoding='utf8') as f:json.dump(data,f,ensure_ascii=False,separators=(',',':'))
    (OUT/'navigation_manifest.json').write_text(json.dumps(dict(file=file.name,world=str(WORLD),nodes=len(data['nodes']),sha256=hashlib.sha256(file.read_bytes()).hexdigest(),derived_static_data=True),ensure_ascii=False,indent=2),'utf8')


if __name__=='__main__':main()
