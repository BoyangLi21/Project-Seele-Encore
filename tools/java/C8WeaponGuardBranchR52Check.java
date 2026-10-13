package com.projectseele.client.render;

import com.google.gson.*;
import com.projectseele.entity.*;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.*;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;

/** Real eligibility policy, real State clock/key branch, and late recordFinal
 * writer on the actual C8 stow endpoint and composed rifle matrices. */
public final class C8WeaponGuardBranchR52Check {
    static void check(boolean v,String why){if(!v)throw new AssertionError(why);}
    static Field field(Class<?> c,String n)throws Exception{var f=c.getDeclaredField(n);f.setAccessible(true);return f;}
    static Method method(Class<?> c,String n,Class<?>...a)throws Exception{var m=c.getDeclaredMethod(n,a);m.setAccessible(true);return m;}
    static Matrix4f matrix(JsonArray a){float[] f=new float[16];for(int i=0;i<16;i++)f[i]=a.get(i).getAsFloat();return new Matrix4f().set(f);}
    static float difference(Matrix4f a,Matrix4f b){float d=0;float[] aa=a.get(new float[16]),bb=b.get(new float[16]);for(int i=0;i<16;i++)d=Math.max(d,Math.abs(aa[i]-bb[i]));return d;}
    static float angle(Quaternionf a,Quaternionf b){return (float)Math.toDegrees(2*Math.acos(Math.min(1,Math.abs(a.dot(b))/Math.sqrt(a.lengthSquared()*b.lengthSquared()))));}
    static LinkedHashMap<String,GeoBone> bones(JsonArray rig){
        var result=new LinkedHashMap<String,GeoBone>();
        for(var e:rig){var r=e.getAsJsonObject();String n=r.get("name").getAsString();GeoBone parent=r.has("parent")?result.get(r.get("parent").getAsString()):null;
            check(!r.has("parent")||parent!=null,"Rig order "+n);var b=new GeoBone(parent,n,false,0D,false,false);var p=r.getAsJsonArray("pivot");b.setPivotX(-p.get(0).getAsFloat());b.setPivotY(p.get(1).getAsFloat());b.setPivotZ(p.get(2).getAsFloat());if(parent!=null)parent.getChildBones().add(b);result.put(n,b);}
        return result;
    }
    static void setMatrices(Map<String,GeoBone> bones,JsonObject captured,Method write)throws Exception {
        for(var entry:bones.entrySet())if(captured.has(entry.getKey()))write.invoke(null,entry.getValue(),matrix(captured.getAsJsonArray(entry.getKey())));
    }
    static Map<String,Quaternionf> rotations(Map<String,GeoBone> bones){var r=new HashMap<String,Quaternionf>();bones.forEach((n,b)->r.put(n,new Quaternionf().rotationZYX(b.getRotZ(),b.getRotY(),b.getRotX())));return r;}
    public static void main(String[] args)throws Exception {
        Path root=Path.of(args[0]),out=root.resolve(".codex/r52_c8_handoff_fix");
        JsonObject before=null,after=null;int rows=0;
        for(String line:Files.readAllLines(root.resolve("artifacts/r52_native_combined_candidate8/ordinary/poses.jsonl"))){var r=JsonParser.parseString(line).getAsJsonObject();rows++;if(r.get("age").getAsInt()==160)before=r;if(r.get("age").getAsInt()==161)after=r;}
        check(rows==244&&before!=null&&after!=null,"Actual C8 recording missing");
        check(before.get("getWeapon").getAsInt()==1&&after.get("getWeapon").getAsInt()==4&&before.get("handling_active").getAsBoolean()&&!after.get("handling_active").getAsBoolean(),"Wrong native switch");
        var body=JsonParser.parseString(Files.readString(root.resolve("artifacts/r52_runtime_candidate/projectseele-local-maps/eva_body_r44.json"))).getAsJsonObject();
        var bs=bones(body.getAsJsonObject("rigs").getAsJsonArray("1"));var model=new BakedGeoModel(bs.values().stream().filter(b->b.getParent()==null).toList(),null);
        var stateType=Class.forName("com.projectseele.client.render.EvaPoseTransition$State");var poseType=Class.forName("com.projectseele.client.render.EvaPoseTransition$Pose");var trackType=Class.forName("com.projectseele.client.render.EvaPoseTransition$Track");
        var sc=stateType.getDeclaredConstructor();sc.setAccessible(true);var tc=trackType.getDeclaredConstructor(poseType);tc.setAccessible(true);
        var read=method(poseType,"read",GeoBone.class);var write=method(EvaPoseTransition.class,"writeModelR52",GeoBone.class,Matrix4f.class);
        var prepare=method(EvaPoseTransition.class,"prepareTransitionR52",stateType,double.class,boolean.class,String.class,String.class,float.class,boolean.class,boolean.class,int.class,boolean.class,boolean.class,float.class);
        var retain=method(EvaPoseTransition.class,"retainNormalWeaponHistoryR52",boolean.class,int.class,int.class,boolean.class,boolean.class);
        check((Boolean)retain.invoke(null,true,1,4,false,true),"Real rifle target still loses history when sharedBody=false");
        check(!(Boolean)retain.invoke(null,false,1,4,false,true)&&!(Boolean)retain.invoke(null,true,1,4,false,false)&&!(Boolean)retain.invoke(null,true,4,4,false,true),"Eligibility broadened to unrelated reset");
        setMatrices(bs,before.getAsJsonObject("final_rendered_model_bones"),write);float reconstructed=0;
        for(var e:bs.entrySet())if(before.getAsJsonObject("final_rendered_model_bones").has(e.getKey()))reconstructed=Math.max(reconstructed,difference(EvaRigTransforms.model(e.getValue()),matrix(before.getAsJsonObject("final_rendered_model_bones").getAsJsonArray(e.getKey()))));
        check(reconstructed<2e-4F,"Actual native model reconstruction "+reconstructed);
        var oldRot=rotations(bs);var state=sc.newInstance();var tracks=(Map<String,Object>)field(stateType,"bones").get(state);
        for(var e:bs.entrySet())tracks.put(e.getKey(),tc.newInstance(read.invoke(null,e.getValue())));
        var history=before.getAsJsonObject("actual_pose_transition_history");double oldTime=history.get("time").getAsDouble();double newTime=after.getAsJsonObject("actual_pose_transition_history").get("time").getAsDouble();
        field(stateType,"finalInitialized").setBoolean(state,true);field(stateType,"weapon").setInt(state,1);field(stateType,"key").set(state,"native-knife-stow");field(stateType,"time").setDouble(state,oldTime);field(stateType,"start").setDouble(state,history.get("start").getAsDouble());field(stateType,"clockInitialized").setBoolean(state,true);field(stateType,"sharedClock").setBoolean(state,true);
        var states=(Map<Object,Object>)field(EvaPoseTransition.class,"STATES").get(null);states.put(null,state);
        setMatrices(bs,after.getAsJsonObject("final_rendered_model_bones"),write);var targetRot=rotations(bs);
        var targetFeet=new HashMap<String,Matrix4f>();for(String n:List.of("root","leg_l","shin_l","foot_l","leg_r","shin_r","foot_r"))targetFeet.put(n,EvaRigTransforms.model(bs.get(n)));
        Matrix4f gunFit=EvaRigTransforms.model(bs.get("hand_r")).invert().mul(EvaRigTransforms.model(bs.get("cannon")));
        double maxStep=0,maxC0=0,maxFinal=0,maxLower=0,maxElbow=0,maxGun=0;Map<String,Quaternionf> previous=null;var sequence=new ArrayList<Map<String,Object>>();
        for(int frame=0;frame<=30;frame++){
            double t=frame/120D;setMatrices(bs,after.getAsJsonObject("final_rendered_model_bones"),write); // actual late rifle/hand writers
            Object next=prepare.invoke(null,state,newTime+t,false,frame<9?"native-rifle-idle":"native-rifle-walk-idle","",0F,false,false,4,false,false,0F);
            check(next==state,"Clock domain or key handoff hard-reset State");
            if(Math.abs(t-.2)>1e-8)check(field(stateType,"weaponGuardExit").getBoolean(state)==(t<.2),"Guard finite window "+t);
            if(frame==0)check(field(stateType,"deferWeaponGuardFinal").getBoolean(state),"Actual regular rifle final writer not selected");
            FirstBattleSignals.beginClientFrame(22_000_000_000L+frame*8_333_333L,false);EvaPoseTransition.recordFinal(null,model);
            var current=rotations(bs);double step=0;
            for(String n:List.of("torso","torso_upper","arm_l","forearm_l","hand_l","arm_r","forearm_r","hand_r"))if(bs.containsKey(n)){
                if(frame==0)maxC0=Math.max(maxC0,angle(current.get(n),oldRot.get(n)));
                if(t>=.2)maxFinal=Math.max(maxFinal,angle(current.get(n),targetRot.get(n)));
                if(previous!=null)step=Math.max(step,angle(previous.get(n),current.get(n)));
            }
            for(var e:targetFeet.entrySet())maxLower=Math.max(maxLower,difference(EvaRigTransforms.model(bs.get(e.getKey())),e.getValue()));
            for(String side:List.of("l","r")){var b=bs.get("forearm_"+side);var p=EvaRigTransforms.elbow(b,side);maxElbow=Math.max(maxElbow,EvaRigTransforms.model(b).transformPosition(new Vector3f(p)).distance(EvaRigTransforms.model(b.getParent()).transformPosition(new Vector3f(p)))*5);}
            var fit=EvaRigTransforms.model(bs.get("hand_r")).invert().mul(EvaRigTransforms.model(bs.get("cannon")));maxGun=Math.max(maxGun,difference(fit,gunFit));
            maxStep=Math.max(maxStep,step);previous=current;sequence.add(Map.of("seconds",t,"maximum_local_joint_step_degrees",step));
        }
        check(maxC0<.06&&maxFinal<.06&&maxLower<1e-5&&maxElbow<2e-4&&maxGun<2e-4,"C0/final/support/hinge/gun residual "+List.of(maxC0,maxFinal,maxLower,maxElbow,maxGun));
        check(maxStep<12,"Still snaps on actual switch "+maxStep);
        // An incoming attack immediately leaves the exit policy and retains its
        // original source phase/entry endpoint, rather than waiting for guard.
        prepare.invoke(null,state,newTime+.26,true,"native-r32_jab","r32_jab",.08F,true,false,4,false,false,.12F);
        check(!field(stateType,"weaponGuardExit").getBoolean(state)&&!field(stateType,"deferWeaponGuardFinal").getBoolean(state)&&field(stateType,"entryCorrection").getBoolean(state)&&field(stateType,"entryStart").getFloat(state)==.08F&&field(stateType,"entryEnd").getFloat(state)==.12F,"Attack delayed or phase rebased");
        EvaPoseTransition.beginFrameR45(null);EvaPoseTransition.recordFinal(null,model);check(!states.containsKey(null),"Complete owner bypass retained guard history");
        var report=new LinkedHashMap<String,Object>();report.put("actual_C8_source_ages",new int[]{160,161});report.put("native_recorded_old_clock",oldTime);report.put("native_recorded_new_clock",newTime);report.put("rifle_non_shared_history_retained",true);report.put("actual_state_not_reconstructed_after_clock_crossing",true);report.put("walk_idle_key_change_window_continues",true);report.put("guard_seconds",.2);report.put("render_hz",120);report.put("native_model_reconstruction_max_component_error",reconstructed);report.put("maximum_C0_joint_rotation_error_degrees",maxC0);report.put("maximum_final_joint_rotation_error_degrees",maxFinal);report.put("maximum_joint_step_degrees",maxStep);report.put("maximum_lower_body_matrix_delta",maxLower);report.put("maximum_elbow_centre_error_blocks",maxElbow);report.put("maximum_rifle_hand_fit_matrix_delta",maxGun);report.put("incoming_attack_phase_and_entry_unchanged",true);report.put("complete_owner_bypass_clears_history",true);report.put("sequence",sequence);report.put("native_verified",false);report.put("limits","Actual C8 same-row composed bone targets drive the production resolved-input State branch and recordFinal writer. Eligibility policy includes non-shared rifle target. Entity/network dispatch and new native pixels remain pending.");
        Files.writeString(out.resolve("ACTUAL_C8_STATE_CLOCK_FINAL_WRITER_REPLAY.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report));var summary=new LinkedHashMap<>(report);summary.remove("sequence");System.out.println(new Gson().toJson(summary));
    }
}
