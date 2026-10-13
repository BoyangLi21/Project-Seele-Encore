package com.projectseele.client.visual;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.projectseele.ProjectSeele;
import com.projectseele.client.FirstBattleClient;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.network.SeeleNetwork;
import com.projectseele.network.ServerboundEvaControlPacket;
import com.projectseele.visual.FirstBattleR10Review;
import com.projectseele.world.EvaPilotResolver;
import net.minecraft.client.CameraType;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.concurrent.*;
import org.lwjgl.glfw.GLFW;

/** Bounded asynchronous recording of the actual native framebuffer in the disposable review world. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class FirstBattleR10Client
{
    private static final boolean NO_FRAME_CAPTURE=Boolean.getBoolean("projectseele.firstBattleNoFrameCaptureR52");
    private static final boolean KEY_FRAMES=Boolean.getBoolean("projectseele.firstBattleKeyFramesR52");
    private static final boolean FRAME_METADATA=Boolean.getBoolean("projectseele.firstBattleFrameMetadataR52");
    private static final int[] KEY_TICKS=keyTicksR52();
    private static boolean initialized,closing;
    private static boolean warmedCamera;
    private static boolean stopCapturedR52;
    private static boolean stopReadyAtFrameStartR52;
    private static boolean oldPause,oldGui;
    private static int oldDistance,serial,closeTicks,nextKeyFrame;
    private static CameraType oldCamera;
    private static long firstNanos,lastNanos,lastMetadataNanos;
    private static Path output;
    private static final JsonArray frames=new JsonArray();
    private static final JsonArray skippedKeyFrames=new JsonArray();
    private static final ThreadPoolExecutor WRITER=new ThreadPoolExecutor(2,2,0,TimeUnit.SECONDS,new ArrayBlockingQueue<>(6),r->{Thread t=new Thread(r,"first-battle-native-frames");t.setDaemon(true);return t;});
    private static volatile String writeFailure="";
    private static int[] keyTicksR52()
    {
        String value=System.getProperty("projectseele.firstBattleKeyTicksR52","");
        if(value.isBlank())return new int[]{10,50,100,160,220,280,330,360,400,440};
        int[] values=java.util.Arrays.stream(value.split(",")).map(String::trim).mapToInt(Integer::parseInt).distinct().sorted().toArray();
        if(values.length==0||values.length>24||values[0]<1||values[values.length-1]>=460)throw new IllegalArgumentException("Bounded native keyframe ticks required");
        return values;
    }

    @SubscribeEvent public static void tick(TickEvent.ClientTickEvent event)
    {
        if(!FirstBattleR10Review.ENABLED||event.phase!=TickEvent.Phase.END)return;
        var mc=Minecraft.getInstance();if(mc.player==null||mc.level==null)return;
        try
        {
            if(!initialized)
            {
                initialized=true;oldPause=mc.options.pauseOnLostFocus;oldGui=mc.options.hideGui;oldDistance=mc.options.renderDistance().get();oldCamera=mc.options.getCameraType();
                mc.options.pauseOnLostFocus=false;mc.options.hideGui=false;mc.options.renderDistance().set(8);mc.options.setCameraType(CameraType.FIRST_PERSON);mc.options.broadcastOptions();
                String declared=System.getProperty("projectseele.firstBattleCaptureOutputR52","");
                output=declared.isBlank()?mc.gameDirectory.toPath().resolve("../artifacts/first_battle_world_r10/native_movie_"+System.currentTimeMillis()).normalize():Path.of(declared).toAbsolutePath().normalize();Files.createDirectories(output);
            }
            var entity=mc.level.getEntity(FirstBattleR10Review.heroId);
            FirstBattleR10Review.clientTracked=entity instanceof EvaUnit01Entity;
            FirstBattleR10Review.clientMounted=entity!=null&&EvaPilotResolver.controlTarget(mc.player)==entity;
            FirstBattleR10Review.clientCameraRestored=!FirstBattleClient.active()&&mc.options.getCameraType()==CameraType.FIRST_PERSON;
            if(FirstBattleR10Review.warming){warmedCamera=true;mc.options.setCameraType(CameraType.THIRD_PERSON_BACK);}
            else if(warmedCamera){warmedCamera=false;mc.options.setCameraType(CameraType.FIRST_PERSON);}
            if(FirstBattleR10Review.capturePostStopR52)mc.options.setCameraType(CameraType.THIRD_PERSON_BACK);
            else if(stopCapturedR52&&!FirstBattleClient.active())mc.options.setCameraType(CameraType.FIRST_PERSON);
            if(FirstBattleR10Review.actionSerial!=serial)
            {
                serial=FirstBattleR10Review.actionSerial;SeeleNetwork.CHANNEL.sendToServer(new ServerboundEvaControlPacket(FirstBattleR10Review.action));
            }
            mc.options.keyUp.setDown(FirstBattleR10Review.forward!=0);
            if(FirstBattleR10Review.finished||FirstBattleR10Review.reloadRequested)
            {
                mc.options.keyUp.setDown(false);
                if(!closing){closing=true;FirstBattleClient.releaseCamera();mc.options.pauseOnLostFocus=oldPause;mc.options.hideGui=oldGui;mc.options.renderDistance().set(oldDistance);mc.options.setCameraType(oldCamera);WRITER.shutdown();}
                if(++closeTicks>20&&WRITER.isTerminated())
                {
                    if(!frames.isEmpty())
                    {
                        JsonObject manifest=new JsonObject();manifest.addProperty("source",FRAME_METADATA?"Native render-frame metadata; no screenshot, pixel readback or bones":"Native Minecraft framebuffer, timestamped at capture; no interpolated frames");manifest.add("frames",frames);manifest.addProperty("dropped",FirstBattleR10Review.droppedFrames);manifest.addProperty("write_failure",writeFailure);
                        manifest.addProperty("capture_mode",FRAME_METADATA?"frame_metadata_r52":KEY_FRAMES?"keyframes_r52":"full_frame_sequence");
                        if(FRAME_METADATA)manifest.addProperty("metadata_wall_interval_seconds",.5);
                        else if(KEY_FRAMES){JsonArray schedule=new JsonArray();for(int tick:KEY_TICKS)schedule.add(tick);manifest.add("keyframe_schedule_ticks",schedule);manifest.add("skipped_keyframe_ticks",skippedKeyFrames);}
                        Files.writeString(output.resolve("frames.json"),manifest.toString());
                    }
                    mc.stop();
                }
            }
        }
        catch(Exception failure){ProjectSeele.LOGGER.error("R10 native client review failed",failure);FirstBattleClient.releaseCamera();mc.stop();}
    }
    @SubscribeEvent public static void render(TickEvent.RenderTickEvent event)
    {
        boolean postStop=FirstBattleR10Review.capturePostStopR52&&!stopCapturedR52;
        if(!FirstBattleR10Review.ENABLED||!initialized||closing)return;
        var mc=Minecraft.getInstance();var entity=mc.level.getEntity(FirstBattleR10Review.heroId);
        if(event.phase==TickEvent.Phase.START)
        {
            // A shared server flag can change after camera setup. Wait for a
            // whole stopped client render, with the exterior camera selected.
            stopReadyAtFrameStartR52=postStop&&entity instanceof EvaUnit01Entity eva
                    &&!eva.isFirstBattleActive()&&!eva.isBerserk();
            if(stopReadyAtFrameStartR52)mc.options.setCameraType(CameraType.THIRD_PERSON_BACK);
            return;
        }
        if(event.phase!=TickEvent.Phase.END||(!FirstBattleR10Review.captureMovie&&!postStop&&!FirstBattleR10Review.captureControlRecoveryR52)
                ||postStop&&!stopReadyAtFrameStartR52)return;
        if(NO_FRAME_CAPTURE&&!KEY_FRAMES&&!FRAME_METADATA)return;
        if(FRAME_METADATA)
        {
            if(!(entity instanceof EvaUnit01Entity eva)||!eva.isFirstBattleActive())return;
            long now=System.nanoTime();if(now-lastMetadataNanos<500_000_000L||frames.size()>=96)return;
            lastMetadataNanos=now;if(firstNanos==0)firstNanos=now;
            JsonObject frame=new JsonObject();frame.addProperty("seconds",(now-firstNanos)/1e9);
            appendMetadata(frame,mc,eva,event.renderTickTime);frames.add(frame);FirstBattleR10Review.clientFrames++;
            return;
        }
        int plannedTick=-1,actualTick=entity instanceof EvaUnit01Entity eva?eva.firstBattleSignals().age(eva):-1;
        if(KEY_FRAMES)
        {
            if(!(entity instanceof EvaUnit01Entity eva))return;
            if(postStop)
            {
                if(eva.isFirstBattleActive()||eva.isBerserk())return;
                actualTick=eva.firstBattleSignals().age(eva);plannedTick=-2;
            }
            else
            {
            if(!eva.isFirstBattleActive()||nextKeyFrame>=KEY_TICKS.length)return;
            actualTick=eva.firstBattleSignals().age(eva);if(actualTick<KEY_TICKS[nextKeyFrame])return;
            // A skipped native render cannot be recreated as a historical frame.
            while(nextKeyFrame+1<KEY_TICKS.length&&actualTick>=KEY_TICKS[nextKeyFrame+1])skippedKeyFrames.add(KEY_TICKS[nextKeyFrame++]);
            plannedTick=KEY_TICKS[nextKeyFrame];
            }
        }
        long now=System.nanoTime();if(now-lastNanos<33_333_333L)return;lastNanos=now;
        if(WRITER.getQueue().remainingCapacity()==0){FirstBattleR10Review.droppedFrames++;return;}
        if(firstNanos==0)firstNanos=now;
        var image=Screenshot.takeScreenshot(mc.getMainRenderTarget());
        int index=FirstBattleR10Review.clientFrames++;String name=postStop?String.format("post_stop_actual_%03d.png",actualTick):KEY_FRAMES?String.format("key_tick_%03d_actual_%03d.png",plannedTick,actualTick):String.format("frame_%05d.jpg",index);
        JsonObject frame=new JsonObject();frame.addProperty("file",name);frame.addProperty("seconds",(now-firstNanos)/1e9);
        if(KEY_FRAMES){frame.addProperty("scheduled_scene_tick",plannedTick);frame.addProperty("synced_age_ticks",actualTick);if(!postStop)nextKeyFrame++;}
        frame.addProperty("post_actual_stop",postStop);
        appendMetadata(frame,mc,entity,event.renderTickTime);
        frames.add(frame);
        if(postStop){stopCapturedR52=true;FirstBattleR10Review.capturePostStopR52=false;}
        WRITER.execute(()->{try(image){
            if(KEY_FRAMES)image.writeToFile(output.resolve(name));else NativeReviewFrames.writeJpeg(image,output.resolve(name));
        }catch(Exception failure){writeFailure=failure.toString();ProjectSeele.LOGGER.error("R10 frame write failed",failure);}});
    }
    private static void appendMetadata(JsonObject frame,Minecraft mc,net.minecraft.world.entity.Entity entity,float partial)
    {
        long window=mc.getWindow().getWindow();
        frame.addProperty("fps",mc.getFps());
        frame.addProperty("window_active",mc.isWindowActive());
        frame.addProperty("glfw_focused",GLFW.glfwGetWindowAttrib(window,GLFW.GLFW_FOCUSED)==GLFW.GLFW_TRUE);
        frame.addProperty("glfw_iconified",GLFW.glfwGetWindowAttrib(window,GLFW.GLFW_ICONIFIED)==GLFW.GLFW_TRUE);
        frame.addProperty("max_fps",mc.options.framerateLimit().get());
        frame.addProperty("vsync",mc.options.enableVsync().get());
        frame.addProperty("paused",mc.isPaused());
        frame.addProperty("control_recovery_window_r52",FirstBattleR10Review.captureControlRecoveryR52);
        frame.addProperty("actual_w_key_down_r52",mc.options.keyUp.isDown());
        if(entity instanceof EvaUnit01Entity eva)
        {
            frame.addProperty("review_sequence_r52",FirstBattleR10Review.reviewSequenceR52);
            frame.addProperty("review_mode_r52",FirstBattleR10Review.reviewSequenceR52==1?"followup_ordinary":"initial");
            frame.addProperty("synced_age_ticks",eva.firstBattleSignals().age(eva));
            frame.addProperty("scene_seconds",eva.firstBattleSignals().time(eva,partial));frame.addProperty("active",eva.isFirstBattleActive());
            frame.addProperty("hero_yaw",eva.yBodyRot);
            frame.addProperty("powered",eva.isPoweredOn());frame.addProperty("berserk",eva.isBerserk());
            frame.addProperty("eyes_enabled",com.projectseele.entity.EvaDorsalMechanism.eyesEnabled(eva));frame.addProperty("eye_surface",com.projectseele.entity.EvaDorsalMechanism.eyeSurface(eva));
            frame.addProperty("pilot_control_locked",eva.pilotControlLockedForReviewR52());frame.addProperty("no_physics",eva.noPhysics);frame.addProperty("no_gravity",eva.isNoGravity());
            JsonArray position=new JsonArray();position.add(eva.getX());position.add(eva.getY());position.add(eva.getZ());frame.add("entity_position_r52",position);
            frame.addProperty("camera_type",mc.options.getCameraType().name());
            frame.addProperty("review_view_r52",FirstBattleClient.reviewViewR52(eva.firstBattleSignals().time(eva,partial),!eva.isFirstBattleActive()&&FirstBattleR10Review.capturePostStopR52));
            var other=mc.level.getEntity(eva.firstBattleSignals().partner(eva));
            if(other instanceof net.minecraft.world.entity.LivingEntity living)frame.addProperty("angel_yaw",living.yBodyRot);
            if(FirstBattleR10Review.reviewSequenceR52==1&&eva.isFirstBattleActive()&&eva.firstBattleSignals().time(eva,partial)>.2F)
            {
                FirstBattleR10Review.ordinaryOpticFramesR52++;
                if(!eva.isPoweredOn()||eva.isBerserk()||!com.projectseele.entity.EvaDorsalMechanism.eyesEnabled(eva)
                        ||com.projectseele.entity.EvaDorsalMechanism.eyeSurface(eva)!=com.projectseele.entity.EvaEyePolicyR52.NORMAL)
                    FirstBattleR10Review.ordinaryDarkFramesR52++;
            }
            if(FirstBattleR10Review.captureControlRecoveryR52&&!eva.isFirstBattleActive()&&mc.options.keyUp.isDown())
            {
                FirstBattleR10Review.controlFramesR52++;
                if(!eva.isPoweredOn()||eva.isBerserk()||eva.pilotControlLockedForReviewR52()
                        ||eva.noPhysics||eva.isNoGravity()||mc.options.getCameraType()!=CameraType.FIRST_PERSON)
                    FirstBattleR10Review.lockedControlFramesR52++;
            }
        }
    }
    private FirstBattleR10Client() {}
}
