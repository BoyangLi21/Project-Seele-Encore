"""Generate a bounded FPS/JFR diagnostic from the existing actual210 input driver.

No app/World/QA mutation. The generated agent only instruments Minecraft and
GameRenderer; it does not instrument EvaPoseGraph, sample bones/feet, take a
screenshot, or change the model/collision/rendering implementation.
"""
from pathlib import Path
import argparse,hashlib,json,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[1]
JDK=Path('C:/Users/liboy/jdks/jdk-17.0.19+10/bin')
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();out=a.out.resolve()
    assert out.is_relative_to(ROOT/'.Codex') and not out.exists();out.mkdir(parents=True);(out/'classes').mkdir()
    original=ROOT/'tools/java/C10HandlingR52Agent.java';source=original.read_text();source=source.replace('C10HandlingR52Agent','C11FpsOnlyR52Agent')
    source=source.replace('"net/minecraft/client/renderer/GameRenderer","com/projectseele/client/render/EvaPoseGraph"','"net/minecraft/client/renderer/GameRenderer"')
    source=source.replace(',c("com.projectseele.client.render.EvaPoseGraph")','')
    insert='''
    private static long perfStart,perfPrevious,perfSample;
    private static final java.util.ArrayList<Long> perfIntervals=new java.util.ArrayList<>();
    private static final java.util.ArrayList<Integer> perfFps=new java.util.ArrayList<>();
    private static boolean perfScriptComplete;
    private static void perfSummary()throws Exception {
        var sorted=new java.util.ArrayList<>(perfIntervals);java.util.Collections.sort(sorted);
        var fps=new java.util.ArrayList<>(perfFps);java.util.Collections.sort(fps);
        var r=new java.util.LinkedHashMap<String,Object>();r.put("diagnostic_only",true);r.put("screenshots",0);r.put("bone_or_foot_samples",0);r.put("production_classes_replaced",false);
        r.put("input_ticks",210);r.put("input_complete",perfScriptComplete);r.put("wall_seconds",(System.nanoTime()-perfStart)/1e9);r.put("render_callbacks",frame);r.put("fps_samples",fps.size());
        if(!fps.isEmpty()){r.put("fps_min",fps.get(0));r.put("fps_median",fps.get(fps.size()/2));r.put("fps_max",fps.get(fps.size()-1));}
        if(!sorted.isEmpty()){r.put("frame_p50_ms",sorted.get(sorted.size()/2)/1e6);r.put("frame_p95_ms",sorted.get((int)Math.floor((sorted.size()-1)*.95))/1e6);r.put("frame_p99_ms",sorted.get((int)Math.floor((sorted.size()-1)*.99))/1e6);}
        r.put("same_frame_pixel_or_support_acceptance",false);write("FPS_ONLY_SUMMARY.json",r);
    }
'''
    source=source.replace('    private static void renderEnd()throws Exception {',insert+'    private static void renderEnd()throws Exception {',1)
    start=source.index('    private static void renderEnd()throws Exception {');end=source.index('    private static void finish()throws Exception {',start)
    source=source[:start]+'''    private static void renderEnd()throws Exception {
        if(!ready||done||failed||age<0)return;
        long now=System.nanoTime();if(perfStart==0){perfStart=now;write("FPS_PROFILE_READY.json",java.util.Map.of("wall_ns",now,"age",age,"diagnostic_only",true));}
        if(perfPrevious!=0)perfIntervals.add(now-perfPrevious);perfPrevious=now;frame++;
        if(now-perfSample>=1_000_000_000L){int fps=((Number)call(mc,new String[]{"getFps","m_260875_"},new Class<?>[0])).intValue();perfFps.add(fps);append(frames,java.util.Map.of("wall_ns",now,"age",age,"fps",fps,"render_callbacks",frame,"diagnostic_only",true));perfSample=now;}
        if(perfScriptComplete&&now-perfStart>=60_000_000_000L)finish();
    }
'''+source[end:]
    source=source.replace('    private static void finish()throws Exception {','''    private static void finish()throws Exception {
        perfScriptComplete=true;if(perfStart==0||System.nanoTime()-perfStart<60_000_000_000L)return;
        perfSummary();
''',1)
    assert 'List.of(c("net.minecraft.client.Minecraft"),c("net.minecraft.client.renderer.GameRenderer"))' in source
    target=out/'C11FpsOnlyR52Agent.java';target.write_text(source,encoding='utf8')
    cp_arg=(ROOT/'.Codex/r52_runtime_close/jar_resource_streaming/compile.args').read_text().splitlines();cp=cp_arg[cp_arg.index('"-cp"')+1].strip('"')
    compile_args=out/'compile.args';compile_args.write_text('\n'.join('"'+s+'"' for s in ['-encoding','UTF-8','-proc:none','-cp',cp,'-d',(out/'classes').as_posix(),target.as_posix()]))
    subprocess.run([str(JDK/'javac.exe'),'-J-Xmx128m','@'+str(compile_args)],cwd=ROOT,check=True)
    jar=out/'fps_only_agent.jar'
    with zipfile.ZipFile(jar,'x',zipfile.ZIP_DEFLATED) as z:
        z.writestr('META-INF/MANIFEST.MF','Manifest-Version: 1.0\nAgent-Class: C11FpsOnlyR52Agent\nCan-Retransform-Classes: true\nCan-Redefine-Classes: true\n\n')
        for p in (out/'classes').rglob('*.class'):z.write(p,p.relative_to(out/'classes').as_posix())
    receipt={'diagnostic_only':True,'world_written':False,'game_started':False,'compile_heap_mb':128,'original_driver':str(original),'original_driver_sha256':sha(original),'generated_source':str(target),'generated_source_sha256':sha(target),'agent':str(jar),'agent_sha256':sha(jar),'instrumented_classes':['net.minecraft.client.Minecraft','net.minecraft.client.renderer.GameRenderer'],'bone_or_foot_samples':0,'screenshots':0,'rendering_or_collision_disabled':False,'input_driver':'Original unit1 handling210 then held camera/idle until60s wall; normal cleanup and quit.','jfr':'Start profile once FPS_PROFILE_READY.json appears; filename exact out/control.jfr; dump on normal exit.'}
    (out/'PREPARED.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
if __name__=='__main__':main()
