"""Record exact installed navigation bytes for the current native/release run.

The graph and nearest cache must equal the explicitly supplied exports. This
is a byte-binding receipt and never marks walking, lifts or visuals as passed.
"""
from pathlib import Path
import argparse,json
from release_scope124_r53 import navigation_pins,reference,sha,need


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--world',type=Path,required=True)
    ap.add_argument('--build-receipt',type=Path,required=True)
    ap.add_argument('--graph-export',type=Path,required=True)
    ap.add_argument('--nearest-export',type=Path,required=True)
    ap.add_argument('--installation-receipt',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();world=a.world.resolve();out=a.out.resolve()
    need(world==Path('D:/eva/artifacts/map_complete_20261013/WORLD').resolve(),
         'Explicit sole current World required')
    need(not out.exists() and not out.is_relative_to(world),'Fresh binding receipt outside World required')
    build=json.loads(a.build_receipt.read_text('utf-8-sig'))
    need(build['build_exit']==0 and sha(build['jar'])==build['sha256'],'Actual successful immutable build required')
    pins=navigation_pins(world)
    for name,path in [('nerv_routes_r24.json.gz',a.graph_export),('nearest_lift_paths_r44.json.gz',a.nearest_export)]:
        need(path.resolve()!=world/name and sha(path)==pins[name],'Actual installed navigation differs from explicit export: '+name)
    bundle=json.loads((world/'ROOT_ASSEMBLY_BUNDLE.json').read_text('utf-8-sig'))
    need(bundle['status']=='installed','Actual installed current bundle required')
    row=lambda p:dict(path=Path(p).resolve().as_posix(),sha256=sha(p))
    receipt=row(a.installation_receipt);reference(receipt)
    result=dict(schema='projectseele.r53.current-navigation-byte-binding.v1',world=world.as_posix(),
                current_round=True,installed=True,files=pins,jar_sha256=build['sha256'],
                directory_fingerprint=bundle['directory_fingerprint'],build_receipt=row(a.build_receipt),
                graph_export=row(a.graph_export),nearest_export=row(a.nearest_export),installation_receipt=receipt,
                native_walk_lift_visual_passed=False,world_written=False,
                validation='Exact current World/export/Jar binding only; native acceptance required separately')
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x',encoding='utf8',newline='\n') as stream:stream.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(receipt=out.as_posix(),world_written=False,native_acceptance=False)))


if __name__=='__main__':main()
