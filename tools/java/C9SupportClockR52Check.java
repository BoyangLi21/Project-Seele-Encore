import com.google.gson.*;
import com.projectseele.entity.EvaOrdinaryStandingSupportR52;
import java.nio.file.*;
import java.util.*;

/** Actual C9 level-time sequence, controlled monotonic entity counter, real
 * production Memory. The prior tool did not export shared-path tickCount. */
public final class C9SupportClockR52Check {
    static void check(boolean v,String why){if(!v)throw new AssertionError(why);}
    public static void main(String[] a)throws Exception {
        Path root=Path.of(a[0]),out=root.resolve(".codex/r52_c10_support_clock");Files.createDirectories(out);
        var sequence=new ArrayList<Map<String,Object>>();var actualWorldTimes=new ArrayList<Double>();
        var memory=new EvaOrdinaryStandingSupportR52.MotionMemory(-20);int reversals=0;double previous=-Double.MAX_VALUE,firstRifle=Double.NaN;
        for(String line:Files.readAllLines(root.resolve("artifacts/r52_native_handling_candidate9_retry1/ordinary/poses.jsonl"))){var r=JsonParser.parseString(line).getAsJsonObject();int age=r.get("age").getAsInt();double partial=r.get("partial").getAsDouble(),world=r.getAsJsonObject("actual_foot_witness").getAsJsonObject("support_r44").get("game_time").getAsDouble()+partial;
            if(world<previous)reversals++;previous=world;actualWorldTimes.add(world);
            // A relative tick counter is a controlled replay input, not an
            // invented capture. Regular rifle samples supply actual tickCount
            // + partial from the already-recorded regular transition clock.
            double entity=age+partial;boolean observedEntity=false;
            if(r.get("getWeapon").getAsInt()==4){double actual=r.getAsJsonObject("actual_pose_transition_history").get("time").getAsDouble()*20;if(Double.isNaN(firstRifle))firstRifle=actual-age-partial;entity=actual-firstRifle;observedEntity=true;}
            double clock=memory.sampleClockR52(entity);float envelope=memory.update(clock,false);check(envelope==1,"World synchronization restarted support envelope");memory.rememberGroundContactR52(clock,-60);memory.rememberGroundFloorR52(-60,-60);
            // A lower partial in a shadow/main pass cannot reverse contact.
            double reversed=memory.sampleClockR52(entity-.25);check(reversed==clock&&memory.retainsGroundContactR52(reversed,-60),"Same-frame partial reversed memory");
            sequence.add(Map.of("age",age,"actual_level_clock",world,"entity_clock_replay_input",entity,"regular_entity_clock_observed",observedEntity,"monotonic_sample_clock",clock,"support_envelope",envelope));
        }
        check(reversals>=3&&actualWorldTimes.stream().anyMatch(t->t>62986)&&actualWorldTimes.stream().anyMatch(t->t>62828&&t<62829),"Actual clock reset fixtures absent");
        var m=new EvaOrdinaryStandingSupportR52.MotionMemory(0);check(m.update(0,false)==0&&m.update(6,false)==.5F&&m.update(12,false)==1,"Fresh 12 tick recovery changed");
        check(m.update(12,true)==1&&m.update(15,true)==.5F&&m.update(18,true)==0,"Action 6 tick fade changed");check(m.update(18,false)==0&&m.update(24,false)==.5F&&m.update(30,false)==1,"Action 12 tick recovery changed");
        m.rememberGroundContactR52(30,-60);m.rememberGroundFloorR52(-60,-60);
        check(m.retainsGroundContactR52(34,-60)&&!m.retainsGroundContactR52(34.00001,-60),"TTL extended or renewed by clock wrapper");
        check(!m.retainsGroundContactR52(31,-59.98)&&!m.retainsGroundContactR52(31,-60.02),"Real jump/fall displacement retained");check(!m.retainsGroundFloorR52(Double.NaN,-60)&&!m.retainsGroundFloorR52(-61,-60)&&!m.retainsGroundFloorR52(-60,-59.5),"Removed floor/step retained");
        var report=new LinkedHashMap<String,Object>();report.put("actual_C9_clock_rows",sequence.size());report.put("actual_level_clock_reversals",reversals);report.put("actual_observed_62986_to62828_sequence",true);report.put("source_clock_uses_entity_counter_not_level_time",true);report.put("same_frame_shadow_main_partial_order_monotonic",true);report.put("fresh12_action6_recovery12_unchanged",true);report.put("4tick_TTL_not_extended",true);report.put("jump_fall_removed_floor_step_negative_cases_passed",true);report.put("sequence",sequence);report.put("native_verified",false);report.put("limits","Actual level timestamps from all 37 C9 captured rows. Shared-path entity tickCount was not exported; relative monotonic entity input is a controlled fixture. The three actual regular rifle clocks supply recorded entity tickCount+partial, with a fixed translation for the same relative fixture. No uncaptured onGround/air flags are invented; hard air/Owner exclusions remain unchanged.");
        Files.writeString(out.resolve("ACTUAL_C9_CLOCK_RESET_MEMORY_REPLAY.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report));var summary=new LinkedHashMap<>(report);summary.remove("sequence");System.out.println(new Gson().toJson(summary));
    }
}
