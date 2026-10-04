"""Prepare a new postrun-only source patch; first-session source/input snapshots untouched."""
from pathlib import Path
import difflib,hashlib,json,sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/rebuild_r45/pyramid_components_sol_v1/v5_relog_candidates_v2'
HELPER='''    private static void composedV5Postrun(JsonObject job,Map<String,String> expected) throws Exception
    {
        var reload=job.getAsJsonObject("postrun_reload");
        for(String name:List.of("cold_snapshot","first_binding","first_job","first_native_result","normal_process_exit"))ref(reload.getAsJsonObject(name));
        var cold=read(Path.of(reload.getAsJsonObject("cold_snapshot").get("path").getAsString()));
        var first=read(Path.of(reload.getAsJsonObject("first_native_result").get("path").getAsString()));
        var process=read(Path.of(reload.getAsJsonObject("normal_process_exit").get("path").getAsString()));
        var firstJob=read(Path.of(reload.getAsJsonObject("first_job").get("path").getAsString()));
        var firstBinding=read(Path.of(reload.getAsJsonObject("first_binding").get("path").getAsString()));
        Path world=Path.of(job.get("world").getAsString()).toRealPath();
        if(!"projectseele.v5-component-postrun-cold-epoch.v1".equals(cold.get("schema").getAsString())
                ||!world.equals(Path.of(cold.get("world").getAsString()).toRealPath())
                ||!world.equals(Path.of(firstJob.get("world").getAsString()).toRealPath())
                ||!world.equals(Path.of(firstBinding.get("world").getAsString()).toRealPath())
                ||firstBinding.has("postrun_reload")||!firstBinding.has("composed_source_v5")
                ||!firstJob.get("candidate_binding_sha256").getAsString().equals(reload.getAsJsonObject("first_binding").get("sha256").getAsString())
                ||!first.get("fresh_session_pass").getAsBoolean()||!first.get("actual_actor_restored").getAsBoolean()
                ||!first.get("error").getAsString().isEmpty()||first.get("walk_complete").getAsInt()!=165||first.get("BE_complete").getAsInt()!=17
                ||process.get("process_exit").getAsInt()!=0||process.get("forced_termination").getAsBoolean()
                ||!process.get("process_and_output_gate").getAsBoolean()
                ||!process.get("world").getAsString().equals(job.get("world").getAsString())
                ||!process.get("first_job_sha256").getAsString().equals(reload.getAsJsonObject("first_job").get("sha256").getAsString())
                ||!process.get("first_native_result_sha256").getAsString().equals(reload.getAsJsonObject("first_native_result").get("sha256").getAsString())
                ||!cold.getAsJsonObject("first_native_result").get("sha256").getAsString().equals(reload.getAsJsonObject("first_native_result").get("sha256").getAsString())
                ||!cold.getAsJsonObject("normal_process_exit").get("sha256").getAsString().equals(reload.getAsJsonObject("normal_process_exit").get("sha256").getAsString())
                ||!firstBinding.getAsJsonObject("composed_source_v5").equals(job.getAsJsonObject("composed_source_v5")))
            throw new IllegalStateException("SameQA actual first165/17 normal-exit parent chain required for relog");
        var coldFiles=files(cold.getAsJsonArray("files"));coldFiles.remove("session.lock");
        if(!coldFiles.equals(expected)||!cold.get("source_v5_written").getAsBoolean()==false)
            throw new IllegalStateException("Exact real postrun cold inventory required; no freshcopy relog");
    }

'''
def main():
    assert not OUT.exists();OUT.mkdir();patches=[];summaries=[]
    source=ROOT/'src/main/java/com/projectseele/world/FacilitySourceAdmissionR45.java';raw=source.read_bytes();before=raw.decode('utf8');norm=before.replace('\r\n','\n')
    needle='        if(!expected.equals(copied))throw new IllegalStateException("QA must be an exact fresh copy of actual composedv5; no second overlay");\n';assert norm.count(needle)==1
    after=norm.replace(needle,'        if(job.has("postrun_reload"))composedV5Postrun(job,expected);\n        else if(!expected.equals(copied))throw new IllegalStateException("QA must be an exact fresh copy of actual composedv5; no second overlay");\n',1)
    after=after.replace('    @SubscribeEvent public static void setup(',HELPER+'    @SubscribeEvent public static void setup(',1)
    after=after.replace('!cold.get("source_v5_written").getAsBoolean()==false','cold.get("source_v5_written").getAsBoolean()')
    if raw.count(b'\r\n')==raw.count(b'\n'):after=after.replace('\n','\r\n')
    patches.append((source,before,after))
    source=ROOT/'src/main/java/com/projectseele/client/visual/FacilityComponentReviewR45.java';raw=source.read_bytes();before=raw.decode('utf8');norm=before.replace('\r\n','\n')
    after=norm.replace('    private static String error="";','    private static boolean postrunReload;\n    private static String error="";',1)
    needle='        job=read(Path.of(name));require(job.get("bound").getAsBoolean(),"Component job remains UNBOUND");\n';assert after.count(needle)==1
    after=after.replace(needle,needle+'        var binding=read(Path.of(job.get("candidate_binding").getAsString()));postrunReload=binding.has("postrun_reload");\n        require(postrunReload==job.has("postrun_reload"),"Component reload job differs from admitted binding phase");\n',1)
    old='result.addProperty("full_lifecycle_pass",false);result.addProperty("relog_pass",false);';assert after.count(old)==1
    after=after.replace(old,'result.addProperty("full_lifecycle_pass",false);result.addProperty("relog_pass",postrunReload&&error.isEmpty()&&restored&&walks.size()==165&&entities.size()==17);result.addProperty("phase",postrunReload?"SAME_QA_POSTRUN_RELOG":"FRESH_COMPOSED_V5");result.addProperty("job_sha256",hash(Path.of(System.getProperty("projectseele.r45FacilityComponentsJob"))));result.addProperty("binding_sha256",job.get("candidate_binding_sha256").getAsString());',1)
    after=after.replace('result.addProperty("fresh_session_pass",error.isEmpty()&&restored&&walks.size()==165&&entities.size()==17);','result.addProperty("fresh_session_pass",!postrunReload&&error.isEmpty()&&restored&&walks.size()==165&&entities.size()==17);',1)
    after=after.replace('row.addProperty("relog_pass",false);','row.addProperty("relog_pass",postrunReload);',1)
    if raw.count(b'\r\n')==raw.count(b'\n'):after=after.replace('\n','\r\n')
    patches.append((source,before,after));text=''
    for p,before,after in patches:
        assert before!=after;stem=p.stem;(OUT/(stem+'.before.txt')).write_bytes(before.encode('utf8'));(OUT/(stem+'.candidate.txt')).write_bytes(after.encode('utf8'))
        text+=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/'+p.relative_to(ROOT).as_posix(),tofile='b/'+p.relative_to(ROOT).as_posix()))
        summaries.append(dict(source=str(p),source_before_sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    p=OUT/'root_same_qa_relog_followup.patch';p.write_bytes(text.encode('utf8'))
    (OUT/'prepared_NOT_APPLIED_NOT_COMPILED.json').write_bytes((json.dumps(dict(applied=False,compiled=False,root_sameQA_normal_exit_required=True,requires_actual_first165_BE17_pass=True,first_session_frozen_inputs_changed=False,MainJava_modified=False,world_written=False,Java_MC_started=False,new_native_pass=False,relog_pass=False,scope='Re-run the SAME165/17 after real sameQA relog. Full lift/City/model/multiplayer lifecycle remainsfalse.',source_before=summaries,patch_sha256=hashlib.sha256(p.read_bytes()).hexdigest()),indent=2)+'\n').encode('utf8'))
    print('Prepared2-source postrun relog patch only; first-source/input/world/runtime untouched.',flush=True)
if __name__=='__main__':main()
