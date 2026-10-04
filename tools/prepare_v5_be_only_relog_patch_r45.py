"""Exact sign-JSON comparison + sameQA BE-only recheck; artifact patches only."""
from pathlib import Path
import copy,difflib,gzip,hashlib,json,sys
sys.dont_write_bytecode=True
import nbtlib
ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r45';OUT=ART/'pyramid_components_sol_v1/v5_BE_only_relog_v1'
ADMISSION='''    private static void composedV5BePostrun(JsonObject job,Map<String,String> expected) throws Exception
    {
        var parent=job.getAsJsonObject("postrun_BE_recheck");
        for(String name:List.of("cold_snapshot","walk_binding","walk_job","walk_receipt","normal_process_exit"))ref(parent.getAsJsonObject(name));
        var cold=read(Path.of(parent.getAsJsonObject("cold_snapshot").get("path").getAsString()));
        var walk=read(Path.of(parent.getAsJsonObject("walk_receipt").get("path").getAsString()));
        var oldJob=read(Path.of(parent.getAsJsonObject("walk_job").get("path").getAsString()));
        var oldBinding=read(Path.of(parent.getAsJsonObject("walk_binding").get("path").getAsString()));
        var exit=read(Path.of(parent.getAsJsonObject("normal_process_exit").get("path").getAsString()));
        Path world=Path.of(job.get("world").getAsString()).toRealPath();
        if(!"projectseele.v5-BE-postrun-cold-epoch.v1".equals(cold.get("schema").getAsString())
                ||!world.equals(Path.of(cold.get("world").getAsString()).toRealPath())
                ||!world.equals(Path.of(oldJob.get("world").getAsString()).toRealPath())
                ||!world.equals(Path.of(oldBinding.get("world").getAsString()).toRealPath())
                ||!oldBinding.has("composed_source_v5")||oldBinding.has("postrun_BE_recheck")
                ||!oldBinding.getAsJsonObject("composed_source_v5").equals(job.getAsJsonObject("composed_source_v5"))
                ||!oldJob.get("candidate_binding_sha256").getAsString().equals(parent.getAsJsonObject("walk_binding").get("sha256").getAsString())
                ||walk.get("walk_complete").getAsInt()!=165||walk.getAsJsonArray("walk_cases").size()!=165
                ||!walk.get("actual_actor_restored").getAsBoolean()
                ||exit.get("process_exit").getAsInt()!=0||exit.get("forced_termination").getAsBoolean()
                ||!exit.get("walk_scope_pass").getAsBoolean()
                ||!exit.get("walk_receipt_sha256").getAsString().equals(parent.getAsJsonObject("walk_receipt").get("sha256").getAsString())
                ||!cold.getAsJsonObject("walk_receipt").get("sha256").getAsString().equals(parent.getAsJsonObject("walk_receipt").get("sha256").getAsString())
                ||!cold.getAsJsonObject("normal_process_exit").get("sha256").getAsString().equals(parent.getAsJsonObject("normal_process_exit").get("sha256").getAsString())
                ||cold.get("source_v5_written").getAsBoolean())throw new IllegalStateException("SameQA165-walk normal-exit parent required; BE need not already pass");
        ref(oldJob.getAsJsonObject("walk_inputs"));var planned=read(Path.of(oldJob.getAsJsonObject("walk_inputs").get("path").getAsString())).getAsJsonArray("cases");
        var plannedIds=new HashSet<String>();for(var raw:planned)plannedIds.add(raw.getAsJsonObject().get("id").getAsString());
        var actualIds=new HashSet<String>();for(var raw:walk.getAsJsonArray("walk_cases"))
        {var row=raw.getAsJsonObject();if(!row.get("passed").getAsBoolean()||!actualIds.add(row.get("id").getAsString()))throw new IllegalStateException("Walk inheritance contains failed/duplicate cases");}
        if(plannedIds.size()!=165||!plannedIds.equals(actualIds))throw new IllegalStateException("Complete same165 physical walk inheritance required");
        var files=files(cold.getAsJsonArray("files"));files.remove("session.lock");
        if(!files.equals(expected))throw new IllegalStateException("Exact actual sameQA postrun cold inventory required; freshcopy is not relog");
    }

'''
SIGN='''    private static boolean retainedPayloadEqual(CompoundTag wanted,CompoundTag actual,net.minecraft.world.level.block.state.BlockState state)
    {
        CompoundTag normalized=wanted.copy();
        if(state.getBlock() instanceof net.minecraft.world.level.block.SignBlock
                &&wanted.getString("id").equals("minecraft:sign")&&actual.getString("id").equals("minecraft:sign"))
        {
            for(String side:List.of("front_text","back_text"))
            {
                if(wanted.contains(side,Tag.TAG_COMPOUND)!=actual.contains(side,Tag.TAG_COMPOUND))return false;
                if(!wanted.contains(side,Tag.TAG_COMPOUND))continue;
                for(String field:List.of("messages","filtered_messages"))
                {
                    var before=wanted.getCompound(side);var after=actual.getCompound(side);
                    if(before.contains(field,Tag.TAG_LIST)!=after.contains(field,Tag.TAG_LIST))return false;
                    if(!before.contains(field,Tag.TAG_LIST))continue;
                    ListTag left=before.getList(field,Tag.TAG_STRING),right=after.getList(field,Tag.TAG_STRING);
                    if(left.size()!=right.size())return false;
                    ListTag same=new ListTag();
                    for(int i=0;i<left.size();i++)
                    {
                        // Only component JSON trees. No text/style/clickEvent,
                        // array order, side, waxing or other typedNBT waiver.
                        if(!JsonParser.parseString(left.getString(i)).equals(JsonParser.parseString(right.getString(i))))return false;
                        same.add(StringTag.valueOf(right.getString(i)));
                    }
                    normalized.getCompound(side).put(field,same);
                }
            }
        }
        return normalized.equals(actual);
    }
'''
def main():
    assert not OUT.exists();OUT.mkdir();patches=[]
    p=ROOT/'src/main/java/com/projectseele/world/FacilitySourceAdmissionR45.java';raw=p.read_bytes();before=raw.decode('utf8');text=before.replace('\r\n','\n')
    old='        if(!expected.equals(copied))throw new IllegalStateException("QA must be an exact fresh copy of actual composedv5; no second overlay");\n';assert text.count(old)==1
    text=text.replace(old,'        if(job.has("postrun_BE_recheck"))composedV5BePostrun(job,expected);\n        else if(!expected.equals(copied))throw new IllegalStateException("QA must be an exact fresh copy of actual composedv5; no second overlay");\n',1)
    text=text.replace('    @SubscribeEvent public static void setup(',ADMISSION+'    @SubscribeEvent public static void setup(',1)
    if raw.count(b'\r\n')==raw.count(b'\n'):text=text.replace('\n','\r\n')
    patches.append((p,before,text))
    p=ROOT/'src/main/java/com/projectseele/client/visual/FacilityComponentReviewR45.java';raw=p.read_bytes();before=raw.decode('utf8');text=before.replace('\r\n','\n')
    text=text.replace('    private static String error="";','    private static boolean BEonlyRecheck;\n    private static String error="";',1)
    old='        require(FacilitySourceAdmissionR45.admit(active,walkJob)&&FacilitySourceAdmissionR45.admit(active,beJob),"Current composedv5 admission required");\n';assert text.count(old)==1
    text=text.replace(old,'''        BEonlyRecheck=job.has("BE_only_recheck")&&job.get("BE_only_recheck").getAsBoolean();
        var admitted=read(Path.of(job.get("candidate_binding").getAsString()));
        require(BEonlyRecheck==admitted.has("postrun_BE_recheck"),"BE-only phase differs from actual admitted postrun binding");
        require(FacilitySourceAdmissionR45.admit(active,beJob)&& (BEonlyRecheck||FacilitySourceAdmissionR45.admit(active,walkJob)),"Current composedv5 admission required");
''',1)
    old='        require(cases.size()==165&&beCases.size()==17,"Complete fixedv5165/17 input set required");\n';assert text.count(old)==1
    text=text.replace(old,old+'        if(BEonlyRecheck)index=cases.size(); // execute0walk; inherit only the explicitly admitted165 receipt\n',1)
    old='            require(wanted.equals(actual),"Actual loaded BE full payload differs: "+at+" actual="+actual);\n';assert text.count(old)==1
    text=text.replace(old,'            require(retainedPayloadEqual(wanted,actual,state),"Actual loaded BE full payload differs: "+at+" actual="+actual);\n',1)
    text=text.replace('    private static void lease(ServerLevel level,ChunkPos at)\n',SIGN+'    private static void lease(ServerLevel level,ChunkPos at)\n',1)
    text=text.replace('row.addProperty("relog_pass",false);','row.addProperty("relog_pass",BEonlyRecheck);',1)
    text=text.replace('result.addProperty("walk_required",165);','result.addProperty("walk_required",BEonlyRecheck?0:165);',1)
    text=text.replace('result.addProperty("fresh_session_pass",error.isEmpty()&&restored&&walks.size()==165&&entities.size()==17);','result.addProperty("fresh_session_pass",!BEonlyRecheck&&error.isEmpty()&&restored&&walks.size()==165&&entities.size()==17);',1)
    old='result.addProperty("relog_pass",false);';assert text.count(old)==1
    text=text.replace(old,'result.addProperty("relog_pass",BEonlyRecheck&&error.isEmpty()&&restored&&walks.size()==0&&entities.size()==17);result.addProperty("walk_executed_this_run",walks.size());result.addProperty("walk_inherited",BEonlyRecheck?165:0);if(BEonlyRecheck)result.add("walk_inheritance",job.getAsJsonObject("walk_inheritance"));result.addProperty("phase",BEonlyRecheck?"SAME_QA_BE_ONLY_RELOG":"FRESH_COMPOSED_V5");',1)
    if raw.count(b'\r\n')==raw.count(b'\n'):text=text.replace('\n','\r\n')
    patches.append((p,before,text));combined=''
    for p,before,after in patches:
        assert before!=after;(OUT/(p.stem+'.before.txt')).write_bytes(before.encode('utf8'));(OUT/(p.stem+'.candidate.txt')).write_bytes(after.encode('utf8'))
        combined+=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/'+p.relative_to(ROOT).as_posix(),tofile='b/'+p.relative_to(ROOT).as_posix()))
    patch=OUT/'root_sign_JSON_only_and_sameQA_BE_relog.patch';patch.write_bytes(combined.encode('utf8'))
    # Actual failed payload and negative controls: no other NBT field waived.
    first=read_json(ART/'native_facility_session_v1/native_components_v5_third_v1/components165_BE17.native.json');planned=read_json(ART/'pyramid_components_sol_v1/v5_native_entry_preparation_v1/BE9_and_replacements8.UNBOUND.json')['cases'][9]
    expected=nbtlib.parse_nbt(planned['expected_full_nbt']);actual=nbtlib.parse_nbt(first['error'].split(' actual=',1)[1])
    def equal(a,b):
        a=copy.deepcopy(a);b=copy.deepcopy(b)
        for side in ('front_text','back_text'):
            for field in ('messages','filtered_messages'):
                if(field in a[side])!=(field in b[side]):return False
                if field not in a[side]:continue
                left,right=a[side][field],b[side][field]
                if len(left)!=len(right)or any(json.loads(str(x))!=json.loads(str(y))for x,y in zip(left,right)):return False
                a[side][field]=copy.deepcopy(right)
        return a==b
    assert equal(expected,actual);neg=[]
    for name,change in [('wax',lambda b:b.__setitem__('is_waxed',nbtlib.Byte(0))),('coord',lambda b:b.__setitem__('x',nbtlib.Int(-1952))),('color',lambda b:b['front_text'].__setitem__('color',nbtlib.String('red'))),('text',lambda b:b['front_text']['messages'].__setitem__(0,nbtlib.String('{"text":"different"}'))),('clickEvent',lambda b:b['front_text']['messages'].__setitem__(0,nbtlib.String('{"text":"西坂旅館","clickEvent":{"action":"run_command","value":"wrong"}}')))]:
        changed=copy.deepcopy(actual);change(changed);assert not equal(expected,changed);neg.append(name)
    result=dict(actual_source_messages_JSON_trees_equal=True,all_other_typedNBT_exact=True,negative_changes_rejected=neg,actual_third_walk165_inherited_only=True,walk_this_BE_recheck0=True,BE_this_recheck17=True,third_overall_session_not_pass=True,requires_sameQA_actual_postrun_cold_and_normal_exit=True,MainJava_modified=False,world_written=False,compiled=False,MC_started=False,relog_pass=False,patch_sha256=hashlib.sha256(patch.read_bytes()).hexdigest())
    (OUT/'actual_sign_equivalence_and_negative_controls.json').write_bytes((json.dumps(result,indent=2)+'\n').encode('utf8'));print(json.dumps(result,indent=2))
def read_json(p):return json.loads(Path(p).read_text('utf8'))
if __name__=='__main__':main()
