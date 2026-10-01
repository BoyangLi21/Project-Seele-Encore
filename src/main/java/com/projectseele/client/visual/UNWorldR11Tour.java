package com.projectseele.client.visual;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import net.minecraft.client.Minecraft;
import net.minecraft.world.phys.Vec3;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.*;

/** Camera-only tour of the measured world and the actual installed vehicle models. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class UNWorldR11Tour
{
    private static boolean actualChunkLoaded(Minecraft mc, net.minecraft.core.BlockPos pos)
    {return mc.level.getChunkSource().hasChunk(pos.getX() >> 4, pos.getZ() >> 4);}

    private static final boolean BENCH="r19-worldtour-bench".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean R29="r29-worldtour".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean R28=R29||"r28-worldtour".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean R26=R28||"r26-worldtour".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean R25=R26||"r25-worldtour".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean R24=R25||"r24-worldtour".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean R23=R24||"r22-worldtour".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean R21=R23||"r21-worldtour".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean R20=R21||"r20-worldtour".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean BOARDS_TOUR="r19-boards-tour".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean R19=R20||BENCH||BOARDS_TOUR||"r19-worldtour".equals(System.getProperty("projectseele.regionalBuild",""));
    public static final boolean ENABLED=R19||"r11-worldtour".equals(System.getProperty("projectseele.regionalBuild",""));
    private static JsonArray shots;private static final JsonArray receipt=new JsonArray();private static int age,index,settle,end,oldDistance;private static boolean requested,done,oldPause,oldGui,ready;
    private static Vec3 eye,target;private static Path folder;private static net.minecraft.client.CameraType oldCamera;
    private static final java.util.List<Double> frameTimes=new java.util.ArrayList<>();
    private static long previousFrame;
    private static int warmup=180;
    @SubscribeEvent public static void tick(TickEvent.ClientTickEvent event)
    {
        if(!ENABLED||event.phase!=TickEvent.Phase.END||BOARDS_TOUR&&!com.projectseele.visual.WorldRepairR19Review.finished)return;var mc=Minecraft.getInstance();if(mc.player==null||mc.level==null||mc.getSingleplayerServer()==null)return;
        String world=mc.getSingleplayerServer().getWorldPath(LevelResource.ROOT).normalize().getFileName().toString();
        if(R19?!world.equals(R29?"SEELE_FIELD_R29_REVIEW":R28?"SEELE_FIELD_R28_REVIEW":R26?"SEELE_R26_REVIEW":R25?"SEELE_R25_REVIEW":R24?"SEELE_R24_TV_REVIEW":R23?"SEELE_R22_REVIEW":R21?"SEELE_R21_REVIEW":R20?"SEELE_R20_REVIEW":"SEELE_R19_NATIVE_REVIEW"):!world.equals("SEELE_R11_CANONICAL_ACCEPTANCE")&&!world.equals("SEELE_TV_WORLD_PREVIEW_20260906"))throw new IllegalStateException("Native tour world boundary");
        if(++age<100)return;
        try
        {
            if(shots==null)
            {
                shots=JsonParser.parseString(Files.readString(mc.gameDirectory.toPath().resolve("projectseele-local-maps/"+(R29?"r29":R28?"r28":R26?"r26":R25?"r25":R24?"r24":R23?"r23":R21?"r21":R20?"r20":R19?"r19":"r11")+"_worldtour.json"))).getAsJsonArray();folder=mc.gameDirectory.toPath().resolve((R29?"../artifacts/facility_r29/native_tour_":R28?"../artifacts/facility_r28/native_tour_":R26?"../artifacts/facility_r26/native_tour_":R25?"../artifacts/facility_r25/native_tour_":R24?"../artifacts/facility_r24/native_tour_":R23?"../artifacts/facility_r23/native_tour_":R21?"../artifacts/world_repair_r21/native_tour_":R20?"../artifacts/world_rebuild_r20/native_tour_":R19?"../artifacts/world_repair_r19/native_tour_":"../artifacts/world_motion_r11/world_native_")+System.currentTimeMillis()).normalize();Files.createDirectories(folder);
                if(R21){var keys=new JsonObject();for(var key:mc.options.keyMappings)if(key.getName().contains("superbwarfare"))keys.addProperty(key.getName(),key.getTranslatedKeyMessage().getString());Files.writeString(folder.resolve("actual_vehicle_keybindings.json"),keys.toString());}
                oldDistance=mc.options.renderDistance().get();oldPause=mc.options.pauseOnLostFocus;oldGui=mc.options.hideGui;oldCamera=mc.options.getCameraType();mc.options.renderDistance().set(R23?8:BENCH?32:12);mc.options.broadcastOptions();mc.options.pauseOnLostFocus=false;mc.player.connection.sendCommand("gamemode spectator");
            }
            if(done)
            {
                if(++end==1){mc.options.renderDistance().set(oldDistance);mc.options.broadcastOptions();mc.options.hideGui=oldGui;mc.options.pauseOnLostFocus=oldPause;mc.options.setCameraType(oldCamera);mc.setCameraEntity(mc.player);Files.writeString(folder.resolve("receipt.json"),receipt.toString());}
                if(end>30)mc.stop();return;
            }
            if(index>=shots.size()){done=true;return;}
            if(!requested)
            {
                var shot=shots.get(index).getAsJsonObject();eye=vec(shot.getAsJsonArray("eye"));target=vec(shot.getAsJsonArray("target"));Vec3 d=target.subtract(eye);warmup=shot.has("warmupTicks")?shot.get("warmupTicks").getAsInt():BENCH?400:180;
                mc.options.renderDistance().set(shot.has("renderDistance")?shot.get("renderDistance").getAsInt():BENCH?32:12);mc.options.broadcastOptions();
                mc.player.connection.sendCommand(String.format(Locale.ROOT,"execute in projectseele:geofront run tp @s %.5f %.5f %.5f %.5f %.5f",eye.x,eye.y-mc.player.getEyeHeight(),eye.z,Math.toDegrees(Math.atan2(-d.x,d.z)),-Math.toDegrees(Math.atan2(d.y,d.horizontalDistance()))));
                mc.options.hideGui=true;mc.options.setCameraType(net.minecraft.client.CameraType.FIRST_PERSON);mc.setCameraEntity(mc.player);requested=true;settle=0;ready=false;frameTimes.clear();previousFrame=0;
            }
            if(mc.level.dimension().location().toString().equals("projectseele:geofront")&&mc.player.getEyePosition().distanceToSqr(eye)<.2&&mc.screen==null)
            {
                // A teleport already queues the destination meshes. Throwing
                // that queue away again produced empty-sky R23 captures.
                if(settle++==40&&!BENCH&&!R23)mc.levelRenderer.allChanged();
                boolean neighbourhoodReady=actualChunkLoaded(mc, net.minecraft.core.BlockPos.containing(target));
                if(R23)
                    for(int dx=-2;dx<=2;dx++)for(int dz=-2;dz<=2;dz++)
                        neighbourhoodReady &= actualChunkLoaded(mc, net.minecraft.core.BlockPos.containing(eye.add(dx*16,0,dz*16)));
                // Loaded block data can precede the actual GPU meshes by
                // several seconds. Do not label a sky-only frame a capture.
                boolean meshesReady=!R24||(mc.levelRenderer.countRenderedChunks()>0
                        &&mc.levelRenderer.isChunkCompiled(net.minecraft.core.BlockPos.containing(target)));
                if(settle>warmup&&neighbourhoodReady&&meshesReady)ready=true;
            }
            if(age>Math.max(8000,shots.size()*600))throw new IllegalStateException("Native tour timeout at "+index);
        }
        catch(Exception e){ProjectSeele.LOGGER.error("R11 UN tour failed",e);done=true;}
    }
    @SubscribeEvent public static void render(TickEvent.RenderTickEvent event)
    {
        if(!ENABLED||done||!requested||shots==null)return;var mc=Minecraft.getInstance();if(mc.player==null)return;
        if(event.phase==TickEvent.Phase.START)
        {Vec3 d=target.subtract(eye);float yaw=(float)Math.toDegrees(Math.atan2(-d.x,d.z)),pitch=(float)-Math.toDegrees(Math.atan2(d.y,d.horizontalDistance()));mc.player.setYRot(yaw);mc.player.yRotO=yaw;mc.player.setXRot(pitch);mc.player.xRotO=pitch;return;}
        if(BENCH&&settle>warmup-80)
        {
            long now=System.nanoTime();if(previousFrame!=0)frameTimes.add((now-previousFrame)/1e6);previousFrame=now;
        }
        if(!ready)return;
        try(var image=net.minecraft.client.Screenshot.takeScreenshot(mc.getMainRenderTarget()))
        {
            JsonObject spec=shots.get(index).getAsJsonObject();String name=spec.get("name").getAsString();image.writeToFile(folder.resolve(name+".png"));JsonObject r=spec.deepCopy();r.addProperty("chunks",mc.levelRenderer.getChunkStatistics());
            r.addProperty("renderer",org.lwjgl.opengl.GL11.glGetString(org.lwjgl.opengl.GL11.GL_RENDERER));r.addProperty("render_distance",mc.options.renderDistance().get());
            r.addProperty("distant_horizons",net.minecraftforge.fml.ModList.get().isLoaded("distanthorizons"));
            boolean gpu=false;try{gpu=Class.forName("me.cortex.nvidium.Nvidium").getField("IS_ENABLED").getBoolean(null);}catch(ReflectiveOperationException ignored){}
            r.addProperty("acedium_enabled",gpu);
            if(!frameTimes.isEmpty()){frameTimes.sort(Double::compareTo);r.addProperty("measured_frames",frameTimes.size());r.addProperty("frame_ms_p50",frameTimes.get(frameTimes.size()/2));r.addProperty("frame_ms_p95",frameTimes.get(Math.min(frameTimes.size()-1,(int)(frameTimes.size()*.95))));}
            receipt.add(r);ProjectSeele.LOGGER.info("R19/11 native tour captured {}",name);
        }
        catch(Exception e){throw new IllegalStateException(e);}
        requested=false;ready=false;index++;
    }
    private static Vec3 vec(JsonArray a){return new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());}
}
