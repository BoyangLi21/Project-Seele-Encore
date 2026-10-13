import com.google.gson.*;
import com.projectseele.entity.*;
import com.projectseele.client.render.EvaPoseTransition;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;

/** Real Track kernel with the actual C7 near-complete stow and returned rifle guard. */
public final class WeaponGuardHandoffR52Check {
    static void check(boolean v,String why){if(!v)throw new AssertionError(why);}
    static float angle(Quaternionf a,Quaternionf b){double d=Math.abs((double)a.x*b.x+(double)a.y*b.y+(double)a.z*b.z+(double)a.w*b.w),aa=(double)a.x*a.x+(double)a.y*a.y+(double)a.z*a.z+(double)a.w*a.w,bb=(double)b.x*b.x+(double)b.y*b.y+(double)b.z*b.z+(double)b.w*b.w;return (float)Math.toDegrees(2*Math.acos(Math.min(1,d/Math.sqrt(aa*bb))));}
    public static void main(String[] args)throws Exception {
        Path root=Path.of(args[0]),out=root.resolve(".codex/r52_weapon_guard_handoff");
        var body=JsonParser.parseString(Files.readString(root.resolve("artifacts/r52_runtime_candidate/projectseele-local-maps/eva_body_r44.json"))).getAsJsonObject();
        var rig=ReplayOrdinaryHandlingR52.rig(body.getAsJsonObject("rigs").getAsJsonArray("1"));
        JsonObject before=null,after=null;
        for(String line:Files.readAllLines(root.resolve("artifacts/r52_native_ordinary_candidate7_retry1/poses.jsonl"))) {
            var row=JsonParser.parseString(line).getAsJsonObject();
            if(row.get("variant").getAsInt()!=1)continue;
            if(row.get("age").getAsInt()==770)before=row;
            if(row.get("age").getAsInt()==772)after=row;
        }
        check(before!=null&&after!=null,"Actual C7 handoff samples absent");
        check(before.get("handling_active").getAsBoolean()&&before.get("handling_phase").getAsFloat()>.99F&&!after.get("handling_active").getAsBoolean(),"Wrong near-endpoint source");
        var source=ReplayOrdinaryHandlingR52.decode(rig,before.getAsJsonObject("final_rendered_model_bones"));
        var target=ReplayOrdinaryHandlingR52.decode(rig,after.getAsJsonObject("final_rendered_model_bones"));
        var poseType=Class.forName("com.projectseele.client.render.EvaPoseTransition$Pose");
        var trackType=Class.forName("com.projectseele.client.render.EvaPoseTransition$Track");
        var pc=poseType.getDeclaredConstructor(Quaternionf.class,Vector3f.class,Vector3f.class);pc.setAccessible(true);
        var tc=trackType.getDeclaredConstructor(poseType);tc.setAccessible(true);
        var begin=trackType.getDeclaredMethod("begin");begin.setAccessible(true);
        var sample=trackType.getDeclaredMethod("sample",poseType,double.class,double.class);sample.setAccessible(true);
        var update=trackType.getDeclaredMethod("update",poseType,double.class);update.setAccessible(true);
        var rot=poseType.getDeclaredMethod("rotation");rot.setAccessible(true);
        var pos=poseType.getDeclaredMethod("position");pos.setAccessible(true);
        var policy=EvaPoseTransition.class.getDeclaredMethod("sharedExitDurationR52",boolean.class,boolean.class,boolean.class);policy.setAccessible(true);
        double duration=(Double)policy.invoke(null,false,true,false);
        check(duration==.20D&&(Double)policy.invoke(null,true,false,false)==.12D,"Guard/action release duration changed");
        check((Double)policy.invoke(null,false,true,true)==0D,"New attack delayed by weapon guard transition");
        var continueExit=EvaPoseTransition.class.getDeclaredMethod("continuesWeaponExitR52",boolean.class,double.class,double.class,boolean.class,boolean.class);continueExit.setAccessible(true);
        check((Boolean)continueExit.invoke(null,true,.08D,duration,true,false),"Walk/idle target change cancelled the guard exit");
        check(!(Boolean)continueExit.invoke(null,true,.08D,duration,true,true),"Guard exit consumed incoming attack");
        check(!(Boolean)continueExit.invoke(null,true,duration,duration,true,false),"Guard exit did not end");
        check(!(Boolean)continueExit.invoke(null,true,.08D,duration,false,false),"New weapon cannot rebase the guard source");
        Map<String,Object> tracks=new LinkedHashMap<>(),targets=new LinkedHashMap<>();
        Set<String> upper=new LinkedHashSet<>();
        for(String name:rig.keySet())if(!EvaBodyPose.locomotionBoneR51(name)&&!Set.of("knife","lance","shield").contains(name)&&!name.contains("_axis_"))upper.add(name);
        double oldMaximum=0,maximumStep=0,maximumSoleDelta=0,maximumElbowError=0,maximumC0=0,maximumFinal=0,maximumFinalPosition=0;
        for(String n:upper) {
            Object from=pc.newInstance(new Quaternionf(source.rotations.get(n)),new Vector3f(source.positions.get(n)),new Vector3f(1));
            Object to=pc.newInstance(new Quaternionf(target.rotations.get(n)),new Vector3f(target.positions.get(n)),new Vector3f(1));
            Object t=tc.newInstance(from);begin.invoke(t);tracks.put(n,t);targets.put(n,to);
            oldMaximum=Math.max(oldMaximum,angle(source.rotations.get(n),target.rotations.get(n)));
        }
        var sequence=new ArrayList<Map<String,Object>>();EvaBodyPose.Sample previous=null;
        for(int frame=0;frame<=24;frame++) {
            double time=frame/120D;var rendered=EvaBodyPose.copy(target);
            for(String n:upper) {
                Object value=sample.invoke(tracks.get(n),targets.get(n),time,duration);
                rendered.rotations.put(n,new Quaternionf((Quaternionf)rot.invoke(value)));
                rendered.positions.put(n,new Vector3f((Vector3f)pos.invoke(value)));
                if(frame==0)maximumC0=Math.max(maximumC0,angle(rendered.rotations.get(n),source.rotations.get(n)));
                if(frame==24)maximumFinal=Math.max(maximumFinal,angle(rendered.rotations.get(n),target.rotations.get(n)));
            }
            rendered.dirty();var corrected=EvaBodyPose.copy(rendered);EvaBodyPose.preserveJointCentres(corrected);
            // Match the real exit writer: correct elbow offsets, preserve every lower-body channel.
            for(String side:List.of("l","r"))rendered.positions.put("forearm_"+side,new Vector3f(corrected.positions.get("forearm_"+side)));
            if(frame==24)for(String name:upper)maximumFinalPosition=Math.max(maximumFinalPosition,rendered.positions.get(name).distance(target.positions.get(name))*5);
            rendered.dirty();double step=0;
            for(String n:rig.keySet()) {
                if(EvaBodyPose.locomotionBoneR51(n))check(rendered.positions.get(n).equals(target.positions.get(n))&&angle(rendered.rotations.get(n),target.rotations.get(n))<.06F,"Locomotion altered: "+n);
                if(previous!=null&&upper.contains(n))step=Math.max(step,angle(previous.rotations.get(n),rendered.rotations.get(n)));
            }
            for(String side:List.of("l","r")) {
                maximumSoleDelta=Math.max(maximumSoleDelta,EvaOrdinaryStandingSupportR52.lowest(1,rendered,side).distance(EvaOrdinaryStandingSupportR52.lowest(1,target,side))*5);
                String elbow="forearm_"+side,marker="r30_elbow_socket_"+side;
                Vector3f centre=rig.containsKey(marker)?new Vector3f(rig.get(marker).pivot()):new Vector3f(side.equals("l")?-23.489652F:23.489652F,123.435069F,7.737214F).div(16);
                var local=rendered.matrix(elbow);var parent=rendered.matrix(rig.get(elbow).parent());
                maximumElbowError=Math.max(maximumElbowError,local.transformPosition(new Vector3f(centre)).distance(parent.transformPosition(new Vector3f(centre)))*5);
            }
            maximumStep=Math.max(maximumStep,step);sequence.add(Map.of("seconds",time,"maximum_joint_step_degrees",step));previous=rendered;
        }
        check(maximumC0<.001&&maximumFinal<.001&&maximumFinalPosition<1e-4,"C0/final convergence residual");
        check(maximumStep<oldMaximum*.15,"Guard remains an instantaneous jump");
        check(maximumSoleDelta<1e-5&&maximumElbowError<1e-4,"Support or elbow joint centre changed");
        // Interrupt midway: the next entry reuses the presented pose, then reaches its own endpoint.
        String arm="arm_r";Object track=tracks.get(arm),mid=sample.invoke(track,targets.get(arm),.08D,duration);
        update.invoke(track,mid,.08D);begin.invoke(track);
        var selectedGame=JsonParser.parseString(Files.readString(root.resolve("artifacts/r52_runtime_candidate/projectseele-local-maps/eva_gameplay_r44_1.json"))).getAsJsonObject();
        var selectedAttack=PoseTransitionsR51Check.frame(rig,selectedGame,"r32_jab",0);
        Object attack=pc.newInstance(new Quaternionf(selectedAttack.rotations.get(arm)),new Vector3f(selectedAttack.positions.get(arm)),new Vector3f(1));
        Object enter=sample.invoke(track,attack,0D,.06D),contact=sample.invoke(track,attack,.06D,.06D);
        check(angle((Quaternionf)rot.invoke(enter),(Quaternionf)rot.invoke(mid))<.06F&&((Vector3f)pos.invoke(enter)).distance((Vector3f)pos.invoke(mid))<1e-6F,"Attack reentry lost presented pose");
        check(angle((Quaternionf)rot.invoke(contact),(Quaternionf)rot.invoke(attack))<.06F,"Guard transition delayed attack entry endpoint");
        var report=new LinkedHashMap<String,Object>();report.put("actual_source_ages",new int[]{770,772});report.put("actual_source_server_tick_gap",after.get("server_tick").getAsLong()-before.get("server_tick").getAsLong());
        report.put("guard_exit_seconds",duration);report.put("tested_render_hz",120);report.put("source_maximum_adjacent_upper_joint_angle_degrees",oldMaximum);report.put("blended_maximum_adjacent_upper_joint_angle_degrees",maximumStep);
        report.put("maximum_C0_rotation_error_degrees",maximumC0);report.put("maximum_final_rotation_error_degrees",maximumFinal);report.put("maximum_final_position_error_blocks",maximumFinalPosition);report.put("maximum_shoe_sole_displacement_blocks",maximumSoleDelta);report.put("maximum_elbow_centre_error_blocks",maximumElbowError);
        report.put("reentry_existing_60ms_entry_endpoint_exact",true);report.put("incoming_attack_duration_policy_unchanged",true);report.put("walk_idle_key_change_keeps_finite_exit",true);report.put("new_weapon_and_attack_rebase_immediately",true);report.put("sequence",sequence);report.put("native_verified",false);report.put("limits","Actual production Track kernel and source policy on actual C7 parent-space bone matrices. Lower-body channels are preserved and elbow centres restored as in writer. No Entity, player/network dispatch, GPU sampler or native frames created.");
        Files.writeString(out.resolve("ACTUAL_C7_GUARD_HANDOFF_KERNEL_REPLAY.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report));
        System.out.println(new Gson().toJson(report));
    }
}
