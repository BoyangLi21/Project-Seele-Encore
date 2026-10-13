"""Combine a verified client payload with its matching delivered save for PCL."""
import argparse,copy,hashlib,json,os,zipfile
from pathlib import Path,PurePosixPath

ROOT=Path(__file__).resolve().parents[1]
DELIVERY=Path('D:/eva/delivery')
WORLD='SEELE_R50_WORLD/'
MOD='overrides/mods/projectseele-0.1.0-all.jar'

def digest(data):return hashlib.sha256(data).hexdigest()
def sha(path):
    with path.open('rb')as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--client',type=Path,default=DELIVERY/'Project_SEELE_Encore_R52_NonMapUnified_20261013_Client_PCL.zip')
    p.add_argument('--server',type=Path,default=DELIVERY/'Project_SEELE_Encore_R52_NonMapUnified_20261013_Server.zip')
    p.add_argument('--output',type=Path,default=DELIVERY/'Project_SEELE_Encore_R52_Unified_WithMap_20261013_Client_PCL.zip')
    a=p.parse_args();a.client=a.client.resolve();a.server=a.server.resolve();a.output=a.output.resolve()
    assert a.output.parent==DELIVERY.resolve()
    part=a.output.with_suffix('.zip.part');assert not a.output.exists()and not part.exists()
    out=ROOT/'artifacts/r52_client_with_world_20261013';out.mkdir(parents=True,exist_ok=True)
    inputs={str(a.client):sha(a.client),str(a.server):sha(a.server)}
    client_hashes={};world_hashes={}
    with zipfile.ZipFile(a.client)as client,zipfile.ZipFile(a.server)as server:
        assert len(client.namelist())==len(set(client.namelist()))
        assert len(server.namelist())==len(set(server.namelist()))
        assert not any(n.startswith('overrides/saves/')for n in client.namelist())
        assert client.read(MOD)==server.read('mods/projectseele-0.1.0-all.jar')
        world=[item for item in server.infolist()if item.filename.startswith(WORLD)]
        assert WORLD+'level.dat'in {item.filename for item in world}
        manifest=json.loads(client.read('manifest.json'))
        manifest.update(name=a.output.stem.removesuffix('_Client_PCL')+'_PCL',version=a.output.stem.removesuffix('_Client_PCL'))
        manifest_bytes=json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf8')
        note='''# R52 统一版：含地图客户端

把本 ZIP 拖入 PCL，安装为新实例，使用 Java 17。进入单人游戏打开随包存档；存档目录名为 SEELE_R50_WORLD。

本包已经包含最新非地图统一模组、动作数据、配置、资源包及地图，无需另外从服务器包搬存档。地图是当前保留的原 R50 世界与已授权的旧机库修复；新地图重构继续停用。客户端 JAR 与同批 NonMapUnified 服务器完全一致。

原三门、幽灵碰撞清理、楼梯无栏杆与地下运输修复保留。新增包中的地图逐文件与已交付服务器对应世界一致；模组、动作与资源包字节保持。原有实例和个人存档由用户继续保留，本包安装为新实例。

已回读全部 ZIP 成员；未再次启动游戏，实际游玩由用户验收。
'''.encode('utf8')
        added={'overrides/README_R52_CLIENT_WITH_WORLD.zh.md':note}
        with zipfile.ZipFile(part,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True)as target:
            for item in client.infolist():
                data=manifest_bytes if item.filename=='manifest.json'else client.read(item.filename)
                target.writestr(copy.copy(item),data);client_hashes[item.filename]=digest(data)
            for item in world:
                local=item.filename[len(WORLD):];rel=PurePosixPath(local)
                assert not rel.is_absolute()and '..'not in rel.parts and ':'not in local
                name='overrides/saves/'+item.filename;data=server.read(item.filename)
                info=copy.copy(item);info.filename=name;info.orig_filename=name
                target.writestr(info,data);world_hashes[name]=digest(data)
            for name,data in added.items():target.writestr(name,data)
        expected=client_hashes|world_hashes|{n:digest(v)for n,v in added.items()}
        with zipfile.ZipFile(part)as final:
            assert len(final.namelist())==len(set(final.namelist()))
            assert set(final.namelist())==set(expected)
            for name,h in expected.items():assert digest(final.read(name))==h,name
            assert final.read(MOD)==client.read(MOD)
            assert final.read('overrides/saves/'+WORLD+'level.dat')==server.read(WORLD+'level.dat')
            actual=json.loads(final.read('manifest.json'))
            assert actual['minecraft']==manifest['minecraft']and actual['overrides']=='overrides'
    assert all(sha(Path(name))==h for name,h in inputs.items())
    os.replace(part,a.output)
    receipt=dict(path=str(a.output),bytes=a.output.stat().st_size,sha256=sha(a.output),inputs=inputs,
                 jar_sha256=client_hashes[MOD],client_members=len(client_hashes),world_members=len(world_hashes),
                 world_directory='overrides/saves/'+WORLD.rstrip('/'),all_member_bytes_readback_verified=True,
                 world_exactly_matches_delivered_server=True,client_payload_only_manifest_changed=True,
                 world_or_player_data_transformed=False,new_game_run=False)
    (out/'EXECUTION_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
