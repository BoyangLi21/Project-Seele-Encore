"""Compile a source-labelled offline node without changing production selection.

This enables paired source checks while a geometric candidate awaits its final
receipt. It does not authorize installation or edit the world.
"""
from pathlib import Path
import argparse, hashlib, json, re, subprocess
REPO=Path(__file__).resolve().parents[1]
NODE=REPO/'.Codex/r52_owner_draft/legacy_current_candidate'
ASSET=REPO/'src/main/resources/assets/projectseele'
JAVA=Path('C:/Users/liboy/jdks/jdk-17.0.19+10/bin/javac.exe')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    global NODE
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node',type=Path,default=NODE)
    parser.add_argument('--stow-source',type=Path)
    args=parser.parse_args();NODE=args.node.resolve()
    if not NODE.is_relative_to((REPO/'.Codex/r52_owner_draft').resolve()):raise ValueError('Offline owner candidate node only')
    resources=NODE/'resources/assets/projectseele';classes=NODE/'classes';classes.mkdir(parents=True,exist_ok=True)
    receipt=json.loads((ASSET/'eva/full_assembly_geometry_r52_sources.json').read_text(encoding='utf-8'))
    for name in ('mesh/legacy_running_heads_r52.json','mesh/foot_guide_dock_r52.json','mesh/carrier_body_trimmed_r52.json','mesh/carrier_sole_bearings_r52.json','mesh/carrier_running_deck_r52.json','mesh/carrier_service_stow_r52.json'):
        source=args.stow_source if name=='mesh/carrier_service_stow_r52.json' and args.stow_source else ASSET/name
        if not source.exists():
            if name in receipt['resources']:raise ValueError('Selected candidate source missing: '+name)
            continue
        target=resources/name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(source.read_bytes())
        if name in receipt['resources']:receipt['resources'][name]=sha(source)
    receipt['resources']['mesh/legacy_running_heads_r52.json']=sha(ASSET/'mesh/legacy_running_heads_r52.json')
    selected=resources/'eva/full_assembly_geometry_r52_sources.json';selected.parent.mkdir(parents=True,exist_ok=True);selected.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    full_sha=sha(selected);original=REPO/'src/main/java/com/projectseele/world/NervOriginalCarrierR52.java';candidate=NODE/'source/com/projectseele/world/NervOriginalCarrierR52.java';candidate.parent.mkdir(parents=True,exist_ok=True)
    text=original.read_text(encoding='utf-8');text,n=re.subn(r'(public static final String SOURCE_SHA=")[0-9a-f]{64}(";)',lambda m:m[1]+full_sha+m[2],text,count=1)
    if n!=1:raise ValueError('Exact Original full selection declaration required')
    candidate.write_text(text,encoding='utf-8')
    arguments=(REPO/'.Codex/r52_owner_draft/whole_envelopes_compile.args').read_text(encoding='utf-8').splitlines();cp=arguments[arguments.index('"-classpath"')+1].strip('"')
    cp=classes.as_posix()+';'+(NODE/'resources').as_posix()+';'+cp
    owned=['NervLegacyCarrierRideR52','NervFootGuideDockR52','NervMechanicalRailBindingR52','NervFootGuideStationR52']
    sources=[candidate]+[REPO/f'src/main/java/com/projectseele/world/{name}.java' for name in owned]
    args=NODE/'compile.args';args.write_text('\n'.join(['-encoding','UTF-8','-proc:none','-classpath','"'+cp+'"','-sourcepath','"'+(REPO/'.Codex/r52_owner_draft/empty').as_posix()+'"','-d','"'+classes.as_posix()+'"']+['"'+p.as_posix()+'"' for p in sources])+'\n',encoding='utf-8')
    checked=subprocess.run([str(JAVA),'@'+str(args)],capture_output=True,text=True,encoding='utf-8',errors='replace');(NODE/'compile.log').write_text(checked.stdout+checked.stderr,encoding='utf-8')
    if checked.returncode:raise RuntimeError('Offline candidate javac failed: '+checked.stderr[-1800:])
    report={'candidate_only':True,'world_written':False,'native_accepted':False,'production_selection_modified':False,'full_receipt_sha256':full_sha,'legacy_sha256':receipt['resources']['mesh/legacy_running_heads_r52.json'],'dock_sha256':sha(ASSET/'mesh/foot_guide_dock_r52.json'),'stow_sha256':receipt['resources']['mesh/carrier_service_stow_r52.json'],'source_java_sha256':{str(p):sha(p) for p in sources},'classpath_prefix':[classes.as_posix(),(NODE/'resources').as_posix()]}
    (NODE/'RECEIPT.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report))
if __name__=='__main__':main()
