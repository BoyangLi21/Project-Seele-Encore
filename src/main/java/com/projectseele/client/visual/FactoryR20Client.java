package com.projectseele.client.visual;

import com.projectseele.visual.FactoryR20Review;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.client.*;
import net.minecraft.client.gui.screens.PauseScreen;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.concurrent.*;
import com.google.gson.*;

@Mod.EventBusSubscriber(modid="projectseele",value=Dist.CLIENT)
public final class FactoryR20Client
{
    private static int distance=-1,exit,age,lastStill=-1,dropped,phaseTicks;private static String previous="",inputPhase="";private static Path folder;
    private static final JsonArray frames=new JsonArray();private static long began,lastFrame;private static boolean closing;
    private static JsonObject looseCameraProbe;
    private static final java.util.Map<String,Integer> facilitySounds=new java.util.HashMap<>();
    private static final JsonArray facilitySoundEventsR45=new JsonArray();
    public static final java.util.Map<Integer,Integer> bodyDraws=new java.util.HashMap<>(),bodyCandidates=new java.util.HashMap<>();
    public static void bodyDraw(EvaUnit01Entity actor){if(FactoryR20Review.R35)bodyDraws.merge(actor.getId(),1,Integer::sum);}
    public static void bodyCandidate(EvaUnit01Entity actor){if(FactoryR20Review.R35)bodyCandidates.merge(actor.getId(),1,Integer::sum);}
    private static volatile String frameError="";private static boolean oldGui;
    private static final ThreadPoolExecutor writer=new ThreadPoolExecutor(2,2,0,TimeUnit.SECONDS,new ArrayBlockingQueue<>(8),r->{Thread t=new Thread(r,"r20-factory-frames");t.setDaemon(true);return t;});
    public record CameraView(net.minecraft.world.phys.Vec3 position,net.minecraft.world.phys.Vec3 target){}
    public static void looseCameraProbe(com.projectseele.entity.EntryPlugCarrierEntity plug,float partial,
            net.minecraft.world.phys.Vec3 pivot,net.minecraft.world.phys.Vec3 chosen,double rawZoom,double appliedZoom,
            net.minecraft.world.phys.BlockHitResult centreHit)
    {
        if(!FactoryR20Review.ENABLED||!Boolean.getBoolean("projectseele.factoryNativePilotCamera"))return;
        var transform=plug.getInterpolatedCanonicalTransform(partial);var local=transform.inverse().transformPoint(chosen);
        var row=new JsonObject();row.addProperty("plug_uuid",plug.getUUID().toString());row.addProperty("plug_tick",plug.tickCount);
        row.addProperty("stage",plug.getInsertionStage());row.addProperty("world_clipped_zoom_before_margin",rawZoom);
        row.addProperty("applied_zoom",appliedZoom);row.addProperty("pivot",pivot.toString());row.addProperty("chosen",chosen.toString());
        row.addProperty("camera_in_plug_frame",local.toString());row.addProperty("plug_frame",transform.toString());
        row.addProperty("centre_ray_hit",centreHit.getType().name());row.addProperty("centre_ray_block",centreHit.getBlockPos().toShortString());
        row.addProperty("centre_ray_location",centreHit.getLocation().toString());
        row.addProperty("centre_ray_block_state",plug.level().getBlockState(centreHit.getBlockPos()).toString());
        var mc=Minecraft.getInstance();var camera=mc.gameRenderer.getMainCamera();
        var look=new net.minecraft.world.phys.Vec3(camera.getLookVector());
        row.addProperty("camera_native_forward",look.toString());
        row.addProperty("camera_euler_forward",net.minecraft.world.phys.Vec3.directionFromRotation(camera.getXRot(),camera.getYRot()).toString());
        var rays=new JsonArray();double distance=32;
        for(int i=0;i<8;i++)
        {
            var offset=new net.minecraft.world.phys.Vec3(((i&1)*2-1)*.1F,(((i>>1)&1)*2-1)*.1F,(((i>>2)&1)*2-1)*.1F);
            var from=pivot.add(offset);var to=pivot.subtract(look.scale(distance)).add(offset);
            var hit=plug.level().clip(new net.minecraft.world.level.ClipContext(from,to,
                    net.minecraft.world.level.ClipContext.Block.VISUAL,net.minecraft.world.level.ClipContext.Fluid.NONE,mc.player));
            var ray=new JsonObject();ray.addProperty("from",from.toString());ray.addProperty("to",to.toString());
            ray.addProperty("hit",hit.getType().name());ray.addProperty("block",hit.getBlockPos().toShortString());
            ray.addProperty("state",plug.level().getBlockState(hit.getBlockPos()).toString());ray.addProperty("distance",hit.getLocation().distanceTo(pivot));rays.add(ray);
            if(hit.getType()!=net.minecraft.world.phys.HitResult.Type.MISS)distance=Math.min(distance,hit.getLocation().distanceTo(pivot));
        }
        row.add("native_eight_corner_rays",rays);row.addProperty("replayed_eight_ray_zoom",distance);
        looseCameraProbe=row;
    }
    public static void looseCameraResolution(double originalEyeZoom,net.minecraft.world.phys.Vec3 localOffset,boolean resolved)
    {
        if(looseCameraProbe==null)return;
        looseCameraProbe.addProperty("original_eye_world_zoom",originalEyeZoom);
        looseCameraProbe.addProperty("canonical_orbit_pivot_offset",localOffset.toString());
        looseCameraProbe.addProperty("outside_shell_and_world_volume_resolved",resolved);
    }
    @SubscribeEvent public static void sound(net.minecraftforge.client.event.sound.PlaySoundEvent event)
    {
        if(FactoryR20Review.R35&&event.getSound()!=null)
        {
            String name=event.getSound().getLocation().toString();
            if(name.startsWith("projectseele:facility_")||name.startsWith("projectseele:pa_"))
            {
                facilitySounds.merge(name,1,Integer::sum);
                var row=new JsonObject();row.addProperty("event",name);row.addProperty("phase",FactoryR20Review.phase);
                row.addProperty("client_tick",age);row.addProperty("x",event.getSound().getX());row.addProperty("y",event.getSound().getY());row.addProperty("z",event.getSound().getZ());
                row.addProperty("volume",event.getSound().getVolume());facilitySoundEventsR45.add(row);
            }
        }
        if(!FactoryR20Review.R28_VISUAL||event.getSound()==null)return;
        var id=event.getSound().getLocation();
        if(id.toString().equals("superbwarfare:ntw_20_fire_3p")&&Minecraft.getInstance().getSoundManager().getSoundEvent(id)!=null)
            com.projectseele.visual.FieldR28Review.ntwSoundsPlayed++;
    }
    public static CameraView cameraView()
    {
        if(Boolean.getBoolean("projectseele.factoryNativePilotCamera"))return null;
        if(FactoryR20Review.R35)
        {
            var mc=Minecraft.getInstance();if(mc.player==null)return null;
            var eva=com.projectseele.world.EvaPilotResolver.controlTarget(mc.player);if(eva==null)return null;
            var p=eva.hasActiveCarrierMotion()?eva.carrierRenderPosition(mc.getFrameTime()):eva.getPosition(mc.getFrameTime());
            if(FactoryR20Review.phase.equals("prepare_transfer")||FactoryR20Review.phase.equals("recover_from_sideways"))return new CameraView(p.add(19,39,24),p.add(0,25,7));
            var bed=FactoryR20Review.launchRoot;
            if(FactoryR20Review.phase.equals("launch")&&bed!=null&&p.y<bed.y+70)return new CameraView(bed.add(16,19,14),bed.add(0,5,0));
        }
        if(!FactoryR20Review.ENABLED||!Boolean.getBoolean("projectseele.factoryCinematic")||!FactoryR20Review.phase.equals("prepare_transfer"))return null;
        var mc=Minecraft.getInstance();if(mc.level==null)return null;
        var units=mc.level.getEntitiesOfClass(EvaUnit01Entity.class,new net.minecraft.world.phys.AABB(-30,-470,-290,96,-330,-180),e->e.getUnitVariant()==1&&!e.isExperimentalUnit());
        if(units.isEmpty()||units.get(0).hasActiveCarrierMotion())return null;
        var root=units.get(0).getPosition(mc.getFrameTime());return new CameraView(root.add(18,68,15),root.add(0,53.3,4.8));
    }
    private static boolean allFramesUsePilotCamera()
    {
        if(frames.isEmpty())return false;
        for(var frame:frames)if(frame.getAsJsonObject().get("mechanical_closeup").getAsBoolean())return false;
        return true;
    }
    @SubscribeEvent public static void tick(TickEvent.ClientTickEvent e)
    {
        if(!FactoryR20Review.ENABLED||e.phase!=TickEvent.Phase.END)return;var mc=Minecraft.getInstance();mc.options.pauseOnLostFocus=false;if(mc.screen instanceof PauseScreen)mc.setScreen(null);
        if(FactoryR20Review.finished){if(distance>=0){mc.options.renderDistance().set(distance);mc.options.broadcastOptions();mc.options.hideGui=oldGui;distance=-1;}if(!closing){writer.shutdown();closing=true;}if(writer.isTerminated()&&++exit==1&&folder!=null){try{JsonObject report=new JsonObject();report.addProperty("source","Native framebuffer. Per-frame mechanical_closeup identifies scripted machinery cameras; only remaining frames use the pilot F5 camera.");report.addProperty("all_frames_are_normal_player_camera",allFramesUsePilotCamera());report.addProperty("dropped",dropped);report.addProperty("write_failure",frameError);report.add("frames",frames);report.add("facility_sounds",new Gson().toJsonTree(facilitySounds));report.add("facility_sound_events_r45",facilitySoundEventsR45);Files.writeString(folder.resolve("frames.json"),report.toString());}catch(Exception x){throw new IllegalStateException(x);}}if(exit>30)mc.stop();return;}
        if(mc.player==null||mc.level==null||mc.screen!=null)return;
        if(distance<0){distance=mc.options.renderDistance().get();oldGui=mc.options.hideGui;mc.options.hideGui=true;mc.options.renderDistance().set(10);mc.options.broadcastOptions();mc.options.setCameraType(CameraType.THIRD_PERSON_BACK);folder=mc.gameDirectory.toPath().resolve((Boolean.getBoolean("projectseele.r44PassengerFactoryReview")?"../artifacts/rebuild_r44/factory_media/variant_"+Integer.getInteger("projectseele.r44PassengerFactoryVariant",0)+"/native_cycle_":FactoryR20Review.R29?"../artifacts/facility_r29/native_factory_":FactoryR20Review.R28?"../artifacts/facility_r28/native_cycle_":FactoryR20Review.R27?"../artifacts/facility_r27/native_cycle_":"r21-factory".equals(System.getProperty("projectseele.regionalBuild",""))?"../artifacts/world_repair_r21/factory/native_cycle_":"../artifacts/world_rebuild_r20/factory/native_cycle_")+System.currentTimeMillis());try{Files.createDirectories(folder);}catch(Exception x){throw new IllegalStateException(x);}}
        FactoryR20Review.ready=true;age++;
        if(FactoryR20Review.R27||FactoryR20Review.R28)mc.options.setCameraType(age%180<90?CameraType.THIRD_PERSON_BACK:CameraType.THIRD_PERSON_FRONT);
        if(!inputPhase.equals(FactoryR20Review.phase)){inputPhase=FactoryR20Review.phase;phaseTicks=0;}else phaseTicks++;
        if("r21-factory".equals(System.getProperty("projectseele.regionalBuild","")))
        {
            boolean free=FactoryR20Review.phase.equals("free_surface_hold");
            mc.options.keyUp.setDown(free&&phaseTicks>=30&&phaseTicks<44);
            mc.options.keyDown.setDown(free&&phaseTicks>=55&&phaseTicks<69);
            mc.options.keyAttack.setDown(free&&phaseTicks>=90&&phaseTicks<120);
            mc.options.keyUse.setDown(free&&phaseTicks>=135&&phaseTicks<140);
            if(free&&phaseTicks==90)KeyMapping.click(mc.options.keyAttack.getKey());
            if(free&&phaseTicks==135)KeyMapping.click(mc.options.keyUse.getKey());
        }
        if(!FactoryR20Review.phase.equals("setup")&&!FactoryR20Review.phase.equals("board"))
        {
            var eva=com.projectseele.world.EvaPilotResolver.controlTarget(mc.player);
            float yaw=FactoryR20Review.R28_VISUAL&&eva!=null&&eva.isCarrierPowerConnected()?230:180;
            float pitch=FactoryR20Review.R28_VISUAL&&FactoryR20Review.phase.equals("free_surface_hold")?35:12;
            mc.player.setYRot(yaw);mc.player.yRotO=yaw;mc.player.setXRot(pitch);mc.player.xRotO=pitch;
        }
    }
    @SubscribeEvent public static void render(TickEvent.RenderTickEvent e)
    {
        if(!FactoryR20Review.ENABLED||closing||e.phase!=TickEvent.Phase.END||folder==null)return;var mc=Minecraft.getInstance();if(mc.player==null||mc.screen!=null)return;
        String phase=FactoryR20Review.phase;
        if(!phase.equals(previous)||age%160==0&&age>0&&lastStill!=age)
        {
            try(var im=Screenshot.takeScreenshot(mc.getMainRenderTarget())){im.writeToFile(folder.resolve(String.format("%06d_%s.png",age,phase)));}catch(Exception x){throw new IllegalStateException(x);}previous=phase;lastStill=age;
        }
        long now=System.nanoTime();if(phase.equals("setup")||now-lastFrame<50_000_000L)return;lastFrame=now;
        if(writer.getQueue().remainingCapacity()==0){dropped++;return;}if(began==0)began=now;
        JsonObject f=new JsonObject();String name=String.format("frame_%05d.jpg",frames.size());f.addProperty("file",name);f.addProperty("seconds",(now-began)/1e9);f.addProperty("phase",phase);f.addProperty("fps",mc.getFps());f.addProperty("mechanical_closeup",cameraView()!=null);
        var camera=mc.gameRenderer.getMainCamera().getPosition();f.addProperty("camera_x",camera.x);f.addProperty("camera_y",camera.y);f.addProperty("camera_z",camera.z);
        var eva=com.projectseele.world.EvaPilotResolver.controlTarget(mc.player);
        f.addProperty("locked_capsule",!(mc.player.getVehicle() instanceof com.projectseele.entity.EntryPlugCarrierEntity plug)||plug.isLockedToEva());
        if(mc.player.getVehicle() instanceof com.projectseele.entity.EntryPlugCarrierEntity capsule&&!capsule.isLockedToEva()&&looseCameraProbe!=null)
            f.add("loose_capsule_camera",looseCameraProbe.deepCopy());
        if(eva!=null){var p=eva.hasActiveCarrierMotion()?eva.carrierRenderPosition(mc.getFrameTime()):eva.getPosition(mc.getFrameTime());f.addProperty("carrier",eva.hasActiveCarrierMotion());f.addProperty("locked",eva.isNervLogisticsLocked());f.addProperty("camera_type",mc.options.getCameraType().name());f.addProperty("eva_x",p.x);f.addProperty("eva_y",p.y);f.addProperty("eva_z",p.z);
            if(FactoryR20Review.R35){f.addProperty("entity_ticks",eva.tickCount);f.addProperty("entity_health",eva.getHealth());f.addProperty("entity_invisible",eva.isInvisible());f.addProperty("entity_removed",eva.isRemoved());f.addProperty("raw_position",eva.position().toString());f.addProperty("body_draws",bodyDraws.getOrDefault(eva.getId(),0));f.addProperty("body_candidates",bodyCandidates.getOrDefault(eva.getId(),0));f.addProperty("raw_chunk_present",mc.level.getChunkSource().hasChunk(eva.blockPosition().getX()>>4,eva.blockPosition().getZ()>>4));f.addProperty("render_chunk_present",mc.level.getChunkSource().hasChunk((int)Math.floor(p.x)>>4,(int)Math.floor(p.z)>>4));}}
        var im=Screenshot.takeScreenshot(mc.getMainRenderTarget());frames.add(f);writer.execute(()->{try(im){NativeReviewFrames.writeJpeg(im,folder.resolve(name));}catch(Exception x){frameError=x.toString();}});
    }
}
