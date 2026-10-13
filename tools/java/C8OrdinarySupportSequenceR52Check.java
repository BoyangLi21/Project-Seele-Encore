import com.google.gson.*;
import com.projectseele.entity.*;
import com.projectseele.physics.CombatBodyProfiles;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import java.nio.file.*;
import java.util.*;

/** All actual C8 244 rows, including draw outlet and post-stow, through the
 * production contact-memory policy, envelope, and original-shoe solver. */
public final class C8OrdinarySupportSequenceR52Check {
    static void check(boolean v,String why){if(!v)throw new AssertionError(why);}
    public static void main(String[] args)throws Exception {
        Path root=Path.of(args[0]),out=root.resolve(".codex/r52_c8_handoff_fix"),bundle=root.resolve("artifacts/r52_runtime_candidate/projectseele-local-maps");
        var body=JsonParser.parseString(Files.readString(bundle.resolve("eva_body_r44.json"))).getAsJsonObject();var physics=JsonParser.parseString(Files.readString(bundle.resolve("articulated_bodies_r35.json"))).getAsJsonObject();
        var rig=ReplayOrdinaryHandlingR52.rig(body.getAsJsonObject("rigs").getAsJsonArray("1"));var profile=new CombatBodyProfiles.Profile("c8-replay",physics.getAsJsonObject("models").getAsJsonObject("1"),rig,null);
        EvaOrdinaryStandingSupportR52.MotionMemory memory=null;var facts=new ArrayList<Map<String,Object>>();int samples=0,bridged=0,applied=0;float maxReconstruction=0,maxSole=0,maxXZ=0,maxOrientation=0;var named=new LinkedHashMap<String,Object>();
        for(String line:Files.readAllLines(root.resolve("artifacts/r52_native_combined_candidate8/ordinary/poses.jsonl"))){var row=JsonParser.parseString(line).getAsJsonObject();
            int age=row.get("age").getAsInt();var captured=row.getAsJsonObject("final_rendered_model_bones");var pose=ReplayOrdinaryHandlingR52.decode(rig,captured);var world=ReplayOrdinaryHandlingR52.matrix(row.getAsJsonArray("model_to_world"));
            double clock=row.getAsJsonObject("actual_foot_witness").getAsJsonObject("support_r44").get("game_time").getAsDouble()+row.get("partial").getAsDouble();double rootY=row.getAsJsonArray("actual_client_render_origin").get(1).getAsDouble();
            boolean ground=row.get("onGround").getAsBoolean(),eligible=row.get("isPoweredOn").getAsBoolean()&&!row.get("isBerserk").getAsBoolean()&&!row.get("isPilotCrouching").getAsBoolean()&&!row.get("isPilotProne").getAsBoolean()&&!row.get("ordinaryStandingSupportLockedR52").getAsBoolean()&&!row.get("isVisuallyAirborneForRender").getAsBoolean()&&row.get("actual_airAge").getAsFloat()<0&&row.get("stance").getAsFloat()<=.01F;
            boolean action=row.get("getOrdinaryAttackStage").getAsInt()>=0||row.get("knife_type").getAsInt()>=0||row.get("sword_active").getAsBoolean();
            if(eligible&&!ground)eligible=memory!=null&&memory.retainsGroundContactR52(clock,rootY);
            if(!eligible)memory=null;
            if(eligible&&memory==null){var prior=row.getAsJsonObject("actual_ordinary_support_memory");memory=new EvaOrdinaryStandingSupportR52.MotionMemory(prior.has("changed")?prior.get("changed").getAsDouble():clock);}
            if(memory!=null&&ground)memory.rememberGroundContactR52(clock,rootY);
            // The named unchanged flat native fixture is known to have two
            // floor hits at -60. This offline replay does not create a Level.
            if(memory!=null&&!ground&&!memory.retainsGroundFloorR52(-60,-60)){memory=null;eligible=false;}
            if(memory!=null&&ground)memory.rememberGroundFloorR52(-60,-60);
            float envelope=memory==null?0:memory.update(clock,action);float amount=eligible&&!action?envelope*EvaOrdinaryStandingSupportR52.settleWeight(row.get("rifleMoveBlend").getAsFloat()):0;
            var lows=new HashMap<String,Vector3f>();var rotations=new HashMap<String,Quaternionf>();
            for(String s:List.of("l","r")){String foot="foot_"+s;maxReconstruction=Math.max(maxReconstruction,C8Difference.matrix(pose.matrix(foot),ReplayOrdinaryHandlingR52.matrix(captured.getAsJsonArray(foot))));lows.put(s,world.transformPosition(EvaOrdinaryStandingSupportR52.lowest(1,pose,s)));rotations.put(s,pose.matrix(foot).getUnnormalizedRotation(new Quaternionf()).normalize());}
            if(amount>0){EvaOrdinaryStandingSupportR52.apply(1,pose,amount,new float[]{0,0},profile);applied++;if(!ground)bridged++;}
            var gap=new LinkedHashMap<String,Float>();for(String s:List.of("l","r")){String foot="foot_"+s;var low=world.transformPosition(EvaOrdinaryStandingSupportR52.lowest(1,pose,s));gap.put(s,low.y+60);if(amount>=.9999F)maxSole=Math.max(maxSole,Math.abs(low.y+60-.08F));var old=lows.get(s);maxXZ=Math.max(maxXZ,(float)Math.hypot(low.x-old.x,low.z-old.z));maxOrientation=Math.max(maxOrientation,1-Math.abs(rotations.get(s).dot(pose.matrix(foot).getUnnormalizedRotation(new Quaternionf()).normalize())));}
            var fact=new LinkedHashMap<String,Object>();fact.put("age",age);fact.put("clock",clock);fact.put("onGround",ground);fact.put("actual_airAge",row.get("actual_airAge").getAsFloat());fact.put("retained_contact_during_flag_gap",eligible&&!ground);fact.put("support_weight",amount);fact.put("replayed_sole_clearance_blocks",gap);facts.add(fact);if(List.of(88,89,161,165).contains(age))named.put("age_"+age,fact);samples++;
        }
        check(samples==244&&bridged>=2&&maxSole<1e-4F&&maxReconstruction<2e-4F&&maxXZ<1e-4F&&maxOrientation<1e-5F,"Full sequence/support mismatch "+List.of(samples,bridged,maxSole,maxReconstruction,maxXZ,maxOrientation));
        var m=new EvaOrdinaryStandingSupportR52.MotionMemory(0);m.rememberGroundContactR52(0,-60);m.rememberGroundFloorR52(-60,-60);
        check(m.retainsGroundContactR52(4,-60)&&!m.retainsGroundContactR52(4.00001,-60),"Ground bridge renews itself without real contact");
        check(!m.retainsGroundContactR52(1,-59.98)&&!m.retainsGroundContactR52(-1,-60),"Jump/clock reversal still retains old contact");
        check(!m.retainsGroundFloorR52(Double.NaN,-60)&&!m.retainsGroundFloorR52(-61,-60)&&!m.retainsGroundFloorR52(-60,-59.5),"Removed floor or step retained old contact");
        check(m.update(0,false)==0&&m.update(6,false)==.5F&&m.update(12,false)==1,"Fresh support original 12 tick initialization changed");
        check(m.update(12,true)==1&&m.update(15,true)==.5F&&m.update(18,true)==0,"Attack original 6 tick release changed");
        check(m.update(18,false)==0&&m.update(24,false)==.5F&&m.update(30,false)==1,"Action original 12 tick recovery changed");
        var report=new LinkedHashMap<String,Object>();report.put("actual_C8_pose_rows",samples);report.put("solver_applied_rows",applied);report.put("retained_real_flag_gap_rows",bridged);report.put("maximum_native_matrix_reconstruction_component_error",maxReconstruction);report.put("maximum_full_support_original_shoe_target_error_blocks",maxSole);report.put("maximum_lowest_shoe_xz_delta_blocks",maxXZ);report.put("maximum_world_shoe_quaternion_dot_error",maxOrientation);report.put("critical_outlet_rows",named);report.put("negative_cases",List.of("actual jump root rises beyond 1cm","airAge/visuallyAirborne remains hard exclusion in production","missing real floor hit clears transient branch","floor lowered or raised as step","no contact beyond 4 ticks","clock reversal","fresh 12 tick initialization","attack 6 tick release and 12 tick recovery"));report.put("rows",facts);report.put("native_verified",false);report.put("limits","Captured ordinary flags and same-row final matrices replayed through production Memory and solver; unrecorded complete-owner fields are covered by unchanged production hard guards, not invented. Named flat fixture supplies floor -60; actual native Level ray branch and final rendered pixels still require targeted handling run.");
        Files.writeString(out.resolve("ACTUAL_C8_244_SUPPORT_SEQUENCE_REPLAY.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report));var summary=new LinkedHashMap<>(report);summary.remove("rows");System.out.println(new Gson().toJson(summary));
    }
    static final class C8Difference{static float matrix(Matrix4f a,Matrix4f b){float d=0;float[] aa=a.get(new float[16]),bb=b.get(new float[16]);for(int i=0;i<16;i++)d=Math.max(d,Math.abs(aa[i]-bb[i]));return d;}}
}
