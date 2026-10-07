package com.projectseele.entity;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import java.io.InputStreamReader;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/** One authored clock drives world roots, poses, sockets and shots. */
public final class FirstBattleClip
{
    public static final int DURATION_TICKS=460,DEATH_TICK=372,RETURN_TICK=432;
    public record BonePose(String[] names,Quaternionf[] rotations,Vector3f[] positions) {}
    public record CameraPose(Vec3 position,Vec3 target,float fov) {}
    private record Role(String[] bones,Quaternionf[][] rotations,Vector3f[][] positions,Map<String,Vec3[]> curves) {}
    private record Data(float fps,Map<String,Role> roles,Vec3[] cameras,Vec3[] targets,float[] fov,Set<Integer> cuts,String surfaceHash,int landingTick,Map<Integer,Integer> eventTicks,float[] referenceSeconds) {}
    private static String loadedFingerprint="";
    private static final Data DATA=load();
    private static Vec3 vector(JsonArray p){return new Vec3(p.get(0).getAsDouble(),p.get(1).getAsDouble(),p.get(2).getAsDouble());}
    private static Vec3[] vectors(JsonArray rows)
    {
        Vec3[] result=new Vec3[rows.size()];for(int i=0;i<result.length;i++)result[i]=vector(rows.get(i).getAsJsonArray());return result;
    }
    private static Data load()
    {
        String review=System.getProperty("projectseele.firstBattleReviewClip","");
        if(!review.isEmpty())
        {
            try{return readLocal(CombatMotionResourcesR44.instancePath(review),"isolated candidate review");}
            catch(Exception e){throw new IllegalStateException("Requested battle candidate could not load",e);}
        }
        String bundle=System.getProperty("projectseele.combatBundleDirectory","");
        if(!bundle.isEmpty())
        {
            try{return readLocal(CombatMotionResourcesR44.instancePath(bundle).resolve("first_battle_r44.json"),"R44 matched combat bundle");}
            catch(Exception e){throw new IllegalStateException("Requested battle bundle could not load",e);}
        }
        for(String revision:List.of("r44","r43","r42","r24","r18","r15","r14","r12"))
        {
            Path local=CombatMotionResourcesR44.instancePath("projectseele-local-maps/first_battle_"+revision+".json");
            if(!Files.isRegularFile(local))continue;
            try{return readLocal(local,revision+" private capture adaptation");}
            catch(Exception e){ProjectSeele.LOGGER.warn("Private first-battle clip rejected; using bundled sequence",e);}
        }
        try(var stream=FirstBattleClip.class.getResourceAsStream("/assets/projectseele/motion/first_battle_r10.json"))
        {return read(stream,"R10 bundled");}
        catch(Exception e){ProjectSeele.LOGGER.error("First-battle clip rejected",e);return null;}
    }
    private static Data readLocal(Path path,String source)throws Exception
    {
        byte[] bytes=CombatMotionResourcesR44.read(path,"first-battle");
        Data result=read(new java.io.ByteArrayInputStream(bytes),source);
        loadedFingerprint=java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(bytes));
        ProjectSeele.LOGGER.info("First-battle loaded clip fingerprint {}",loadedFingerprint);
        return result;
    }
    private static Data read(InputStream stream,String source)throws Exception
    {
            if(stream==null)throw new IllegalStateException("Missing first-battle authored clip");
            JsonObject root=JsonParser.parseReader(new InputStreamReader(stream,StandardCharsets.UTF_8)).getAsJsonObject();float fps=root.get("fps").getAsFloat();
            if((fps!=30&&fps!=60)||root.get("duration_ticks").getAsInt()!=DURATION_TICKS)throw new IllegalArgumentException("First-battle clock mismatch");
            int count=Math.round(DURATION_TICKS/20F*fps)+1;
            Map<String,Role> roles=new HashMap<>();
            for(String name:List.of("eva","angel"))
            {
                var role=root.getAsJsonObject(name);var names=role.getAsJsonArray("bones");String[] bones=new String[names.size()];
                for(int i=0;i<bones.length;i++)bones[i]=names.get(i).getAsString();
                if(new HashSet<>(Arrays.asList(bones)).size()!=bones.length||!Arrays.asList(bones).contains("root"))throw new IllegalArgumentException("Invalid first-battle bone names");
                var frames=role.getAsJsonArray("frames");Quaternionf[][] qs=new Quaternionf[frames.size()][bones.length];Vector3f[][] ps=new Vector3f[frames.size()][bones.length];
                if(frames.size()!=count)throw new IllegalArgumentException("First-battle frame count mismatch");
                for(int i=0;i<frames.size();i++)
                {
                    var frame=frames.get(i).getAsJsonObject();var rotations=frame.getAsJsonArray("rotation_wxyz");var offsets=frame.getAsJsonObject("bone_position_xyz");
                    if(rotations.size()!=bones.length)throw new IllegalArgumentException("First-battle bone count mismatch");
                    for(int b=0;b<bones.length;b++)
                    {
                        var q=rotations.get(b).getAsJsonArray();qs[i][b]=new Quaternionf(q.get(1).getAsFloat(),q.get(2).getAsFloat(),q.get(3).getAsFloat(),q.get(0).getAsFloat());
                        if(!qs[i][b].isFinite()||qs[i][b].lengthSquared()<.5F)throw new IllegalArgumentException("Invalid first-battle quaternion");
                        qs[i][b].normalize();
                        Vec3 p=bones[b].equals("root")?vector(frame.getAsJsonArray("root_m")).scale(112):offsets!=null&&offsets.has(bones[b])?vector(offsets.getAsJsonArray(bones[b])):Vec3.ZERO;
                        ps[i][b]=new Vector3f((float)p.x,(float)p.y,(float)p.z);
                        if(!ps[i][b].isFinite())throw new IllegalArgumentException("Invalid first-battle translation");
                    }
                }
                Map<String,Vec3[]> curves=new HashMap<>();
                for(String curve:List.of("root_blocks","eye_blocks","look_blocks","socket_blocks","socket_outward_blocks","socket_up_blocks","hand_l_blocks","hand_r_blocks","foot_l_blocks","foot_r_blocks","core_blocks","waist_blocks","rib_tip_blocks","rib_side_blocks"))
                    if(role.has(curve))
                    {
                        Vec3[] rows=vectors(role.getAsJsonArray(curve));validateCurve(rows,count);curves.put(curve,rows);
                    }
                for(String required:List.of("root_blocks","eye_blocks","hand_l_blocks","hand_r_blocks"))
                    if(!curves.containsKey(required))throw new IllegalArgumentException("Missing first-battle curve "+required);
                if(name.equals("eva"))adaptDorsalCurves(root,curves);
                roles.put(name,new Role(bones,qs,ps,Map.copyOf(curves)));
            }
            var camera=root.getAsJsonObject("camera");var f=camera.getAsJsonArray("fov");float[] fov=new float[f.size()];for(int i=0;i<fov.length;i++)fov[i]=f.get(i).getAsFloat();
            if(fov.length!=count)throw new IllegalArgumentException("First-battle camera length mismatch");
            for(float angle:fov)if(!Float.isFinite(angle)||angle<20||angle>110)throw new IllegalArgumentException("Invalid first-battle field of view");
            Vec3[] positions=vectors(camera.getAsJsonArray("position")),targets=vectors(camera.getAsJsonArray("target"));validateCurve(positions,count);validateCurve(targets,count);
            Set<Integer> cuts=new HashSet<>();
            if(camera.has("cuts"))for(var cut:camera.getAsJsonArray("cuts"))
            {
                int index=cut.getAsInt();if(index<=0||index>=count)throw new IllegalArgumentException("Invalid first-battle camera cut");cuts.add(index);
            }
            ProjectSeele.LOGGER.info("{} first battle loaded: fps={} frames={} durationTicks={}",source,fps,fov.length,DURATION_TICKS);
            String surfaceHash=root.has("surface_deformation_r14")?root.get("surface_deformation_r14").getAsString():"";
            if(!surfaceHash.isEmpty()&&!surfaceHash.matches("[0-9a-f]{64}"))throw new IllegalArgumentException("Invalid surface cache fingerprint");
            if(!surfaceHash.isEmpty())
            {
                Path cache=CombatMotionResourcesR44.instancePath("projectseele-local-maps/sachiel_wrap_r14.bin");
                if(!Files.isRegularFile(cache)||Files.size(cache)>96*1024*1024L)throw new IllegalArgumentException("Missing private surface performance");
                String digest=HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(cache)));
                if(!digest.equals(surfaceHash))throw new IllegalArgumentException("Private movie / surface mismatch");
            }
            int landing=root.has("landing_tick")?root.get("landing_tick").getAsInt():234;
            if(landing<0||landing>=DURATION_TICKS)throw new IllegalArgumentException("Invalid landing cue");
            Map<Integer,Integer> cues=new HashMap<>();
            if(root.has("event_tick_remap_r42"))root.getAsJsonObject("event_tick_remap_r42").entrySet().forEach(e->cues.put(Integer.parseInt(e.getKey()),e.getValue().getAsInt()));
            float[] reference=new float[count];for(int i=0;i<count;i++)reference[i]=root.has("reference_seconds_r42")?root.getAsJsonArray("reference_seconds_r42").get(i).getAsFloat():i/fps;
            return new Data(fps,Map.copyOf(roles),positions,targets,fov,Set.copyOf(cuts),surfaceHash,landing,Map.copyOf(cues),reference);
    }
    private static void validateCurve(Vec3[] curve,int count)
    {
        if(curve.length!=count)throw new IllegalArgumentException("First-battle curve length mismatch");
        for(Vec3 point:curve)if(!Double.isFinite(point.x)||!Double.isFinite(point.y)||!Double.isFinite(point.z))throw new IllegalArgumentException("Invalid first-battle curve point");
    }
    public static int eventTick(int original){return DATA==null?original:DATA.eventTicks.getOrDefault(original,original);}
    public static float referenceSeconds(float seconds)
    {if(DATA==null)return seconds;float frame=frame(seconds,DATA.referenceSeconds.length);int a=(int)frame,b=Math.min(a+1,DATA.referenceSeconds.length-1);return Mth.lerp(frame-a,DATA.referenceSeconds[a],DATA.referenceSeconds[b]);}
    private static void adaptDorsalCurves(JsonObject root,Map<String,Vec3[]> curves)
    {
        if(root.has("dorsal_profile_version")&&root.get("dorsal_profile_version").getAsInt()>=13)return;
        Vec3[] points=curves.get("socket_blocks"),outs=curves.get("socket_outward_blocks"),ups=curves.get("socket_up_blocks");
        if(points==null||outs==null||ups==null)return;
        var profile=EvaDorsalProfile.byVariant(1);Vec3 delta=profile.centreBlocks().subtract(0,52.9,4.35),oldN=new Vec3(0,.8660254037844386,.5),oldY=new Vec3(0,.5,-.8660254037844386);
        Vec3 newN=profile.outwardModel(),newY=new Vec3(0,newN.z,-newN.y);
        for(int i=0;i<points.length;i++)
        {
            Vec3 origin=points[i],out=outs[i].subtract(origin).normalize(),up=ups[i].subtract(origin).normalize();
            if(out.lengthSqr()<.99||up.lengthSqr()<.99||Math.abs(out.dot(up))>.001)throw new IllegalArgumentException("Invalid authored dorsal basis");
            Vec3 point=origin.add(up.scale(delta.dot(oldY))).add(out.scale(delta.dot(oldN))).add(up.cross(out).scale(-delta.x));
            Vec3 outward=up.scale(newN.dot(oldY)).add(out.scale(newN.dot(oldN))).normalize(),hatchUp=up.scale(newY.dot(oldY)).add(out.scale(newY.dot(oldN))).normalize();
            points[i]=point;outs[i]=point.add(outward.scale(2));ups[i]=point.add(hatchUp.scale(2));
        }
    }
    public static boolean ready(){return DATA!=null;}
    public static String surfaceHash(){return DATA==null?"":DATA.surfaceHash;}
    public static int landingTick(){return DATA==null?234:DATA.landingTick;}
    public static String fingerprint(){return loadedFingerprint;}
    public static boolean hasCurve(boolean eva,String curve){return DATA!=null&&DATA.roles.get(eva?"eva":"angel").curves.containsKey(curve);}
    private static float frame(float seconds,int length){return Mth.clamp(seconds*DATA.fps,0,length-1);}
    private static Vec3 sample(Vec3[] values,float seconds)
    {
        if(values==null||values.length==0)return Vec3.ZERO;float f=frame(seconds,values.length);int a=(int)f,b=Math.min(a+1,values.length-1);return values[a].lerp(values[b],f-a);
    }
    public static BonePose pose(boolean eva,float seconds)
    {
        if(DATA==null)return new BonePose(new String[0],new Quaternionf[0],new Vector3f[0]);
        Role role=DATA.roles.get(eva?"eva":"angel");float f=frame(seconds,role.rotations.length);int a=(int)f,b=Math.min(a+1,role.rotations.length-1);float mix=f-a;
        Quaternionf[] qs=new Quaternionf[role.bones.length];Vector3f[] ps=new Vector3f[role.bones.length];
        for(int i=0;i<qs.length;i++){qs[i]=new Quaternionf(role.rotations[a][i]).slerp(role.rotations[b][i],mix);ps[i]=new Vector3f(role.positions[a][i]).lerp(role.positions[b][i],mix);}
        return new BonePose(role.bones,qs,ps);
    }
    public static EvaBodyPose.Sample finalEvaPose(EvaUnit01Entity eva)
    {
        var result=EvaBodyPose.neutralForTransportR32(eva);var authored=pose(true,DURATION_TICKS/20F);
        for(int i=0;i<authored.names().length;i++)
        {
            String name=authored.names()[i];if(!result.rig.containsKey(name))continue;
            var q=authored.rotations()[i];var p=authored.positions()[i];
            result.rotations.put(name,new Quaternionf(-q.x,-q.y,q.z,q.w));
            result.positions.put(name,new Vector3f(-p.x,p.y,p.z).div(16));
        }
        result.dirty();return result;
    }
    public static Vec3 world(FirstBattleSignals.Spec spec,Vec3 local)
    {
        Vec3 f=Vec3.directionFromRotation(0,spec.yaw()),side=new Vec3(f.z,0,-f.x);
        return spec.origin().add(side.scale(local.x)).add(0,local.y,0).add(f.scale(local.z));
    }
    public static float smooth(float value)
    {
        float t=Mth.clamp(value,0,1);return t*t*t*(10+t*(-15+6*t));
    }
    public static Vec3 localPoint(FirstBattleSignals.Spec spec,boolean eva,String curve,float seconds)
    {
        if(DATA==null)return Vec3.ZERO;Vec3 p=sample(DATA.roles.get(eva?"eva":"angel").curves.get(curve),seconds);
        Vec3 correction=eva?Vec3.ZERO:new Vec3(0,spec.initialHeight()*(1-smooth(seconds/1.2F)),(spec.initialDistance()-34)*(1-smooth(seconds/1.2F)));
        p=p.add(correction);
        if(!curve.equals("root_blocks"))
        {
            // Socket, sole and eye curves follow the same initial heading
            // blend as the actual body, around that actor's moving origin.
            Vec3 origin=sample(DATA.roles.get(eva?"eva":"angel").curves.get("root_blocks"),seconds).add(correction);
            float delta=yaw(spec,eva,seconds)-spec.yaw()-(eva?0:180);
            p=origin.add(p.subtract(origin).yRot((float)Math.toRadians(-delta)));
        }
        return p;
    }
    public static Vec3 point(FirstBattleSignals.Spec spec,boolean eva,String curve,float seconds){return world(spec,localPoint(spec,eva,curve,seconds));}
    public static float yaw(FirstBattleSignals.Spec spec,boolean eva,float seconds)
    {
        return Mth.rotLerp(smooth(seconds/1.2F),eva?spec.evaYaw():spec.angelYaw(),spec.yaw()+(eva?0:180));
    }
    public static CameraPose camera(FirstBattleSignals.Spec spec,float seconds)
    {
        if(DATA==null)return new CameraPose(spec.origin().add(0,45,-50),spec.origin().add(0,30,0),70);
        float f=frame(seconds,DATA.fov.length);int a=(int)f,b=Math.min(a+1,DATA.fov.length-1);
        float mix=DATA.cuts.contains(b)&&b!=a?0:f-a;
        return new CameraPose(world(spec,DATA.cameras[a].lerp(DATA.cameras[b],mix)),world(spec,DATA.targets[a].lerp(DATA.targets[b],mix)),Mth.lerp(mix,DATA.fov[a],DATA.fov[b]));
    }
    public static void applyKinematics(Mob entity)
    {
        if(!(entity instanceof FirstBattleSignals.Actor actor)||!actor.firstBattleSignals().active(entity)||DATA==null)return;
        var signals=actor.firstBattleSignals();var spec=signals.spec(entity);boolean eva=actor.isFirstBattleEva();
        float time=signals.time(entity,1);Vec3 current=point(spec,eva,"root_blocks",time),previous=point(spec,eva,"root_blocks",Math.max(0,time-.05F));
        if("r10-choreography".equals(System.getProperty("projectseele.regionalBuild","")))previous=current;
        entity.setPos(current);entity.xOld=entity.xo=previous.x;entity.yOld=entity.yo=previous.y;entity.zOld=entity.zo=previous.z;
        float heading=yaw(spec,eva,time),oldHeading=yaw(spec,eva,Math.max(0,time-.05F));entity.setYRot(heading);entity.yBodyRot=entity.yHeadRot=heading;entity.yRotO=entity.yBodyRotO=entity.yHeadRotO=oldHeading;
        entity.setDeltaMovement(Vec3.ZERO);entity.fallDistance=0;entity.noPhysics=true;entity.setNoGravity(true);
    }
    public static Vec3 renderOffset(net.minecraft.world.entity.Entity entity,float partial)
    {
        if(!(entity instanceof FirstBattleSignals.Actor actor)||!actor.firstBattleSignals().active(entity)||DATA==null)return Vec3.ZERO;
        var signals=actor.firstBattleSignals();Vec3 desired=point(signals.spec(entity),actor.isFirstBattleEva(),"root_blocks",signals.time(entity,partial));
        Vec3 interpolated=new Vec3(Mth.lerp((double)partial,entity.xOld,entity.getX()),Mth.lerp((double)partial,entity.yOld,entity.getY()),Mth.lerp((double)partial,entity.zOld,entity.getZ()));return desired.subtract(interpolated);
    }
    private FirstBattleClip() {}
}
