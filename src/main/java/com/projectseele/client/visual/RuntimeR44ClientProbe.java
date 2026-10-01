package com.projectseele.client.visual;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.*;
import net.minecraft.client.CameraType;
import net.minecraft.client.KeyMapping;
import net.minecraft.client.Minecraft;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.ClientChatReceivedEvent;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import java.nio.file.*;

/** A separate JVM uses production key inputs and records the final rendered skeleton. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class RuntimeR44ClientProbe
{
    private static final boolean ENABLED=Boolean.getBoolean("projectseele.r44NetworkClient");
    private static final JsonArray SAMPLES=new JsonArray();
    private static int index,entity=-1,age,retry,deadline,doneTicks;
    private static final int[] VARIANTS={1,0,2,3,4};
    private static long recorded=-1;
    private static final boolean MEDIA=Boolean.getBoolean("projectseele.r44NetworkMedia");
    private static final boolean HAND_STANCES=Boolean.getBoolean("projectseele.r44NetworkHandStances");
    private static final java.util.concurrent.ThreadPoolExecutor WRITER=new java.util.concurrent.ThreadPoolExecutor(1,1,0,java.util.concurrent.TimeUnit.SECONDS,new java.util.concurrent.ArrayBlockingQueue<>(2),r->{var t=new Thread(r,"R44 independent gameplay frames");t.setDaemon(true);return t;});
    private static final JsonArray FRAMES=new JsonArray();
    private static Path media;
    private static int lastMediaAge=-1;
    private static volatile String mediaError="";
    /** Reproduce old cleanup only on this explicitly opted-in local QA actor. */
    public static boolean passengerCleanupBefore(EvaUnit01Entity e)
    {
        if(!ENABLED||!Boolean.getBoolean("projectseele.r44PassengerCleanupBefore")||e.getId()!=entity)return false;
        var server=Minecraft.getInstance().getCurrentServer();
        return server!=null&&"127.0.0.1:25576".equals(server.ip);
    }
    public static boolean poseLayerActor(EvaUnit01Entity e){return ENABLED&&e.getId()==entity;}
    public record CameraView(net.minecraft.world.phys.Vec3 position,net.minecraft.world.phys.Vec3 target) {}
    public static CameraView cameraView(float partial)
    {
        if(!ENABLED||!MEDIA||!"orbit".equals(System.getProperty("projectseele.r44NetworkView","gameplay")))return null;
        var mc=Minecraft.getInstance();if(mc.level==null||!(mc.level.getEntity(entity) instanceof EvaUnit01Entity e))return null;
        var target=e.getPosition(partial).add(0,30,0);double yaw=Math.toRadians(e.yBodyRot+135);
        return new CameraView(target.add(Math.sin(yaw)*88,12,Math.cos(yaw)*88),target);
    }
    @SubscribeEvent public static void input(TickEvent.ClientTickEvent event)
    {
        if(!ENABLED||event.phase!=TickEvent.Phase.START||entity<0)return;var mc=Minecraft.getInstance();
        if(mc.player==null||mc.level==null||mc.player.getRootVehicle().getId()!=entity)return;
        if(mc.screen!=null)mc.setScreen(null);
        if(age==250||age==290||age==330)KeyMapping.click(mc.options.keyAttack.getKey());
        if(age==375)KeyMapping.click(mc.options.keyUse.getKey());
        if(HAND_STANCES)
        {
            if(age==440||age==490)
                com.projectseele.network.SeeleNetwork.CHANNEL.sendToServer(new com.projectseele.network.ServerboundEvaControlPacket(
                        age==440?com.projectseele.network.ServerboundEvaControlPacket.ACTION_CROUCH_START:com.projectseele.network.ServerboundEvaControlPacket.ACTION_CROUCH_STOP));
            if(age==510||age==630)KeyMapping.click(com.projectseele.client.Keybinds.TOGGLE_PRONE.getKey());
        }
    }
    @SubscribeEvent public static void chat(ClientChatReceivedEvent event)
    {
        if(!ENABLED)return;String message=event.getMessage().getString();
        if(message.startsWith("R44_QA_ACTOR ")){entity=Integer.parseInt(message.split(" ")[1]);age=0;}
    }
    @SubscribeEvent public static void tick(TickEvent.ClientTickEvent event)
    {
        if(!ENABLED||event.phase!=TickEvent.Phase.END)return;var mc=Minecraft.getInstance();
        mc.options.pauseOnLostFocus=false;if(mc.player==null||mc.level==null)return;
        if(++deadline>4500)throw new IllegalStateException("R44 network client deadline");
        mc.options.setCameraType(CameraType.THIRD_PERSON_BACK);
        boolean orbit=MEDIA&&"orbit".equals(System.getProperty("projectseele.r44NetworkView","gameplay"));
        mc.options.renderDistance().set(orbit?12:6);
        if(orbit)mc.options.hideGui=true;
        if(index>=VARIANTS.length)
        {
            if(doneTicks++==0)
            {
                mc.player.connection.sendCommand("seele review_r44 finish");
                try{Files.writeString(mc.gameDirectory.toPath().resolve("r44_network_client.json"),new Gson().toJson(SAMPLES));com.projectseele.visual.BodyPoseLayersR40.write(mc.gameDirectory.toPath());}
                catch(Exception failure){throw new IllegalStateException(failure);}
            }
            if(doneTicks>35&&WRITER.getActiveCount()==0&&WRITER.getQueue().isEmpty()
                    &&!com.projectseele.client.render.EvaHandWitnessR44.awaitingWrites())
            {
                if(!mediaError.isEmpty())throw new IllegalStateException(mediaError);
                try{if(media!=null)Files.writeString(media.resolve("frames.json"),new Gson().toJson(FRAMES));}catch(Exception failure){throw new IllegalStateException(failure);}
                mc.stop();
            }return;
        }
        if(entity<0)
        {
            if(retry++%40==0)mc.player.connection.sendCommand("seele review_r44 actor "+VARIANTS[index]);
            return;
        }
        if(!(mc.level.getEntity(entity) instanceof EvaUnit01Entity e)||mc.player.getRootVehicle()!=e||e.getActivationTicks()>0)return;
        ++age;boolean walk=age>=35&&age<100,run=age>=120&&age<210;
        boolean crawl=HAND_STANCES&&age>=550&&age<600,advance=walk||run||crawl;
        mc.options.keyUp.setDown(advance);mc.options.keySprint.setDown(run);mc.options.keyJump.setDown(false);mc.options.keyShift.setDown(false);
        mc.player.input.up=advance;mc.player.input.forwardImpulse=advance?1:0;mc.player.zza=advance?1:0;mc.player.setYRot(0);mc.player.setXRot(0);
        if(age>(HAND_STANCES?690:435)){mc.options.keyUp.setDown(false);mc.options.keySprint.setDown(false);entity=-1;index++;retry=0;}
    }
    public static void capture(EvaUnit01Entity e,BakedGeoModel model,float partial,org.joml.Matrix4f modelToWorld)
    {
        if(!ENABLED||e.getId()!=entity||age==recorded)return;recorded=age;
        JsonObject row=new JsonObject();row.addProperty("variant",EvaGameplayMotionR32.variant(e));row.addProperty("age",age);
        row.addProperty("entity_uuid",e.getUUID().toString());row.addProperty("entity_id",e.getId());
        var player=Minecraft.getInstance().player;
        row.addProperty("local_player_id",player==null?-1:player.getId());row.addProperty("local_root_vehicle",player==null?-1:player.getRootVehicle().getId());
        row.addProperty("ordinary",e.getOrdinaryAttackStage());row.addProperty("phase",e.getOrdinaryAttackProgress(partial));
        row.addProperty("gait",e.rifleGaitPhase(partial));row.addProperty("run",e.rifleRunBlend(partial));row.addProperty("owns",EvaGameplayMotionR32.owns(e,partial));row.addProperty("weapon",e.getWeapon());
        row.addProperty("stance",e.rifleStanceLevel(partial));row.addProperty("pilot_prone",e.isPilotProne());row.addProperty("pilot_crouching",e.isPilotCrouching());
        row.addProperty("server_movement_owner",EvaGameplayMotionR32.serverMovement(e));
        row.addProperty("body_movement_owner",com.projectseele.physics.CombatBodyDynamics.ownsGroundAction(e));
        row.add("actual_owner_inputs",EvaGameplayMotionR32.ownerDiagnosticR44(e,partial));
        int knife=e.getKnifeMotionType(partial);row.addProperty("knife_type",knife);row.addProperty("knife_phase",e.getKnifeMotionProgress(knife,partial));row.addProperty("kick_active",e.isKickMotionActive(partial));row.addProperty("kick_phase",e.getKickAttackProgress(partial));
        row.addProperty("shutdown",EvaShutdownR30.mode(e));row.addProperty("activation",e.getActivationTicks());row.addProperty("ground",e.onGround());
        row.addProperty("x",e.getX());row.addProperty("y",e.getY());row.addProperty("z",e.getZ());JsonObject bones=new JsonObject();
        for(String name:new String[]{"torso_lower","torso_upper","arm_l","arm_r","forearm_l","forearm_r","hand_l","hand_r","leg_l","leg_r","shin_l","shin_r","foot_l","foot_r"})
            model.getBone(name).ifPresent(b->{JsonArray v=new JsonArray();v.add(b.getRotX());v.add(b.getRotY());v.add(b.getRotZ());bones.add(name,v);});
        row.add("rendered",bones);row.add("foot_witness",com.projectseele.client.render.EvaFootWitnessR44.capture(e,model,partial,modelToWorld));SAMPLES.add(row);
    }
    @SubscribeEvent public static void media(TickEvent.RenderTickEvent event)
    {
        if(!ENABLED||!MEDIA||event.phase!=TickEvent.Phase.END||entity<0||age==lastMediaAge||age%2!=0||age<20)return;
        var mc=Minecraft.getInstance();if(mc.player==null||mc.level==null||!(mc.level.getEntity(entity) instanceof EvaUnit01Entity e)||WRITER.getQueue().remainingCapacity()==0)return;
        lastMediaAge=age;
        try
        {
            if(media==null){media=mc.gameDirectory.toPath().resolve("r44_network_media").resolve(Long.toString(System.currentTimeMillis()));Files.createDirectories(media);}
            String filename=String.format(java.util.Locale.ROOT,"rig_%d_%05d.jpg",EvaGameplayMotionR32.variant(e),age);Path file=media.resolve(filename);
            var row=new JsonObject();row.addProperty("file",filename);row.addProperty("variant",EvaGameplayMotionR32.variant(e));row.addProperty("age",age);row.addProperty("wall_ns",System.nanoTime());row.addProperty("fps",mc.getFps());row.addProperty("ordinary",e.getOrdinaryAttackStage());row.addProperty("knife",e.getKnifeMotionType(event.renderTickTime));FRAMES.add(row);
            row.addProperty("camera",mc.gameRenderer.getMainCamera().getPosition().toString());row.addProperty("view",System.getProperty("projectseele.r44NetworkView","gameplay"));row.addProperty("render_distance",mc.options.renderDistance().get());
            var capture=net.minecraft.client.Screenshot.takeScreenshot(mc.getMainRenderTarget());
            WRITER.execute(()->{try(capture){NativeReviewFrames.writeJpeg(capture,file);}catch(Exception failure){mediaError=failure.toString();}});
        }
        catch(Exception failure){throw new IllegalStateException(failure);}
    }
    private RuntimeR44ClientProbe() {}
}
