from pathlib import Path
import json,hashlib,difflib
R=Path('D:/eva');O=R/'artifacts/rebuild_r45/lifts_doors_lifecycle_sol_v2/command17_first_contact_postrun_job_v2';O.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
write=lambda p,d:Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
patch=[]
def save(rel,s,t):
 p=R/rel;name=p.name
 (O/(name+'.before.txt')).write_bytes(p.read_bytes());(O/(name+'.candidate.txt')).write_text(t,encoding='utf8')
 patch.extend(difflib.unified_diff(s.splitlines(True),t.splitlines(True),fromfile='a/'+rel,tofile='b/'+rel))
 return {'source':str(p),'before_sha256':sha(p),'candidate_sha256':sha(O/(name+'.candidate.txt'))}
rel='src/main/java/com/projectseele/world/FacilitySourceAdmissionR45.java';s=(R/rel).read_text('utf8');t=s.replace('private static volatile boolean ready;','private static volatile boolean ready,id6Postrun;')
a='var fresh=new TreeMap<String,String>(source);fresh.remove("session.lock");if(job.has("postrun_BE_recheck")||!fresh.equals(expected))throw new IllegalStateException("Actual fresh v13 copy required; no consumed QA progress");'
b='var fresh=new TreeMap<String,String>(source);fresh.remove("session.lock");\n        if(job.has("postrun_ID6_first_contact"))id6RestoredPostrun(job,expected);\n        else if(job.has("postrun_BE_recheck")||!fresh.equals(expected))throw new IllegalStateException("Actual fresh v13 copy required; no consumed QA progress");'
assert t.count(a)==1;t=t.replace(a,b)
method='''    private static void id6RestoredPostrun(JsonObject job,Map<String,String> expected) throws Exception
    {
        var parent=job.getAsJsonObject("postrun_ID6_first_contact");
        for(String key:List.of("cold_snapshot","parent_binding","parent_job","parent_admission","parent_result"))ref(parent.getAsJsonObject(key));
        var cold=read(Path.of(parent.getAsJsonObject("cold_snapshot").get("path").getAsString()));
        var oldBinding=read(Path.of(parent.getAsJsonObject("parent_binding").get("path").getAsString()));
        var oldJob=read(Path.of(parent.getAsJsonObject("parent_job").get("path").getAsString()));
        var admission=read(Path.of(parent.getAsJsonObject("parent_admission").get("path").getAsString()));
        var result=read(Path.of(parent.getAsJsonObject("parent_result").get("path").getAsString()));
        Path world=Path.of(job.get("world").getAsString()).toRealPath();
        if(!"projectseele.ID6-restored-postrun-first-contact.v1".equals(cold.get("schema").getAsString())
                ||!world.equals(Path.of(cold.get("world").getAsString()).toRealPath())||cold.get("file_count").getAsInt()!=1739
                ||!cold.get("parent_root_actual_exit0").getAsBoolean()||!cold.get("parent_restored").getAsBoolean()
                ||!world.equals(Path.of(oldBinding.get("world").getAsString()).toRealPath())||!world.equals(Path.of(oldJob.get("world").getAsString()).toRealPath())
                ||oldBinding.has("postrun_ID6_first_contact")||!oldBinding.getAsJsonObject("composed_source_v13").equals(job.getAsJsonObject("composed_source_v13"))
                ||!oldJob.get("candidate_binding_sha256").getAsString().equals(parent.getAsJsonObject("parent_binding").get("sha256").getAsString())
                ||!oldJob.get("short_art_preview_v13").equals(job.get("photo_views"))
                ||!admission.get("passed").getAsBoolean()||!admission.get("binding_sha256").getAsString().equals(parent.getAsJsonObject("parent_binding").get("sha256").getAsString())
                ||!"projectseele.command17-actual-native-receipt.v1".equals(result.get("schema").getAsString())||!result.get("actual_actor_restored").getAsBoolean()
                ||!result.get("original_snapshot_captured").getAsBoolean()||result.get("required_cases").getAsInt()!=1||result.get("completed_cases").getAsInt()!=0
                ||!"cross/6/lane1/from-1".equals(result.getAsJsonObject("first_failure").getAsJsonObject("current_input").get("id").getAsString())
                ||!"WALK".equals(result.getAsJsonObject("first_failure").get("phase").getAsString())
                ||job.getAsJsonArray("active_scopes").size()!=1||!"COMMAND17".equals(job.getAsJsonArray("active_scopes").get(0).getAsString()))
            throw new IllegalStateException("Only actual restored ID6 failed-lane sameQA diagnostic is admitted");
        for(String key:List.of("parent_binding","parent_admission","parent_result"))if(!cold.getAsJsonObject(key).equals(parent.getAsJsonObject(key)))throw new IllegalStateException("Different ID6 cold parent receipt");
        var files=files(cold.getAsJsonArray("files"));files.remove("session.lock");
        if(!files.equals(expected))throw new IllegalStateException("Exact1739 restored ID6 postrun inventory required");
    }

'''
needle='    private static void composedV11Source';assert t.count(needle)==1;t=t.replace(needle,method+needle)
t=t.replace('admittedWorld=world;admittedBinding=binding;', 'id6Postrun=job.has("postrun_ID6_first_contact");admittedWorld=world;admittedBinding=binding;')
a='||!job.get("candidate_binding_sha256").getAsString().equals(admittedHash)||!scopes.contains(job.get("facility_scope").getAsString()))';b='||!job.get("candidate_binding_sha256").getAsString().equals(admittedHash)||!scopes.contains(job.get("facility_scope").getAsString())\n                    ||id6Postrun&&(!job.has("first_contact_diagnostic")||!job.get("first_contact_diagnostic").getAsBoolean()||!"COMMAND17".equals(job.get("facility_scope").getAsString())))';assert t.count(a)==1;t=t.replace(a,b)
proofs=[save(rel,s,t)]
rel='src/main/java/com/projectseele/client/visual/CommandDoorInteractionReviewR45.java';s=(R/rel).read_text('utf8');t=s.replace('private static boolean shortArt;','private static boolean shortArt,firstContact;\n    private static long firstContactScopeStart=-1;')
t=t.replace('if(shortArt&&!phase.equals("CAR_DONE"))','if(shortArt&&!firstContact&&!phase.equals("CAR_DONE"))')
t=t.replace('if(shortArt&&artPhotos.size()==0)','if(shortArt&&!firstContact&&artPhotos.size()==0)').replace('if(shortArt&&artPhotos.size()==1)','if(shortArt&&!firstContact&&artPhotos.size()==1)')
a='require(++caseAge<5000,"Actual COMMAND17 case timed out: "+current.get("id")+" phase="+phase);';b=a+'\n            if(firstContact&&firstContactScopeStart>=0)require(level.getGameTime()-firstContactScopeStart<160,"First-contact scope ended at160 actual server gameTicks: "+phase);';assert t.count(a)==1;t=t.replace(a,b)
a='if(++ackTicks<3)return;bearing(p);phase="CLOSED";return;';b='if(++ackTicks<3)return;bearing(p);if(firstContact)firstContactScopeStart=level.getGameTime();phase="CLOSED";return;';assert t.count(a)==1;t=t.replace(a,b)
a='Path world=p.server.getWorldPath(LevelResource.ROOT).toRealPath();require(hash(world.resolve';b='firstContact=job.has("first_contact_diagnostic")&&job.get("first_contact_diagnostic").getAsBoolean();\n        require(!firstContact||shortArt,"First-contact diagnostic requires the one actual failed ID6 lane selection");\n        Path world=p.server.getWorldPath(LevelResource.ROOT).toRealPath();require(hash(world.resolve';assert t.count(a)==1;t=t.replace(a,b)
t=t.replace('r.addProperty("cabin_inspection_teleport_only_no_lift_trip",shortArt);','r.addProperty("first_contact_diagnostic",firstContact);r.addProperty("first_contact_scope_start_actual_gameTime",firstContactScopeStart);r.addProperty("first_contact_scope_limit_actual_gameTicks",firstContact?160:0);r.addProperty("cabin_inspection_teleport_only_no_lift_trip",shortArt&&!firstContact);')
t=t.replace('r.addProperty("requested_three_images_captured",shortArt&&','r.addProperty("requested_three_images_captured",shortArt&&!firstContact&&')
proofs.append(save(rel,s,t))
(O/'root_sameQA_ID6_no_photos_addendum.patch').write_text(''.join(patch),encoding='utf8')
write(O/'source_patch_receipt.json',{'source_preimages':proofs,'patch_sha256':sha(O/'root_sameQA_ID6_no_photos_addendum.patch'),'shared_Java_written':False,'Java_world_started_or_written':False,'normal_production_unchanged':True,'scope':'Only restored postrun short ID6, no art capture, max160 actual server ticks after staging ready'})
print(O)
