"""Short, neutral facility PA. Original wording; no character/actor voice cloning."""
from pathlib import Path
import asyncio
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/dialogue_audio_r31'
ASSET = ROOT / 'src/main/resources/assets/projectseele'
sys.path.insert(0, str(ROOT / '.Codex/audio-runtime'))
import edge_tts

# Subtitle spelling can retain technical identifiers; synthesis uses their spoken form.
LINES = {
    'pa_prepare': ('准备出击。登机桥收回。', 'Sortie preparation. Boarding bridge retracting.'),
    'pa_insert': ('插入栓接入。', 'Entry plug inserting.'),
    'pa_lock': ('插入栓锁定。', 'Entry plug locked.'),
    'pa_drain': ('开始排液。', 'Draining coolant.'),
    'pa_transfer': ('机体转移。请离开轨道。', 'Unit transfer. Clear the track.'),
    'pa_ready': ('弹射器锁定。等待发射。', 'Catapult locked. Awaiting launch.'),
    'pa_recover': ('开始回收。请离开平台。', 'Recovery commencing. Clear the platform.'),
    'pa_return': ('机体返回机库。', 'Unit returning to the cage.'),
    'pa_fill': ('机体固定。开始注液。', 'Unit secured. Filling coolant.'),
    'pa_standby': ('机体进入待机。', 'Unit on standby.'),
    'pa_fault': ('作业暂停。请检修人员到场。', 'Operation paused. Maintenance crew required.'),
    'pa_door_open': ('舱门开启。请保持距离。', 'Door opening. Stand clear.'),
    'pa_door_close': ('舱门关闭。请保持距离。', 'Door closing. Stand clear.'),
    'pa_3': ('三。', 'Three.'), 'pa_2': ('二。', 'Two.'), 'pa_1': ('一。', 'One.'),
    'pa_launch': ('发射。', 'Launch.'),
    'pa_combat_r31': ('第一种战斗配置。全员就位。', 'Battle stations. All personnel to assigned posts.'),
}

def ffmpeg(*args):
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', *map(str, args)], check=True)

def duration(path):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', str(path)]))

async def synthesize():
    semaphore = asyncio.Semaphore(2)
    async def line(name, text):
        path = OUT / (name + '.mp3')
        if path.is_file() and path.stat().st_size > 1000:
            return
        async with semaphore:
            for attempt in range(3):
                try:
                    await edge_tts.Communicate(text, 'zh-CN-XiaoxiaoNeural', rate='+2%', pitch='-2Hz').save(str(path))
                    print('Synthesized', name, flush=True)
                    return
                except Exception:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(1 + attempt)
    await asyncio.gather(*(line(name, wording[0]) for name, wording in LINES.items()))

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    asyncio.run(synthesize())
    rows = []
    for name, (text, english) in LINES.items():
        target = ASSET / 'sounds' / (name + '.ogg')
        trim = 'silenceremove=start_periods=1:start_threshold=-48dB:start_silence=0.045,areverse,silenceremove=start_periods=1:start_threshold=-48dB:start_silence=0.12,areverse'
        # Retain the natural prosody. Avoid the old forced atempo speed-up and
        # hard radio filtering that made voices sharp and synthetic.
        ffmpeg('-i', OUT / (name + '.mp3'), '-af', trim + ',highpass=f=90,lowpass=f=9500,loudnorm=I=-20:TP=-3:LRA=8', '-ar', 48000, '-ac', 1, '-c:a', 'libvorbis', '-q:a', 5, target)
        seconds = duration(target)
        if name in ('pa_1', 'pa_2', 'pa_3'):
            assert seconds < .95, (name, seconds)
        rows.append(dict(name=name, text=text, voice='zh-CN-XiaoxiaoNeural', rate='+2%', pitch='-2Hz', seconds=seconds,
                         sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                         source='Original project facility announcement. Standard Microsoft voice via edge-tts. No character voice or TV audio.',
                         reference='https://learn.microsoft.com/azure/ai-services/speech-service/language-support?tabs=tts'))
    events_path = ASSET / 'sounds.json'
    events = json.loads(events_path.read_text(encoding='utf8'))
    for name in LINES:
        events[name] = dict(subtitle='subtitles.projectseele.' + name,
                            sounds=[dict(name='projectseele:' + name, attenuation_distance=160)])
    events_path.write_text(json.dumps(events, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    for code, offset in (('zh_cn', 0), ('en_us', 1)):
        path = ASSET / 'lang' / (code + '.json')
        data = json.loads(path.read_text(encoding='utf8'))
        for name, wording in LINES.items():
            data['subtitles.projectseele.' + name] = wording[offset]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    (OUT / 'sources.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    ticks = {row['name']: int(row['seconds'] * 20 + .999) + 6 for row in rows}
    (OUT / 'voice_ticks.json').write_text(json.dumps(ticks, indent=2) + '\n', encoding='utf8')
    names = ('pa_prepare', 'pa_insert', 'pa_lock', 'pa_transfer', 'pa_combat_r31')
    inputs = [arg for name in names for arg in ('-i', ASSET / 'sounds' / (name + '.ogg'))]
    filters = ';'.join(f'[{i}:a]apad=pad_dur=0.65[a{i}]' for i in range(len(names)))
    filters += ';' + ''.join(f'[a{i}]' for i in range(len(names))) + f'concat=n={len(names)}:v=0:a=1[out]'
    ffmpeg(*inputs, '-filter_complex', filters, '-map', '[out]', '-c:a', 'libmp3lame', '-q:a', 3, OUT / 'facility_pa_sample.mp3')
    print(json.dumps(ticks), flush=True)

if __name__ == '__main__':
    raise SystemExit('R31 asset writer retired: use build_facility_voice_r45.py for candidates, then install_facility_audio_r45.py for the selected frozen voice and measured timing. This old writer would overwrite the R45 assets.')
