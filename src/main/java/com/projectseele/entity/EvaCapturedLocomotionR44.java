package com.projectseele.entity;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import com.projectseele.util.WeakIdentityMap;
import java.nio.file.*;
import java.util.*;
import net.minecraft.util.Mth;
import net.minecraft.network.syncher.*;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.Vec3;
import net.minecraft.world.phys.HitResult;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Captured locomotion channels sampled inside the shared body owner. */
public final class EvaCapturedLocomotionR44
{
    public static final boolean SUPPORT_OWNERSHIP_CANDIDATE=Boolean.getBoolean("projectseele.r44CapturedSupportOwnership");
    private record Clip(float duration, String[] names, Quaternionf[][] rotations, Vector3f[][] positions,
                        Vector3f[][] patches,float[][] support,double travelWorld) {}
    private record Profile(JsonArray rig, Map<String,Clip> clips,Map<String,Vector3f[]> boots) {}
    private static volatile Map<Integer,Profile> PROFILES=Map.of();
    private static final WeakIdentityMap<Level,LevelStates> STATES=new WeakIdentityMap<>();
    private static final WeakIdentityMap<Level,Boolean> RETIRED_LEVELS=new WeakIdentityMap<>();
    private static final EntityDataAccessor<String> CLIP=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.STRING);
    private static final EntityDataAccessor<String> DESTINATION=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.STRING);
    private static final EntityDataAccessor<Long> SINCE=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.LONG);
    private static final EntityDataAccessor<CompoundTag> ORIGIN=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.COMPOUND_TAG);
    private static final EntityDataAccessor<Vector3f> DISPLACEMENT=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.VECTOR3);
    private static volatile boolean loaded;
    private static boolean lifecycleRegistered;
    private static final boolean STATE_WITNESS=Boolean.getBoolean("projectseele.r44CapturedStateWitness");
    private static final String STATE_WITNESS_PATH=System.getProperty("projectseele.r44CapturedStateWitnessPath","");
    private static final Object STATE_WITNESS_LOCK=new Object();
    private static int stateWitnessRows;
    private static boolean stateWitnessFailed;
    private static final class LevelStates
    {
        final boolean client;
        final WeakIdentityMap<EvaUnit01Entity,State> actors=new WeakIdentityMap<>();
        LevelStates(boolean client){this.client=client;}
    }
    private static final class State
    {
        final Map<String,Plant> plants=new HashMap<>();
        String clip;double last;
    }
    private static final class Plant {Vector3f anchor,patch;Matrix4f footWorld;boolean bearing;}
    public static synchronized boolean bootstrap()
    {
        if(!lifecycleRegistered)
        {
            net.minecraftforge.common.MinecraftForge.EVENT_BUS.addListener(EvaCapturedLocomotionR44::onLevelUnload);
            net.minecraftforge.common.MinecraftForge.EVENT_BUS.addListener(EvaCapturedLocomotionR44::onEntityLeave);
            lifecycleRegistered=true;
        }
        return true;
    }
    private static void onLevelUnload(net.minecraftforge.event.level.LevelEvent.Unload event)
    {
        if(event.getLevel() instanceof Level level)
        {
            RETIRED_LEVELS.put(level,true);var state=STATES.remove(level);int before=state==null?0:state.actors.size();
            if(state!=null)state.actors.clear();stateLifecycleWitness("level_unload",level,null,null,before,0);
        }
    }
    private static void onEntityLeave(net.minecraftforge.event.entity.EntityLeaveLevelEvent event)
    {
        if(event.getEntity() instanceof EvaUnit01Entity actor)
        {
            var state=STATES.get(actor.level());if(state==null)return;var removed=state.actors.remove(actor);
            if(removed!=null)synchronized(removed){stateLifecycleWitness("actor_leave",actor.level(),actor,removed,-1,state.actors.size());}
        }
    }
    private static void stateLifecycleWitness(String kind,Level level,EvaUnit01Entity actor,State state,int before,int after)
    {
        if(!STATE_WITNESS||STATE_WITNESS_PATH.isEmpty())return;
        synchronized(STATE_WITNESS_LOCK)
        {
            if(stateWitnessFailed||stateWitnessRows>=256)return;
            try
            {
                Path path=Path.of(STATE_WITNESS_PATH);if(!path.isAbsolute())throw new IllegalArgumentException("Captured state witness path must be absolute");
                if(stateWitnessRows==0){Files.createDirectories(path.getParent());Files.createFile(path);}
                JsonObject row=new JsonObject();row.addProperty("kind",kind);row.addProperty("logical_client",level.isClientSide);
                row.addProperty("level_identity",System.identityHashCode(level));row.addProperty("dimension",level.dimension().location().toString());
                row.addProperty("world_tick",level.getGameTime());row.addProperty("thread",Thread.currentThread().getName());
                row.addProperty("tracked_actors_before",before);row.addProperty("tracked_actors_after",after);
                if(actor!=null){row.addProperty("actor_uuid",actor.getUUID().toString());row.addProperty("network_id",actor.getId());row.addProperty("actor_identity",System.identityHashCode(actor));}
                if(state!=null)
                {
                    row.addProperty("state_identity",System.identityHashCode(state));row.addProperty("clip",state.clip);
                    if(Double.isFinite(state.last))row.addProperty("last_sample_time",state.last);
                    else row.addProperty("last_sample_available",false);
                    row.addProperty("anchors",state.plants.size());
                }
                Files.writeString(path,row.toString()+"\n",java.nio.charset.StandardCharsets.UTF_8,StandardOpenOption.APPEND);stateWitnessRows++;
            }
            catch(Exception failure){stateWitnessFailed=true;ProjectSeele.LOGGER.error("Explicit captured state witness failed",failure);}
        }
    }
    public static void define(SynchedEntityData data)
    {data.define(CLIP,"");data.define(DESTINATION,"");data.define(SINCE,0L);data.define(ORIGIN,new CompoundTag());data.define(DISPLACEMENT,new Vector3f());}

    public static synchronized void reload()
    {
        Map<Integer,Profile> profiles=new HashMap<>();STATES.clear();String directory=System.getProperty("projectseele.capturedLocomotionDirectory","");
        if(directory.isEmpty()){PROFILES=Map.of();loaded=true;return;}
        for(int variant=0;variant<5;variant++)
        {
            Path path=Path.of(directory,"eva_locomotion_capture_r44_"+variant+".json");
            if(!Files.isRegularFile(path))continue;
            try
            {
                byte[] bytes=CombatMotionResourcesR44.read(path,"captured-locomotion-"+variant);
                JsonObject profile=JsonParser.parseString(new String(bytes,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();
                if(!profile.get("schema").getAsString().equals("projectseele.captured-locomotion.r44")
                        ||profile.get("rig_key").getAsInt()!=variant
                        ||!profile.get("root_authority").getAsString().equals("entity-world-pose; captured-stage-travel-removed-once"))
                    throw new IllegalArgumentException("Captured locomotion identity/root authority: "+path);
                String[] names=new String[profile.getAsJsonArray("bones").size()];Set<String> unique=new HashSet<>();
                for(int i=0;i<names.length;i++)
                {names[i]=profile.getAsJsonArray("bones").get(i).getAsString();if(!unique.add(names[i]))throw new IllegalArgumentException("Duplicate bone: "+names[i]);}
                Map<String,Clip> clips=new HashMap<>();
                for(var entry:profile.getAsJsonObject("clips").entrySet())
                {
                    JsonObject source=entry.getValue().getAsJsonObject();JsonArray frames=source.getAsJsonArray("frames");
                    float duration=source.get("duration_seconds").getAsFloat();
                    if(frames.size()<1||!Float.isFinite(duration)||duration<=0)throw new IllegalArgumentException("Invalid captured duration: "+entry.getKey());
                    Quaternionf[][] rotations=new Quaternionf[frames.size()][names.length];Vector3f[][] positions=new Vector3f[frames.size()][names.length];
                    Vector3f[][] patches=new Vector3f[frames.size()][2];float[][] support=new float[frames.size()][2];
                    for(int f=0;f<frames.size();f++)
                    {
                        JsonObject frame=frames.get(f).getAsJsonObject();JsonArray qs=frame.getAsJsonArray("rotation_wxyz");
                        if(qs.size()!=names.length)throw new IllegalArgumentException("Captured channel count: "+entry.getKey());
                        for(int b=0;b<names.length;b++)
                        {
                            JsonArray q=qs.get(b).getAsJsonArray();Quaternionf rotation=new Quaternionf(-q.get(1).getAsFloat(),-q.get(2).getAsFloat(),q.get(3).getAsFloat(),q.get(0).getAsFloat());
                            if(!Float.isFinite(rotation.lengthSquared())||Math.abs(rotation.lengthSquared()-1)>.01F)throw new IllegalArgumentException("Invalid captured quaternion: "+names[b]);
                            rotations[f][b]=rotation.normalize();Vector3f p=new Vector3f();
                            JsonArray xyz=names[b].equals("root")?frame.getAsJsonArray("root_m"):frame.getAsJsonObject("bone_position_xyz").getAsJsonArray(names[b]);
                            if(xyz!=null)p.set(xyz.get(0).getAsFloat(),xyz.get(1).getAsFloat(),xyz.get(2).getAsFloat());
                            if(names[b].equals("root"))p.mul(112);
                            p.mul(-1,1,1).div(16);
                            if(!p.isFinite())throw new IllegalArgumentException("Invalid captured translation: "+names[b]);positions[f][b]=p;
                        }
                        for(int side=0;side<2;side++)
                        {
                            String key=side==0?"l":"r";JsonObject contact=frame.getAsJsonObject("boot_contacts_body").getAsJsonObject(key);
                            patches[f][side]=vector(contact.getAsJsonArray("point"));support[f][side]=contact.get("stance_weight").getAsFloat();
                            if(!patches[f][side].isFinite()||support[f][side]<0||support[f][side]>1)throw new IllegalArgumentException("Invalid actual boot contact: "+entry.getKey());
                        }
                    }
                    double travel=source.get("cycle_travel_world_blocks").getAsDouble();
                    if(!Double.isFinite(travel)||travel<0)throw new IllegalArgumentException("Invalid captured stage travel");
                    clips.put(entry.getKey(),new Clip(duration,names,rotations,positions,patches,support,travel));
                }
                for(String required:List.of("idle","walk","run","crouch_idle","prone_hold","crawl","stand_to_walk","walk_to_run","brake","crouch","to_prone","from_prone","stand"))
                    if(!clips.containsKey(required))throw new IllegalArgumentException("Missing captured state/transition: "+required);
                if(profile.get("render_scale").getAsFloat()!=EvaScale.RENDER_SCALE||!profile.get("contact_units").getAsString().equals("body-model-blocks-before-render-scale"))
                    throw new IllegalArgumentException("Captured contact/render scale contract");
                Map<String,Vector3f[]> boots=new HashMap<>();
                for(String side:List.of("l","r"))
                {var values=profile.getAsJsonObject("boot_vertices_body").getAsJsonArray(side);Vector3f[] points=new Vector3f[values.size()];for(int i=0;i<points.length;i++)points[i]=vector(values.get(i).getAsJsonArray());boots.put(side,points);}
                profiles.put(variant,new Profile(profile.getAsJsonArray("rig_contract_r44"),Map.copyOf(clips),Map.copyOf(boots)));
                ProjectSeele.LOGGER.info("Explicit captured locomotion candidate loaded: rig={} file={} clips={}",variant,path,clips.size());
            }
            catch(Exception failure){throw new IllegalStateException("Cannot load explicit captured locomotion "+path,failure);}
        }
        if(profiles.isEmpty())throw new IllegalStateException("Explicit captured locomotion directory contains no profiles: "+directory);
        PROFILES=Map.copyOf(profiles);loaded=true;
    }

    public static void validateRig(int variant,JsonElement rig)
    {
        Profile profile=PROFILES.get(variant);
        if(profile!=null&&!profile.rig().equals(rig))throw new IllegalArgumentException("Captured/body rig identity mismatch: "+variant);
    }
    private static Vector3f vector(JsonArray a){return new Vector3f(a.get(0).getAsFloat(),a.get(1).getAsFloat(),a.get(2).getAsFloat());}

    private static EvaBodyPose.Sample sample(Clip clip,Map<String,EvaBodyPose.Bone> rig,float phase)
    {
        EvaBodyPose.Sample pose=new EvaBodyPose.Sample(rig);float frame=Mth.clamp(phase,0,1)*(clip.rotations().length-1);
        int first=(int)frame,last=Math.min(first+1,clip.rotations().length-1);float amount=frame-first;
        for(int b=0;b<clip.names().length;b++)
        {
            String name=clip.names()[b];if(!rig.containsKey(name))throw new IllegalArgumentException("Captured bone absent from body rig: "+name);
            pose.rotations.put(name,new Quaternionf(clip.rotations()[first][b]).slerp(clip.rotations()[last][b],amount));
            pose.positions.put(name,new Vector3f(clip.positions()[first][b]).lerp(clip.positions()[last][b],amount));
        }
        return pose;
    }

    private static EvaBodyPose.Sample copy(EvaBodyPose.Sample from)
    {
        EvaBodyPose.Sample pose=new EvaBodyPose.Sample(from.rig);
        from.rotations.forEach((n,q)->pose.rotations.put(n,new Quaternionf(q)));from.positions.forEach((n,p)->pose.positions.put(n,new Vector3f(p)));return pose;
    }
    private static EvaBodyPose.Sample mix(EvaBodyPose.Sample from,EvaBodyPose.Sample to,float amount)
    {
        EvaBodyPose.Sample result=copy(from);
        for(String name:to.rig.keySet())
        {result.rotations.get(name).slerp(to.rotations.get(name),amount);result.positions.get(name).lerp(to.positions.get(name),amount);}
        return result;
    }

    private static String desired(EvaUnit01Entity e,float partial)
    {
        boolean moving=e.rifleMoveBlend(partial)>.12F;
        if(e.isPilotProne())return moving?"crawl":"prone_hold";
        if(e.isPilotCrouching())
        {
            Profile profile=PROFILES.get(variant(e));
            return moving&&profile!=null&&profile.clips().containsKey("crouch_walk")?"crouch_walk":"crouch_idle";
        }
        return moving?(e.rifleRunBlend(partial)>.5F?"run":"walk"):"idle";
    }
    private static boolean prone(String state){return state.equals("crawl")||state.equals("prone_hold");}
    private static boolean crouched(String state){return state.equals("crouch_idle")||state.equals("crouch_walk");}
    private static String transition(String from,String to)
    {
        if(prone(from)&&!prone(to))return "from_prone";
        if(!prone(from)&&prone(to))return crouched(from)?"to_prone":"crouch";
        if(crouched(from)&&!crouched(to))return "stand";
        if(!crouched(from)&&crouched(to))return "crouch";
        if(from.equals("idle")&&(to.equals("walk")||to.equals("run")))return "stand_to_walk";
        if(from.equals("walk")&&to.equals("run"))return "walk_to_run";
        if((from.equals("walk")||from.equals("run"))&&to.equals("idle"))return "brake";
        return "";
    }

    public static EvaBodyPose.Sample sample(EvaUnit01Entity e,int variant,Map<String,EvaBodyPose.Bone> rig,float partial)
    {
        Profile profile=PROFILES.get(variant);
        String clipName=e.getEntityData().get(CLIP);
        if(profile==null||!eligible(e)||clipName.isEmpty())return null;
        if(e.isPilotCrouching()&&!e.isPilotProne()&&e.rifleMoveBlend(partial)>.12F&&!profile.clips().containsKey("crouch_walk"))return null;
        Clip clip=profile.clips().get(clipName);float elapsed=(e.level().getGameTime()-e.getEntityData().get(SINCE)+partial)/20F;
        float phase=phase(e,clipName,clip,elapsed,partial);EvaBodyPose.Sample pose=sample(clip,rig,phase);
        CompoundTag origin=e.getEntityData().get(ORIGIN);
        if(com.projectseele.visual.BodyPoseLayersR40.ENABLED)
        {
            JsonObject review=new JsonObject();review.addProperty("clip",clipName);review.addProperty("phase",phase);
            review.addProperty("elapsed_seconds",elapsed);review.addProperty("since_world_tick",e.getEntityData().get(SINCE));
            review.addProperty("origin_blend_weight",!origin.isEmpty()&&elapsed<.3F?ease(elapsed/.3F):1F);
            float frame=Mth.clamp(phase,0,1)*(clip.patches().length-1);int first=(int)frame,last=Math.min(first+1,clip.patches().length-1);
            JsonObject plants=new JsonObject();
            for(int side=0;side<2;side++)
            {
                JsonObject plant=new JsonObject();Vector3f patch=new Vector3f(clip.patches()[first][side]).lerp(clip.patches()[last][side],frame-first);
                JsonArray point=new JsonArray();point.add(patch.x);point.add(patch.y);point.add(patch.z);plant.add("patch_body",point);
                plant.addProperty("authored_plant_weight",Mth.lerp(frame-first,clip.support()[first][side],clip.support()[last][side]));
                plants.add(side==0?"l":"r",plant);
            }
            review.add("plants",plants);com.projectseele.visual.BodyPoseLayersR40.metadata("actual_captured_sample",review);
        }
        if(!origin.isEmpty()&&elapsed<.3F)
        {var from=new EvaBodyPose.Sample(rig);EvaShutdownR30.decode(origin,from);pose=mix(from,pose,ease(elapsed/.3F));}
        return pose;
    }

    private static int variant(EvaUnit01Entity e){return e instanceof EvaPrototypeEntity un?3+un.getUNSerial():e.getUnitVariant();}
    private static boolean eligible(EvaUnit01Entity e)
    {return !e.isRemoved()&&!RETIRED_LEVELS.getOrDefault(e.level(),false)&&e.isPoweredOn()&&!e.isNervLogisticsLocked()&&!e.isFirstBattleActive()&&!e.isBerserk()&&!e.isCrucified()
            &&e.getActivationTicks()==0&&e.getVisualPose()==0&&e.getWeapon()==EvaUnit01Entity.WEAPON_FISTS;}
    private static boolean stable(String name){return List.of("idle","walk","run","crouch_idle","crouch_walk","prone_hold","crawl").contains(name);}
    private static float ease(float value){value=Mth.clamp(value,0,1);return value*value*value*(10+value*(-15+6*value));}
    private static float phase(EvaUnit01Entity e,String name,Clip clip,float elapsed,float partial)
    {
        if(!stable(name))return Mth.clamp(elapsed/clip.duration(),0,1);
        if(name.equals("walk")||name.equals("run")||name.equals("crawl")||name.equals("crouch_walk")){float phase=e.rifleGaitPhase(partial);return phase-Mth.floor(phase);}
        return elapsed/clip.duration()%1;
    }

    /** Called only by the existing server pose-signal update. */
    public static double serverCycle(EvaUnit01Entity e,float run,double dx,double dz)
    {
        if(!loaded&&System.getProperty("projectseele.capturedLocomotionDirectory","").isEmpty())return 0;
        if(!loaded)EvaBodyPose.hasTerrainStances();Profile profile=PROFILES.get(variant(e));
        if(profile==null||!eligible(e))
        {if(!e.getEntityData().get(CLIP).isEmpty())e.getEntityData().set(CLIP,"");return 0;}
        e.getEntityData().set(DISPLACEMENT,new Vector3f((float)dx,0,(float)dz));
        String requested=desired(e,1),name=e.getEntityData().get(CLIP),destination=e.getEntityData().get(DESTINATION);
        long now=e.level().getGameTime();
        if(name.isEmpty())
        {e.getEntityData().set(CLIP,requested);e.getEntityData().set(DESTINATION,requested);e.getEntityData().set(SINCE,now);e.getEntityData().set(ORIGIN,new CompoundTag());name=requested;destination=requested;}
        float elapsed=(now-e.getEntityData().get(SINCE))/20F;Clip current=profile.clips().get(name);
        String from=name;
        if(!stable(name)&&(elapsed>=current.duration()||!destination.equals(requested)))
        {
            if(elapsed>=current.duration())from=switch(name){case "crouch","from_prone"->"crouch_idle";case "stand"->"idle";case "stand_to_walk"->"walk";default->destination;};
            else from=switch(name){case "to_prone"->elapsed/current.duration()>.5F?"prone_hold":"crouch_idle";case "from_prone"->elapsed/current.duration()>.5F?"crouch_idle":"prone_hold";case "crouch"->"crouch_idle";case "stand"->"idle";default->"idle";};
        }
        if(stable(from)&&(!from.equals(requested)||!name.equals(from)))
        {
            var pose=sample(e,variant(e),EvaBodyPose.neutralForTransportR32(e).rig,1);
            String transition=transition(from,requested);String next=transition.isEmpty()?requested:transition;
            e.getEntityData().set(ORIGIN,pose==null?new CompoundTag():EvaShutdownR30.encode(pose));
            e.getEntityData().set(CLIP,next);e.getEntityData().set(DESTINATION,requested);e.getEntityData().set(SINCE,now);
        }
        if(e.isPilotCrouching()&&!e.isPilotProne())
            return requested.equals("crouch_walk")&&profile.clips().containsKey("crouch_walk")?profile.clips().get("crouch_walk").duration():0;
        return e.isPilotProne()?profile.clips().get("crawl").duration():Mth.lerp(run,profile.clips().get("walk").duration(),profile.clips().get("run").duration());
    }

    /** Contact points are body model blocks; anchors/displacement are world blocks. */
    public static void adapt(EvaUnit01Entity e,EvaBodyPose.Sample pose,float partial)
    {
        Profile profile=PROFILES.get(variant(e));String name=e.getEntityData().get(CLIP);
        if(profile==null||!eligible(e)||name.isEmpty()||e.hasLiveActionForRender(partial)||e.isVisuallyAirborneForRender()
                ||EvaCombatR31.action(e)!=EvaCombatR31.NONE||CombatReactionsR36.active(e))return;
        Clip clip=profile.clips().get(name);float elapsed=(e.level().getGameTime()-e.getEntityData().get(SINCE)+partial)/20F;
        float phase=phase(e,name,clip,elapsed,partial),frame=phase*(clip.patches().length-1);int first=(int)frame,last=Math.min(first+1,clip.patches().length-1);
        double time=e.level().getGameTime()+partial;LevelStates levelState=STATES.computeIfAbsent(e.level(),level->new LevelStates(level.isClientSide));
        State state=levelState.actors.computeIfAbsent(e,key->
        {State created=new State();stateLifecycleWitness("state_create",key.level(),key,created,levelState.actors.size(),levelState.actors.size()+1);return created;});
        synchronized(state)
        {
        if(com.projectseele.visual.BodyPoseLayersR40.ENABLED)
        {
            JsonObject scope=new JsonObject();scope.addProperty("level_identity",System.identityHashCode(e.level()));
            scope.addProperty("logical_client",levelState.client);scope.addProperty("actor_identity",System.identityHashCode(e));
            scope.addProperty("state_identity",System.identityHashCode(state));
            com.projectseele.visual.BodyPoseLayersR40.metadata("actual_captured_state_scope",scope);
        }
        if(!name.equals(state.clip)||time<state.last||time-state.last>20)state.plants.clear();state.clip=name;state.last=time;
        Matrix4f world=EvaRifleKinematics.world(e,partial),inverse=new Matrix4f(world).invert();
        Vector3f displacement=new Vector3f(e.getEntityData().get(DISPLACEMENT));Vector3f localVelocity=inverse.transformDirection(new Vector3f(displacement));
        float worldSpeed=(float)Math.hypot(displacement.x,displacement.z)*20;
        float factor=clip.travelWorld()>1e-5?Mth.clamp((float)(worldSpeed*clip.duration()/clip.travelWorld()),0,1.6F):1;
        var physics=com.projectseele.physics.CombatBodyProfiles.get(e);
        for(int side=0;side<2;side++)
        {
            String suffix=side==0?"l":"r",bone="foot_"+suffix;
            Vector3f patch=new Vector3f(clip.patches()[first][side]).lerp(clip.patches()[last][side],frame-first);
            float weight=Mth.lerp(frame-first,clip.support()[first][side],clip.support()[last][side]);
            Matrix4f foot=pose.matrix(bone);Quaternionf orientation=foot.getUnnormalizedRotation(new Quaternionf()).normalize();
            Vector3f goal=foot.transformPosition(new Vector3f(patch));
            if((name.equals("walk")||name.equals("run")||name.equals("crouch_walk"))&&worldSpeed>.12F)
            {
                Vector3f neutral=new Vector3f(patch),swing=new Vector3f(goal).sub(neutral);
                float forward=-swing.z;Vector3f direction=new Vector3f(localVelocity.x,0,localVelocity.z);
                if(direction.lengthSquared()>1e-8F)direction.normalize();else direction.set(0,0,-1);
                goal.x=neutral.x+swing.x+direction.x*forward*factor;goal.z=neutral.z+direction.z*forward*factor;
            }
            Plant plant=state.plants.computeIfAbsent(suffix,key->new Plant());boolean bearing=weight>.55F&&worldSpeed<160;
            Vector3f worldGoal=world.transformPosition(new Vector3f(goal));
            Vector3f beforeWorldGoal=new Vector3f(worldGoal);
            if(bearing)
            {
                if(!plant.bearing||plant.anchor==null)
                {plant.anchor=new Vector3f(worldGoal);plant.anchor.y=ground(e,plant.anchor,worldGoal.y);}
                else if(plant.footWorld!=null&&plant.patch!=null)
                {
                    Vector3f prior=plant.footWorld.transformPosition(new Vector3f(plant.patch));
                    Vector3f next=plant.footWorld.transformPosition(new Vector3f(patch));plant.anchor.add(next.sub(prior));
                    plant.anchor.y=ground(e,plant.anchor,plant.anchor.y);
                }
                worldGoal.lerp(plant.anchor,ease((weight-.35F)/.45F));goal=inverse.transformPosition(new Vector3f(worldGoal));
            }
            Vector3f offset=new Vector3f(patch).sub(pose.rig.get(bone).pivot());
            Vector3f target=new Vector3f(goal).sub(orientation.transform(new Vector3f(offset)));
            com.projectseele.physics.AnatomicalLimbConstraints.reachFoot(pose,physics,suffix,target,orientation);
            Matrix4f actual=new Matrix4f(world).mul(pose.matrix(bone));float minimum=Float.POSITIVE_INFINITY;
            for(Vector3f vertex:profile.boots().get(suffix))minimum=Math.min(minimum,actual.transformPosition(new Vector3f(vertex)).y);
            float floor=ground(e,worldGoal,worldGoal.y);
            if(minimum<floor-.005F)
            {
                target.y+=(floor-minimum)/EvaScale.RENDER_SCALE;
                com.projectseele.physics.AnatomicalLimbConstraints.reachFoot(pose,physics,suffix,target,orientation);
            }
            plant.bearing=bearing;plant.patch=patch;plant.footWorld=new Matrix4f(world).mul(pose.matrix(bone));
            if(com.projectseele.visual.BodyPoseLayersR40.ENABLED)
            {
                JsonObject row=new JsonObject();row.addProperty("side",suffix);row.addProperty("clip",name);row.addProperty("phase",phase);
                row.addProperty("authored_plant_weight",weight);row.addProperty("bearing",bearing);row.addProperty("world_speed",worldSpeed);
                row.addProperty("stride_warp_factor",factor);row.addProperty("actual_floor_world_y",floor);
                row.addProperty("actual_whole_boot_minimum_before_floor_correction",minimum);
                row.add("source_patch_body",reviewVector(patch));row.add("before_anchor_patch_world",reviewVector(beforeWorldGoal));
                row.add("constrained_patch_world",reviewVector(worldGoal));row.add("actual_final_patch_world",reviewVector(plant.footWorld.transformPosition(new Vector3f(patch))));
                if(plant.anchor!=null)row.add("actual_anchor_world",reviewVector(plant.anchor));
                com.projectseele.visual.BodyPoseLayersR40.appendMetadata("actual_captured_adapt",row);
            }
        }
        }
    }
    public static void invalidateSupportOwnerR44(EvaUnit01Entity e)
    {
        if(SUPPORT_OWNERSHIP_CANDIDATE)
        {
            var levelState=STATES.get(e.level());if(levelState==null)return;
            var state=levelState.actors.get(e);if(state==null)return;
            synchronized(state){state.plants.clear();state.clip="";state.last=Double.NEGATIVE_INFINITY;}
        }
    }
    private static JsonArray reviewVector(Vector3f value)
    {JsonArray out=new JsonArray();out.add(value.x);out.add(value.y);out.add(value.z);return out;}
    private static float ground(EvaUnit01Entity e,Vector3f point,float fallback)
    {
        Vec3 start=new Vec3(point.x,point.y+3,point.z),end=start.add(0,-6,0);
        var hit=e.level().clip(new ClipContext(start,end,ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,e));
        float result=hit.getType()==HitResult.Type.MISS?fallback:(float)hit.getLocation().y+.015F;
        if(com.projectseele.visual.BodyPoseLayersR40.ENABLED)
        {
            JsonObject row=new JsonObject();row.add("query_patch_world",reviewVector(point));row.addProperty("fallback_y",fallback);
            row.addProperty("actual_hit_type",hit.getType().name());row.addProperty("actual_result_y",result);
            com.projectseele.visual.BodyPoseLayersR40.appendMetadata("actual_captured_ground_queries",row);
        }
        return result;
    }
    private EvaCapturedLocomotionR44() {}
}
