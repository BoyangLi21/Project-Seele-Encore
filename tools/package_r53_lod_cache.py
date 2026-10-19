"""Export the current world's GeoFront LOD cache without changing its terrain."""
import argparse
import json
import msvcrt
import sqlite3
import zipfile
from pathlib import Path

from audit_r53_lod_hierarchy import audit
from audit_r53_lod_voxel_coverage import audit as audit_geometry


def package(world, coverage, destination):
    proof = json.loads(coverage.read_text('utf8'))
    if proof.get('remaining') or proof['statuses'].get('full') != proof['checked']:
        raise ValueError('The measured terrain completion list is not complete')
    relative = Path('dimensions/projectseele/geofront/data/DistantHorizons.sqlite')
    database = world / relative
    with (world/'session.lock').open('r+b') as lock:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        with sqlite3.connect(database.resolve().as_uri()+'?mode=ro', uri=True) as sql:
            if sql.execute('pragma quick_check').fetchone()[0] != 'ok':
                raise ValueError('LOD database integrity check failed')
            levels = sql.execute('select DetailLevel,count(*),min(PosX),max(PosX),min(PosZ),max(PosZ) from FullData group by DetailLevel').fetchall()
            # The authored GeoFront dome is centered here with radius 1800.
            # Remote surface/out-of-dome data is not part of this export claim.
            hierarchy = audit(sql, center=(30, 296), radius=1800)
            if not hierarchy['verified']:
                raise ValueError('Child data is missing from the LOD parent hierarchy')
        geometry = audit_geometry(world)
        if not geometry['verified']:
            raise ValueError('LOD geometry is missing or contradicts the actual cavern roof')
        # A live WAL would make copying just the main file an incomplete export.
        wal = Path(str(database)+'-wal')
        if wal.exists() and wal.stat().st_size:
            raise ValueError('Close the game normally so its cache is checkpointed')
        manifest = {
            'format': 'Distant Horizons 2.3.4-b / Minecraft Forge 1.20.1',
            'source_world': str(world.resolve()),
            'dimension': 'projectseele:geofront',
            'database_bytes': database.stat().st_size,
            'source_modified_ns': database.stat().st_mtime_ns,
            'terrain_completion': proof,
            'lod_hierarchy': hierarchy,
            'lod_geometry': geometry,
            'lod_rows_by_detail': [dict(zip(('detail','rows','min_x','max_x','min_z','max_z'), row)) for row in levels],
            'scope': 'Current generated GeoFront cache; distant surface battle coverage remains a separate task',
            'changes_block_destruction': False,
            'contains_world_chunks_or_entity_progress': False,
            'recommended_settings': {'verticalQuality':'PIXEL_ART','enableCaveCulling':False,'enableDistantGeneration':False},
        }
        readme = '''# R53 GeoFront 远景缓存

这是当前单人存档生成的三维远景数据，不是普通材质包，也不是宣传图片投影。
当前实际试玩存档已经使用此缓存；此包供迁移同一份世界时使用。

游戏和服务器正常保存退出后，将 dimensions 文件夹合并到同一份存档根目录。
请使用固定版本 Distant Horizons 2.3.4-b。勿用于另一份不同建筑进度的世界。
本包不包含或覆盖 region、entities、playerdata、设备和任务进度。
近处仍为真实可交互方块，破坏后沿用 DH 原生的局部更新，不增加不可破坏限制。

manifest.json 记录实际缓存层级范围及本次地形补全回读结果。
它不表示地表超远距屋岛战场、全地图美术及所有玩法已经验收完成。
远景缓存降低重复生成开销，不提供离线路径追踪的实时画质保证。
'''
        destination.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            archive.write(database, relative.as_posix())
            archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
            archive.writestr('README.zh.md', readme)
        with zipfile.ZipFile(destination) as archive:
            if archive.testzip() is not None:
                raise ValueError('Export readback failed')
            if archive.getinfo(relative.as_posix()).file_size != manifest['database_bytes']:
                raise ValueError('Export length differs from source')
    print(json.dumps({'file':str(destination), 'bytes':destination.stat().st_size,'lod_rows':sum(row[1] for row in levels),'verified':True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('world', type=Path)
    parser.add_argument('coverage', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    package(args.world, args.coverage, args.destination)
