"""Final real facility views with the shipped shader enabled and disabled."""
from pathlib import Path
from contextlib import ExitStack
import json,copy,shutil,subprocess,sys
from run_combat_review_r31 import temporary_options
from release_combat_r36 import guard
from launch_rendered_client_r17 import java_environment

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/world_combat_r40/reception_review'


def main():
    guard();world=ROOT/'run/saves/SEELE_FIELD_R40_REVIEW';file=world/'r30_photo_views.json';original=file.read_bytes()
    views=json.loads((ART/'final_views.json').read_text())
    previous=json.loads((ROOT/'run/saves/SEELE_FIELD_R39_REVIEW/r30_photo_views.json').read_text())
    for row in previous[:2]+previous[3:]:
        row=copy.deepcopy(row);row['file']=row['file'].replace('r39_checked_','r40_light_');views.append(row)
    try:
        for enabled in [True,False]:
            label='on' if enabled else 'off';folder=ART/('shader_'+label);folder.mkdir(parents=True,exist_ok=True)
            selected=copy.deepcopy(views if enabled else [v for v in views if any(s in v['file'] for s in ['header','hangar_station','rear_ring','light_'])])
            for view in selected:view['file']='r40_'+label+'_'+view['file']
            file.write_text(json.dumps(selected,ensure_ascii=False),'utf8');(folder/'views.json').write_bytes(file.read_bytes())
            with ExitStack() as stack:
                stack.enter_context(temporary_options(ROOT/'run/config/oculus.properties','=',{'enableShaders':str(enabled).lower()}))
                stack.enter_context(temporary_options(ROOT/'run/options.txt',':',{'renderDistance':'10','pauseOnLostFocus':'false'}))
                with (folder/'native.log').open('w',encoding='utf8') as log:
                    result=subprocess.call([sys.executable,'tools/launch_rendered_client_r17.py','--prepared-file',str(ROOT/'.Codex/client-r40-all-photos.json')],cwd=ROOT,env=java_environment()[1],stdout=log,stderr=subprocess.STDOUT)
                    assert result==0,result
            for row in selected:
                path=ROOT/'run/screenshots'/row['file'];assert path.is_file(),path;shutil.copy2(path,folder/path.name)
            print(label,len(selected),'native photos complete',flush=True)
    finally:file.write_bytes(original)


if __name__=='__main__':main()
