"""Exact whole-volume states for visually questioned roof and shop frontage."""
from pathlib import Path
import json,gzip,argparse,hashlib
from PIL import Image,ImageDraw
from collections import Counter
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('plan',type=Path);a=p.parse_args();out=a.plan/'exact_roof_and_forecourt_volume_v1';assert not out.exists();out.mkdir()
 d=json.loads((a.plan/'new_district.json').read_text('utf8'));rows=[json.loads(s) for s in gzip.open(a.plan/'forward.jsonl.gz','rt',encoding='utf8')];patch={tuple(r['pos']):r['after'] for r in rows}
 w=MeasuredWorld(ROOT/'run/saves/SEELE_FIELD_R44_REVIEW');w.box((36,54,-712),(114,90,-676));w.load()
 def state(q):return patch.get(q,w.block(q))
 b=next(b for b in d['buildings'] if b['id'].endswith('/11'));x,z,X,Z=b['bounds'];f=b['floor'];front=[]
 for zz in range(-706,-699):
  for xx in range(x-3,X+4):
   volume=[dict(y=yy,state=state((xx,yy,zz))) for yy in range(f-8,f+5)]
   ground=state((xx,f,zz));front.append(dict(pos=[xx,zz],expected_floor_y=f,at_expected_floor=ground,whole_vertical_column=volume,full_or_flush_support=ground is not None and (ground.split('[')[0] in ['minecraft:smooth_stone','minecraft:stone_bricks','minecraft:stone','minecraft:black_concrete'] or ('iron_trapdoor[' in ground and 'half=top' in ground))))
 im=Image.new('RGB',(1400,550),(239,244,239));draw=ImageDraw.Draw(im)
 for c in front:
  xx,zz=c['pos'];px=40+(xx-x+3)*49;pz=80+(zz+706)*49;st=c['at_expected_floor'] or 'UNKNOWN';col=(164,177,160) if c['full_or_flush_support'] else (95,147,165) if 'water' in st else (147,180,94) if 'grass' in st else (231,195,117) if st in AIR else (196,155,136)
  draw.rectangle((px,pz,px+49,pz+49),fill=col,outline=(62,75,67));draw.text((px+3,pz+5),str(xx),fill=(20,30,25));draw.text((px+3,pz+22),st.split(':')[-1].split('[')[0][:6],fill=(20,30,25))
 draw.text((35,25),'WHOLE SHOP11 FRONT / all 175 columns at actual floor67 / retained water = blue / AIR = ochre',fill=(20,30,25));im.save(out/'whole_forecourt_states.png')
 b=next(b for b in d['buildings'] if b['id'].endswith('/10'));x,z,X,Z=b['bounds'];roof=b['roof'];roofcols=[]
 for xx in range(x,X+1):
  roofcols.append(dict(x=xx,whole_volume=[dict(y=yy,state=state((xx,yy,z-1))) for yy in range(roof,roof+8)],solid_weather_deck=state((xx,roof,z))))
 result=dict(frontage_columns=front,frontage_summary=dict(Counter(c['at_expected_floor'] for c in front)),non_flush_columns=[c for c in front if not c['full_or_flush_support']],roof10_front_complete_cross_section=roofcols,weather_deck_continuous=all(c['solid_weather_deck']=='minecraft:smooth_stone' for c in roofcols),world_written=False,native_visual_passed=False,patch_sha256=hashlib.sha256((a.plan/'forward.jsonl.gz').read_bytes()).hexdigest())
 (out/'exact_volume.json').write_text(json.dumps(result,indent=2),'utf8');print('Whole front',len(front),'nonflush',len(result['non_flush_columns']),'roof deck',result['weather_deck_continuous'])
if __name__=='__main__':main()
