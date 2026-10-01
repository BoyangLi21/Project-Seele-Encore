"""Summarise an existing native recording; does not attach, launch or edit settings."""
from pathlib import Path
from collections import Counter, defaultdict
import argparse, hashlib, json, subprocess


def main():
    p=argparse.ArgumentParser();p.add_argument('recording',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--jfr',type=Path,default=Path('C:/Users/liboy/jdks/jdk-17.0.19+10/bin/jfr.exe'));a=p.parse_args()
    assert not a.output.exists(),'Retain earlier profiles and summaries'
    command=[str(a.jfr),'print','--json','--events','jdk.ExecutionSample,jdk.NativeMethodSample,jdk.ThreadCPULoad,jdk.CPULoad',str(a.recording.resolve())]
    response=subprocess.run(command,capture_output=True,text=True,encoding='utf8',check=True)
    events=json.loads(response.stdout)['recording']['events'];threads=defaultdict(Counter);inclusive=defaultdict(Counter);samples=Counter();kinds=Counter();times=[];cpu=[]
    for event in events:
        kind=event['type'];v=event['values'];kinds[kind]+=1
        if 'startTime' in v:times.append(v['startTime'])
        if kind=='jdk.CPULoad':cpu.append(v);continue
        if kind not in {'jdk.ExecutionSample','jdk.NativeMethodSample'}:continue
        thread=v.get('sampledThread') or v.get('eventThread') or {};name=thread.get('javaName',thread.get('osName','unknown'))
        frames=(v.get('stackTrace') or {}).get('frames',[])
        if not frames:continue
        def method(frame):
            m=frame['method'];return m['type']['name'].replace('/','.')+'.'+m['name']
        methods=[method(frame) for frame in frames];samples[name]+=1;threads[name][methods[0]]+=1
        inclusive[name].update(set(methods))
    def table(counts,total):return [dict(method=k,samples=n,sampled_stack_percent=round(100*n/total,2)) for k,n in counts.most_common(25)]
    result=dict(recording=str(a.recording.resolve()),recording_sha256=hashlib.sha256(a.recording.read_bytes()).hexdigest(),
        event_counts=dict(kinds),sample_time_range=[min(times),max(times)] if times else [],
        threads={name:dict(sampled_stacks=n,top_frame=table(threads[name],n),inclusive_stack=table(inclusive[name],n)) for name,n in samples.items()},
        machine_cpu_load=cpu,world_written=False,java_attached=False,visual_or_performance_passed=False,
        limits='Stack counts are statistical CPU samples, not elapsed timing or GPU milliseconds. A render-thread native OpenGL wait can indicate a driver/GPU boundary but does not identify GPU draw cost. Old no-shader/low-distance scenes cannot establish the current three-rig shader bottleneck.',
        current_scene_sampling_contract=['Hold the exact existing three-rig camera, entities, loaded sections, renderDistance14, maxFps120 and vsyncfalse; no witness export or Blender workload during capture.',
            'Record camera/actual FPS/frame times, server tick times, loaded chunks/entities, source/frozen resource hashes and shader identity in the same time window.',
            'Use root-owned PID jcmd JFR 20s for CPU stacks with current scene, one shader run and one no-shader run; do not restart a second Minecraft or reduce quality as diagnosis.',
            'Collect synchronized NVIDIA GPU utilization/clock/power/memory and per-process Windows GPU engine counters while the camera is stable. GPU busy plus render native waits is an inference requiring GPU timer-query/draw-pass timings to identify the actual costly pass.',
            'If GPU-bound, root-owned GPU GL_TIME_ELAPSED timing should bracket world terrain, shadows, entity meshes and translucent LCL on one consistent frame and resolve queries asynchronously. Never force glFinish or synchronous query waits during the measured render.',
            'If CPU-bound, inspect the new render/server JFR stacks, separate world generation from entity/mesh/driver submission, and profile the same resource dispatch before changing it.'])
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print(a.recording.parent.name,dict(samples))
    for name in ('Render thread','Server thread'):
        if name in samples:print(name,threads[name].most_common(6))


if __name__=='__main__':main()
