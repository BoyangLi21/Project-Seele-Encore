package com.projectseele.client.visual;

import com.projectseele.ProjectSeele;
import com.projectseele.world.FacilitySchemaV2;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;
import net.minecraft.resources.ResourceKey;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;

/** Explicit screenshot review cameras; restores the player's position, abilities and options. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class RegionalStationPhoto
{
    private static final String MODE=System.getProperty("projectseele.regionalBuild","");
    private static final boolean R10_MODELS=MODE.equals("r10-models")||MODE.equals("r10-choreography");
    private static final boolean R16=MODE.equals("r16-photos");
    private static final boolean R41=MODE.equals("r41-facility-photos");
    private static final boolean R40=R41||MODE.equals("r40-facility-photos");
    private static final boolean R39=MODE.equals("r39-lighting-photos");
    private static final boolean R38=MODE.equals("r38-lighting-photos");
    private static final boolean R30=MODE.equals("r30-lighting-photos")||R38||R39||R40;
    private static final boolean R07=MODE.equals("r07-photos")||MODE.equals("r10-world")||R10_MODELS||R16,DETAIL=R30||R07||MODE.equals("detail-photos");
    private static final boolean ENABLED=MODE.equals("station-photo")||MODE.equals("quality-photos")||DETAIL;
    private record View(String file,Vec3 position,float yaw,float pitch,String action,int warmup,
                        java.util.List<net.minecraft.core.BlockPos> requiredSections)
    {View(String file,Vec3 position,float yaw,float pitch){this(file,position,yaw,pitch,"",220,java.util.List.of());}}
    private static volatile boolean actionReady=true;
    private static View[] VIEWS=MODE.equals("quality-photos")?new View[]{
            new View("quality_kirisato_exterior.png",new Vec3(-2918.5,97,-1150.5),-60,8),
            new View("quality_kirisato_402.png",new Vec3(-2846.5,86,-1106.5),25,12),
            new View("quality_airport_current.png",new Vec3(737.5,84,1021.5),0,3),
            new View("quality_station_current.png",new Vec3(-699.5,104.38,171.5),0,12.7F)
    }:new View[]{new View("quality_station_current.png",new Vec3(-699.5,104.38,171.5),0,12.7F)};
    private static boolean entered,ready,captured,finishing,endpointCheckRequested;
    private static int age,frames,finishTicks,oldDistance,view,sceneAge;
    private static boolean oldGui,oldPause,oldFlying;
    private static Vec3 oldPos;
    private static float oldYaw,oldPitch;
    private static GameType oldMode;
    private static ResourceKey<Level> oldDimension;
    private static net.minecraft.client.CameraType oldCamera;

    @SubscribeEvent
    public static void tick(TickEvent.ClientTickEvent event)
    {
        if(!ENABLED||event.phase!=TickEvent.Phase.END)return;
        Minecraft mc=Minecraft.getInstance();if(mc.player==null||mc.getSingleplayerServer()==null)return;
        var server=mc.getSingleplayerServer();Path world=server.getWorldPath(LevelResource.ROOT).normalize();
        if(!world.getFileName().toString().equals(R41?"SEELE_FIELD_R41_REVIEW":R40?"SEELE_FIELD_R40_REVIEW":R39?"SEELE_FIELD_R39_REVIEW":R38?"SEELE_FIELD_R38_REVIEW":R30?"SEELE_FIELD_R30_REVIEW":R16?"SEELE_TV_FACILITIES_R16":R10_MODELS?"SEELE_ANGEL_MODEL_REVIEW_R10":"SEELE_TV_WORLD_PREVIEW_20260906"))return;
        try
        {
            if(finishing)
            {
                if(MODE.equals("r10-world")&&!com.projectseele.visual.RegionalSpatialAuditDriver.done){mc.options.pauseOnLostFocus=false;return;}
                mc.options.pauseOnLostFocus=oldPause;
                if(++finishTicks>40)mc.stop();return;
            }
            if(++age<80)return;
            // The walk audit temporarily owns the real player too. Let it
            // restore that player before taking the photo itinerary snapshot.
            if(MODE.equals("r10-world")&&!entered&&!com.projectseele.visual.RegionalSpatialAuditDriver.done)return;
            if(!entered)
            {
                if(DETAIL)
                {
                    var data=com.google.gson.JsonParser.parseString(Files.readString(world.resolve(R30?"r30_photo_views.json":R07?"r07_photo_views.json":"regional_photo_views.json"))).getAsJsonArray();
                    java.util.List<View> views=new java.util.ArrayList<>();
                    for(var item:data)
                    {
                        var d=item.getAsJsonObject();var p=d.getAsJsonArray("position");String file=d.get("file").getAsString();
                        if(!file.matches("[A-Za-z0-9_-]+\\.png"))throw new IllegalArgumentException("Invalid photo filename");
                        java.util.List<net.minecraft.core.BlockPos> required=new java.util.ArrayList<>();
                        if(d.has("requiredSections"))for(var point:d.getAsJsonArray("requiredSections"))
                        {
                            var xyz=point.getAsJsonArray();
                            required.add(new net.minecraft.core.BlockPos(xyz.get(0).getAsInt(),xyz.get(1).getAsInt(),xyz.get(2).getAsInt()));
                        }
                        views.add(new View(file,new Vec3(p.get(0).getAsDouble(),p.get(1).getAsDouble(),p.get(2).getAsDouble()),d.get("yaw").getAsFloat(),d.get("pitch").getAsFloat(),d.has("action")?d.get("action").getAsString():"",d.has("warmupTicks")?d.get("warmupTicks").getAsInt():220,java.util.List.copyOf(required)));
                    }
                    if(views.isEmpty())throw new IllegalArgumentException("Empty photo itinerary");
                    VIEWS=views.toArray(View[]::new);
                }
                entered=true;oldDistance=mc.options.renderDistance().get();oldGui=mc.options.hideGui;oldPause=mc.options.pauseOnLostFocus;oldCamera=mc.options.getCameraType();
                Files.deleteIfExists(world.resolve("station_photo_ready.json"));
                mc.options.pauseOnLostFocus=false;mc.options.renderDistance().set(net.minecraft.util.Mth.clamp(Integer.getInteger("projectseele.photoRenderDistance",R07?18:DETAIL?10:8),4,24));mc.options.hideGui=true;mc.options.setCameraType(net.minecraft.client.CameraType.FIRST_PERSON);mc.options.broadcastOptions();
                actionReady=VIEWS[view].action().isEmpty();
                server.execute(()->{
                    var p=server.getPlayerList().getPlayers().get(0);oldPos=p.position();oldDimension=p.level().dimension();oldMode=p.gameMode.getGameModeForPlayer();oldYaw=p.getYRot();oldPitch=p.getXRot();oldFlying=p.getAbilities().flying;
                    p.setGameMode(GameType.SPECTATOR);position(mc);
                });
            }
            if(!actionReady)
            {
                sceneAge=0;frames=0;
                if(age%20==0)server.execute(()->{
                    var level=server.getLevel(FacilitySchemaV2.DIMENSION);var state=com.projectseele.world.MilitaryR07Director.state(level);
                    String action=VIEWS[view].action();
                    if(R10_MODELS&&action.startsWith("pose:"))
                    {
                        com.projectseele.visual.AngelModelR10Review.seek(Float.parseFloat(action.substring(5)));actionReady=true;
                    }
                    else if(R30&&action.startsWith("lights_"))
                    {
                        var at=new net.minecraft.core.BlockPos(26,-405,275);var lever=level.getBlockState(at);
                        boolean on=action.equals("lights_on");level.setBlock(at,lever.setValue(net.minecraft.world.level.block.state.properties.BlockStateProperties.POWERED,on),3);actionReady=true;
                    }
                    else if(R30&&action.equals("airboards"))
                    {
                        var observations=new com.google.gson.JsonArray();boolean valid=true;
                        for(var at:java.util.List.of(new net.minecraft.core.BlockPos(420,76,77),new net.minecraft.core.BlockPos(451,76,41)))
                        {
                            if(!(level.getBlockEntity(at) instanceof com.projectseele.world.StationDepartureBoardBlockEntity board)){valid=false;continue;}
                            var row=new com.google.gson.JsonObject();row.addProperty("pos",at.toShortString());row.addProperty("platform",board.linkedPlatformId());row.addProperty("title",board.title());
                            row.add("departures",new com.google.gson.Gson().toJsonTree(board.departureTimes()));row.add("rows",new com.google.gson.Gson().toJsonTree(board.rows()));observations.add(row);
                            valid&=board.linkedPlatformId()==5148309000717330621L&&!board.departureTimes().isEmpty()&&board.title().contains("航班动态")
                                    &&board.rows().stream().allMatch(s->s.contains("联合国"));
                        }
                        if(valid){try{Files.writeString(world.resolve("r30_terminal_departures.json"),observations.toString());}catch(java.io.IOException e){throw new IllegalStateException(e);}actionReady=true;}
                    }
                    else if(action.equals("open"))
                    {
                        if(state.phase==com.projectseele.world.MilitaryR07Director.Phase.WET)com.projectseele.world.MilitaryR07Director.request(level,"drain",null);
                        if(state.phase==com.projectseele.world.MilitaryR07Director.Phase.DRY)com.projectseele.world.MilitaryR07Director.request(level,"door",null);
                        actionReady=state.phase==com.projectseele.world.MilitaryR07Director.Phase.OPEN;
                    }
                    else if(action.equals("wet"))
                    {
                        if(state.phase==com.projectseele.world.MilitaryR07Director.Phase.OPEN)com.projectseele.world.MilitaryR07Director.request(level,"door",null);
                        if(state.phase==com.projectseele.world.MilitaryR07Director.Phase.DRY)com.projectseele.world.MilitaryR07Director.request(level,"fill",null);
                        actionReady=state.phase==com.projectseele.world.MilitaryR07Director.Phase.WET;
                    }
                    else throw new IllegalStateException("Unknown R07 photo action "+action);
                });
                if(age>20000)throw new IllegalStateException("R07 photo machinery did not settle");return;
            }
            sceneAge++;
            if(sceneAge==120)mc.levelRenderer.allChanged();
            if(MODE.equals("quality-photos")&&sceneAge==120&&!endpointCheckRequested)
            {
                endpointCheckRequested=true;
                server.execute(()->{
                    try
                    {
                        var proof=com.projectseele.visual.RegionalNativeTransitInspection.checkRouteEndpoints();
                        Files.writeString(world.resolve("native_endpoint_checks.json"),proof.toString());
                        ProjectSeele.LOGGER.info("NATIVE ROUTE ENDPOINT CHECKS PASS {}",proof);
                    }
                    catch(Exception failure)
                    {
                        ProjectSeele.LOGGER.error("NATIVE ROUTE ENDPOINT CHECKS FAILED",failure);
                        try{Files.writeString(world.resolve("native_endpoint_failure.txt"),failure.toString());}catch(Exception ignored){}
                    }
                });
            }
            // A timer alone can capture an incomplete building while distant
            // sections are still arriving in this very tall dimension.
            boolean geometryReady=VIEWS[view].requiredSections().stream().allMatch(
                    p->mc.level.hasChunkAt(p)&&mc.levelRenderer.isChunkCompiled(p));
            if(!geometryReady&&sceneAge%200==0)
                for(var p:VIEWS[view].requiredSections())
                    ProjectSeele.LOGGER.info("REGIONAL PHOTO WAIT file={} anchor={} loaded={} compiled={} state={}",
                            VIEWS[view].file(),p,mc.level.hasChunkAt(p),mc.levelRenderer.isChunkCompiled(p),mc.level.getBlockState(p));
            if(sceneAge>VIEWS[view].warmup()&&frames>100&&!ready&&geometryReady)
            {
                ready=true;Files.writeString(world.resolve("station_photo_ready.json"),"{\"ready\":true,\"renderedSections\":"+mc.levelRenderer.countRenderedChunks()+"}");
                ProjectSeele.LOGGER.info("REGIONAL PHOTO READY file={} sections={} camera={}",VIEWS[view].file(),mc.levelRenderer.countRenderedChunks(),mc.gameRenderer.getMainCamera().getPosition());
                ProjectSeele.LOGGER.info("REGIONAL PHOTO GEOMETRY {}",mc.levelRenderer.getChunkStatistics());
                if(!VIEWS[view].requiredSections().isEmpty())
                    ProjectSeele.LOGGER.info("REGIONAL PHOTO REQUIRED SECTIONS PASS file={} anchors={}",VIEWS[view].file(),VIEWS[view].requiredSections());
                if(VIEWS[view].file().startsWith("r09_"))
                {
                    var pane=new net.minecraft.core.BlockPos(53,-327,313);var outside=new net.minecraft.core.BlockPos(126,-316,275);
                    var state=mc.level.getBlockState(pane);
                    ProjectSeele.LOGGER.info("R09 OPTICAL STATE file={} fps={} pane={} solid={} outside={} compiled={}",
                            VIEWS[view].file(),mc.getFps(),state,state.isSolidRender(mc.level,pane),
                            mc.level.getBlockState(outside),mc.levelRenderer.isChunkCompiled(outside));
                }
                if(R07)for(var actor:mc.level.entitiesForRendering())
                    if(actor instanceof com.projectseele.entity.EvaUnit01Entity eva&&eva.isExperimentalUnit())
                        ProjectSeele.LOGGER.info("PROTOTYPE PHOTO STATE file={} position={} bounds={} hidden={} locked={} passengers={}",VIEWS[view].file(),eva.position(),eva.getBoundingBox(),eva.isInvisible(),eva.isNervLogisticsLocked(),eva.getPassengers());
            }
            if(captured&&sceneAge>Math.max(280,VIEWS[view].warmup()+60)&&view+1<VIEWS.length)
            {
                view++;sceneAge=0;frames=0;ready=false;captured=false;actionReady=VIEWS[view].action().isEmpty();server.execute(()->position(mc));
            }
            int itineraryBudget=java.util.Arrays.stream(VIEWS).mapToInt(v->v.warmup()+140).sum()+1400;
            if(Files.exists(world.resolve("regional_stop_requested"))||age>Math.max(2400,itineraryBudget)||(!MODE.equals("station-photo")&&captured&&view+1==VIEWS.length&&sceneAge>280))
            {
                Files.deleteIfExists(world.resolve("regional_stop_requested"));finishing=true;
                mc.options.hideGui=oldGui;mc.options.renderDistance().set(oldDistance);mc.options.pauseOnLostFocus=oldPause;mc.options.setCameraType(oldCamera);
                server.execute(()->{var p=server.getPlayerList().getPlayers().get(0);p.teleportTo(server.getLevel(oldDimension),oldPos.x,oldPos.y,oldPos.z,oldYaw,oldPitch);p.setGameMode(oldMode);p.fallDistance=0;p.setDeltaMovement(Vec3.ZERO);p.getAbilities().flying=oldFlying;p.onUpdateAbilities();});
            }
        }
        catch(Exception e){ProjectSeele.LOGGER.error("STATION PHOTO",e);mc.stop();}
    }
    @SubscribeEvent
    public static void render(TickEvent.RenderTickEvent event)
    {
        if(!ENABLED||!entered||finishing)return;Minecraft mc=Minecraft.getInstance();if(mc.player==null)return;
        View camera=VIEWS[view];
        if(event.phase==TickEvent.Phase.START){mc.player.setYRot(camera.yaw());mc.player.yRotO=camera.yaw();mc.player.setXRot(camera.pitch());mc.player.xRotO=camera.pitch();return;}
        frames++;
        if(ready&&!captured)
        {
            Screenshot.grab(mc.gameDirectory,camera.file(),mc.getMainRenderTarget(),ignored->{});captured=true;
        }
    }
    private static void position(Minecraft mc)
    {
        var server=mc.getSingleplayerServer();var p=server.getPlayerList().getPlayers().get(0);View camera=VIEWS[view];
        var level=R10_MODELS?server.overworld():server.getLevel(FacilitySchemaV2.DIMENSION);
        Vec3 eye=camera.position().add(0,1.62,0);var cell=net.minecraft.core.BlockPos.containing(eye);
        var state=level.getBlockState(cell);
        if(DETAIL&&state.getCollisionShape(level,cell).toAabbs().stream().anyMatch(b->b.move(cell).contains(eye)))
            throw new IllegalStateException("Review camera intersects a solid block: "+camera.file()+" "+cell+" "+state);
        p.teleportTo(level,camera.position().x,camera.position().y,camera.position().z,camera.yaw(),camera.pitch());
    }
}
