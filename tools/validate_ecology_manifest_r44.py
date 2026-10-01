"""Root queue preflight of a completed native manifest with bounded disk uniqueness."""
from pathlib import Path
import argparse,json,gzip,sqlite3,hashlib
from validate_ecology_plans_r44 import verify_blocks,verify_biomes

def main():
    p=argparse.ArgumentParser();p.add_argument('complete_manifest',type=Path);args=p.parse_args()
    path=args.complete_manifest;manifest=json.loads(path.read_text('utf8'))
    assert manifest['complete'] and manifest['cross_batch_vegetation_cells_disjoint']
    assert manifest['per_batch_biomes_applyable'] is False
    ledger=Path(manifest['ledger_directory']);db=sqlite3.connect(ledger/'preflight_uniqueness.sqlite')
    db.execute('CREATE TABLE IF NOT EXISTS cells(pos INTEGER PRIMARY KEY) WITHOUT ROWID')
    db.execute('CREATE TABLE IF NOT EXISTS sections(cx INTEGER,cz INTEGER,sy INTEGER,PRIMARY KEY(cx,cz,sy)) WITHOUT ROWID')
    db.execute('DELETE FROM cells');db.execute('DELETE FROM sections')
    report=dict(native_manifest=str(path),native_manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),blocks=[],biomes=[],passed=True,world_written=False)
    try:
        for kind,key in [('blocks','block_plans'),('biomes','merged_biome_plans')]:
            for i,plan in enumerate(manifest[key]):
                forward,inverse=Path(plan['forward']),Path(plan['inverse'])
                if kind=='blocks':
                    with gzip.open(forward,'rt',encoding='utf8') as a,gzip.open(inverse,'rt',encoding='utf8') as b:
                        count=0
                        while True:
                            first,second=a.readline(),b.readline()
                            if not first or not second:assert first==second;break
                            row,back=json.loads(first),json.loads(second)
                            assert row['pos']==back['pos'] and row['before']==back['after'] and row['after']==back['before']
                            assert row.get('before_nbt')==back.get('after_nbt') and row.get('after_nbt')==back.get('before_nbt')
                            x,y,z=map(int,row['pos']);packed=((x&0x3ffffff)<<38)|((z&0x3ffffff)<<12)|(y&0xfff)
                            if packed>=1<<63:packed-=1<<64
                            db.execute('INSERT INTO cells VALUES(?)',(packed,));count+=1
                    result=verify_blocks(forward)
                else:
                    rows=json.loads(forward.read_text('utf8'));back=json.loads(inverse.read_text('utf8'));assert len(rows)==len(back)
                    for row,reversed_row in zip(rows,back):
                        assert row['before_snbt']==reversed_row['after_snbt'] and row['after_snbt']==reversed_row['before_snbt']
                        assert row['before_names']==reversed_row['after_names'] and row['after_names']==reversed_row['before_names']
                        db.execute('INSERT INTO sections VALUES(?,?,?)',(*row['chunk'],row['section_y']))
                    result=verify_biomes(forward)
                report[kind].append(result);report['passed']&=result['passed'];db.commit()
                print(kind,i+1,'/',len(manifest[key]),'passed',result['passed'],flush=True)
        report['unique_block_cells']=db.execute('SELECT count(*) FROM cells').fetchone()[0]
        report['unique_biome_sections']=db.execute('SELECT count(*) FROM sections').fetchone()[0]
    finally:
        db.close()
    target=path.with_name(path.name+'.preflight.json');target.write_text(json.dumps(report,indent=2),'utf8')
    print({k:v for k,v in report.items() if k not in ('blocks','biomes')},flush=True)
    if not report['passed']:raise SystemExit(1)

if __name__=='__main__':main()
