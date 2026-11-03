"""Stage installed map regions into a stopped, isolated native LOD cache."""
import argparse,json,sqlite3,zipfile,shutil
from pathlib import Path
from install_r53_carrier_trays import stopped_world
from install_hakone_array_patch import atomic_replace,prepare_jar
from native_transit_additions import inventory,assert_preserved

def stage(a):
    r=json.loads(a.installation.read_text('utf8'))
    if r['status']!='installed':raise ValueError('Complete installation required')
    if {Path(c).resolve()for c in r['candidates']}!={c.resolve()for c in a.candidate}:raise ValueError('Candidate receipt mismatch')
    a.out.mkdir(exist_ok=False);actual_jar=a.world.parent.parent/'mods/projectseele-0.1.0-all.jar';cache_jar=a.cache.parent/'mods/projectseele-0.1.0-all.jar'
    old_jar=Path(next(row['backup']for row in r['files']if Path(row['target'])==actual_jar))
    allowed={'data/projectseele/worldgen/hakone_surface.bin.gz','data/projectseele/worldgen/hakone_surface_blend.bin.gz'}|{'com/projectseele/world/HakoneSurfaceField'+s+'.class'for s in('','$Field','$Surface')}
    with zipfile.ZipFile(old_jar)as old,zipfile.ZipFile(actual_jar)as current:
        if set(old.namelist())!=set(current.namelist()):raise ValueError('JAR entry set changed')
        changed=[name for name in old.namelist()if old.read(name)!=current.read(name)]
        if not set(changed)<=allowed:raise ValueError('Non-map code or asset changed')
    (a.installation.parent/'terrain-jar-readback.json').write_text(json.dumps(dict(all_other_entries_exact=True,changed_entries=changed),indent=2),'utf8')
    with stopped_world(a.world),stopped_world(a.cache):
        kept=json.loads((a.candidate[0]/'identity-before/files.json').read_text('utf8'))
        for name in kept:
            if (a.candidate[0]/'identity-before'/name).read_bytes()!=(a.world/name).read_bytes():raise ValueError('World/player/entity identity changed '+name)
        for C in a.candidate:assert_preserved(a.world,inventory(C/'preserved-native'))
        (a.installation.parent/'identity-readback.json').write_text(json.dumps(dict(files_exact=len(kept),native_members_exact=len(inventory(a.candidate[0]/'preserved-native')),actors_players_level_untouched=True),indent=2),'utf8')
        for name in {p.stem+'.mca'for C in a.candidate for p in(C/'delta').glob('*.npz')}:
            rel=Path('dimensions/projectseele/geofront/region')/name;backup=a.out/'cache-before'/rel;backup.parent.mkdir(parents=True,exist_ok=True)
            if (a.cache/rel).exists():shutil.copy2(a.cache/rel,backup)
            atomic_replace(a.cache/rel,(a.world/rel).read_bytes())
        rel=Path('dimensions/projectseele/geofront/data/DistantHorizons.sqlite')
        with sqlite3.connect((a.world/rel).resolve().as_uri()+'?mode=ro',uri=True)as src,sqlite3.connect(a.cache/rel)as dst:src.backup(dst)
        shutil.copy2(cache_jar,a.out/'cache-before/projectseele-0.1.0-all.jar');prepared=a.out/'cache-terrain.jar';prepare_jar(cache_jar,a.field/'terrain-delivery.jar',prepared,terrain_consumer_only=True);atomic_replace(cache_jar,prepared.read_bytes())
    (a.out/'cache-preparation.json').write_text(json.dumps(dict(regions=r['regions'],tiles=len(r['tiles']),actual_world_written=False,other_installed_jar_entries_exact=True),indent=2),'utf8')
    print('Prepared isolated LOD cache; identities and unrelated client JAR entries read back exactly',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('world','cache','installation','field','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--candidate',type=Path,action='append',required=True);stage(p.parse_args())
