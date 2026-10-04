package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import net.minecraft.nbt.NbtIo;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.event.lifecycle.FMLCommonSetupEvent;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

/** Independent facility-only admission; source City remains honestly unplaced. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,bus=Mod.EventBusSubscriber.Bus.MOD)
public final class FacilitySourceAdmissionR45
{
    private static final String SCHEMA="projectseele.facility-source-native-binding-r45.v1";
    private static final String CLASS="FACILITY_SOURCE_UNPLACED";
    private static final Set<String> SCOPES=Set.of("LIFT90","LANDING24","COMMAND17","MTR2","READER5","SOURCE_PHOTOS","COMPONENT_WALK","COMPONENT_BE");
    private static volatile boolean ready,id6Postrun;
    private static Path admittedWorld,admittedBinding;
    private static String admittedHash,worldId;
    private static long seed;
    private static Set<String> scopes=Set.of();
    private static Path views;
    private static String viewsHash;
    private FacilitySourceAdmissionR45() { }
    private static String hash(Path p) throws Exception
    {
        var digest=MessageDigest.getInstance("SHA-256");try(var input=Files.newInputStream(p))
        { byte[] bytes=new byte[1024*1024];for(int n;(n=input.read(bytes))>=0;)if(n>0)digest.update(bytes,0,n); }
        return HexFormat.of().formatHex(digest.digest());
    }
    private static JsonObject read(Path p) throws Exception { return JsonParser.parseString(Files.readString(p)).getAsJsonObject(); }
    private static void ref(JsonObject row) throws Exception
    { if(!hash(Path.of(row.get("path").getAsString())).equals(row.get("sha256").getAsString()))throw new IllegalStateException("Facility input bytes changed"); }
    private static Map<String,String> files(JsonArray rows)
    {
        var result=new TreeMap<String,String>();
        for(var raw:rows)
        {
            var row=raw.getAsJsonObject();String relative=row.get("relative").getAsString();var p=Path.of(relative);
            if(p.isAbsolute()||p.normalize().startsWith("..")||!relative.equals(relative.replace('\\','/'))
                    ||result.put(relative,row.get("sha256").getAsString())!=null)throw new IllegalStateException("Invalid/repeated world inventory");
        }
        return result;
    }
    private static void exact(Path root,Map<String,String> expected,boolean allowLock) throws Exception
    {
        var found=new HashSet<String>();try(var walk=Files.walk(root))
        {
            for(var path:walk.toList())
            {
                if(Files.isSymbolicLink(path))throw new IllegalStateException("Facility world must be a physical copy");
                if(!Files.isRegularFile(path))continue;String relative=root.relativize(path).toString().replace('\\','/');
                if(allowLock&&relative.equals("session.lock"))continue;
                if(!found.add(relative)||!expected.containsKey(relative)||!hash(path).equals(expected.get(relative)))throw new IllegalStateException("Facility cold world drift: "+relative);
            }
        }
        if(!found.equals(expected.keySet()))throw new IllegalStateException("Incomplete facility world inventory");
    }
    private static Map<String,String> objectFiles(JsonObject object)
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
        if(job.has("postrun_BE_recheck"))composedV5BePostrun(job,expected);
        else if(!expected.equals(copied))throw new IllegalStateException("QA must be an exact fresh copy of actual composedv5; no second overlay");
    }

    private static void composedV13Source(JsonObject job,Path sourceWorld,Map<String,String> source,Map<String,String> expected) throws Exception
    {
        var origin=job.getAsJsonObject("composed_source_v13");for(String key:List.of("actual_readback","parent_readback","composition_receipt"))ref(origin.getAsJsonObject(key));
        var actual=read(Path.of(origin.getAsJsonObject("actual_readback").get("path").getAsString()));var parent=read(Path.of(origin.getAsJsonObject("parent_readback").get("path").getAsString()));var composition=read(Path.of(origin.getAsJsonObject("composition_receipt").get("path").getAsString()));
        var counts=actual.getAsJsonObject("counts");
        if(!"projectseele.r45.tv-current-v12-exact591.v1".equals(actual.get("schema").getAsString())||!"COMPLETE_STATIC_NOT_ART_NOT_NATIVE".equals(actual.get("phase").getAsString())
                ||!"r45.complete-source-city-config-current-navigation.v1".equals(parent.get("schema").getAsString())||!"COMPLETE".equals(parent.get("phase").getAsString())
                ||!sourceWorld.equals(Path.of(actual.get("world").getAsString()).toRealPath())||!sourceWorld.equals(Path.of(composition.get("world").getAsString()).toRealPath())
                ||!Path.of(actual.get("original_source").getAsString()).toRealPath().equals(Path.of(parent.get("world").getAsString()).toRealPath())
                ||!actual.get("source1739_unchanged").getAsBoolean()||!actual.get("all_player_actor_task_MTR_and_nav_files_byte_preserved").getAsBoolean()
                ||counts.get("rows").getAsInt()!=591||counts.get("chunks").getAsInt()!=20||counts.get("all_original_BE").getAsInt()!=358
                ||!source.equals(objectFiles(actual.getAsJsonObject("full_after_inventory")))||composition.getAsJsonArray("regions").size()!=4||composition.getAsJsonArray("files").size()!=1
                ||composition.getAsJsonArray("selected_components").size()!=1||!"tv_command17_cabin7_finish591".equals(composition.getAsJsonArray("selected_components").get(0).getAsString()))throw new IllegalStateException("Actual Root v13 finite591/1739 proof required");
        var previous=objectFiles(parent.getAsJsonObject("full_after_inventory"));if(source.size()!=1739||!source.keySet().equals(previous.keySet()))throw new IllegalStateException("Actual v12/v13 file denominator differs");
        var changed=new HashSet<String>();for(var r:source.entrySet())if(!r.getValue().equals(previous.get(r.getKey())))changed.add(r.getKey());var proven=new HashSet<String>();int total=0;
        for(var raw:composition.getAsJsonArray("regions"))
        {
            var r=raw.getAsJsonObject();String path=r.get("target").getAsString();if(!path.matches("dimensions/projectseele/geofront/region/r\\.-?[0-9]+\\.-?[0-9]+\\.mca")||!r.get("before_sha256").getAsString().equals(previous.get(path))||!r.get("after_sha256").getAsString().equals(source.get(path))||!proven.add(path))throw new IllegalStateException("Actual v13 full region before/after chain differs");total+=r.get("cells").getAsInt();
        }
        var meta=composition.getAsJsonArray("files").get(0).getAsJsonObject();String target=meta.get("target").getAsString();
        if(total!=591||!".projectseele_command_sliding_doors_r01.json".equals(target)||!meta.get("before_sha256").getAsString().equals(previous.get(target))||!meta.get("after_sha256").getAsString().equals(source.get(target))||!proven.add(target)||!changed.equals(proven))throw new IllegalStateException("Actual v13 change exceeded591/frame support metadata");
        var fresh=new TreeMap<String,String>(source);fresh.remove("session.lock");
        if(job.has("postrun_ID6_first_contact"))id6RestoredPostrun(job,expected);
        else if(job.has("postrun_BE_recheck")||!fresh.equals(expected))throw new IllegalStateException("Actual fresh v13 copy required; no consumed QA progress");
    }

    private static void id6RestoredPostrun(JsonObject job,Map<String,String> expected) throws Exception
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

    private static void composedV11Source(JsonObject job,Path sourceWorld,Map<String,String> source,Map<String,String> expected) throws Exception
    {
        var origin=job.getAsJsonObject("composed_source_v11");
        for(String key:List.of("actual_readback","parent_readback","static_WAL","metadata_WAL"))ref(origin.getAsJsonObject(key));
        var actual=read(Path.of(origin.getAsJsonObject("actual_readback").get("path").getAsString()));
        var parent=read(Path.of(origin.getAsJsonObject("parent_readback").get("path").getAsString()));
        var counts=actual.getAsJsonObject("counts");
        if(!"r45.complete-v11-arrival-stair-command-inputs.v1".equals(actual.get("schema").getAsString())
                ||!"COMPLETE".equals(actual.get("phase").getAsString())
                ||!"projectseele.complete-v10-bay-map-state-BE-reader.v1".equals(parent.get("schema").getAsString())
                ||!"COMPLETE".equals(parent.get("phase").getAsString())
                ||!sourceWorld.equals(Path.of(actual.get("world").getAsString()).toRealPath())
                ||!Path.of(actual.get("original_source").getAsString()).toRealPath().equals(Path.of(parent.get("world").getAsString()).toRealPath())
                ||!actual.get("source1736_unchanged").getAsBoolean()
                ||!actual.get("actual_component_fullstate_typedNBT_and_all5_lanes_readback").getAsBoolean()
                ||!actual.get("all_actor_player_task_MTR_and_unrelated_files_byte_preserved").getAsBoolean()
                ||counts.get("static_rows").getAsInt()!=11||counts.get("original_stairs_preserved").getAsInt()!=30
                ||counts.get("complete_stair_lanes").getAsInt()!=5||counts.get("metadata_inputs_added").getAsInt()!=2
                ||counts.get("files_changed").getAsInt()!=2
                ||!actual.get("static_WAL_SHA256").getAsString().equals(origin.getAsJsonObject("static_WAL").get("sha256").getAsString())
                ||!actual.get("metadata_WAL_SHA256").getAsString().equals(origin.getAsJsonObject("metadata_WAL").get("sha256").getAsString())
                ||!source.equals(objectFiles(actual.getAsJsonObject("full_after_inventory"))))
            throw new IllegalStateException("Actual Root v11 complete source/readback/WAL required");
        var staticWAL=read(Path.of(origin.getAsJsonObject("static_WAL").get("path").getAsString()));
        var metadataWAL=read(Path.of(origin.getAsJsonObject("metadata_WAL").get("path").getAsString()));
        if(!"COMPLETE".equals(staticWAL.get("phase").getAsString())
                ||!staticWAL.get("stage_complete").getAsBoolean()||staticWAL.get("source_rows").getAsInt()!=11
                ||staticWAL.get("final_exact_cells").getAsInt()!=11||!staticWAL.get("all_exact_final_actual_voxels_and_nbt_readback").getAsBoolean()
                ||staticWAL.getAsJsonArray("regions").size()!=1
                ||!sourceWorld.equals(Path.of(staticWAL.get("world").getAsString()).toRealPath())
                ||!"COMPLETE".equals(metadataWAL.get("phase").getAsString())
                ||!sourceWorld.equals(Path.of(metadataWAL.get("world").getAsString()).toRealPath())
                ||!".projectseele_command_sliding_doors_r01.json".equals(metadataWAL.get("target").getAsString())
                ||!metadataWAL.get("only_two_existing_input_registrations_added").getAsBoolean()
                ||!metadataWAL.get("original37_input_positions_preserved").getAsBoolean()
                ||!metadataWAL.get("static_WAL_sha256").getAsString().equals(origin.getAsJsonObject("static_WAL").get("sha256").getAsString())
                ||!source.equals(objectFiles(metadataWAL.getAsJsonObject("full_after_inventory"))))
            throw new IllegalStateException("Actual complete11 typed-state WAL and39 input metadata WAL required");
        var previous=objectFiles(parent.getAsJsonObject("full_after_inventory"));
        if(source.size()!=1736||!source.keySet().equals(previous.keySet()))throw new IllegalStateException("Actual v11 full1736 inventory changed");
        var changed=new HashSet<String>();for(var r:source.entrySet())if(!r.getValue().equals(previous.get(r.getKey())))changed.add(r.getKey());
        if(!changed.equals(Set.of("dimensions/projectseele/geofront/region/r.-1.1.mca",".projectseele_command_sliding_doors_r01.json")))
            throw new IllegalStateException("Actual v11 change exceeded complete NERV11/2-input marker files");
        var region=staticWAL.getAsJsonArray("regions").get(0).getAsJsonObject();
        if(!"COMMITTED".equals(region.get("phase").getAsString())||region.get("cells").getAsInt()!=11
                ||!region.get("before_sha256").getAsString().equals(previous.get("dimensions/projectseele/geofront/region/r.-1.1.mca"))
                ||!region.get("after_sha256").getAsString().equals(source.get("dimensions/projectseele/geofront/region/r.-1.1.mca"))
                ||!metadataWAL.get("before_sha256").getAsString().equals(previous.get(".projectseele_command_sliding_doors_r01.json"))
                ||!metadataWAL.get("after_sha256").getAsString().equals(source.get(".projectseele_command_sliding_doors_r01.json")))
            throw new IllegalStateException("Actual complete v10/v11 region and metadata byte chain differs");
        var fresh=new TreeMap<String,String>(source);fresh.remove("session.lock");
        if(job.has("postrun_BE_recheck")||!fresh.equals(expected))throw new IllegalStateException("COMMAND17 requires exact fresh actualv11 copy; no QA progress or second overlay");
    }

    private static void composedV5BePostrun(JsonObject job,Map<String,String> expected) throws Exception
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

    @SubscribeEvent public static void setup(FMLCommonSetupEvent event)
    {
        String file=System.getProperty("projectseele.nativeFacilityBindingR45","");
        String digest=System.getProperty("projectseele.nativeFacilityBindingR45SHA256","");
        String output=System.getProperty("projectseele.nativeFacilityAdmissionR45","");
        if(file.isEmpty()&&digest.isEmpty()&&output.isEmpty())return;
        var receipt=new JsonObject();receipt.addProperty("schema","projectseele.facility-source-preworld-admission-r45.v1");
        receipt.addProperty("test_class",CLASS);receipt.addProperty("phase","FML_COMMON_SETUP_BEFORE_WORLD_OPEN");receipt.addProperty("passed",false);
        receipt.addProperty("world_written",false);receipt.addProperty("city_MOVE_READY_or_delivery_pass",false);Path destination=null;
        try
        {
            if(file.isEmpty()||!digest.matches("[0-9a-f]{64}")||output.isEmpty())throw new IllegalStateException("Three exact facility admission properties required");
            for(String property:System.getProperties().stringPropertyNames())
                if(property.startsWith("projectseele.r45City")||property.startsWith("projectseele.nativeCandidateBinding")
                        ||property.equals("projectseele.nativeCandidateAdmissionR45"))throw new IllegalStateException("City jobs/old City admission cannot run in facility source scope");
            Path binding=Path.of(file).toRealPath();if(!hash(binding).equals(digest))throw new IllegalStateException("Facility binding changed");
            var job=read(binding);Path world=Path.of(job.get("world").getAsString()).toRealPath();
            destination=Path.of(output).toAbsolutePath().normalize();
            if(!SCHEMA.equals(job.get("schema").getAsString())||!CLASS.equals(job.get("test_class").getAsString())
                    ||!job.get("facility_only").getAsBoolean()||job.get("city_native_structure_pass").getAsBoolean()
                    ||!world.getFileName().toString().equals("SEELE_FIELD_R45_REVIEW")||!world.getParent().getFileName().toString().equals("saves")
                    ||!world.getParent().getParent().getParent().getFileName().toString().equals("native_facility_session_v1")
                    ||destination.startsWith(world)||Files.exists(destination)
                    ||!destination.equals(Path.of(job.get("preworld_receipt_output").getAsString()).toAbsolutePath().normalize()))
                throw new IllegalStateException("Only this fresh physical facility source copy is admitted");
            var allowed=new HashSet<String>();for(var raw:job.getAsJsonArray("active_scopes"))if(!allowed.add(raw.getAsString())||!SCOPES.contains(raw.getAsString()))throw new IllegalStateException("Unknown/repeated facility active scope");
            if(allowed.isEmpty())throw new IllegalStateException("No active facility test scope");
            ref(job.getAsJsonObject("source_baseline"));var baseline=read(Path.of(job.getAsJsonObject("source_baseline").get("path").getAsString()));
            Map<String,String> source=files(baseline.getAsJsonArray("files"));
            int sourceCount=job.has("composed_source_v13")?1739:1736;
            if(source.size()!=sourceCount)throw new IllegalStateException("Full immutable source required: "+sourceCount);
            Path sourceWorld=Path.of(baseline.get("source_world").getAsString()).toRealPath();if(sourceWorld.equals(world))throw new IllegalStateException("Source cannot be the active world");
            exact(sourceWorld,source,false);
            ref(job.getAsJsonObject("copy_receipt"));var copy=read(Path.of(job.getAsJsonObject("copy_receipt").get("path").getAsString()));
            if(!"projectseele.facility-source-copy-receipt-r45.v1".equals(copy.get("schema").getAsString())||!copy.get("copy_complete").getAsBoolean()
                    ||copy.get("source_written").getAsBoolean()||!source.equals(files(copy.getAsJsonArray("files")))
                    ||!world.equals(Path.of(copy.get("target_world").getAsString()).toRealPath()))throw new IllegalStateException("Exact fresh source-copy receipt required");
            Map<String,String> expected=files(job.getAsJsonArray("world_files"));
            if(job.has("composed_source_v13"))composedV13Source(job,sourceWorld,source,expected);
            else if(job.has("composed_source_v11"))composedV11Source(job,sourceWorld,source,expected);
            else if(job.has("composed_source_v5"))composedV5Source(job,sourceWorld,source,expected);
            else
            {
                ref(job.getAsJsonObject("physical_bundle"));ref(job.getAsJsonObject("physical_apply_receipt"));
                var bundle=read(Path.of(job.getAsJsonObject("physical_bundle").get("path").getAsString()));
                var overlay=read(Path.of(job.getAsJsonObject("physical_apply_receipt").get("path").getAsString()));
                if(!"projectseele.device25-actual-root-apply-r45.v1".equals(overlay.get("schema").getAsString())||!overlay.get("installed").getAsBoolean()
                        ||overlay.get("cells").getAsInt()!=25||overlay.get("navigation_or_model_installed").getAsBoolean()
                        ||!world.equals(Path.of(overlay.get("world").getAsString()).toRealPath())
                        ||!job.getAsJsonObject("physical_bundle").get("sha256").getAsString().equals(overlay.get("bundle_sha256").getAsString()))
                    throw new IllegalStateException("Only actual25/marker overlay is admitted");
                var before=overlay.getAsJsonObject("before_files");var after=overlay.getAsJsonObject("after_files");
                if(before.size()!=1736||after.size()!=1736)throw new IllegalStateException("Overlay changed complete copy inventory");
                var permitted=new HashSet<String>();for(var raw:overlay.getAsJsonArray("backups"))permitted.add(raw.getAsJsonObject().get("relative").getAsString());
                if(!permitted.equals(Set.of("dimensions/projectseele/geofront/region/r.0.0.mca","dimensions/projectseele/geofront/region/r.0.-1.mca",".projectseele_command_sliding_doors_r01.json")))throw new IllegalStateException("Physical overlay exceeded exact fixed mask files");
                for(var row:source.entrySet())
                {
                    if(!before.has(row.getKey())||!row.getValue().equals(before.get(row.getKey()).getAsString())
                            ||!after.has(row.getKey())||!permitted.contains(row.getKey())&&!row.getValue().equals(after.get(row.getKey()).getAsString()))
                        throw new IllegalStateException("Overlay altered UUID/progress/traffic/fixed City data");
                }
                if(!overlay.get("all_complete_BE_records_preserved").getAsBoolean()||!overlay.get("all_outside_mask_voxels_preserved").getAsBoolean()
                        ||!overlay.get("all_other_chunk_blobs_preserved").getAsBoolean())throw new IllegalStateException("Incomplete actual overlay readback");
                if(expected.size()!=1735)throw new IllegalStateException("Exact post-overlay inventory required");
                for(var row:expected.entrySet())if(!row.getValue().equals(after.get(row.getKey()).getAsString()))throw new IllegalStateException("Lease differs from actual overlay epoch");
            }
            exact(world,expected,true);
            var identity=NbtIo.readCompressed(world.resolve("dimensions/projectseele/geofront/data/projectseele_tokyo3_building_world_id_r44.dat").toFile()).getCompound("data");
            String id=identity.getString("WorldUUID");UUID.fromString(id);long actualSeed=NbtIo.readCompressed(world.resolve("level.dat").toFile()).getCompound("Data").getCompound("WorldGenSettings").getLong("seed");
            if(!id.equals(job.get("world_id").getAsString())||actualSeed!=job.get("world_seed").getAsLong())throw new IllegalStateException("Facility UUID/seed mismatch");
            var city=job.getAsJsonObject("city_source_prestate");
            if(!city.get("runtime_control_absent").getAsBoolean()||!"CANDIDATE_DISABLED".equals(city.get("actual_topology_stage").getAsString())
                    ||city.get("runtime_enabled").getAsBoolean()||city.get("native_structure_passed").getAsBoolean())throw new IllegalStateException("Facility scope cannot label source City MOVE/READY/complete");
            String cityMarker=city.get("topology_relative").getAsString();var topology=NbtIo.readCompressed(world.resolve(cityMarker).toFile()).getCompound("data");
            if(!topology.getString("Stage").equals("CANDIDATE_DISABLED")||topology.getBoolean("RuntimeEnabled")||topology.getBoolean("NativeStructurePassed"))throw new IllegalStateException("Actual source City classification differs");
            Path cityData=world.resolve("dimensions/projectseele/geofront/data");try(var entries=Files.list(cityData))
            { if(entries.anyMatch(p->p.getFileName().toString().startsWith("projectseele_city_rigid_control_r45_")))throw new IllegalStateException("Source facility test cannot reuse prior City controller progress"); }
            var fixedCity=files(job.getAsJsonArray("fixed_city_files"));var completeCity=new TreeMap<String,String>();
            for(var row:source.entrySet())if(row.getKey().startsWith("dimensions/projectseele/geofront/data/")&&row.getKey().toLowerCase(Locale.ROOT).contains("city"))completeCity.put(row.getKey(),row.getValue());
            if(completeCity.isEmpty()||!fixedCity.equals(completeCity))throw new IllegalStateException("Complete original unplaced City data inventory required");
            for(var row:fixedCity.entrySet())if(!hash(world.resolve(row.getKey())).equals(row.getValue()))throw new IllegalStateException("Original unplaced City bytes changed");
            for(var raw:job.getAsJsonArray("source_epoch"))ref(raw.getAsJsonObject());
            var baseRequiredClasses=Set.of("/com/projectseele/world/FacilitySourceAdmissionR45.class","/com/projectseele/visual/LiftPassengerR20Review.class",
                    "/com/projectseele/client/visual/NervSecurityLifecycleR45.class","/com/projectseele/client/visual/RegionalStationPhoto.class","/com/projectseele/world/NervOperationsConsole.class");
            final Set<String> requiredClasses=new HashSet<>(baseRequiredClasses);
            if(allowed.contains("COMPONENT_WALK")||allowed.contains("COMPONENT_BE"))requiredClasses.add("/com/projectseele/client/visual/FacilityComponentReviewR45.class");
            if(job.has("composed_source_v13"))requiredClasses.addAll(Set.of("/com/projectseele/client/render/NervPressureDoorFinishR45.class","/com/projectseele/client/render/NervSlidingDoorRenderer.class"));
            if(allowed.contains("COMMAND17"))requiredClasses.addAll(Set.of(
                    "/com/projectseele/client/visual/CommandDoorInteractionReviewR45.class",
                    "/com/projectseele/world/CommandRoomSlidingDoorDirector.class",
                    "/com/projectseele/entity/NervSlidingDoorEntity.class"));
            var actualClasses=new HashSet<String>();
            for(var raw:job.getAsJsonArray("runtime_classes"))
            {
                var row=raw.getAsJsonObject();String resource=row.get("resource").getAsString();
                boolean allowedClass=requiredClasses.contains(resource)||requiredClasses.stream().anyMatch(r->resource.startsWith(r.substring(0,r.length()-6)+"$")&&resource.endsWith(".class"));
                if(!allowedClass||!actualClasses.add(resource))throw new IllegalStateException("Unexpected/repeated compiled facility class");
                try(var input=FacilitySourceAdmissionR45.class.getResourceAsStream(resource))
                {
                    if(input==null)throw new IllegalStateException("Compiled facility resource absent: "+resource);
                    var classDigest=MessageDigest.getInstance("SHA-256");byte[] bytes=new byte[1024*1024];
                    for(int n;(n=input.read(bytes))>=0;)if(n>0)classDigest.update(bytes,0,n);
                    if(!HexFormat.of().formatHex(classDigest.digest()).equals(row.get("sha256").getAsString()))throw new IllegalStateException("Actual loaded facility class differs: "+resource);
                }
            }
            if(!actualClasses.containsAll(requiredClasses))throw new IllegalStateException("Complete loaded facility admission/consumer class identities required");
            if(job.has("photo_views")){ref(job.getAsJsonObject("photo_views"));views=Path.of(job.getAsJsonObject("photo_views").get("path").getAsString()).toRealPath();viewsHash=job.getAsJsonObject("photo_views").get("sha256").getAsString();if(views.startsWith(world))throw new IllegalStateException("Photo itinerary must be an external bound input");}
            id6Postrun=job.has("postrun_ID6_first_contact");admittedWorld=world;admittedBinding=binding;admittedHash=digest;worldId=id;seed=actualSeed;scopes=Set.copyOf(allowed);
            receipt.addProperty("world",world.toString());receipt.addProperty("world_id",id);receipt.addProperty("world_seed",actualSeed);
            long sourceBytes=0;for(String relative:source.keySet())sourceBytes+=Files.size(sourceWorld.resolve(relative));
            receipt.addProperty("binding_sha256",digest);receipt.addProperty("source_files",sourceCount);receipt.addProperty("source_bytes",sourceBytes);
            receipt.addProperty("fixed_city_prestate","CANDIDATE_DISABLED / runtime controller absent / no MOVE or READY claim");receipt.addProperty("physical_overlay_cells",job.has("composed_source_v13")||job.has("composed_source_v11")?0:job.has("composed_source_v5")?631:25);receipt.addProperty("passed",true);
            Files.createDirectories(destination.getParent());Files.writeString(destination,new GsonBuilder().setPrettyPrinting().create().toJson(receipt),StandardCharsets.UTF_8,StandardOpenOption.CREATE_NEW);ready=true;
        }
        catch(Exception failure)
        {
            receipt.addProperty("error",failure.toString());try{if(destination!=null&&!Files.exists(destination)){Files.createDirectories(destination.getParent());Files.writeString(destination,receipt.toString(),StandardCharsets.UTF_8,StandardOpenOption.CREATE_NEW);}}catch(Exception ignored){}
            throw new IllegalStateException("Facility source pre-world admission rejected",failure);
        }
    }
    public static boolean admit(ServerLevel level,JsonObject job)
    {
        if(!job.has("facility_source_test")||!job.get("facility_source_test").getAsBoolean())return CityAtomicCandidateBindingR45.admit(level,job);
        try
        {
            if(!ready||!level.dimension().location().toString().equals("projectseele:geofront")||level.getSeed()!=seed
                    ||!level.getServer().getWorldPath(LevelResource.ROOT).toRealPath().equals(admittedWorld)
                    ||!job.get("world_id").getAsString().equals(worldId)||job.get("world_seed").getAsLong()!=seed
                    ||!Path.of(job.get("world").getAsString()).toRealPath().equals(admittedWorld)
                    ||!Path.of(job.get("candidate_binding").getAsString()).toRealPath().equals(admittedBinding)
                    ||!job.get("candidate_binding_sha256").getAsString().equals(admittedHash)||!scopes.contains(job.get("facility_scope").getAsString())
                    ||id6Postrun&&(!job.has("first_contact_diagnostic")||!job.get("first_contact_diagnostic").getAsBoolean()||!"COMMAND17".equals(job.get("facility_scope").getAsString())))
                throw new IllegalStateException("Facility device job/world/scope differs from admitted exact source");
            return true;
        }
        catch(Exception failure){throw new IllegalStateException("Facility source device job rejected",failure);}
    }
    public static boolean active(ServerLevel level)
    { return ready&&level.dimension().location().toString().equals("projectseele:geofront")&&level.getSeed()==seed&&level.getServer().getWorldPath(LevelResource.ROOT).toAbsolutePath().normalize().equals(admittedWorld); }
    public static boolean cityRequestsProhibited(ServerLevel level) { return active(level); }
    public static Path photoViews(Path world) throws Exception
    {
        if(!ready||!world.toRealPath().equals(admittedWorld)||!scopes.contains("SOURCE_PHOTOS")||views==null||!hash(views).equals(viewsHash))throw new IllegalStateException("Current source photos require their fresh admitted itinerary");
        return views;
    }
}
