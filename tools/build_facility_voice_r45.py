"""Generate review candidates; install only after language and sound audition."""
from pathlib import Path
import argparse,asyncio,hashlib,json,subprocess,sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.Codex/audio-runtime'))
import edge_tts
from build_facility_audio_r31 import LINES

JAPANESE={
 'pa_prepare':'出撃準備。搭乗橋を収納します。',
 'pa_insert':'エントリープラグ、挿入開始。',
 'pa_lock':'エントリープラグ、固定完了。',
 'pa_drain':'エルシーエル、排出開始。',
 'pa_transfer':'機体の移送を開始します。作業員はレールから離れてください。',
 'pa_ready':'射出台、固定完了。発進待機。',
 'pa_recover':'回収作業を開始します。プラットフォームから離れてください。',
 'pa_return':'機体をケイジへ移送します。',
 'pa_fill':'機体固定。エルシーエル、注入開始。',
 'pa_standby':'機体、待機状態。',
 'pa_fault':'作業を停止しました。担当者は設備を確認してください。',
 'pa_door_open':'ゲートを開きます。周囲から離れてください。',
 'pa_door_close':'ゲートを閉じます。周囲から離れてください。',
 'pa_3':'三。','pa_2':'二。','pa_1':'一。','pa_launch':'発進。',
 'pa_combat_r31':'使徒の反応を確認。第一種戦闘配置。各部署は所定の位置についてください。'
}

def duration(p):
 return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(p)]))

async def generate(language):
 voice,rate,pitch=('ja-JP-NanamiNeural','-4%','-2Hz') if language=='ja' else ('zh-CN-XiaoyiNeural','-6%','-4Hz')
 out=ROOT/'artifacts/rebuild_r45/audio/facility'/language;out.mkdir(parents=True,exist_ok=True);rows=[]
 for name,wording in LINES.items():
  text=JAPANESE[name] if language=='ja' else wording[0]
  raw=out/(name+'.mp3');ogg=out/(name+'.ogg')
  if not raw.exists():await edge_tts.Communicate(text,voice,rate=rate,pitch=pitch).save(str(raw))
  assert raw.stat().st_size>1000
  subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(raw),'-af',
   'silenceremove=start_periods=1:start_threshold=-48dB:start_silence=0.05,areverse,silenceremove=start_periods=1:start_threshold=-48dB:start_silence=0.10,areverse,loudnorm=I=-19:TP=-3:LRA=8',
   '-ar','48000','-ac','1','-c:a','libvorbis','-q:a','6',str(ogg)],check=True)
  seconds=duration(ogg);rows.append(dict(name=name,text=text,subtitle_cn=wording[0],voice=voice,rate=rate,pitch=pitch,
   seconds=seconds,minimum_sequence_ticks=int(seconds*20+.999)+6,sha256=hashlib.sha256(ogg.read_bytes()).hexdigest(),
   source='Original facility wording with standard Microsoft neural voice, no actor voice clone or TV audio',installed=False))
  print(language,name,round(seconds,2),flush=True)
 (out/'sources.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf8')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--language',choices=['ja','zh'],default='ja');a=p.parse_args();asyncio.run(generate(a.language))
