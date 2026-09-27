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
    private static final Map<String,Integer> receivedSounds=new java.util.concurrent.ConcurrentHashMap<>();
    @SubscribeEvent public static void sound(net.minecraftforge.client.event.sound.PlaySoundEvent event)
    {
        if(!CombatR31Review.ENABLED||event.getSound()==null)return;
        String id=event.getSound().getLocation().toString();
        if(id.startsWith("projectseele:eva_")||id.startsWith("projectseele:sachiel_"))receivedSounds.merge(id,1,Integer::sum);
    }
    public record View(Vec3 position,Vec3 target) {}
    private static Vec3 lastAngelCamera;
    public static View cameraView(float partial)
    {
        if(!CombatR31Review.ENABLED||!Boolean.getBoolean("projectseele.combatSideView"))return null;
        var mc=Minecraft.getInstance();if(mc.level==null)return null;
        var eva=mc.level.getEntity(CombatR31Review.evaId);var angel=mc.level.getEntity(CombatR31Review.angelId);if(eva==null)return null;
        if(angel!=null)lastAngelCamera=angel.getPosition(partial);if(lastAngelCamera==null)return null;
        Vec3 p=eva.getPosition(partial),q=lastAngelCamera,centre=p.lerp(q,.5).add(0,30,0);
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
        if(CombatR31Review.ENABLED&&Boolean.getBoolean("projectseele.combatSideView"))
        {event.setNearPlaneDistance(256);event.setFarPlaneDistance(768);event.setCanceled(true);}
    }
    private static final JsonArray supportContacts=new JsonArray();
    public static void toeSupport(com.projectseele.entity.EvaUnit01Entity e,String side,Vec3 actual,Vec3 target)
    {if(e.getId()!=CombatR31Review.evaId||supportContacts.size()>12000)return;var r=new JsonObject();r.addProperty("stage",CombatR31Review.stageName);r.addProperty("tick",CombatR31Review.stageTicks);r.addProperty("phase",e.getOrdinaryAttackStage()>=0?e.getOrdinaryAttackProgress(1):e.heavyMotionProgress(1));r.addProperty("side",side);r.addProperty("error_blocks",actual.distanceTo(target));supportContacts.add(r);}
    private static boolean started,oldPause,oldGui;private static int oldDistance,epoch,end;
    private static CameraType oldCamera;private static Path folder;private static String lastPhoto="";
    private static long nextFrame,lastWitness;private static int frame;
    private static final java.util.concurrent.ThreadPoolExecutor frameWriter=new java.util.concurrent.ThreadPoolExecutor(2,2,0,java.util.concurrent.TimeUnit.SECONDS,new java.util.concurrent.ArrayBlockingQueue<>(8),r->{var t=new Thread(r,"r35-combat-frames");t.setDaemon(true);return t;});
    private static boolean writerClosing;private static int droppedFrames;private static volatile String frameWriteFailure="";
    private static final JsonArray frames=new JsonArray(),hands=new JsonArray(),keys=new JsonArray(),normalBones=new JsonArray(),angelSoles=new JsonArray();
    private static long lastAngelSole;
    public static void angelSupport(net.minecraft.world.entity.LivingEntity actor,double lowest)
    {
        if(!CombatR31Review.ENABLED||actor.getId()!=CombatR31Review.angelId||CombatR31Review.done)return;
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
            started=true;oldPause=mc.options.pauseOnLostFocus;oldGui=mc.options.hideGui;oldDistance=mc.options.renderDistance().get();oldCamera=mc.options.getCameraType();
            mc.options.pauseOnLostFocus=false;mc.options.hideGui=Boolean.getBoolean("projectseele.combatSideView");mc.options.renderDistance().set(8);mc.options.broadcastOptions();mc.options.setCameraType(CameraType.THIRD_PERSON_BACK);mc.setCameraEntity(mc.player);
            folder=mc.gameDirectory.toPath().resolve("../artifacts/facility_r31/native_combat_"+System.currentTimeMillis()).normalize();
            try{Files.createDirectories(folder);}catch(Exception e){throw new IllegalStateException(e);}
            CombatR31Review.mediaFolder=folder.toString();CombatR31Review.ready=true;
        }
        if(mc.screen!=null&&!CombatR31Review.done)mc.setScreen(null);
        CombatR31Review.tracked=mc.level.getEntity(CombatR31Review.evaId)!=null&&mc.level.getEntity(CombatR31Review.angelId)!=null;
        CombatR31Review.mounted=mc.player.getRootVehicle().getId()==CombatR31Review.evaId;
        boolean autonomous=mc.level.getEntity(CombatR31Review.evaId) instanceof EvaUnit01Entity actor&&actor.isBerserk();
        boolean driving=CombatR31Review.mounted&&!CombatR31Review.done&&!autonomous;int forward=driving?CombatR31Review.forward:0;
        mc.options.keyUp.setDown(forward>0);mc.options.keyDown.setDown(forward<0);mc.options.keyJump.setDown(driving&&CombatR31Review.jump);
        int strafe=driving?CombatR31Review.strafe:0;
        mc.options.keyLeft.setDown(strafe>0);mc.options.keyRight.setDown(strafe<0);mc.options.keySprint.setDown(false);mc.options.keyShift.setDown(false);
        mc.player.input.up=forward>0;mc.player.input.down=forward<0;mc.player.input.left=strafe>0;mc.player.input.right=strafe<0;mc.player.input.forwardImpulse=forward;mc.player.input.leftImpulse=strafe;
        mc.player.input.jumping=driving&&CombatR31Review.jump;mc.player.zza=forward;mc.player.xxa=strafe;
        mc.player.setYRot(CombatR31Review.heading);mc.player.setXRot(0);mc.setCameraEntity(mc.player);
        if(event.phase==TickEvent.Phase.START&&driving&&epoch!=CombatR31Review.inputEpoch)
        {
            epoch=CombatR31Review.inputEpoch;int action=CombatR31Review.inputAction;
            KeyMapping key=switch(action){case 1->mc.options.keyAttack;case 2->mc.options.keyUse;case 3->Keybinds.EVA_GRAPPLE;case 4->Keybinds.TOGGLE_AT_FIELD;default->null;};
            if(key!=null){KeyMapping.click(key.getKey());var row=new JsonObject();row.addProperty("epoch",epoch);row.addProperty("key",key.getName());row.addProperty("stage",CombatR31Review.stageName);row.addProperty("tick",CombatR31Review.stageTicks);keys.add(row);}
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
            }
            catch(Exception e){throw new IllegalStateException("R31 client evidence",e);}
            mc.options.keyUp.setDown(false);mc.options.keyDown.setDown(false);mc.options.keyJump.setDown(false);mc.options.keyAttack.setDown(false);mc.options.keyUse.setDown(false);
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
        if(!CombatR31Review.ENABLED||eva.getId()!=CombatR31Review.evaId||CombatR31Review.done)return;
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
        if(!CombatR31Review.ENABLED||eva.getId()!=CombatR31Review.evaId||CombatR31Review.done||normalBones.size()>3500)return;
        long now=System.nanoTime();if(point.equals("before")&&now-boneAt<35_000_000)return;if(point.equals("before"))boneAt=now;else if(now-boneAt>25_000_000)return;
        var row=new JsonObject();row.addProperty("stage",CombatR31Review.stageName);row.addProperty("tick",CombatR31Review.stageTicks);row.addProperty("point",point);row.addProperty("action",com.projectseele.entity.EvaCombatR31.action(eva));row.addProperty("ordinary",eva.getOrdinaryAttackStage());row.addProperty("live_phase",eva.combatPhaseR31());row.addProperty("gameplay",com.projectseele.entity.EvaGameplayMotionR32.ready(eva));row.addProperty("gameplay_air_age",com.projectseele.entity.EvaGameplayMotionR32.airAge(eva,0));row.addProperty("ground",eva.onGround());row.addProperty("airborne",eva.isVisuallyAirborneForRender());row.addProperty("y",eva.getY());
        row.addProperty("berserk",eva.isBerserk());row.addProperty("berserk_kind",com.projectseele.entity.EvaBerserkMotionR34.kind(eva));row.addProperty("mouth",com.projectseele.entity.EvaBerserkMotionR34.mouth(eva,0));row.addProperty("powered",eva.isPoweredOn());row.addProperty("health",eva.getHealth());
        model.getBone("r37_jaw").ifPresent(b->{var jaw=new JsonArray();jaw.add(b.getRotX());jaw.add(b.getPosZ());row.add("jaw",jaw);});
        var beat=com.projectseele.entity.CombatFeelR31.beat(eva);row.addProperty("reaction",beat==null?0:beat.kind());
        var bones=new JsonObject();for(String n:List.of("root","torso_lower","torso_upper","head","arm_l","arm_r","forearm_l","forearm_r","wrist_l","wrist_r","hand_l","hand_r","leg_l","leg_r","shin_l","shin_r","ankle_l","ankle_r","foot_l","foot_r","finger_thumb_l","finger_thumb_r","finger_thumb_axis_l","finger_thumb_axis_r","finger_thumb_tip_l","finger_thumb_tip_r","finger_middle_l","finger_middle_r","finger_middle_tip_l","finger_middle_tip_r","finger_middle_distal_l","finger_middle_distal_r"))model.getBone(n).ifPresent(b->{var values=new JsonArray();for(float value:new float[]{b.getRotX(),b.getRotY(),b.getRotZ(),b.getPosX(),b.getPosY(),b.getPosZ(),b.getScaleX(),b.getScaleY(),b.getScaleZ()})values.add(value);bones.add(n,values);});row.add("bones",bones);normalBones.add(row);
    }
    @SubscribeEvent public static void render(TickEvent.RenderTickEvent event)
    {
        if(!CombatR31Review.ENABLED||!started||event.phase!=TickEvent.Phase.END||CombatR31Review.done)return;
        var mc=Minecraft.getInstance();if(mc.level==null||mc.player==null)return;
        long frameAt=System.nanoTime();if(renderCount++==0)firstRender=frameAt;lastRender=frameAt;performance.computeIfAbsent(CombatR31Review.stageName,name->new FrameStats()).sample(frameAt);
        if(CombatR31Review.mounted)CombatR31Review.warmFrames++;
        try
        {
            String photo=CombatR31Review.photo;
            if(!photo.isEmpty()&&!photo.equals(lastPhoto))
            {try(var capture=net.minecraft.client.Screenshot.takeScreenshot(mc.getMainRenderTarget())){capture.writeToFile(folder.resolve(photo+".png"));}lastPhoto=photo;}
            long now=System.nanoTime();String stage=CombatR31Review.stageName;
            boolean video=Boolean.getBoolean("projectseele.combatVideo");
            if(now>=nextFrame&&(stage.startsWith("normal_")||Set.of("air_strike","air_slam","reach","hold","throw","reaction","duel").contains(stage))&&frames.size()<(video?1800:180))
            {
                nextFrame=now+(video?41_666_667L:400_000_000L);String file=String.format(Locale.ROOT,"contact_%04d.jpg",frame++);
                if(frameWriter.getQueue().remainingCapacity()==0){droppedFrames++;return;}
                var capture=net.minecraft.client.Screenshot.takeScreenshot(mc.getMainRenderTarget());
                frameWriter.execute(()->{try(capture){NativeReviewFrames.writeJpeg(capture,folder.resolve(file));}catch(Exception failure){frameWriteFailure=failure.toString();}});
                var row=new JsonObject();row.addProperty("file",file);row.addProperty("stage",stage);row.addProperty("server_tick",CombatR31Review.stageTicks);row.addProperty("actual_rendered_frame",renderCount);row.addProperty("render_elapsed_seconds",(now-firstRender)/1e9);
                row.addProperty("capture_epoch_ms",System.currentTimeMillis());
                frames.add(row);
            }
        }
        catch(Exception error){throw new IllegalStateException("R31 native frame capture",error);}
    }
    private CombatR31Client() {}
}
