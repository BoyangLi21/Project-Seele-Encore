"""Prepare one existing-admission source patch; never edit Java sources/worlds."""
from pathlib import Path
import difflib,hashlib,json,sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/rebuild_r45/pyramid_components_sol_v1/v5_native_entry_preparation_v1/admission_candidate_v2';SOURCE=ROOT/'src/main/java/com/projectseele/world/FacilitySourceAdmissionR45.java'
HELPER='''    private static Map<String,String> objectFiles(JsonObject object)
    {
        var rows=new JsonArray();for(var entry:object.entrySet())
        {var row=new JsonObject();row.addProperty("relative",entry.getKey());row.addProperty("sha256",entry.getValue().getAsString());rows.add(row);}
        return files(rows);
    }
    private static void composedV5Source(JsonObject job,Path sourceWorld,Map<String,String> source,Map<String,String> expected) throws Exception
    {
        var origin=job.getAsJsonObject("composed_source_v5");
        for(String name:List.of("composition","actual_readback","original_baseline","catalog"))ref(origin.getAsJsonObject(name));
        var composition=read(Path.of(origin.getAsJsonObject("composition").get("path").getAsString()));
        var actual=read(Path.of(origin.getAsJsonObject("actual_readback").get("path").getAsString()));
        var original=read(Path.of(origin.getAsJsonObject("original_baseline").get("path").getAsString()));
        var originalFiles=files(original.getAsJsonArray("files"));
        if(!"projectseele.v5-exact-readback.v1".equals(actual.get("schema").getAsString())
                ||!sourceWorld.equals(Path.of(composition.get("world").getAsString()).toRealPath())
                ||!sourceWorld.equals(Path.of(actual.get("world").getAsString()).toRealPath())
                ||!Path.of(original.get("source_world").getAsString()).toRealPath().equals(Path.of(composition.get("original_source").getAsString()).toRealPath())
                ||!actual.get("source1736_unchanged").getAsBoolean()
                ||!actual.get("actual_replacement_fixtures8_full_state_NBT_preserved").getAsBoolean()
                ||actual.get("counts").getAsJsonObject().get("rows").getAsInt()!=631
                ||actual.get("counts").getAsJsonObject().get("before_BE").getAsInt()-actual.get("counts").getAsJsonObject().get("after_BE").getAsInt()!=8
                ||!source.equals(objectFiles(actual.getAsJsonObject("full_after_inventory")))
                ||!actual.get("catalog_sha256").getAsString().equals(origin.getAsJsonObject("catalog").get("sha256").getAsString()))
            throw new IllegalStateException("Actual Root631 composed source/readback required");
        var components=new HashSet<String>();for(var item:composition.getAsJsonArray("selected_components"))components.add(item.getAsString());
        if(!components.equals(Set.of("registered_stairs243","middle_waiting354","retired_fixture_be8","route_sign_be1","device_physical25")))throw new IllegalStateException("Different complete component composition");
        var changed=new HashSet<String>();int cells=0;
        for(String group:List.of("regions","files"))for(var raw:composition.getAsJsonArray(group))
        {
            var row=raw.getAsJsonObject();String name=row.get("target").getAsString();
            if(!changed.add(name)||!originalFiles.containsKey(name)||!row.get("before_sha256").getAsString().equals(originalFiles.get(name))
                    ||!row.get("after_sha256").getAsString().equals(source.get(name)))throw new IllegalStateException("Composed exact before/after file chain differs");
            if(group.equals("regions"))cells+=row.get("cells").getAsInt();
        }
        if(cells!=631||!changed.equals(Set.of("dimensions/projectseele/geofront/region/r.-4.0.mca","dimensions/projectseele/geofront/region/r.-4.1.mca",
                "dimensions/projectseele/geofront/region/r.-1.-1.mca","dimensions/projectseele/geofront/region/r.0.-1.mca","dimensions/projectseele/geofront/region/r.0.0.mca",
                "spatial_contract_r21.json",".projectseele_command_sliding_doors_r01.json")))throw new IllegalStateException("Composed fixed631/2-file mask differs");
        if(!source.keySet().equals(originalFiles.keySet())||source.size()!=1736)throw new IllegalStateException("Composed source inventory differs");
        for(var row:source.entrySet())if(!changed.contains(row.getKey())&&!row.getKey().equals("session.lock")&&!row.getValue().equals(originalFiles.get(row.getKey())))throw new IllegalStateException("Composed source changed UUID/progress/transport/other bytes");
        var copied=new TreeMap<String,String>(source);copied.remove("session.lock");
        if(!expected.equals(copied))throw new IllegalStateException("QA must be an exact fresh copy of actual composedv5; no second overlay");
    }

'''
def main():
    assert not OUT.exists();OUT.mkdir();raw_before=SOURCE.read_bytes();before=raw_before.decode('utf8').replace('\r\n','\n');after=before
    after=after.replace('"READER5","SOURCE_PHOTOS"','"READER5","SOURCE_PHOTOS","COMPONENT_WALK","COMPONENT_BE"',1)
    after=after.replace('    @SubscribeEvent public static void setup(',HELPER+'    @SubscribeEvent public static void setup(',1)
    begin='            ref(job.getAsJsonObject("physical_bundle"));ref(job.getAsJsonObject("physical_apply_receipt"));\n';end='            exact(world,expected,true);\n'
    assert after.count(begin)==after.count(end)==1
    start=after.index(begin);stop=after.index(end,start);old=after[start:stop]
    expected_line='            Map<String,String> expected=files(job.getAsJsonArray("world_files"));if(expected.size()!=1735)throw new IllegalStateException("Exact post-overlay inventory required");\n'
    assert old.count(expected_line)==1;old=old.replace(expected_line,'            if(expected.size()!=1735)throw new IllegalStateException("Exact post-overlay inventory required");\n')
    replacement='            Map<String,String> expected=files(job.getAsJsonArray("world_files"));\n            if(job.has("composed_source_v5"))composedV5Source(job,sourceWorld,source,expected);\n            else\n            {\n'+''.join('    '+line for line in old.splitlines(True))+'            }\n'
    after=after[:start]+replacement+after[stop:]
    after=after.replace('            var actualClasses=new HashSet<String>();\n','            requiredClasses=new HashSet<>(requiredClasses);\n            if(allowed.contains("COMPONENT_WALK")||allowed.contains("COMPONENT_BE"))requiredClasses.add("/com/projectseele/client/visual/FacilityComponentReviewR45.class");\n            var actualClasses=new HashSet<String>();\n',1)
    # The existing lambda captures requiredClasses: keep the variable final.
    after=after.replace('            Set<String> requiredClasses=Set.of(','            var baseRequiredClasses=Set.of(',1).replace('            requiredClasses=new HashSet<>(requiredClasses);','            final Set<String> requiredClasses=new HashSet<>(baseRequiredClasses);',1)
    old_receipt='            receipt.addProperty("binding_sha256",digest);receipt.addProperty("source_files",1736);receipt.addProperty("source_bytes",520513536L);\n'
    assert after.count(old_receipt)==1
    after=after.replace(old_receipt,'            long sourceBytes=0;for(String relative:source.keySet())sourceBytes+=Files.size(sourceWorld.resolve(relative));\n            receipt.addProperty("binding_sha256",digest);receipt.addProperty("source_files",1736);receipt.addProperty("source_bytes",sourceBytes);\n',1)
    after=after.replace('receipt.addProperty("physical_overlay_cells",25);','receipt.addProperty("physical_overlay_cells",job.has("composed_source_v5")?631:25);',1)
    assert after!=before
    if raw_before.count(b'\r\n')==raw_before.count(b'\n'):
        after=after.replace('\n','\r\n')
    before=raw_before.decode('utf8')
    (OUT/'FacilitySourceAdmissionR45.before.txt').write_bytes(before.encode('utf8'));(OUT/'FacilitySourceAdmissionR45.candidate.txt').write_bytes(after.encode('utf8'))
    patch=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/src/main/java/com/projectseele/world/FacilitySourceAdmissionR45.java',tofile='b/src/main/java/com/projectseele/world/FacilitySourceAdmissionR45.java'))
    (OUT/'root_composed_v5_source_admission.patch').write_bytes(patch.encode('utf8'))
    (OUT/'prepared_not_compiled.json').write_bytes((json.dumps(dict(shared_Java_modified=False,world_written=False,Java_MC_started=False,compiled=False,applied=False,consumer_implementation_pending=True,first_fresh_source_only=True,relog_phase_not_implemented=True,before_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),patch_sha256=hashlib.sha256(patch.encode('utf8')).hexdigest()),indent=2)+'\n').encode('utf8'))
    print('Prepared single shared admission candidate patch; no Java/source/world write or compile.',flush=True)
if __name__=='__main__':main()
