package com.projectseele.client.visual;

import com.google.gson.*;
import com.projectseele.client.Keybinds;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.visual.CombatR31Review;
import net.minecraft.client.CameraType;
import net.minecraft.client.KeyMapping;
import net.minecraft.client.Minecraft;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.*;

/** Exercises the same key mappings and client dispatcher as a human driver. */
@Mod.EventBusSubscriber(modid="projectseele",value=Dist.CLIENT)
public final class CombatR31Client
{
    private static final boolean PERFORMANCE_ONLY=Boolean.getBoolean("projectseele.combatPerformanceOnly");
    private static final boolean STILLS_ONLY=Boolean.getBoolean("projectseele.nativeStillsOnlyR45");
    private static final Map<String,Integer> receivedSounds=new java.util.concurrent.ConcurrentHashMap<>();
    @SubscribeEvent public static void sound(net.minecraftforge.client.event.sound.PlaySoundEvent event)
    {
        if(!CombatR31Review.ENABLED||event.getSound()==null)return;
        String id=event.getSound().getLocation().toString();
        if(id.startsWith("projectseele:eva_")||id.startsWith("projectseele:sachiel_")
                ||Set.of("superbwarfare:ntw_20_fire_3p","superbwarfare:annihilator_fire_1p","superbwarfare:annihilator_fire_3p","superbwarfare:annihilator_far","superbwarfare:annihilator_veryfar").contains(id))
            receivedSounds.merge(id,1,Integer::sum);
    }
    public record View(Vec3 position,Vec3 target) {}
    private static Vec3 lastAngelCamera;
    public static View cameraView(float partial)
    {
        if(Boolean.getBoolean("projectseele.pilotViewReviewR45"))return null;
        if(CombatR31Review.AT_FIELD_REVIEW&&CombatR31Review.atFieldPilotView)return null;
        if(!CombatR31Review.ENABLED||!Boolean.getBoolean("projectseele.combatSideView")&&!Boolean.getBoolean("projectseele.r42OpticsReview"))return null;
        var mc=Minecraft.getInstance();if(mc.level==null)return null;
        var eva=mc.level.getEntity(CombatR31Review.evaId);var angel=mc.level.getEntity(CombatR31Review.angelId);if(eva==null)return null;
        if(angel!=null)lastAngelCamera=angel.getPosition(partial);if(lastAngelCamera==null)return null;
        Vec3 p=eva.getPosition(partial),q=lastAngelCamera,centre=p.lerp(q,.5).add(0,30,0);
        if(CombatR31Review.stageName.equals("normal_moving"))
        {
            // The moving case can leave the stationary target far behind.
            // A pair-midpoint camera stopped drawing the EVA halfway through
            // the case, so those later screenshots could not validate motion.
            Vec3 target=p.add(0,28,0);
            return new View(target.add(62,22,56),target);
        }
        if((CombatR31Review.postFinaleOptics||OpticsR43Review.ENABLED)&&eva instanceof EvaUnit01Entity unit)
        {
            Vec3 eye=com.projectseele.entity.EvaBodyPose.opticalEye(unit,partial);
            return new View(eye.add(new Vec3(4,1,10).yRot(-(float)Math.toRadians(unit.getYRot()))),eye);
        }
        if(com.projectseele.visual.StanceContactR41Review.ARTICULATION&&eva instanceof EvaUnit01Entity unit)
        {
            int tick=CombatR31Review.stageTicks;
            if(!com.projectseele.visual.StanceContactR41Review.GAIT_R43&&tick<160&&CombatR31Review.stageName.equals("reaction"))
            {
                String side=tick<80?"r":"l",name="hand_"+side;
                var body=com.projectseele.entity.EvaBodyPose.sample(unit,partial);
                var local=body.matrix(name).transformPosition(new org.joml.Vector3f(body.rig.get(name).pivot()))
                        .mul(com.projectseele.entity.EvaScale.RENDER_SCALE).rotateY((180-unit.getYRot())*(float)Math.PI/180);
                Vec3 target=p.add(local.x,local.y-1,local.z);
                return new View(target.add(side.equals("r")?-12:12,5,12),target);
            }
            Vec3 target=com.projectseele.physics.CombatBodyContacts.coreBounds(unit).getCenter();
            return new View(target.add(57,14,53),target);
        }
        if(com.projectseele.visual.StanceContactR41Review.ENABLED&&CombatR31Review.stageTicks<=360
                &&CombatR31Review.stageName.equals("reaction")&&eva instanceof EvaUnit01Entity unit)
        {
            if(Boolean.getBoolean("projectseele.weaponHandlingReviewR45"))
            {
                var body=com.projectseele.entity.EvaBodyPose.sample(unit,partial);
                var local=body.matrix("pylon_l").transformPosition(new org.joml.Vector3f(-18.8F,177F,3F).div(16))
                        .mul(com.projectseele.entity.EvaScale.RENDER_SCALE).rotateY((180-unit.getYRot())*(float)Math.PI/180);
                Vec3 target=p.add(local.x,local.y,local.z);
                return new View(target.add(new Vec3(29,9,37).yRot(-(float)Math.toRadians(unit.getYRot()))),target);
            }
            if(Boolean.getBoolean("projectseele.r41HandCamera"))
            {
                String side=CombatR31Review.stageTicks<=160?"r":"l",bone="hand_"+side;
                var pose=com.projectseele.entity.EvaBodyPose.sample(unit,partial);
                var local=pose.matrix(bone).transformPosition(new org.joml.Vector3f(pose.rig.get(bone).pivot()))
                        .mul(com.projectseele.entity.EvaScale.RENDER_SCALE).rotateY((180-unit.getYRot())*(float)Math.PI/180);
                Vec3 target=p.add(local.x,local.y,local.z);
                if(unit.getWeapon()==EvaUnit01Entity.WEAPON_RIFLE)
                {
                    var rifle=com.projectseele.entity.EvaRifleKinematics.sample(unit,partial,unit.getAimDirectionForPoseCapture(partial));
                    target=rifle.grip().add(rifle.forward().scale(side.equals("l")?5:0));
                }
                return new View(target.add(side.equals("r")?-13:13,8,12),target);
            }
            Vec3 target=com.projectseele.physics.CombatBodyContacts.coreBounds(unit).getCenter();
            return new View(target.add(62,27,56),target);
        }
        if(CombatR31Review.AWAKENING&&eva instanceof EvaUnit01Entity unit&&com.projectseele.entity.EvaBerserkMotionR34.introduction(unit))
        {
            Vec3 target=com.projectseele.entity.EvaBodyPose.opticalEye(unit,partial).add(0,-1.8,0);
            return new View(target.add(new Vec3(5,2,12).yRot(-(float)Math.toRadians(unit.getYRot()))),target);
        }
        double spread=Math.min(80,p.distanceTo(q)*.35);
        return new View(centre.add(62+spread*.25,24,-52-spread*.10),centre);
    }
    @SubscribeEvent public static void reviewFog(net.minecraftforge.client.event.ViewportEvent.RenderFog event)
    {
        if(CombatR31Review.ENABLED&&Boolean.getBoolean("projectseele.combatSideView")
                &&!Boolean.getBoolean("projectseele.pilotViewReviewR45")
                &&!(CombatR31Review.AT_FIELD_REVIEW&&CombatR31Review.atFieldPilotView))
        {event.setNearPlaneDistance(256);event.setFarPlaneDistance(768);event.setCanceled(true);}
    }
    private static final JsonArray supportContacts=new JsonArray();
    public static void toeSupport(com.projectseele.entity.EvaUnit01Entity e,String side,Vec3 actual,Vec3 target)
    {if(PERFORMANCE_ONLY||e.getId()!=CombatR31Review.evaId||supportContacts.size()>12000)return;var r=new JsonObject();r.addProperty("stage",CombatR31Review.stageName);r.addProperty("tick",CombatR31Review.stageTicks);r.addProperty("phase",e.getOrdinaryAttackStage()>=0?e.getOrdinaryAttackProgress(1):e.heavyMotionProgress(1));r.addProperty("side",side);r.addProperty("error_blocks",actual.distanceTo(target));supportContacts.add(r);}
    private static boolean started,oldPause,oldGui;private static int oldDistance,epoch,end;
    private static CameraType oldCamera;private static Path folder;private static String lastPhoto="";
    private static long nextFrame,lastWitness;private static int frame;
    private static final java.util.concurrent.ThreadPoolExecutor frameWriter=new java.util.concurrent.ThreadPoolExecutor(2,2,0,java.util.concurrent.TimeUnit.SECONDS,new java.util.concurrent.ArrayBlockingQueue<>(8),r->{var t=new Thread(r,"r35-combat-frames");t.setDaemon(true);return t;});
    private static boolean writerClosing;private static int droppedFrames;private static volatile String frameWriteFailure="";
    private static final JsonArray frames=new JsonArray(),hands=new JsonArray(),keys=new JsonArray(),normalBones=new JsonArray(),angelSoles=new JsonArray();
    private static final Map<KeyMapping,Boolean> fieldOriginalKeysR45=new LinkedHashMap<>();
    private static boolean fieldRestoreRecordedR45;
    private static long lastAngelSole;
    public static void angelSupport(net.minecraft.world.entity.LivingEntity actor,double lowest)
    {
        if(PERFORMANCE_ONLY||!CombatR31Review.ENABLED||actor.getId()!=CombatR31Review.angelId||CombatR31Review.done)return;
        long now=System.nanoTime();if(now-lastAngelSole<80_000_000)return;lastAngelSole=now;
        var row=new JsonObject();var beat=com.projectseele.entity.CombatFeelR31.beat(actor);row.addProperty("stage",CombatR31Review.stageName);row.addProperty("tick",CombatR31Review.stageTicks);row.addProperty("world_min_y",lowest);row.addProperty("root_y",actor.getY());row.addProperty("ground",actor.onGround());row.addProperty("reaction",beat==null?0:beat.kind());angelSoles.add(row);
    }
    private static long boneAt;
    private static final Map<String,FrameStats> performance=new LinkedHashMap<>();
    private static long firstRender,lastRender,renderCount;
    private static final class FrameStats
    {
        long count,first,last;final ArrayDeque<Double> tail=new ArrayDeque<>();
        void sample(long now){if(count++==0)first=now;else{tail.addLast((now-last)/1e6);if(tail.size()>120)tail.removeFirst();}last=now;}
        JsonObject json()
        {
            var out=new JsonObject();out.addProperty("rendered_frames",count);out.addProperty("observed_seconds",(last-first)/1e9);out.addProperty("average_fps",last>first?(count-1)*1e9/(last-first):0);
            var sorted=new ArrayList<Double>(tail);Collections.sort(sorted);double sum=tail.stream().mapToDouble(Double::doubleValue).sum();out.addProperty("tail_frame_intervals",tail.size());out.addProperty("tail_fps",sum>0?tail.size()*1000/sum:0);
            if(!sorted.isEmpty()){out.addProperty("tail_median_frame_ms",sorted.get(sorted.size()/2));out.addProperty("tail_p95_frame_ms",sorted.get(Math.min(sorted.size()-1,(int)Math.ceil(sorted.size()*.95)-1)));}return out;
        }
    }
    private static JsonObject performance()
    {
        var out=new JsonObject();out.addProperty("rendered_frames",renderCount);out.addProperty("observed_seconds",(lastRender-firstRender)/1e9);out.addProperty("average_fps",lastRender>firstRender?(renderCount-1)*1e9/(lastRender-firstRender):0);out.addProperty("capture_overhead_included",true);
        var phases=new JsonObject();performance.forEach((name,stats)->phases.add(name,stats.json()));out.add("phases",phases);return out;
    }

    @SubscribeEvent(priority=EventPriority.HIGHEST)
    public static void tick(TickEvent.ClientTickEvent event)
    {
        if(!CombatR31Review.ENABLED)return;var mc=Minecraft.getInstance();if(mc.player==null||mc.level==null)return;
        if(!started)
        {
            var server=mc.getSingleplayerServer();
            if(server==null||!server.getWorldPath(LevelResource.ROOT).normalize().getFileName().toString().equals(CombatR31Review.WORLD))throw new IllegalStateException("R31 client fixture only supports the isolated integrated review world");
            if(com.projectseele.visual.StanceContactR41Review.FIELD_INPUT_R45)
                for(var key:java.util.List.of(mc.options.keyUp,mc.options.keyDown,mc.options.keyLeft,mc.options.keyRight,mc.options.keySprint,mc.options.keyJump,mc.options.keyAttack,mc.options.keyUse,mc.options.keyShift,Keybinds.CANCEL_LAUNCH))fieldOriginalKeysR45.put(key,key.isDown());
            started=true;oldPause=mc.options.pauseOnLostFocus;oldGui=mc.options.hideGui;oldDistance=mc.options.renderDistance().get();oldCamera=mc.options.getCameraType();
            boolean pilotView=Boolean.getBoolean("projectseele.pilotViewReviewR45");
            mc.options.pauseOnLostFocus=false;mc.options.hideGui=!pilotView&&(Boolean.getBoolean("projectseele.combatSideView")||Boolean.getBoolean("projectseele.r42OpticsReview"));mc.options.renderDistance().set(8);mc.options.broadcastOptions();mc.options.setCameraType(pilotView?CameraType.FIRST_PERSON:CameraType.THIRD_PERSON_BACK);mc.setCameraEntity(mc.player);
            String root=System.getProperty("projectseele.reviewArtifactRoot","");
            folder=(root.isEmpty()?mc.gameDirectory.toPath().resolve("../artifacts/facility_r31"):Path.of(root)).resolve("native_combat_"+System.currentTimeMillis()).normalize();
            try{Files.createDirectories(folder);}catch(Exception e){throw new IllegalStateException(e);}
            CombatR31Review.mediaFolder=folder.toString();CombatR31Review.ready=true;
        }
        if(mc.screen!=null&&!CombatR31Review.done)mc.setScreen(null);
        if(CombatR31Review.AT_FIELD_REVIEW&&!CombatR31Review.done)
        {
            mc.options.setCameraType(CombatR31Review.atFieldPilotView?CameraType.FIRST_PERSON:CameraType.THIRD_PERSON_BACK);
            mc.options.hideGui=!CombatR31Review.atFieldPilotView;
        }
        CombatR31Review.tracked=mc.level.getEntity(CombatR31Review.evaId)!=null&&mc.level.getEntity(CombatR31Review.angelId)!=null;
        CombatR31Review.mounted=com.projectseele.visual.StanceContactR41Review.SHUTDOWN_LIFECYCLE
                ?com.projectseele.world.EvaPilotResolver.controlTarget(mc.player)!=null&&com.projectseele.world.EvaPilotResolver.controlTarget(mc.player).getId()==CombatR31Review.evaId
                :mc.player.getRootVehicle().getId()==CombatR31Review.evaId;
        boolean autonomous=mc.level.getEntity(CombatR31Review.evaId) instanceof EvaUnit01Entity actor&&actor.isBerserk();
        boolean driving=CombatR31Review.mounted&&!CombatR31Review.done&&!autonomous;int forward=driving?CombatR31Review.forward:0;
        mc.options.keyUp.setDown(forward>0);mc.options.keyDown.setDown(forward<0);mc.options.keyJump.setDown(driving&&CombatR31Review.jump);
        int strafe=driving?CombatR31Review.strafe:0;
        mc.options.keyLeft.setDown(strafe>0);mc.options.keyRight.setDown(strafe<0);mc.options.keySprint.setDown(driving&&CombatR31Review.sprint);mc.options.keyShift.setDown(false);
        if(Boolean.getBoolean("projectseele.r45WeaponActionReview"))
        {
            boolean fire=driving&&CombatR31Review.rifleFireHeldR45,aim=driving&&CombatR31Review.rifleAimHeldR45;
            if(fire!=mc.options.keyAttack.isDown()||aim!=mc.options.keyUse.isDown())
            {
                var row=new JsonObject();row.addProperty("kind","physical_hold_edges");row.addProperty("tick",CombatR31Review.stageTicks);
                row.addProperty("attack_down",fire);row.addProperty("use_down",aim);keys.add(row);
            }
            mc.options.keyAttack.setDown(fire);mc.options.keyUse.setDown(aim);
        }
        if(com.projectseele.visual.StanceContactR41Review.CANNON_FIRE_R45)
        {
            boolean held=driving&&com.projectseele.visual.StanceContactR41Review.cannonUseHeldR45;
            if(held!=mc.options.keyUse.isDown()){var row=new JsonObject();row.addProperty("kind","actual_cannon_use_key_edge");row.addProperty("held",held);row.addProperty("tick",CombatR31Review.stageTicks);keys.add(row);}
            mc.options.keyUse.setDown(held);mc.options.keyAttack.setDown(false);
        }
        mc.player.input.up=forward>0;mc.player.input.down=forward<0;mc.player.input.left=strafe>0;mc.player.input.right=strafe<0;mc.player.input.forwardImpulse=forward;mc.player.input.leftImpulse=strafe;
        mc.player.input.jumping=driving&&CombatR31Review.jump;mc.player.zza=forward;mc.player.xxa=strafe;
        mc.player.setYRot(CombatR31Review.heading);mc.player.setXRot(com.projectseele.visual.StanceContactR41Review.CANNON_FIRE_R45?com.projectseele.visual.StanceContactR41Review.cannonViewPitchR45:0);mc.setCameraEntity(mc.player);
        boolean shutdown=com.projectseele.visual.StanceContactR41Review.SHUTDOWN_LIFECYCLE;
        if(shutdown&&!driving&&com.projectseele.visual.StanceContactR41Review.shutdownPhaseR45==2
                &&mc.level.getEntity(CombatR31Review.evaId) instanceof EvaUnit01Entity target)
        {
            Vec3 aim=target.getEntryPlugSocketPosition().subtract(mc.player.getEyePosition());
            mc.player.setYRot((float)Math.toDegrees(Math.atan2(-aim.x,aim.z)));mc.player.setXRot((float)-Math.toDegrees(Math.atan2(aim.y,aim.horizontalDistance())));
        }
        if(event.phase==TickEvent.Phase.START&&(driving||shutdown&&CombatR31Review.inputAction==9)&&epoch!=CombatR31Review.inputEpoch)
        {
            epoch=CombatR31Review.inputEpoch;int action=CombatR31Review.inputAction;
                KeyMapping key=switch(action){case 1->mc.options.keyAttack;case 2->mc.options.keyUse;case 3->Keybinds.EVA_GRAPPLE;case 4->Keybinds.TOGGLE_AT_FIELD;case 5->Keybinds.STOMP;case 6->Keybinds.CYCLE_WEAPON;case 10->com.projectseele.visual.StanceContactR41Review.FIELD_INPUT_R45?Keybinds.CANCEL_LAUNCH:null;case 7->shutdown?Keybinds.EXIT_EVA:null;case 9->shutdown?mc.options.keyUse:null;default->null;};
            if(shutdown&&action==7&&mc.level.getEntity(CombatR31Review.evaId) instanceof EvaUnit01Entity target)
            {
                try{com.projectseele.visual.StanceContactR41Review.shutdownAtExitKeyR45=shutdownCacheR45(target,"live");}
                catch(Exception failure){com.projectseele.visual.StanceContactR41Review.shutdownClientFailureR45=failure.toString();}
                com.projectseele.visual.StanceContactR41Review.shutdownExitKeyR45=true;
            }
            if(shutdown&&action==9)com.projectseele.visual.StanceContactR41Review.shutdownReboardKeyR45=true;
            if(key!=null){
                if(action==10){var actual=new JsonObject();actual.addProperty("kind","actual_direction_mapping_and_C_click");actual.addProperty("up",mc.options.keyUp.isDown());actual.addProperty("down",mc.options.keyDown.isDown());actual.addProperty("left",mc.options.keyLeft.isDown());actual.addProperty("right",mc.options.keyRight.isDown());actual.addProperty("sprint",mc.options.keySprint.isDown());actual.addProperty("C_key_name",key.getName());actual.addProperty("C_binding",key.getTranslatedKeyMessage().getString());actual.addProperty("epoch",epoch);actual.addProperty("tick",CombatR31Review.stageTicks);keys.add(actual);}
                KeyMapping.click(key.getKey());var row=new JsonObject();row.addProperty("epoch",epoch);row.addProperty("key",key.getName());row.addProperty("stage",CombatR31Review.stageName);row.addProperty("tick",CombatR31Review.stageTicks);keys.add(row);}
        }
        if(com.projectseele.visual.StanceContactR41Review.FIELD_INPUT_R45&&com.projectseele.visual.StanceContactR41Review.fieldRestoreInputsR45)
        {
            for(var entry:fieldOriginalKeysR45.entrySet())entry.getKey().setDown(entry.getValue());
            boolean exact=fieldOriginalKeysR45.entrySet().stream().allMatch(entry->entry.getKey().isDown()==entry.getValue());
            com.projectseele.visual.StanceContactR41Review.fieldInputsRestoredR45=exact;
            if(!fieldRestoreRecordedR45){fieldRestoreRecordedR45=true;var row=new JsonObject();row.addProperty("kind","actual_input_restore");row.addProperty("exact",exact);row.addProperty("keys",fieldOriginalKeysR45.size());keys.add(row);}
        }
        if(CombatR31Review.done&&event.phase==TickEvent.Phase.END)
        {
            if(!writerClosing){frameWriter.shutdown();writerClosing=true;}
            if(!frameWriter.isTerminated()||++end<=30)return;
            try
            {
                var output=new JsonObject();output.add("frames",frames);output.add("hand_contacts",hands);output.add("production_key_inputs",keys);output.add("angel_draw_support",angelSoles);output.addProperty("server_failure",CombatR31Review.failure);
                output.addProperty("dropped_capture_frames",droppedFrames);output.addProperty("capture_write_failure",frameWriteFailure);
                var soundCounts=new JsonObject();receivedSounds.forEach(soundCounts::addProperty);output.add("received_combat_sounds",soundCounts);
                output.add("normal_bones",normalBones);output.add("support_contacts_r33",supportContacts);output.add("render_performance",performance());Files.writeString(folder.resolve("render_performance.json"),new GsonBuilder().setPrettyPrinting().create().toJson(performance()));
                Files.writeString(folder.resolve("client_evidence.json"),new GsonBuilder().setPrettyPrinting().create().toJson(output));
                com.projectseele.visual.BodyPoseLayersR40.write(folder);
                com.projectseele.client.render.SharedHandContactWitnessR44.write(folder);
                OpticsR43Review.write(folder);
            }
            catch(Exception e){throw new IllegalStateException("R31 client evidence",e);}
            mc.options.keyUp.setDown(false);mc.options.keyDown.setDown(false);mc.options.keyJump.setDown(false);mc.options.keyAttack.setDown(false);mc.options.keyUse.setDown(false);mc.options.keySprint.setDown(false);
            if(com.projectseele.visual.StanceContactR41Review.FIELD_INPUT_R45)for(var entry:fieldOriginalKeysR45.entrySet())entry.getKey().setDown(entry.getValue());
            mc.options.pauseOnLostFocus=oldPause;mc.options.hideGui=oldGui;mc.options.renderDistance().set(oldDistance);mc.options.broadcastOptions();mc.options.setCameraType(oldCamera);mc.stop();
        }
    }

    /** Called after the real contact IK has written bones, not from a planned proxy. */
    public static void handWitness(EvaUnit01Entity eva,String side,double error,float weight)
    {witness(eva,side,error,weight,null,null);}
    public static void handWitness(EvaUnit01Entity eva,String side,Vec3 actual,Vec3 expected,float weight)
    {witness(eva,side,actual.distanceTo(expected),weight,actual,expected);}
    private static void witness(EvaUnit01Entity eva,String side,double error,float weight,Vec3 actual,Vec3 expected)
    {
        if(PERFORMANCE_ONLY||!CombatR31Review.ENABLED||eva.getId()!=CombatR31Review.evaId||CombatR31Review.done)return;
        // A blended approach is deliberately not at the contact yet. Check the
        // exact contact constraint only at full weight, retaining ALL blends below.
        if(weight>=.9999F){CombatR31Review.handSamples++;CombatR31Review.maximumHandError=Math.max(CombatR31Review.maximumHandError,Double.isFinite(error)?error:Double.POSITIVE_INFINITY);}
        long now=System.nanoTime();if(side.equals("l")&&now-lastWitness<60_000_000L)return;if(side.equals("l"))lastWitness=now;
        if(hands.size()>5000)return;var row=new JsonObject();row.addProperty("stage",CombatR31Review.stageName);row.addProperty("tick",CombatR31Review.stageTicks);row.addProperty("side",side);row.addProperty("weight",weight);row.addProperty("error",Double.isFinite(error)?error:-1);
        if(actual!=null)row.add("actual_palm",vector(actual));if(expected!=null)row.add("target_contact",vector(expected));hands.add(row);
    }
    private static JsonArray vector(Vec3 p){var a=new JsonArray();a.add(p.x);a.add(p.y);a.add(p.z);return a;}
    public static void normalWitness(EvaUnit01Entity eva,software.bernie.geckolib.cache.object.BakedGeoModel model,String point)
    {
        if(PERFORMANCE_ONLY||!CombatR31Review.ENABLED||eva.getId()!=CombatR31Review.evaId||CombatR31Review.done||normalBones.size()>3500)return;
        long now=System.nanoTime();if(point.equals("before")&&now-boneAt<35_000_000)return;if(point.equals("before"))boneAt=now;else if(now-boneAt>25_000_000)return;
        var row=new JsonObject();row.addProperty("stage",CombatR31Review.stageName);row.addProperty("tick",CombatR31Review.stageTicks);row.addProperty("point",point);row.addProperty("action",com.projectseele.entity.EvaCombatR31.action(eva));row.addProperty("ordinary",eva.getOrdinaryAttackStage());row.addProperty("live_phase",eva.combatPhaseR31());row.addProperty("gameplay",com.projectseele.entity.EvaGameplayMotionR32.ready(eva));row.addProperty("gameplay_air_age",com.projectseele.entity.EvaGameplayMotionR32.airAge(eva,0));row.addProperty("ground",eva.onGround());row.addProperty("airborne",eva.isVisuallyAirborneForRender());row.addProperty("y",eva.getY());
        row.addProperty("berserk",eva.isBerserk());row.addProperty("berserk_kind",com.projectseele.entity.EvaBerserkMotionR34.kind(eva));row.addProperty("mouth",com.projectseele.entity.EvaBerserkMotionR34.mouth(eva,0));row.addProperty("powered",eva.isPoweredOn());row.addProperty("health",eva.getHealth());
        model.getBone("r37_jaw").ifPresent(b->{var jaw=new JsonArray();jaw.add(b.getRotX());jaw.add(b.getPosZ());row.add("jaw",jaw);});
        var beat=com.projectseele.entity.CombatFeelR31.beat(eva);row.addProperty("reaction",beat==null?0:beat.kind());
        var bones=new JsonObject();for(String n:List.of("root","torso_lower","torso_upper","head","arm_l","arm_r","forearm_l","forearm_r","wrist_l","wrist_r","hand_l","hand_r","leg_l","leg_r","shin_l","shin_r","ankle_l","ankle_r","foot_l","foot_r","finger_thumb_l","finger_thumb_r","finger_thumb_axis_l","finger_thumb_axis_r","finger_thumb_tip_l","finger_thumb_tip_r","finger_middle_l","finger_middle_r","finger_middle_tip_l","finger_middle_tip_r","finger_middle_distal_l","finger_middle_distal_r"))model.getBone(n).ifPresent(b->{var values=new JsonArray();for(float value:new float[]{b.getRotX(),b.getRotY(),b.getRotZ(),b.getPosX(),b.getPosY(),b.getPosZ(),b.getScaleX(),b.getScaleY(),b.getScaleZ()})values.add(value);bones.add(n,values);});row.add("bones",bones);normalBones.add(row);
    }
    /** Read the existing final-frame cache; never asks a renderer to write bones. */
    private static net.minecraft.nbt.CompoundTag shutdownCacheR45(EvaUnit01Entity eva,String name) throws Exception
    {
        Class<?> type=Class.forName("com.projectseele.client.render.EvaShutdownPoseR30");
        var field=type.getDeclaredField("VIEWS");field.setAccessible(true);
        var views=(Map<?,?>)field.get(null);Object view=views.get(eva);
        if(view==null)return new net.minecraft.nbt.CompoundTag();
        var value=view.getClass().getDeclaredField(name);value.setAccessible(true);
        return ((net.minecraft.nbt.CompoundTag)value.get(view)).copy();
    }
    private static void shutdownBoneReadR45(software.bernie.geckolib.cache.object.GeoBone bone,net.minecraft.nbt.CompoundTag tag)
    {
        var list=new net.minecraft.nbt.ListTag();
        for(float n:new float[]{bone.getRotX(),bone.getRotY(),bone.getRotZ(),bone.getPosX(),bone.getPosY(),bone.getPosZ(),bone.getScaleX(),bone.getScaleY(),bone.getScaleZ()})
        {if(!Float.isFinite(n))throw new IllegalStateException("Nonfinite actual shutdown bone "+bone.getName());list.add(net.minecraft.nbt.FloatTag.valueOf(n));}
        tag.put(bone.getName(),list);for(var child:bone.getChildBones())shutdownBoneReadR45(child,tag);
    }
    private static double shutdownPoseErrorR45(net.minecraft.nbt.CompoundTag actual,net.minecraft.nbt.CompoundTag expected)
    {
        if(!actual.getAllKeys().equals(expected.getAllKeys()))throw new IllegalStateException("Captured/actual shutdown bone set differs");
        double rotation=0,position=0,scale=0;
        for(String name:expected.getAllKeys())
        {
            var a=actual.getList(name,net.minecraft.nbt.Tag.TAG_FLOAT);var b=expected.getList(name,net.minecraft.nbt.Tag.TAG_FLOAT);
            if(a.size()!=9||b.size()!=9)throw new IllegalStateException("Shutdown bone does not have nine channels "+name);
            var qa=new org.joml.Quaternionf().rotationZYX(a.getFloat(2),a.getFloat(1),a.getFloat(0));
            var qb=new org.joml.Quaternionf().rotationZYX(b.getFloat(2),b.getFloat(1),b.getFloat(0));
            rotation=Math.max(rotation,1-Math.min(1,Math.abs(qa.dot(qb))));
            for(int i=3;i<6;i++)position=Math.max(position,Math.abs(a.getFloat(i)-b.getFloat(i)));
            for(int i=6;i<9;i++)scale=Math.max(scale,Math.abs(a.getFloat(i)-b.getFloat(i)));
        }
        return Math.max(rotation,Math.max(position,scale));
    }
    private static void shutdownWitnessR45(Minecraft mc)
    {
        if(!com.projectseele.visual.StanceContactR41Review.SHUTDOWN_LIFECYCLE)return;
        try
        {
            if(!(mc.level.getEntity(CombatR31Review.evaId) instanceof EvaUnit01Entity eva)
                    ||!mc.player.getUUID().equals(com.projectseele.visual.StanceContactR41Review.shutdownPilotR45))return;
            if(!(mc.getEntityRenderDispatcher().getRenderer(eva) instanceof com.projectseele.client.render.EvaUnit01Renderer renderer))throw new IllegalStateException("Actual EVA renderer missing");
            var model=renderer.getGeoModel().getBakedModel(renderer.getGeoModel().getModelResource(eva));var actual=new net.minecraft.nbt.CompoundTag();
            for(var bone:model.topLevelBones())shutdownBoneReadR45(bone,actual);
            if(actual.getAllKeys().size()!=110)throw new IllegalStateException("Expected current v49 complete 110-bone model, got "+actual.getAllKeys().size());
            int mode=com.projectseele.entity.EvaShutdownR30.mode(eva),phase=com.projectseele.visual.StanceContactR41Review.shutdownPhaseR45;
            if(mode==com.projectseele.entity.EvaShutdownR30.ACTIVE&&eva.isPoweredOn())
                com.projectseele.visual.StanceContactR41Review.shutdownLiveR45=shutdownCacheR45(eva,"live");
            if(phase==2&&mode==com.projectseele.entity.EvaShutdownR30.ACTIVE
                    &&com.projectseele.world.EvaPilotResolver.controlTarget(mc.player)==eva
                    &&!com.projectseele.visual.StanceContactR41Review.shutdownEmptyEntryR45.isEmpty()
                    &&shutdownPoseErrorR45(actual,com.projectseele.visual.StanceContactR41Review.shutdownEmptyEntryR45)>1e-3)
                com.projectseele.visual.StanceContactR41Review.shutdownReleasedR45=true;
            if(phase>=5)
            {
                if(com.projectseele.physics.CombatBodyDynamics.active(eva)
                        &&!com.projectseele.entity.EvaShutdownR30.displaysCapturedPoseR45(eva)
                        &&!com.projectseele.visual.StanceContactR41Review.shutdownPowerEntryR45.isEmpty())
                {
                    com.projectseele.visual.StanceContactR41Review.shutdownDownFramesR45++;
                    if(shutdownPoseErrorR45(actual,com.projectseele.visual.StanceContactR41Review.shutdownPowerEntryR45)>1e-3)
                        com.projectseele.visual.StanceContactR41Review.shutdownDownRenderedR45=true;
                }
                return;
            }
            boolean empty=mode==com.projectseele.entity.EvaShutdownR30.EMPTY,power=mode==com.projectseele.entity.EvaShutdownR30.POWER_LOCK;
            if(!empty&&!power)return;
            var entry=shutdownCacheR45(eva,"entry");if(entry.isEmpty())return;
            if(empty&&com.projectseele.visual.StanceContactR41Review.shutdownEmptyEntryR45.isEmpty())
            {
                if(!entry.equals(com.projectseele.visual.StanceContactR41Review.shutdownLiveR45))throw new IllegalStateException("EMPTY cut is not the latest actual live frame");
                com.projectseele.visual.StanceContactR41Review.shutdownEmptyEntryR45=entry.copy();
            }
            if(power&&com.projectseele.visual.StanceContactR41Review.shutdownPowerEntryR45.isEmpty())
            {
                if(!entry.equals(com.projectseele.visual.StanceContactR41Review.shutdownLiveR45))throw new IllegalStateException("POWER cut reused an earlier episode instead of the latest actual live frame");
                com.projectseele.visual.StanceContactR41Review.shutdownPowerEntryR45=entry.copy();
            }
            if(eva.level().getGameTime()-com.projectseele.entity.EvaShutdownR30.since(eva)<20)return;
            if(!com.projectseele.entity.EvaShutdownR30.displaysCapturedPoseR45(eva))throw new IllegalStateException("Unexpected physics/transport owner during normal freeze");
            var held=empty?com.projectseele.visual.StanceContactR41Review.shutdownEmptyEntryR45:com.projectseele.visual.StanceContactR41Review.shutdownPowerEntryR45;
            shutdownPoseErrorR45(actual,held);
            double rotation=0,position=0,scale=0;
            for(String name:held.getAllKeys())
            {
                var a=actual.getList(name,net.minecraft.nbt.Tag.TAG_FLOAT);var b=held.getList(name,net.minecraft.nbt.Tag.TAG_FLOAT);
                var qa=new org.joml.Quaternionf().rotationZYX(a.getFloat(2),a.getFloat(1),a.getFloat(0));var qb=new org.joml.Quaternionf().rotationZYX(b.getFloat(2),b.getFloat(1),b.getFloat(0));
                rotation=Math.max(rotation,1-Math.min(1,Math.abs(qa.dot(qb))));for(int i=3;i<6;i++)position=Math.max(position,Math.abs(a.getFloat(i)-b.getFloat(i)));for(int i=6;i<9;i++)scale=Math.max(scale,Math.abs(a.getFloat(i)-b.getFloat(i)));
            }
            com.projectseele.visual.StanceContactR41Review.shutdownRotationErrorR45=Math.max(com.projectseele.visual.StanceContactR41Review.shutdownRotationErrorR45,rotation);
            com.projectseele.visual.StanceContactR41Review.shutdownPositionErrorR45=Math.max(com.projectseele.visual.StanceContactR41Review.shutdownPositionErrorR45,position);
            com.projectseele.visual.StanceContactR41Review.shutdownScaleErrorR45=Math.max(com.projectseele.visual.StanceContactR41Review.shutdownScaleErrorR45,scale);
            if(empty)com.projectseele.visual.StanceContactR41Review.shutdownEmptyFramesR45++;else com.projectseele.visual.StanceContactR41Review.shutdownPowerFramesR45++;
        }
        catch(Exception failure){com.projectseele.visual.StanceContactR41Review.shutdownClientFailureR45=failure.toString();}
    }

    @SubscribeEvent public static void render(TickEvent.RenderTickEvent event)
    {
        if(event.phase==TickEvent.Phase.END)com.projectseele.client.render.SharedHandContactWitnessR44.finishFrame();
        if(!CombatR31Review.ENABLED||!started||event.phase!=TickEvent.Phase.END||CombatR31Review.done)return;
        var mc=Minecraft.getInstance();if(mc.level==null||mc.player==null)return;
        shutdownWitnessR45(mc);
        long frameAt=System.nanoTime();if(renderCount++==0)firstRender=frameAt;lastRender=frameAt;performance.computeIfAbsent(CombatR31Review.stageName,name->new FrameStats()).sample(frameAt);
        if(CombatR31Review.mounted)CombatR31Review.warmFrames++;
        if(PERFORMANCE_ONLY&&!STILLS_ONLY)return;
        try
        {
            String photo=CombatR31Review.photo;
            if(!photo.isEmpty()&&!photo.equals(lastPhoto))
            {try(var capture=net.minecraft.client.Screenshot.takeScreenshot(mc.getMainRenderTarget())){capture.writeToFile(folder.resolve(photo+".png"));}lastPhoto=photo;}
            if(STILLS_ONLY)return;
            long now=System.nanoTime();String stage=CombatR31Review.stageName;
            boolean video=Boolean.getBoolean("projectseele.combatVideo");
            if(now>=nextFrame&&(stage.startsWith("normal_")||stage.startsWith("atfield_")||Set.of("air_strike","air_slam","reach","hold","throw","reaction","duel").contains(stage))&&frames.size()<(video?1800:180))
            {
                nextFrame=now+(video?41_666_667L:400_000_000L);String file=String.format(Locale.ROOT,"contact_%04d.jpg",frame++);
                if(frameWriter.getQueue().remainingCapacity()==0){droppedFrames++;return;}
                var capture=net.minecraft.client.Screenshot.takeScreenshot(mc.getMainRenderTarget());
                frameWriter.execute(()->{try(capture){NativeReviewFrames.writeJpeg(capture,folder.resolve(file));}catch(Exception failure){frameWriteFailure=failure.toString();}});
                var row=new JsonObject();row.addProperty("file",file);row.addProperty("stage",stage);row.addProperty("server_tick",CombatR31Review.stageTicks);row.addProperty("actual_rendered_frame",renderCount);row.addProperty("render_elapsed_seconds",(now-firstRender)/1e9);
                if(mc.level.getEntity(CombatR31Review.evaId) instanceof EvaUnit01Entity actor)
                    row.addProperty("first_battle_seconds",actor.isFirstBattleActive()?actor.firstBattleSignals().time(actor,mc.getFrameTime()):-1);
                row.addProperty("capture_epoch_ms",System.currentTimeMillis());
                frames.add(row);
            }
        }
        catch(Exception error){throw new IllegalStateException("R31 native frame capture",error);}
    }
    private CombatR31Client() {}
}
