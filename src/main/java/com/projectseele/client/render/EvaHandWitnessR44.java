package com.projectseele.client.render;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.projectseele.entity.EvaGameplayMotionR32;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.FirstBattleSignals;
import com.projectseele.util.WeakIdentityMap;
import net.minecraft.client.Minecraft;
import net.minecraft.resources.ResourceLocation;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import software.bernie.geckolib.cache.object.GeoBone;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.util.HashMap;
import java.util.HashSet;
import java.util.HexFormat;
import java.util.Map;
import java.util.Set;

/** Opt-in final named palette and actual CPU hand vertex submission, never an art verdict. */
public final class EvaHandWitnessR44
{
    private static final String OUTPUT=System.getProperty("projectseele.r44HandWitnessPath","");
    private static final class State
    {
        long tick=Long.MIN_VALUE,frame;int samples;final Set<String> parts=new HashSet<>();
    }
    private static final WeakIdentityMap<EvaUnit01Entity,State> STATES=new WeakIdentityMap<>();
    private static final Map<ResourceLocation,String> HASHES=new HashMap<>();
    private static final Set<String> GEOMETRY_WRITTEN=new HashSet<>();
    private static final java.util.concurrent.ThreadPoolExecutor WRITER=new java.util.concurrent.ThreadPoolExecutor(
            1,1,0,java.util.concurrent.TimeUnit.SECONDS,new java.util.concurrent.ArrayBlockingQueue<>(256),r->{
                Thread thread=new Thread(r,"R44 actual hand witness writer");thread.setDaemon(true);return thread;
            });
    private static volatile String writeFailure="";
    public static boolean awaitingWrites()
    {
        if(!writeFailure.isEmpty())throw new IllegalStateException("Actual hand witness write failed: "+writeFailure);
        return WRITER.getActiveCount()!=0||!WRITER.getQueue().isEmpty();
    }
    static boolean enabled(){return !OUTPUT.isEmpty();}
    static void capture(EvaUnit01Entity eva,BakedGeoModel model,float partial,Matrix4f modelToWorld)
    {
        if(!enabled()||ShaderShadowPassR44.active())return;
        int minimumReviewTick=Integer.getInteger("projectseele.r45HandWitnessMinReviewTick",-1);
        int maximumReviewTick=Integer.getInteger("projectseele.r45HandWitnessMaxReviewTick",Integer.MAX_VALUE);
        if(minimumReviewTick>=0)
        {
            if(!com.projectseele.visual.CombatR31Review.ENABLED||eva.getId()!=com.projectseele.visual.CombatR31Review.evaId)return;
            int reviewTick=com.projectseele.visual.CombatR31Review.stageTicks;
            if(reviewTick<minimumReviewTick||reviewTick>maximumReviewTick)return;
        }
        String stage=System.getProperty("projectseele.r45HandWitnessStage","");
        if(!stage.isEmpty()&&!stage.equals(com.projectseele.visual.CombatR31Review.stageName))return;
        float minimum=Float.parseFloat(System.getProperty("projectseele.r45HandWitnessMinStance","0"));
        if(eva.rifleStanceLevel(partial)<minimum)return;
        State state=STATES.get(eva);if(state==null){state=new State();STATES.put(eva,state);}
        long tick=eva.level().getGameTime();
        int gap=Math.max(1,Integer.getInteger("projectseele.r44HandWitnessTickGap",3));
        if(state.samples>=Integer.getInteger("projectseele.r44HandWitnessFrames",180)
                ||state.tick!=Long.MIN_VALUE&&tick-state.tick<gap)return;
        state.tick=tick;state.frame=FirstBattleSignals.clientFrameTime();state.samples++;state.parts.clear();
        JsonObject row=base(eva,state,"final_named_palette");
        String asset=eva.isExperimentalUnit()?eva.experimentalAssetName():"eva_unit0"+eva.getUnitVariant();
        row.addProperty("loaded_geometry_sha256",hash(new ResourceLocation("projectseele","geo/"+asset+".geo.json")));
        row.addProperty("stance",eva.rifleStanceLevel(partial));row.addProperty("gait",eva.rifleGaitPhase(partial));
        row.addProperty("move_blend",eva.rifleMoveBlend(partial));row.addProperty("run_blend",eva.rifleRunBlend(partial));
        row.addProperty("review_stage",com.projectseele.visual.CombatR31Review.stageName);
        row.addProperty("review_tick",com.projectseele.visual.CombatR31Review.stageTicks);
        row.addProperty("action_clip",EvaGameplayMotionR32.activeGroundClip(eva,partial));
        row.addProperty("action_phase",EvaGameplayMotionR32.activeGroundPhase(eva,partial));
        row.addProperty("actor_y",eva.getY());row.addProperty("partial",partial);
        row.addProperty("rifle_sight",eva.rifleSightBlendR45(partial));
        var firearm=EvaRifleContactRig.LAST.get(eva.getId());
        if(firearm!=null&&firearm.left()!=null&&firearm.right()!=null)
        {
            var trace=new JsonObject();trace.addProperty("measured_grip",firearm.measured());
            for(String side:java.util.List.of("l","r"))
            {
                var arm=side.equals("l")?firearm.left():firearm.right();var entry=new JsonObject();
                entry.add("elbow_after_rifle",vector(arm.elbow()));entry.add("wrist_after_rifle",vector(arm.wrist()));entry.add("pole",vector(arm.pole()));trace.add(side,entry);
            }
            row.add("rifle_arm_owner_trace",trace);
        }
        row.addProperty("shared_hands",EvaGameplayMotionR32.sharedHands(eva,partial));
        row.add("actual_owner_inputs",EvaGameplayMotionR32.ownerDiagnosticR44(eva,partial));
        row.add("model_to_world_column_major",matrix(modelToWorld));JsonArray palette=new JsonArray();
        for(String name:observedNames())
        {
            GeoBone bone=model.getBone(name).orElse(null);if(bone==null)continue;
            JsonObject b=new JsonObject();b.addProperty("name",name);b.addProperty("parent",bone.getParent()==null?"":bone.getParent().getName());
            b.add("final_model_column_major",matrix(EvaRigTransforms.model(bone)));
            b.add("local_euler_radians",vector(new Vector3f(bone.getRotX(),bone.getRotY(),bone.getRotZ())));
            var bind=bone.getInitialSnapshot();b.add("bind_local_euler_radians",vector(new Vector3f(bind.getRotX(),bind.getRotY(),bind.getRotZ())));
            b.add("pivot_model",vector(EvaRigTransforms.pivot(bone)));palette.add(b);
        }
        row.add("bones",palette);
        if(Boolean.getBoolean("projectseele.r45BodySurfaceWitness"))
        {
            var joints=new JsonObject();
            for(String side:new String[]{"l","r"})for(String family:new String[]{"knee","elbow"})
            {
                var marker=model.getBone("r30_"+family+"_socket_"+side).orElse(null);
                var upper=model.getBone((family.equals("knee")?"leg_":"arm_")+side).orElse(null);
                var lower=model.getBone((family.equals("knee")?"shin_":"forearm_")+side).orElse(null);
                if(marker==null||upper==null||lower==null)continue;
                var centre=EvaRigTransforms.pivot(marker);
                var first=EvaRigTransforms.model(upper).transformPosition(new Vector3f(centre));
                var second=EvaRigTransforms.model(lower).transformPosition(new Vector3f(centre));
                joints.addProperty(family+"_"+side,first.distance(second)*com.projectseele.entity.EvaScale.RENDER_SCALE);
            }
            row.add("actual_parent_child_joint_error_blocks",joints);
        }
        write(row);
    }
    static void submitted(EvaUnit01Entity eva,GeoBone bone,ResourceLocation resource,float[] original,float[] submitted,
                          int stride,float px,float py,float pz,Matrix4f meshToWorld)
    {
        if(!enabled()||ShaderShadowPassR44.active()||!observedPart(bone.getName()))return;
        State state=STATES.get(eva);
        if(state==null||state.frame!=FirstBattleSignals.clientFrameTime()||!state.parts.add(bone.getName()))return;
        JsonObject row=base(eva,state,"actual_cpu_submitted_part");row.addProperty("bone",bone.getName());
        row.addProperty("resource",resource.toString());row.addProperty("loaded_resource_sha256",hash(resource));
        row.addProperty("stride",stride);row.addProperty("cpu_skin_changed",original!=submitted);
        row.add("mesh_to_world_column_major",matrix(meshToWorld));
        row.add("part_pivot_authored",vector(new Vector3f(px,py,pz)));
        int count=submitted.length/stride;row.addProperty("actual_part_vertex_count",count);
        String key=resource+":"+bone.getName();
        if(GEOMETRY_WRITTEN.add(key))
        {
            JsonObject geometry=base(eva,state,"actual_static_part_geometry");geometry.addProperty("resource_part",key);
            geometry.addProperty("loaded_resource_sha256",hash(resource));geometry.addProperty("actual_part_vertex_count",count);
            geometry.add("part_pivot_authored",vector(new Vector3f(px,py,pz)));JsonArray originalPoints=new JsonArray();
            for(int i=0;i+stride<=original.length;i+=stride)for(int j=0;j<3;j++)originalPoints.add(original[i+j]);
            geometry.add("original_part_xyz",originalPoints);write(geometry);
        }
        row.addProperty("resource_part",key);JsonArray changes=new JsonArray(),world=new JsonArray(),sampleIds=new JsonArray();
        for(int i=0;i+stride<=submitted.length;i+=stride)
        {
            if(Float.floatToIntBits(original[i])!=Float.floatToIntBits(submitted[i])
                    ||Float.floatToIntBits(original[i+1])!=Float.floatToIntBits(submitted[i+1])
                    ||Float.floatToIntBits(original[i+2])!=Float.floatToIntBits(submitted[i+2]))
            {changes.add(i/stride);changes.add(submitted[i]);changes.add(submitted[i+1]);changes.add(submitted[i+2]);}
        }
        int samples=Math.min(18,count);
        for(int i=0;i<samples;i++)
        {
            int vertex=samples==1?0:(int)((long)i*(count-1)/(samples-1));sampleIds.add(vertex);int at=vertex*stride;
            Vector3f p=meshToWorld.transformPosition(new Vector3f(-(submitted[at]+px)/16,(submitted[at+1]+py)/16,(submitted[at+2]+pz)/16));
            world.add(p.x);world.add(p.y);world.add(p.z);
        }
        row.addProperty("exact_cpu_position_change_count",changes.size()/4);
        row.add("submitted_position_changes_index_xyz",changes);row.add("actual_world_sample_vertex_indices",sampleIds);row.add("actual_world_sample_xyz",world);
        row.addProperty("readback_scope","All submitted CPU positions reconstruct exactly from static resource part + sparse changes + actual matrix; 18 indexed world points independently read back. No GPU sample or full world-point dump.");write(row);
    }
    private static String[] handNames(String side)
    {
        java.util.List<String> names=new java.util.ArrayList<>();
        for(String root:new String[]{"arm_","forearm_","wrist_","hand_","r30_hand_frame_"})names.add(root+side);
        for(String digit:new String[]{"index","middle","ring","little","thumb"})
        {
            for(String suffix:new String[]{"_axis","","_tip","_distal"})names.add("finger_"+digit+suffix+"_"+side);
            for(int i=1;i<=3;i++)names.add("r45_hand_"+side+"_"+digit+"_"+i);
        }
        return names.toArray(String[]::new);
    }
    private static String[] observedNames()
    {
        var names=new java.util.LinkedHashSet<String>();
        for(String side:new String[]{"l","r"})java.util.Collections.addAll(names,handNames(side));
        for(String side:new String[]{"l","r"})java.util.Collections.addAll(names,"r45_hand_"+side+"_cup_ring","r45_hand_"+side+"_cup_little");
        java.util.Collections.addAll(names,"cannon","knife");
        java.util.Collections.addAll(names,"pylon_l","r45_knife_hatch_l","r45_knife_carriage_l","r45_knife_actuator_l");
        if(Boolean.getBoolean("projectseele.r45BodySurfaceWitness"))
            java.util.Collections.addAll(names,"root","torso_lower","torso_upper","head","leg_l","leg_r","shin_l","shin_r","ankle_l","ankle_r","foot_l","foot_r");
        return names.toArray(String[]::new);
    }
    private static boolean observedPart(String name)
    {
        return name.startsWith("finger_")||name.startsWith("hand_")||name.startsWith("r45_hand_")||name.equals("cannon")||name.equals("knife")||name.startsWith("r45_knife_")||name.equals("pylon_l")
                ||Boolean.getBoolean("projectseele.r45BodySurfaceWitness")
                &&java.util.Set.of("torso_lower","torso_upper","head","arm_l","arm_r","forearm_l","forearm_r","leg_l","leg_r","shin_l","shin_r","ankle_l","ankle_r","foot_l","foot_r").contains(name);
    }
    private static JsonObject base(EvaUnit01Entity eva,State state,String kind)
    {
        JsonObject row=new JsonObject();row.addProperty("kind",kind);row.addProperty("entity_uuid",eva.getUUID().toString());
        row.addProperty("variant",EvaGameplayMotionR32.variant(eva));row.addProperty("tick",state.tick);row.addProperty("frame",state.frame);
        row.addProperty("scope","Final Gecko palette and actual CPU submission; GPU output and artistic quality are not validated");return row;
    }
    private static JsonArray matrix(Matrix4f value)
    {JsonArray a=new JsonArray();if(value!=null)for(float v:value.get(new float[16]))a.add(v);return a;}
    private static JsonArray vector(Vector3f value)
    {JsonArray a=new JsonArray();a.add(value.x);a.add(value.y);a.add(value.z);return a;}
    private static String hash(ResourceLocation resource)
    {
        return HASHES.computeIfAbsent(resource,key->{try(var in=Minecraft.getInstance().getResourceManager().getResource(key).orElseThrow().open())
        {MessageDigest digest=MessageDigest.getInstance("SHA-256");byte[] block=new byte[65536];int length;
            while((length=in.read(block))>=0)if(length>0)digest.update(block,0,length);return HexFormat.of().formatHex(digest.digest());}
        catch(Exception error){throw new IllegalStateException("Actual hand resource identity missing",error);}});
    }
    private static void write(JsonObject row)
    {
        if(!writeFailure.isEmpty())throw new IllegalStateException("Actual hand witness write failed: "+writeFailure);
        try{WRITER.execute(()->{try{Path path=Path.of(OUTPUT).toAbsolutePath();Files.createDirectories(path.getParent());Files.writeString(path,row+"\n",StandardOpenOption.CREATE,StandardOpenOption.APPEND);}
            catch(Exception error){writeFailure=error.toString();}});}
        catch(java.util.concurrent.RejectedExecutionException error)
        {throw new IllegalStateException("Actual hand witness queue is full; no evidence was silently dropped. Preserve the partial file and retry with a larger tick gap.",error);}
    }
    private EvaHandWitnessR44(){}
}
