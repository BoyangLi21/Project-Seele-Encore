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
    private static final boolean R44=MODE.equals("r44-facility-photos");
    private static final boolean R43=R44||MODE.equals("r43-facility-photos");
    private static final boolean R42=R43||MODE.equals("r42-facility-photos");
    private static final boolean R41=R42||MODE.equals("r41-facility-photos");
    private static final boolean R40=R41||MODE.equals("r40-facility-photos");
    private static final boolean R39=MODE.equals("r39-lighting-photos");
    private static final boolean R38=MODE.equals("r38-lighting-photos");
    private static final boolean R30=MODE.equals("r30-lighting-photos")||R38||R39||R40;
    private static final boolean R07=MODE.equals("r07-photos")||MODE.equals("r10-world")||R10_MODELS||R16,DETAIL=R30||R07||MODE.equals("detail-photos");
    private static final boolean ENABLED=MODE.equals("station-photo")||MODE.equals("quality-photos")||DETAIL;
    private record View(String file,Vec3 position,float yaw,float pitch,String action,int warmup,
                        java.util.List<net.minecraft.core.BlockPos> requiredSections,int fov)
    {View(String file,Vec3 position,float yaw,float pitch){this(file,position,yaw,pitch,"",220,java.util.List.of(),70);}}
    private static volatile boolean actionReady=true;
    private static Long reviewOriginalDayTime,reviewOriginalGameTime;
    private static Boolean reviewOriginalDayCycle;
    private static volatile String positioningFailure="";
    private static final com.google.gson.JsonArray PHOTO_EVIDENCE=new com.google.gson.JsonArray();
    private static java.util.concurrent.CompletableFuture<Void> resourceReload;
    private static com.google.gson.JsonObject beforeResourceReload;
    private static final com.google.gson.JsonArray RESOURCE_RELOADS=new com.google.gson.JsonArray();
    private static View[] VIEWS=MODE.equals("quality-photos")?new View[]{
            new View("quality_kirisato_exterior.png",new Vec3(-2918.5,97,-1150.5),-60,8),
            new View("quality_kirisato_402.png",new Vec3(-2846.5,86,-1106.5),25,12),
            new View("quality_airport_current.png",new Vec3(737.5,84,1021.5),0,3),
            new View("quality_station_current.png",new Vec3(-699.5,104.38,171.5),0,12.7F)
    }:new View[]{new View("quality_station_current.png",new Vec3(-699.5,104.38,171.5),0,12.7F)};
    private static boolean entered,ready,captured,finishing,endpointCheckRequested;
    private static int age,frames,finishTicks,oldDistance,oldFov,view,sceneAge,capturedAtSceneAge;
    private static double oldFovEffects,lastEffectiveFov=Double.NaN;
    public static void observeEffectiveFov(double value)
    {if(R44&&entered&&!finishing)lastEffectiveFov=value;}
    private static boolean oldGui,oldPause,oldFlying;
    private static Vec3 oldPos;
    private static float oldYaw,oldPitch;
    private static GameType oldMode;
    private static ResourceKey<Level> oldDimension;
    private static net.minecraft.client.CameraType oldCamera;
    private static boolean oldSmartCull;
    private static int occlusionRestores;
    private static long sceneStartedNanos;
    private static final int CAPTURE_HOLD=net.minecraft.util.Mth.clamp(Integer.getInteger("projectseele.photoCaptureHoldTicks",0),0,2400);

    @SubscribeEvent
    public static void tick(TickEvent.ClientTickEvent event)
    {
        if(!ENABLED||event.phase!=TickEvent.Phase.END)return;
        Minecraft mc=Minecraft.getInstance();if(mc.player==null||mc.getSingleplayerServer()==null)return;
        var server=mc.getSingleplayerServer();Path world=server.getWorldPath(LevelResource.ROOT).normalize();
        if(!world.getFileName().toString().equals(R44?com.projectseele.visual.NativeReviewWorldsR45.expectedName():R43?"SEELE_FIELD_R43_REVIEW":R42?"SEELE_FIELD_R42_REVIEW":R41?"SEELE_FIELD_R41_REVIEW":R40?"SEELE_FIELD_R40_REVIEW":R39?"SEELE_FIELD_R39_REVIEW":R38?"SEELE_FIELD_R38_REVIEW":R30?"SEELE_FIELD_R30_REVIEW":R16?"SEELE_TV_FACILITIES_R16":R10_MODELS?"SEELE_ANGEL_MODEL_REVIEW_R10":"SEELE_TV_WORLD_PREVIEW_20260906"))return;
        try
        {
            if(!positioningFailure.isEmpty())throw new IllegalStateException(positioningFailure);
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
                    Path itinerary=world.resolve(R30?"r30_photo_views.json":R07?"r07_photo_views.json":"regional_photo_views.json");
                    if(!System.getProperty("projectseele.nativeFacilityBindingR45","").isEmpty())itinerary=com.projectseele.world.FacilitySourceAdmissionR45.photoViews(world);
                    var data=com.google.gson.JsonParser.parseString(Files.readString(itinerary)).getAsJsonArray();
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
                        int fov=d.has("fovDegrees")?d.get("fovDegrees").getAsInt():70;
                        if(d.has("fovDegrees")&&Math.abs(d.get("fovDegrees").getAsDouble()-fov)>.0001)throw new IllegalArgumentException("Photo FOV must match the integer Minecraft option");
                        if(fov<30||fov>110)throw new IllegalArgumentException("Photo FOV outside Minecraft range");
                        views.add(new View(file,new Vec3(p.get(0).getAsDouble(),p.get(1).getAsDouble(),p.get(2).getAsDouble()),d.get("yaw").getAsFloat(),d.get("pitch").getAsFloat(),d.has("action")?d.get("action").getAsString():"",d.has("warmupTicks")?d.get("warmupTicks").getAsInt():220,java.util.List.copyOf(required),fov));
                    }
                    if(views.isEmpty())throw new IllegalArgumentException("Empty photo itinerary");
                    VIEWS=views.toArray(View[]::new);
                }
                entered=true;sceneStartedNanos=System.nanoTime();oldDistance=mc.options.renderDistance().get();oldFov=mc.options.fov().get();oldGui=mc.options.hideGui;oldPause=mc.options.pauseOnLostFocus;oldCamera=mc.options.getCameraType();oldSmartCull=mc.smartCull;
                if(R44){oldFovEffects=mc.options.fovEffectScale().get();mc.options.fovEffectScale().set(0D);mc.options.fov().set(70);}
                if(Boolean.getBoolean("projectseele.reviewNoOcclusion"))mc.smartCull=false;
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
                if(R44&&VIEWS[view].action().equals("reload_resources"))
                {
                    if(System.nanoTime()-sceneStartedNanos>600_000_000_000L)
                        throw new IllegalStateException("Native resource reload or GPU cache release did not complete within ten minutes");
                    if(resourceReload==null)
                    {
                        beforeResourceReload=com.projectseele.client.render.RigidMachineryGpuR44.snapshot();
                        if(!beforeResourceReload.get("enabled").getAsBoolean()||beforeResourceReload.get("cached_batches").getAsInt()==0)
                            throw new IllegalStateException("GPU reload review needs a previously rendered actual machinery cache");
                        resourceReload=mc.reloadResourcePacks();return;
                    }
                    if(!resourceReload.isDone())return;
                    resourceReload.join();
                    var after=com.projectseele.client.render.RigidMachineryGpuR44.snapshot();
                    if(after.get("clear_calls").getAsLong()<=beforeResourceReload.get("clear_calls").getAsLong())return;
                    var evidence=new com.google.gson.JsonObject();evidence.addProperty("before_view",view-1);
                    evidence.add("before",beforeResourceReload);evidence.add("after_native_reload",after);
                    evidence.addProperty("native_reload_completed",true);RESOURCE_RELOADS.add(evidence);
                    actionReady=true;return;
                }
                if(age%20==0)server.execute(()->{
                    var level=server.getLevel(FacilitySchemaV2.DIMENSION);
                    String action=VIEWS[view].action();
                    if(R44&&action.startsWith("daytime:"))
                    {
                        var clockLevel=server.overworld();
                        if(reviewOriginalDayTime==null)
                        {
                            reviewOriginalDayTime=clockLevel.getDayTime();reviewOriginalGameTime=clockLevel.getGameTime();
                            reviewOriginalDayCycle=clockLevel.getGameRules().getBoolean(net.minecraft.world.level.GameRules.RULE_DAYLIGHT);
                        }
                        long daytime=Long.parseLong(action.substring(8));
                        if(daytime<0||daytime>=24000)throw new IllegalStateException("Review daytime outside a single native day");
                        var fixed=level.dimensionType().fixedTime();
                        if(fixed.isPresent()&&Math.floorMod(fixed.getAsLong(),24000)!=daytime)
                        {positioningFailure="Actual dimension fixed sky time prevents requested day/night review: "+fixed.getAsLong()+" != "+daytime;return;}
                        // Custom dimensions use DerivedLevelData: their setDayTime is a no-op.
                        // Hold the shared clock for comparable views, then restore its elapsed time.
                        clockLevel.getGameRules().getRule(net.minecraft.world.level.GameRules.RULE_DAYLIGHT).set(false,server);
                        clockLevel.setDayTime(daytime);actionReady=true;
                    }
                    else if(R10_MODELS&&action.startsWith("pose:"))
                    {
                        com.projectseele.visual.AngelModelR10Review.seek(Float.parseFloat(action.substring(5)));actionReady=true;
                    }
                    else if(R44&&action.equals("read_archive"))
                    {
                        var at=new net.minecraft.core.BlockPos(30,-329,340);
                        if(!(level.getBlockEntity(at) instanceof com.projectseele.world.DeadSeaArchiveEntityR45)
                                ||server.getPlayerList().getPlayers().get(0).distanceToSqr(Vec3.atCenterOf(at))>16)
                            throw new IllegalStateException("Archive physical approach unavailable");
                        server.getPlayerList().getPlayers().get(0).setGameMode(GameType.CREATIVE);
                        actionReady=true;
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
                        var state=com.projectseele.world.MilitaryR07Director.state(level);
                        if(state.phase==com.projectseele.world.MilitaryR07Director.Phase.WET)com.projectseele.world.MilitaryR07Director.request(level,"drain",null);
                        if(state.phase==com.projectseele.world.MilitaryR07Director.Phase.DRY)com.projectseele.world.MilitaryR07Director.request(level,"door",null);
                        actionReady=state.phase==com.projectseele.world.MilitaryR07Director.Phase.OPEN;
                    }
                    else if(action.equals("wet"))
                    {
                        var state=com.projectseele.world.MilitaryR07Director.state(level);
                        if(state.phase==com.projectseele.world.MilitaryR07Director.Phase.OPEN)com.projectseele.world.MilitaryR07Director.request(level,"door",null);
                        if(state.phase==com.projectseele.world.MilitaryR07Director.Phase.DRY)com.projectseele.world.MilitaryR07Director.request(level,"fill",null);
                        actionReady=state.phase==com.projectseele.world.MilitaryR07Director.Phase.WET;
                    }
                    else throw new IllegalStateException("Unknown R07 photo action "+action);
                });
                if(age>20000)throw new IllegalStateException("R07 photo machinery did not settle");return;
            }
            if(Boolean.getBoolean("projectseele.reviewNoOcclusion")&&mc.smartCull)
            {
                occlusionRestores++;mc.smartCull=false;
                if(occlusionRestores<=4)ProjectSeele.LOGGER.info("R43 review reapplied visibility control at sceneTick={} view={}",sceneAge,view);
            }
            sceneAge++;
            if(sceneAge==120&&(!R43||Boolean.getBoolean("projectseele.reviewRebuildTerrain")))mc.levelRenderer.allChanged();
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
                    p->mc.level.getChunkSource().hasChunk(p.getX()>>4,p.getZ()>>4)&&mc.levelRenderer.isChunkCompiled(p));
            if(!geometryReady&&sceneAge%200==0)
                for(var p:VIEWS[view].requiredSections())
                    ProjectSeele.LOGGER.info("REGIONAL PHOTO WAIT file={} anchor={} loaded={} compiled={} state={}",
                            VIEWS[view].file(),p,mc.level.getChunkSource().hasChunk(p.getX()>>4,p.getZ()>>4),mc.levelRenderer.isChunkCompiled(p),mc.level.getBlockState(p));
            boolean cameraReady=mc.gameRenderer.getMainCamera().getPosition().distanceToSqr(VIEWS[view].position().add(0,1.62,0))<.01
                    &&mc.level.dimension().equals(R10_MODELS?net.minecraft.world.level.Level.OVERWORLD:FacilitySchemaV2.DIMENSION)
                    &&mc.getCameraEntity()==mc.player;
            if(R44&&VIEWS[view].action().startsWith("daytime:"))
                cameraReady&=Math.floorMod(mc.level.getDayTime(),24000)==Long.parseLong(VIEWS[view].action().substring(8));
            if(!cameraReady&&sceneAge%40==0)server.execute(()->position(mc));
            if(sceneAge>VIEWS[view].warmup()&&frames>100&&!ready&&geometryReady&&cameraReady)
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
            if(captured&&sceneAge>Math.max(280,capturedAtSceneAge+60)+CAPTURE_HOLD&&view+1<VIEWS.length)
            {
                view++;sceneAge=0;frames=0;ready=false;captured=false;sceneStartedNanos=System.nanoTime();resourceReload=null;actionReady=VIEWS[view].action().isEmpty();server.execute(()->position(mc));
            }
            int itineraryBudget=java.util.Arrays.stream(VIEWS).mapToInt(v->v.warmup()+140).sum()+1400;
            boolean exhausted=R44?System.nanoTime()-sceneStartedNanos>600_000_000_000L:age>Math.max(2400,itineraryBudget);
            if(exhausted&&R44&&!captured)
            {
                var failure=new com.google.gson.JsonObject();failure.addProperty("file",VIEWS[view].file());failure.addProperty("reason","Current view did not become ready within ten wall-clock minutes");
                failure.addProperty("elapsed_millis",(System.nanoTime()-sceneStartedNanos)/1_000_000L);failure.addProperty("frames",frames);failure.addProperty("camera_ready",cameraReady);
                var missing=new com.google.gson.JsonArray();for(var p:VIEWS[view].requiredSections())if(!mc.level.getChunkSource().hasChunk(p.getX()>>4,p.getZ()>>4)||!mc.levelRenderer.isChunkCompiled(p))missing.add(p.toShortString());failure.add("missing_sections",missing);
                Files.writeString(world.resolve("photo_failure_r44.json"),failure.toString());ProjectSeele.LOGGER.error("REGIONAL PHOTO INCOMPLETE {}",failure);
            }
            if(Files.exists(world.resolve("regional_stop_requested"))||exhausted||(!MODE.equals("station-photo")&&captured&&view+1==VIEWS.length&&sceneAge>Math.max(280,capturedAtSceneAge+60)+CAPTURE_HOLD))
            {
                Files.deleteIfExists(world.resolve("regional_stop_requested"));finishing=true;
                mc.options.hideGui=oldGui;mc.options.renderDistance().set(oldDistance);if(R44){mc.options.fov().set(oldFov);mc.options.fovEffectScale().set(oldFovEffects);}mc.options.pauseOnLostFocus=oldPause;mc.options.setCameraType(oldCamera);mc.smartCull=oldSmartCull;
                server.execute(()->{var p=server.getPlayerList().getPlayers().get(0);p.teleportTo(server.getLevel(oldDimension),oldPos.x,oldPos.y,oldPos.z,oldYaw,oldPitch);p.setGameMode(oldMode);p.fallDistance=0;p.setDeltaMovement(Vec3.ZERO);p.getAbilities().flying=oldFlying;p.onUpdateAbilities();
                    restoreReviewClock(server);});
            }
        }
        catch(Exception e){ProjectSeele.LOGGER.error("STATION PHOTO",e);if(R44&&entered){mc.options.fov().set(oldFov);mc.options.fovEffectScale().set(oldFovEffects);}server.execute(()->restoreReviewClock(server));mc.stop();}
    }
    @SubscribeEvent
    public static void render(TickEvent.RenderTickEvent event)
    {
        if(!ENABLED||!entered||finishing)return;Minecraft mc=Minecraft.getInstance();if(mc.player==null)return;
        View camera=VIEWS[view];
        if(event.phase==TickEvent.Phase.START){lastEffectiveFov=Double.NaN;if(R44&&mc.options.fov().get()!=camera.fov())mc.options.fov().set(camera.fov());mc.setCameraEntity(mc.player);mc.player.setYRot(camera.yaw());mc.player.yRotO=camera.yaw();mc.player.setXRot(camera.pitch());mc.player.xRotO=camera.pitch();return;}
        frames++;
        if(ready&&!captured)
        {
            if(camera.action().equals("read_archive")&&!(mc.screen instanceof com.projectseele.client.DeadSeaArchiveScreenR45))
            {
                // The photo camera uses spectator mode, which deliberately
                // refuses ordinary block use. Await the real mode packet.
                if(mc.gameMode.getPlayerMode()!=GameType.CREATIVE)return;
                var at=new net.minecraft.core.BlockPos(30,-329,340);
                mc.gameMode.useItemOn(mc.player,net.minecraft.world.InteractionHand.MAIN_HAND,
                        new net.minecraft.world.phys.BlockHitResult(new Vec3(30.5,-327.9,340.5),net.minecraft.core.Direction.UP,at,false));
                if(!(mc.screen instanceof com.projectseele.client.DeadSeaArchiveScreenR45))throw new IllegalStateException("Native archive right click failed");
                return;
            }
            Vec3 actual=mc.gameRenderer.getMainCamera().getPosition();
            if(actual.distanceToSqr(camera.position().add(0,1.62,0))>=.01){ready=false;return;}
            if(R44&&(!Double.isFinite(lastEffectiveFov)||Math.abs(lastEffectiveFov-camera.fov())>.02)){ready=false;return;}
            Screenshot.grab(mc.gameDirectory,camera.file(),mc.getMainRenderTarget(),ignored->{});captured=true;capturedAtSceneAge=sceneAge;
            var row=new com.google.gson.JsonObject();row.addProperty("file",camera.file());row.addProperty("actual_camera",actual.toString());
            if(camera.action().equals("read_archive"))row.addProperty("actual_open_archive_page",((com.projectseele.client.DeadSeaArchiveScreenR45)mc.screen).pageIndex());
            row.addProperty("actual_day_time",mc.level.getDayTime());row.addProperty("actual_fixed_time",mc.level.dimensionType().fixedTime().isPresent()?mc.level.dimensionType().fixedTime().getAsLong():-1);
            row.addProperty("dimension_effects_class",mc.level.effects().getClass().getName());
            row.addProperty("dimension_effects_id",mc.level.dimensionType().effectsLocation().toString());
            row.add("vertical_cavern_visibility",com.projectseele.client.GeoFrontVerticalVisibilityR44.snapshot());
            row.addProperty("actual_shader_active",com.projectseele.client.render.ShaderShadowPassR44.enabled());
            // A matching camera and asset can still depict a different
            // mechanical state. Record the actual tracked gantries in the
            // same capture callback, rather than borrowing a later snapshot.
            var gantriesAtCapture=new com.google.gson.JsonArray();
            for(var entity:mc.level.entitiesForRendering())
                if(entity instanceof com.projectseele.entity.NervCarrierPlatformEntity gantry&&gantry.isRestraintGantry())
                {
                    var machine=new com.google.gson.JsonObject();
                    machine.addProperty("uuid",gantry.getStringUUID());
                    machine.addProperty("variant",gantry.getUnitVariant());
                    machine.addProperty("restraint_progress",gantry.getRestraintProgress());
                    machine.addProperty("position",gantry.position().toString());
                    gantriesAtCapture.add(machine);
                }
            row.add("actual_tracked_gantries_at_capture",gantriesAtCapture);
            row.addProperty("smart_cull",mc.smartCull);row.addProperty("occlusion_reapplies",occlusionRestores);row.addProperty("fps",mc.getFps());row.addProperty("rendered_sections",mc.levelRenderer.countRenderedChunks());
            row.addProperty("fov_degrees",mc.options.fov().get());row.addProperty("required_section_count",camera.requiredSections().size());
            if(R44&&RESOURCE_RELOADS.size()>0)row.add("native_resource_reloads",RESOURCE_RELOADS.deepCopy());
            if(R44){row.addProperty("effective_fov_degrees",lastEffectiveFov);row.addProperty("fov_effect_scale",mc.options.fovEffectScale().get());}
            row.add("rigid_machinery_gpu",com.projectseele.client.render.RigidMachineryGpuR44.snapshot());
            row.addProperty("position_error_metres",actual.distanceTo(camera.position().add(0,1.62,0)));row.addProperty("dimension",mc.level.dimension().location().toString());PHOTO_EVIDENCE.add(row);
            try{Files.writeString(mc.getSingleplayerServer().getWorldPath(LevelResource.ROOT).resolve("verified_photo_positions_r42.json"),PHOTO_EVIDENCE.toString());}
            catch(Exception failure){throw new IllegalStateException("Could not record photo position",failure);}
        }
    }
    private static void position(Minecraft mc)
    {
        var server=mc.getSingleplayerServer();var p=server.getPlayerList().getPlayers().get(0);View camera=VIEWS[view];
        var level=R10_MODELS?server.overworld():server.getLevel(FacilitySchemaV2.DIMENSION);
        Vec3 eye=camera.position().add(0,1.62,0);var cell=net.minecraft.core.BlockPos.containing(eye);
        var state=level.getBlockState(cell);
        if(DETAIL&&state.getCollisionShape(level,cell).toAabbs().stream().anyMatch(b->b.move(cell).contains(eye)))
        {positioningFailure="Review camera intersects a solid block: "+camera.file()+" "+cell+" "+state;return;}
        p.stopRiding();
        p.teleportTo(level,camera.position().x,camera.position().y,camera.position().z,camera.yaw(),camera.pitch());
    }
    private static void restoreReviewClock(net.minecraft.server.MinecraftServer server)
    {
        if(reviewOriginalDayTime==null)return;
        var clockLevel=server.overworld();
        long elapsed=Boolean.TRUE.equals(reviewOriginalDayCycle)?clockLevel.getGameTime()-reviewOriginalGameTime:0;
        clockLevel.setDayTime(reviewOriginalDayTime+elapsed);
        clockLevel.getGameRules().getRule(net.minecraft.world.level.GameRules.RULE_DAYLIGHT).set(Boolean.TRUE.equals(reviewOriginalDayCycle),server);
        reviewOriginalDayTime=null;reviewOriginalGameTime=null;reviewOriginalDayCycle=null;
    }
}
