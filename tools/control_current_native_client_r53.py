"""Send an ordinary client input through ASCII-safe attach parameters."""
from pathlib import Path
import argparse,base64,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--host',type=Path,required=True);ap.add_argument('--action',choices=('snapshot','radio','look','walk','stop_flying','close_screen','ui_button','ui_text','use_block'),required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--value',action='append',default=[]);a=ap.parse_args()
    h=a.host.resolve();spec=json.loads((h/'launch.json').read_text('utf-8-sig'));run=json.loads((h/'RUNNING.json').read_text('utf-8-sig'));assert not (h/'RESULT.json').exists() and run['jar_sha256']==spec['jar_sha256'];assert Path(spec['world']).resolve()==Path('D:/eva/artifacts/map_complete_20261013/WORLD').resolve();assert not a.output.exists() and not a.output.resolve().is_relative_to(Path(spec['world']).resolve())
    classes=ROOT/'.Codex/map_complete_20261013/route_audit/client_input_tools/ordinary_controls_v7';values=a.value or ['-'];encoded=['b64u8:'+base64.b64encode(v.encode('utf-8')).decode('ascii') for v in values]
    subprocess.run([spec['command'][0],'-Xmx128m','-cp',str(classes),'CurrentClientInputAttachV7R53',str(run['pid']),str(classes/'current_client_input_agent_v7.jar'),a.action,str(a.output.resolve()),*encoded],check=True)
    print(json.dumps({'action':a.action,'submitted':True,'output':str(a.output.resolve()),'input_submission_not_functional_pass':True}))
if __name__=='__main__':main()
