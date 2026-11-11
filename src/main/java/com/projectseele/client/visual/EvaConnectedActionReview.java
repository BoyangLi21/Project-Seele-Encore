package com.projectseele.client.visual;

import java.io.BufferedWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.projectseele.ProjectSeele;
import com.projectseele.client.render.EvaPoseGraph;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.network.SeeleNetwork;
import com.projectseele.network.ServerboundEvaControlPacket;
import com.projectseele.world.EvaPilotResolver;
import net.minecraft.client.CameraType;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import software.bernie.geckolib.cache.object.BakedGeoModel;

/** Explicit userdev replay through normal pilot packets, in a disposable save only. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class EvaConnectedActionReview
{
    public static final boolean ENABLED = Boolean.getBoolean("projectseele.connectedActionReview");
    private static final boolean RIFLE = Boolean.getBoolean("projectseele.rifleActionReview");
    /** Transition tour: every stance/weapon change the pilot can make, back to back (pose continuity review). */
    private static final boolean TOUR=Boolean.getBoolean("projectseele.transitionTour");
    private static final int TOUR_START=Integer.getInteger("projectseele.tourStart",0);
    private static final boolean COMBO=Boolean.getBoolean("projectseele.tourComboR57");
    private static final boolean DASH=Boolean.getBoolean("projectseele.tourDashR57");
    private static final boolean STEPS=Boolean.getBoolean("projectseele.tourStepsR57");
    private static final boolean CLIMB=Boolean.getBoolean("projectseele.tourClimbR57");
    private static final boolean JUMP=Boolean.getBoolean("projectseele.tourJumpR57");
    /** Weapon check (run with tourStart past the script, e.g. 2000): rifle, positron cannon standing and prone, Unit-02's sword. */
    private static final boolean WEAPONS=Boolean.getBoolean("projectseele.tourWeaponsR57");
    /** Effects check: a positron shot, a scripted Ramiel (-Dprojectseele.ramielReviewR58) firing on Unit-00's shield, then the Sachiel finale. */
    private static final boolean FX=Boolean.getBoolean("projectseele.tourFxR58");
    /** Movement check: turning on the spot, walking backward and sideways, curving, and hard turns at a run. */
    private static final boolean MOVES=Boolean.getBoolean("projectseele.tourMovesR59");
    /** Terrain check: a terraced hill on the review ground, walked over and across. */
    private static final boolean HILL=Boolean.getBoolean("projectseele.tourHillR60");
    /** Melee check: a still Sachiel placed around the body, kicked on the ground and from the air. */
    private static final boolean STRIKE=Boolean.getBoolean("projectseele.tourStrikeR60");
    /** A.T. Field look: a still Sachiel's field struck from the pilot's side, then the piloted unit's own field, at noon and at dusk. */
    private static final boolean ATF=Boolean.getBoolean("projectseele.tourAtFieldR63");
    /**
     * Launch check: one catapult launch of the unit, recorded from the start of its ascent to a few
     * seconds after control comes back. It builds a test launch complex of its own at a far site of
     * the review world (-Dprojectseele.launchSite=<n>, a fresh number for every run: a launched unit
     * does not go back into its cage).
     */
    private static final boolean LAUNCH=Boolean.getBoolean("projectseele.tourLaunchR62");
    private static final int LAUNCH_SITE=Integer.getInteger("projectseele.launchSite",0);
    /** Ticks recorded after the launch sequence hands the unit back. */
    private static final int LAUNCH_AFTER=Integer.getInteger("projectseele.launchAfter",160);
    private static int launchAscentAt=-1,launchIdleAt=-1;
    /**
     * A sortie from the GeoFront runs under the launch director, which keeps the unit under the
     * logistics lock from its cage until the launch sequence has ended on the surface (phase
     * SILO_READY of EvaLogisticsDirector). The test complex has no director: the review holds
     * and releases the lock by the same rule. -Dprojectseele.launchCustody=false leaves it out.
     */
    private static final boolean LAUNCH_CUSTODY=!"false".equals(System.getProperty("projectseele.launchCustody"));
    /**
     * -Dprojectseele.launchReal=true runs the sortie the game runs, in a copy of the facility world
     * (a save named SEELE_LAUNCH_REVIEW...): the unit is put back in its hangar, the pilot boards its
     * entry plug through the hatch, and the logistics commands prepare and launch it to the exit
     * named by -Dprojectseele.launchExit (geofront, surface or hakone). The launch director holds
     * and releases the unit itself; nothing is emulated.
     */
    private static final boolean LAUNCH_REAL=Boolean.getBoolean("projectseele.launchReal");
    private static final String LAUNCH_EXIT=System.getProperty("projectseele.launchExit","surface");
    private static int realStage,realStageAt,realFreeTicks;
    private static final int STRIKE_LEAD=20,STRIKE_CYCLE=140;
    /** Each case: air (1) or ground (0), blocks ahead of the body, blocks to its right, blocks up, the target. */
    private static final int[][] STRIKE_CASES={{0,10,0,0,0},{0,20,0,0,0},{0,32,0,0,0},{0,20,10,0,0},{0,20,-10,0,0},
            {0,18,0,2,1},{0,18,0,14,1},{0,18,0,28,1},{0,24,0,2,1},{0,24,0,14,1},{0,24,0,28,1},
            {0,16,0,0,2},{0,24,0,0,2},
            {1,24,0,0,0},{1,34,0,0,0},{1,30,10,0,0},{1,24,0,2,1},{1,34,0,2,1}};
    private static final String[] STRIKE_TARGETS={"sachiel","ramiel","shamshel"};
    private static int strikeSpawned=-1,strikeFired=-1;
    private static boolean strikeCleared;
    private static final int DASH_END=Integer.getInteger("projectseele.tourDashEnd",130);
    /** Starts the sprint this many ticks sooner: the review ground ends in a wall. */
    private static final int DASH_LEAD=Integer.getInteger("projectseele.tourDashLead",0);
    private static final String DASH_WEAPON=System.getProperty("projectseele.tourDashWeapon");
    /** The unit the tour pilots: unit00, unit01 or unit02. */
    private static final String UNIT=System.getProperty("projectseele.tourUnit","unit01");
    private static final int UNIT_VARIANT=UNIT.endsWith("00")?EvaUnit01Entity.UNIT_00:UNIT.endsWith("02")?EvaUnit01Entity.UNIT_02:EvaUnit01Entity.UNIT_01;
    /** Ticks a terrain tour keeps running after its script, unrecorded, so its cleanup is carried out. */
    private static final int TERRAIN_GRACE=30;
    /** Where the piloted unit last stood, and for how many ticks: a tour starts once it stands still on its pad. */
    private static Vec3 settledAt;
    private static int settledTicks;
    /** Block x of the piloted unit's pad: the terrain tours build in its lane (Unit-01's is 0). */
    private static int lane=Integer.MIN_VALUE;
    private static int lane(EvaUnit01Entity eva){if(lane==Integer.MIN_VALUE)lane=(int)Math.floor(eva.getX());return lane;}
    private static Vec3 camPos, camAim, fxRamiel, fxFront, fxOrigin;
    private static EvaUnit01Entity fxUnit00;
    /** Record every drawn frame, not the first of each tick: offline renders then show the frames the game drew. */
    private static final boolean EVERY_FRAME=Boolean.getBoolean("projectseele.recordEveryFrame");
    private static float poseTime = Float.NaN;
    private static final int TOUR_END=Integer.getInteger("projectseele.tourEnd",1600)-TOUR_START;
    private static final String BATCH = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss"));
    private static int wait;
    private static int tick;
    private static int frame;
    private static int capturedTick = -1;
    private static int poseTick = -1;
    private static int entityId = -1;
    private static int serverStart = -1;
    private static int previousTick = -1;
    private static int warmupFrames;
    private static int missingPilotTicks;
    private static boolean finished;
    private static Entity camera;
    private static BufferedWriter poses;
    private static boolean preferencesSaved,oldPause,oldGui;
    private static CameraType oldCamera;

    private EvaConnectedActionReview() {}

    @SubscribeEvent
    public static void tick(TickEvent.ClientTickEvent event)
    {
        Minecraft mc = Minecraft.getInstance();
        if (!ENABLED || finished || event.phase != TickEvent.Phase.END
                || mc.player == null || mc.level == null || mc.getSingleplayerServer() == null) return;
        Path world = mc.getSingleplayerServer().getWorldPath(LevelResource.ROOT).normalize();
        String save = world.getFileName().toString();
        // The launch check may also run in a copy of the facility world, made for it under this name.
        if (!save.startsWith("SEELE_EVA_CONNECTED_REVIEW") && !(LAUNCH && LAUNCH_REAL && save.startsWith("SEELE_LAUNCH_REVIEW")))
        {
            finished = true;
            ProjectSeele.LOGGER.error("Connected action review requires a disposable SEELE_EVA_CONNECTED_REVIEW save");
            return;
        }
        if(!preferencesSaved){preferencesSaved=true;oldPause=mc.options.pauseOnLostFocus;oldGui=mc.options.hideGui;oldCamera=mc.options.getCameraType();}
        mc.options.pauseOnLostFocus = false;
        if (++wait < 100) return;
        if (LAUNCH) { launchR62(mc, world); return; }
        if (wait == 100)
        {
            mc.player.connection.sendCommand("seele dev motionlab reset");
            mc.player.connection.sendCommand("seele dev motionlab demo " + UNIT + " stop");
            mc.player.connection.sendCommand("seele dev motionlab enter " + UNIT);
            mc.player.connection.sendCommand("seele dev motionlab weapon " + UNIT + " " + (RIFLE ? "rifle" : "fists"));
            return;
        }
        EvaUnit01Entity eva = EvaPilotResolver.controlTarget(mc.player);
        // The link to the unit the previous run piloted outlives the request for
        // this one by a few ticks: do not start on it.
        if (eva == null || eva.getActivationTicks() > 0 || !eva.isPoweredOn()
                || serverStart < 0 && eva.getUnitVariant() != UNIT_VARIANT)
        {
            if (++missingPilotTicks > 400) finish(mc, "pilot_setup_timeout");
            return;
        }
        missingPilotTicks = 0;
        entityId = eva.getId();
        if (serverStart < 0)
        {
            // The lab reset walks or carries the unit back to its pad over the next second or two.
            // A tour that started before it stood there built its terrain where the last run ended.
            if (settledAt == null || eva.position().distanceToSqr(settledAt) > .0001) { settledAt = eva.position(); settledTicks = 0; return; }
            if (++settledTicks < 20) return;
            positionCamera(mc, eva);
            if (warmupFrames < 10) return;
            serverStart = mc.getSingleplayerServer().getTickCount();
        }
        tick = mc.getSingleplayerServer().getTickCount() - serverStart;
        openPoses(mc, world);
        if (TOUR)
        {
            tour(mc, eva);
            previousTick = tick;
            // A tour that built terrain clears it two ticks before its end; the
            // server needs time to run those commands before the client stops,
            // or half a hill stays in the save and blocks every later tour.
            if (tick >= TOUR_END + (HILL || STEPS || CLIMB ? TERRAIN_GRACE : 0)) finish(mc, "complete");
            return;
        }
        if (RIFLE)
        {
            rifleControls(mc, eva);
            previousTick = tick;
            if (tick >= 1845) finish(mc, "complete");
            return;
        }
        boolean moving = tick >= 30 && tick < 110 || tick >= 200 && tick < 225
                || tick >= 270 && tick < 362
                || tick >= 590 && tick < 650;
        boolean running = tick >= 65 && tick < 110;
        boolean backward = tick >= 590;
        mc.options.keyUp.setDown(moving && !backward);
        mc.options.keyDown.setDown(moving && backward);
        mc.options.keySprint.setDown(running);
        mc.player.input.up = moving && !backward;
        mc.player.input.down = moving && backward;
        mc.player.input.forwardImpulse = moving ? backward ? -1.0F : 1.0F : 0.0F;
        mc.player.zza = mc.player.input.forwardImpulse;
        mc.player.xxa = 0.0F;
        mc.player.setYRot(0.0F);
        mc.player.setXRot(0.0F);
        if (at(65)) send(ServerboundEvaControlPacket.ACTION_SPRINT_START);
        if (at(110)) send(ServerboundEvaControlPacket.ACTION_SPRINT_STOP);
        if (at(115) || at(300)) send(ServerboundEvaControlPacket.ACTION_SMASH);
        if (at(122)) send(ServerboundEvaControlPacket.ACTION_MELEE);
        if (at(160))
        {
            send(ServerboundEvaControlPacket.ACTION_SPRINT_STOP);
            send(ServerboundEvaControlPacket.ACTION_CROUCH_START);
        }
        if (at(245) || at(575)) send(ServerboundEvaControlPacket.ACTION_CROUCH_STOP);
        if (tick >= 270 && tick < 323 && tick / 4 != previousTick / 4) send(ServerboundEvaControlPacket.ACTION_MELEE);
        if (at(318)) send(ServerboundEvaControlPacket.ACTION_STOMP);
        if (at(365)) mc.player.connection.sendCommand("seele dev motionlab weapon unit01 knife");
        if (at(380) || at(465) || at(550)) send(ServerboundEvaControlPacket.ACTION_MELEE);
        if (at(400)) send(ServerboundEvaControlPacket.ACTION_SMASH);
        if (at(558)) send(ServerboundEvaControlPacket.ACTION_CROUCH_START);
        positionCamera(mc, eva);
        previousTick = tick;
        if (tick >= 690) finish(mc, "complete");
    }

    private static void openPoses(Minecraft mc, Path world)
    {
        if (poses != null) return;
        ProjectSeele.LOGGER.info("Connected action review started: batch={} entity={} world={}", BATCH, entityId, world);
        try
        {
            Path dir = mc.gameDirectory.toPath().resolve("screenshots/projectseele_connected/" + BATCH);
            Files.createDirectories(dir);
            poses = Files.newBufferedWriter(dir.resolve("poses.jsonl"), StandardCharsets.UTF_8);
        }
        catch (Exception exception)
        {
            throw new IllegalStateException("Unable to create action review", exception);
        }
    }

    /**
     * On the integrated server: where the unit and its own entry plug stand and whether the
     * facility has finished loading; with {@code board}, the pilot is set before the plug's hatch,
     * within reach and looking at it, and presses it as a right click does. Boarding itself is the
     * plug's own check of range, view and line of sight.
     */
    private static void boardR63(Minecraft mc,boolean board)
    {
        var server=mc.getSingleplayerServer();var id=mc.player.getUUID();int variant=UNIT_VARIANT;
        server.execute(()->{
            var pilot=server.getPlayerList().getPlayer(id);
            if(pilot==null)return;
            var level=pilot.serverLevel();
            var unit=com.projectseele.world.EvaLogisticsDirector.canonicalUnit(level,variant);
            var plug=com.projectseele.world.EntryPlugDirector.canonical(level,variant);
            boolean ready=com.projectseele.world.NervRouteRuntimeR52.ready(level);
            ProjectSeele.LOGGER.info("Real launch review: facility ready={} unit={} plug={}",ready,
                    unit==null?"none":unit.blockPosition().toShortString()+" locked "+unit.isNervLogisticsLocked()+" phase "+unit.getLaunchPhase(),
                    plug==null?"none":plug.blockPosition().toShortString()+" stage "+plug.getInsertionStage()+" hatch open "+plug.isHatchOpen()+" rider "+(plug.getFirstPassenger()==null?"none":plug.getFirstPassenger().getName().getString()));
            if(!board||unit==null||plug==null||!ready||pilot.isPassenger())return;
            Vec3 hatch=plug.hasCanonicalPose()?plug.transformPlugMarker(com.projectseele.world.EntryPlugKinematics.HATCH_PORTAL_CENTRE_P):plug.getBoundingBox().getCenter();
            Vec3 out=hatch.subtract(plug.getBoundingBox().getCenter()).multiply(1,0,1);
            out=out.lengthSqr()<1e-4?new Vec3(0,0,1):out.normalize();
            Vec3 stand=hatch.add(out.scale(4)).add(0,-1.6,0),look=hatch.subtract(stand.add(0,pilot.getEyeHeight(),0));
            float yaw=(float)(Mth.atan2(look.z,look.x)*Mth.RAD_TO_DEG)-90,pitch=(float)(-Mth.atan2(look.y,look.horizontalDistance())*Mth.RAD_TO_DEG);
            pilot.getAbilities().flying=pilot.getAbilities().mayfly;pilot.onUpdateAbilities();
            pilot.teleportTo(level,stand.x,stand.y,stand.z,yaw,pitch);
            var result=plug.mobInteract(pilot,net.minecraft.world.InteractionHand.MAIN_HAND);
            ProjectSeele.LOGGER.info("Real launch review: pressed the hatch from {} -> {} riding {}",stand,result,pilot.getVehicle()==null?"nothing":pilot.getVehicle().getType().toShortString());
        });
    }

    private static void realStage(int stage,int step)
    {
        ProjectSeele.LOGGER.info("Real launch review: stage {} at step {}",stage,step);
        realStage=stage;realStageAt=step;
    }

    private static void launchRealR63(Minecraft mc, Path world)
    {
        int step=wait-100,since=step-realStageAt;
        var link=mc.player.connection;
        EvaUnit01Entity eva=EvaPilotResolver.controlTarget(mc.player);
        if(step%40==0)ProjectSeele.LOGGER.info("Real launch review: step={} stage={} dim={} at={} vehicle={} eva={}",step,realStage,
                mc.level.dimension().location(),mc.player.blockPosition().toShortString(),
                mc.player.getVehicle()==null?"none":mc.player.getVehicle().getType().toShortString(),
                eva==null?"none":String.format("phase %d ticks %d activation %d locked %s y %.1f",eva.getLaunchPhase(),eva.getLaunchTicks(),eva.getActivationTicks(),eva.isNervLogisticsLocked(),eva.getY()));
        switch(realStage)
        {
            case 0 ->
            {
                // Whatever the last run left: off the seat, and the unit, its plug and the pilot back in the hangar.
                if(step==0)link.sendCommand("ride @s dismount");
                if(step==5){link.sendCommand("time set 6000");link.sendCommand("weather clear");}
                if(step==10)link.sendCommand("seele eva reset "+UNIT);
                if(step==80)link.sendCommand("seele tp hangar");
                if(step==160){link.sendCommand("seele eva status "+UNIT);realStage(1,step);}
            }
            case 1 ->
            {
                // The facility loads its units after the world: ask until the unit and its plug are there.
                if(mc.player.getVehicle() instanceof com.projectseele.entity.EntryPlugCarrierEntity||eva!=null){realStage(3,step);return;}
                if(since%40==20)boardR63(mc,since>=100);
                if(since>2400)finish(mc,"launch_boarding_timeout");
            }
            case 3 ->
            {
                if(since==10)link.sendCommand("seele eva prepare "+UNIT+" "+LAUNCH_EXIT);
                // The director refuses a launch until the unit stands ready in its silo: ask until it goes.
                if(since>200&&since%60==0)
                {
                    link.sendCommand("seele eva status "+UNIT);
                    link.sendCommand("seele eva launch "+UNIT);
                }
                if(eva!=null&&eva.getLaunchPhase()==EvaUnit01Entity.LAUNCH_ASCENT){launchAscentAt=step;realStage(4,step);}
                else if(since>8000)finish(mc,"launch_prepare_timeout");
            }
            default ->
            {
                // The unit changes dimension on the way: on the far side the client has a new entity for it.
                if(eva==null)
                {
                    if(++missingPilotTicks>600)finish(mc,"launch_pilot_lost");
                    return;
                }
                missingPilotTicks=0;
                entityId=eva.getId();
                if(!Boolean.getBoolean("projectseele.launchFirstPerson"))positionCamera(mc,eva);
                if(serverStart<0)
                {
                    if(warmupFrames<3)return;
                    serverStart=mc.getSingleplayerServer().getTickCount();
                }
                tick=mc.getSingleplayerServer().getTickCount()-serverStart;
                openPoses(mc,world);
                // Handed back: the launch over and the lock open for half a second (a new entity reads idle for a tick).
                realFreeTicks=!eva.isLaunchSequenceActive()&&!eva.isNervLogisticsLocked()?realFreeTicks+1:0;
                if(launchIdleAt<0&&realFreeTicks>=10)
                {
                    launchIdleAt=tick-10;
                    ProjectSeele.LOGGER.info("Real launch review: control back at tick {} y={} dim={}",launchIdleAt,String.format("%.2f",eva.getY()),mc.level.dimension().location());
                }
                previousTick=tick;
                if(launchIdleAt>=0&&tick>=launchIdleAt+LAUNCH_AFTER)finish(mc,"complete");
                else if(tick>3000)finish(mc,"launch_timeout");
            }
        }
    }

    private static void launchR62(Minecraft mc, Path world)
    {
        if(LAUNCH_REAL){launchRealR63(mc,world);return;}
        int step=wait-100,x=8000+LAUNCH_SITE*400,z=8000,bay=UNIT_VARIANT==0?-42:UNIT_VARIANT==2?42:0;
        var net=mc.player.connection;
        // The last run may have ended in a lab unit's seat; a complex is not built from a seat.
        if(step==0)net.sendCommand("ride @s dismount");
        if(step==5){net.sendCommand("time set 6000");net.sendCommand("weather clear");}
        if(step==10)net.sendCommand("tp @s "+x+" -59 "+z);
        if(step==70)net.sendCommand("seele dev silo setup");
        // Setup leaves the player on Unit-01's gantry; boarding takes the nearest caged unit.
        if(step==140&&bay!=0)net.sendCommand("tp @s ~"+bay+" ~ ~");
        if(step==160)net.sendCommand("seele dev silo board");
        if(step<180)return;
        EvaUnit01Entity eva=EvaPilotResolver.controlTarget(mc.player);
        if(eva==null||eva.getUnitVariant()!=UNIT_VARIANT)
        {
            if(++missingPilotTicks>400)finish(mc,"launch_boarding_timeout");
            return;
        }
        missingPilotTicks=0;
        entityId=eva.getId();
        // -Dprojectseele.launchFirstPerson=true stays in the pilot's seat, to check what the pilot sees of the landing.
        if(!Boolean.getBoolean("projectseele.launchFirstPerson"))positionCamera(mc,eva);
        if(LAUNCH_CUSTODY)
        {
            var server=mc.getSingleplayerServer();var id=eva.getUUID();
            server.execute(()->{
                for(var level:server.getAllLevels())
                    if(level.getEntity(id) instanceof EvaUnit01Entity unit)unit.setNervLogisticsLocked(unit.isLaunchSequenceActive());
            });
        }
        // The cage holds the unit until it is released; the pilot's own test release stands in for operations.
        if(launchAscentAt<0&&eva.getLaunchPhase()==EvaUnit01Entity.LAUNCH_LOCKED&&eva.getActivationTicks()<=21&&step%10==0)
            send(ServerboundEvaControlPacket.ACTION_SELF_LAUNCH);
        if(launchAscentAt<0&&eva.getLaunchPhase()==EvaUnit01Entity.LAUNCH_ASCENT)launchAscentAt=step;
        if(launchAscentAt<0)
        {
            if(step>3000)finish(mc,"launch_release_timeout");
            return;
        }
        if(serverStart<0)
        {
            if(warmupFrames<3)return;
            serverStart=mc.getSingleplayerServer().getTickCount();
        }
        tick=mc.getSingleplayerServer().getTickCount()-serverStart;
        openPoses(mc,world);
        if(launchIdleAt<0&&!eva.isLaunchSequenceActive())
        {
            launchIdleAt=tick;
            ProjectSeele.LOGGER.info("Launch review: control back at tick {} y={}",tick,String.format("%.2f",eva.getY()));
        }
        previousTick=tick;
        if(launchIdleAt>=0&&tick>=launchIdleAt+LAUNCH_AFTER)finish(mc,"complete");
        else if(tick>1500)finish(mc,"launch_timeout");
    }

    private static boolean at(int requested)
    {
        return previousTick < requested && tick >= requested;
    }

    private static void rifleControls(Minecraft mc, EvaUnit01Entity eva)
    {
        if (tick >= 1670)
        {
            mc.options.keyUp.setDown(false);
            mc.player.input.up=false;mc.player.input.forwardImpulse=0;mc.player.zza=0;mc.player.xxa=0;
            if(at(1670))mc.player.connection.sendCommand("seele dev motionlab weapon unit02 knife");
            if(at(1685))send(ServerboundEvaControlPacket.ACTION_MELEE);
            if(at(1705))send(ServerboundEvaControlPacket.ACTION_SMASH);
            if(at(1770))mc.player.connection.sendCommand("seele dev motionlab weapon unit02 fists");
            if(at(1805))send(ServerboundEvaControlPacket.ACTION_SMASH);
            positionCamera(mc,eva);
            return;
        }
        if (at(560) || at(1120))
        {
            String unit = tick >= 1120 ? "unit02" : "unit00";
            mc.player.connection.sendCommand("seele dev motionlab enter " + unit);
            mc.player.connection.sendCommand("seele dev motionlab weapon " + unit + " rifle");
        }
        int local = tick % 560;
        int offset = tick - local;
        boolean move = local >= 60 && local < 125 || local >= 200 && local < 235 || local >= 435 && local < 470;
        mc.options.keyUp.setDown(move);
        mc.player.input.up = move;
        mc.player.input.forwardImpulse = move ? 1 : 0;
        mc.player.zza = move ? 1 : 0;
        mc.player.xxa = 0;
        mc.player.setYRot(local >= 370 ? 50 : 0);
        mc.player.setXRot(local >= 495 ? 60 : local >= 475 ? -60 : local >= 370 && local < 435 ? -15 : local >= 435 ? 12 : 0);
        if (at(offset+90)) send(ServerboundEvaControlPacket.ACTION_SPRINT_START);
        if (at(offset+125)) send(ServerboundEvaControlPacket.ACTION_SPRINT_STOP);
        if (at(offset+160)) send(ServerboundEvaControlPacket.ACTION_CROUCH_START);
        if (at(offset+250)) send(ServerboundEvaControlPacket.ACTION_CROUCH_STOP);
        if (at(offset+275) || at(offset+355)) send(ServerboundEvaControlPacket.ACTION_TOGGLE_PRONE);
        if (local >= 30 && local < 510 && tick / 8 != previousTick / 8) send(ServerboundEvaControlPacket.ACTION_RIFLE_FIRE);
        positionCamera(mc, eva);
    }

    private static void tour(Minecraft mc,EvaUnit01Entity eva)
    {
        if(FX){fxR58(mc,eva);positionCamera(mc,eva);return;}
        if(MOVES){movesR59(mc);positionCamera(mc,eva);return;}
        if(HILL){hillR60(mc,lane(eva));positionCamera(mc,eva);return;}
        if(STRIKE){strikeR60(mc,eva);positionCamera(mc,eva);return;}
        if(ATF){atFieldR63(mc,eva);positionCamera(mc,eva);return;}
        int t=tick+TOUR_START;
        boolean move=CLIMB?t>=40&&t<104||t>=134&&t<166||t>=222&&t<236
                :t>=40&&t<Math.max(140,DASH_END+10)||t>=360&&t<420||t>=500&&t<580||t>=720&&t<800
                ||t>=840&&t<900||t>=1000&&t<1060||t>=1270&&t<1330||t>=1470&&t<1530;
        mc.options.keyUp.setDown(move);mc.player.input.up=move;mc.player.input.forwardImpulse=move?1:0;mc.player.zza=move?1:0;mc.player.xxa=0;
        // Turn about between the bare-hand and rifle parts so the long walk
        // stays inside the open review ground, then back for the knife.
        // (A tour started part-way has room ahead and does not turn.)
        mc.player.setYRot(TOUR_START==0&&t>=610&&t<1085?180:0);mc.player.setXRot(0);
        // The ledge check walks onto the step, as a pilot usually does.
        if(tourAt(70-DASH_LEAD)&&!CLIMB)send(ServerboundEvaControlPacket.ACTION_SPRINT_START);
        if(tourAt(20)&&DASH_WEAPON!=null)mc.player.connection.sendCommand("seele dev motionlab weapon "+UNIT+" "+DASH_WEAPON);
        // Optional checks: a full sprint over the run, and kerbs on the walk.
        // The client re-syncs held sprint and dash to the real keys, so hold them.
        int sprintEnd=DASH?DASH_END:110;
        if(DASH)com.projectseele.client.Keybinds.EVA_DASH.setDown(t>=98-DASH_LEAD&&t<sprintEnd);
        mc.options.keySprint.setDown(!CLIMB&&t>=70-DASH_LEAD&&t<sprintEnd);
        int x=lane(eva);
        if(STEPS&&at(1))
        {
            mc.player.connection.sendCommand("fill "+(x-30)+" -60 -88 "+(x+30)+" -57 -78 minecraft:stone");
            mc.player.connection.sendCommand("fill "+(x-30)+" -60 -72 "+(x+30)+" -54 -60 minecraft:stone");
        }
        // A kerb 20 high (walked up), on it a ledge 30 high, hip height (Space:
        // stepped up), and on that a wall 54 high, above the shoulders (Space: climbed).
        // A fill takes at most 32768 blocks: the ledge and the wall go in slices.
        if(CLIMB&&(at(1)||at(TOUR_END-2)))
        {
            String block=at(1)?" minecraft:stone":" minecraft:air";
            mc.player.connection.sendCommand("fill "+(x-24)+" -60 -66 "+(x+24)+" -41 -41"+block);
            for(int z=-40;z<=-14;z+=10)mc.player.connection.sendCommand("fill "+(x-24)+" -40 "+z+" "+(x+24)+" -11 "+Math.min(-14,z+9)+block);
            for(int z=-13;z<=14;z+=10)mc.player.connection.sendCommand("fill "+(x-24)+" -10 "+z+" "+(x+24)+" 43 "+Math.min(14,z+9)+block);
        }
        if(CLIMB)mc.options.keyJump.setDown(t>=100&&t<104||t>=166&&t<170);
        // A plain jump, then one with the hammer and one with the kick.
        if(JUMP)mc.options.keyJump.setDown(t>=50&&t<53||t>=100&&t<103||t>=150&&t<153);
        // The jump leaves the ground after its squat (seven ticks).
        if(JUMP&&tourAt(114))send(ServerboundEvaControlPacket.ACTION_MELEE);
        if(JUMP&&tourAt(164))send(ServerboundEvaControlPacket.ACTION_SMASH);
        if(STEPS&&at(TOUR_END-2))
        {
            mc.player.connection.sendCommand("fill "+(x-30)+" -60 -88 "+(x+30)+" -57 -78 minecraft:air");
            mc.player.connection.sendCommand("fill "+(x-30)+" -60 -72 "+(x+30)+" -54 -60 minecraft:air");
        }
        if(WEAPONS)weaponsR57(mc,tick);
        if(tourAt(sprintEnd))send(ServerboundEvaControlPacket.ACTION_SPRINT_STOP);
        if(!CLIMB&&(tourAt(170)||tourAt(182)||!COMBO&&(tourAt(194)||tourAt(206))))send(ServerboundEvaControlPacket.ACTION_MELEE);
        if(!CLIMB&&tourAt(240))send(ServerboundEvaControlPacket.ACTION_SMASH);
        // Optional chain check: the heavy pressed during the punch string.
        if(COMBO&&tourAt(193))send(ServerboundEvaControlPacket.ACTION_SMASH);
        if(!CLIMB&&tourAt(290))send(ServerboundEvaControlPacket.ACTION_STOMP);
        if(tourAt(340)||tourAt(820))send(ServerboundEvaControlPacket.ACTION_CROUCH_START);
        if(tourAt(440)||tourAt(920))send(ServerboundEvaControlPacket.ACTION_CROUCH_STOP);
        if(tourAt(470)||tourAt(600)||tourAt(940)||tourAt(1080)||tourAt(1340)||tourAt(1550))send(ServerboundEvaControlPacket.ACTION_TOGGLE_PRONE);
        if(tourAt(660))mc.player.connection.sendCommand("seele dev motionlab weapon unit01 rifle");
        if((t>=680&&t<900||t>=970&&t<1000)&&tick/4!=previousTick/4)send(ServerboundEvaControlPacket.ACTION_RIFLE_FIRE);
        if(tourAt(1130))mc.player.connection.sendCommand("seele dev motionlab weapon unit01 knife");
        if(tourAt(1150)||tourAt(1165)||tourAt(1180)||tourAt(1370)||tourAt(1385)||tourAt(1400))send(ServerboundEvaControlPacket.ACTION_MELEE);
        if(tourAt(1220)||tourAt(1430))send(ServerboundEvaControlPacket.ACTION_SMASH);
        positionCamera(mc,eva);
    }

    /** Up a terraced hill with a stop on the slope, over the top, then across the slope and back. */
    private static void strikeR60(Minecraft mc,EvaUnit01Entity eva)
    {
        // Slopes left by an earlier hill tour would stand between the body and the target.
        if(at(2))for(int z=-110;z<=70;z++)mc.player.connection.sendCommand("fill -60 -60 "+z+" 60 -25 "+z+" minecraft:air");
        int t=tick-STRIKE_LEAD;
        if(t<0)return;
        int index=t/STRIKE_CYCLE,local=t%STRIKE_CYCLE;
        mc.options.keyJump.setDown(false);
        if(index>=STRIKE_CASES.length)
        {
            if(!strikeCleared){strikeCleared=true;for(var name:STRIKE_TARGETS)mc.player.connection.sendCommand("kill @e[type=projectseele:"+name+"]");}
            return;
        }
        var c=STRIKE_CASES[index];
        double yaw=Math.toRadians(eva.getYRot());
        Vec3 ahead=new Vec3(-Math.sin(yaw),0,Math.cos(yaw)),right=new Vec3(-ahead.z,0,ahead.x);
        if(index!=strikeSpawned)
        {
            strikeSpawned=index;
            Vec3 at=eva.position().add(ahead.scale(c[1])).add(right.scale(c[2])).add(0,c[3],0);
            for(var name:STRIKE_TARGETS)mc.player.connection.sendCommand("kill @e[type=projectseele:"+name+"]");
            mc.player.connection.sendCommand("summon projectseele:"+STRIKE_TARGETS[c[4]]+" "+at.x+" "+at.y+" "+at.z+" {NoAI:1b,Rotation:["+(eva.getYRot()+180)+"F,0F]}");
            com.projectseele.ProjectSeele.LOGGER.info("R60CASE {} kind {} ahead {} right {} up {} target {}",index,c[0],c[1],c[2],c[3],STRIKE_TARGETS[c[4]]);
        }
        if(c[0]==1)mc.options.keyJump.setDown(local>=30&&local<33);
        if(index!=strikeFired&&local>=(c[0]==1?46:30)){strikeFired=index;send(ServerboundEvaControlPacket.ACTION_SMASH);}
    }

    private static void atFieldR63(Minecraft mc,EvaUnit01Entity eva)
    {
        int t=tick;
        mc.options.keyUp.setDown(false);mc.player.input.up=false;mc.player.input.forwardImpulse=0;mc.player.zza=0;mc.player.xxa=0;
        Vec3 fwd=Vec3.directionFromRotation(0,eva.getYRot()).multiply(1,0,1).normalize(),right=new Vec3(-fwd.z,0,fwd.x);
        String angel="@e[type=projectseele:sachiel,limit=1,sort=nearest]",unit="@e[type=projectseele:eva_unit01,limit=1,sort=nearest]";
        if(at(1))
        {
            // A field turns /kill away: an Angel left by an earlier run is emptied instead.
            for(int i=0;i<4;i++)mc.player.connection.sendCommand("data merge entity "+angel+" {Health:0.0f}");
            mc.player.connection.sendCommand("time set noon");mc.player.connection.sendCommand("weather clear");
        }
        if(at(12))
        {
            Vec3 a=eva.position().add(fwd.scale(40));
            mc.player.connection.sendCommand(String.format(java.util.Locale.ROOT,"summon projectseele:sachiel %.1f %.1f %.1f {NoAI:1b,Silent:1b,Rotation:[%.1fF,0F]}",a.x,a.y,a.z,eva.getYRot()+180));
        }
        // Single hits, then one every tick (the field shows at most every third), then the unit's own field.
        if(at(40)||at(70)||t>=100&&t<=106||at(210))mc.player.connection.sendCommand("damage "+angel+" 4 minecraft:arrow by @s");
        if(at(130))send(ServerboundEvaControlPacket.ACTION_TOGGLE_AT_FIELD);
        if(at(160)||at(240))mc.player.connection.sendCommand("damage "+unit+" 6 minecraft:mob_attack by "+angel);
        if(at(190))mc.player.connection.sendCommand("time set 12900");
        camPos=eva.position().add(fwd.scale(-30)).add(right.scale(45)).add(0,30,0);camAim=eva.position().add(fwd.scale(32)).add(0,26,0);
    }

    private static void hillR60(Minecraft mc,int x)
    {
        int t=tick;
        // Clear first: commands sent in one tick run in order, and an earlier
        // run that was cut short may have left its hill standing.
        if(at(1)){hillClearR60(mc,x);hillBlocksR60(mc,x);}
        if(at(TOUR_END-2))hillClearR60(mc,x);
        boolean up=t>=60&&t<120||t>=170&&t<300||t>=350&&t<410;
        mc.options.keyUp.setDown(up);mc.player.input.up=up;mc.player.input.forwardImpulse=up?1:0;mc.player.zza=up?1:0;mc.player.xxa=0;
        mc.player.setYRot(t<340?0:t<350?(t-340)*9:90);mc.player.setXRot(0);
    }

    /** The hill's own box only: nothing else on the review ground stands in it. */
    private static void hillClearR60(Minecraft mc,int x)
    {
        for(int z=-92;z<=60;z++)mc.player.connection.sendCommand("fill "+(x-44)+" -60 "+z+" "+(x+46)+" -30 "+z+" minecraft:air");
    }

    /** One-block terraces a few blocks wide, uneven across the slope, as the Hakone hillsides are. */
    private static void hillBlocksR60(Minecraft mc,int x)
    {
        int[][] bands={{-44,-14},{-13,-4},{-3,5},{6,15},{16,46}};
        for(int z=-92;z<=60;z++)
        {
            double along=Math.sin(Math.PI*(z+92)/152.0);
            for(int[] band:bands)
            {
                double centre=(band[0]+band[1])*.5;
                int height=(int)Math.round(26*along+1.6*Math.sin(z/5.0)+2.2*Math.sin((centre+z)/11.0));
                if(height>0)mc.player.connection.sendCommand("fill "+(x+band[0])+" -60 "+z+" "+(x+band[1])+" "+(-61+height)+" "+z+" minecraft:grass_block");
            }
        }
    }

    private static void movesR59(Minecraft mc)
    {
        int t=tick;
        if(at(20)&&DASH_WEAPON!=null)mc.player.connection.sendCommand("seele dev motionlab weapon "+UNIT+" "+DASH_WEAPON);
        boolean sprint=t>=400&&t<500;
        boolean up=t>=320&&t<380||sprint,down=t>=130&&t<175,left=t>=195&&t<240,right=t>=255&&t<300;
        float forward=(up?1:0)-(down?1:0),side=(left?1:0)-(right?1:0);
        mc.options.keyUp.setDown(up);mc.options.keyDown.setDown(down);mc.options.keyLeft.setDown(left);mc.options.keyRight.setDown(right);
        mc.player.input.up=up;mc.player.input.down=down;mc.player.input.left=left;mc.player.input.right=right;
        mc.player.input.forwardImpulse=forward;mc.player.input.leftImpulse=side;mc.player.zza=forward;mc.player.xxa=side;
        mc.options.keySprint.setDown(sprint);
        if(at(400))send(ServerboundEvaControlPacket.ACTION_SPRINT_START);
        if(at(500))send(ServerboundEvaControlPacket.ACTION_SPRINT_STOP);
        // A slow quarter turn on the spot and a fast one back; a steady curve; a right angle and a reversal at a run.
        float yaw=t<30?0:t<70?(t-30)*2.25F:t<90?90:t<100?90-(t-90)*9:t<320?0:t<380?(t-320)*3:t<430?180:t<460?270:90;
        mc.player.setYRot(yaw);mc.player.setXRot(0);
    }

    private static void weaponsR57(Minecraft mc,int w)
    {
        boolean walk=w>=60&&w<100||w>=490&&w<530;
        mc.options.keyUp.setDown(walk);mc.player.input.up=walk;mc.player.input.forwardImpulse=walk?1:0;mc.player.zza=walk?1:0;mc.player.xxa=0;
        if(at(1))mc.player.connection.sendCommand("seele dev motionlab weapon unit01 rifle");
        if(w>=20&&w<116&&w%4==0)send(ServerboundEvaControlPacket.ACTION_RIFLE_FIRE);
        if(at(125))mc.player.connection.sendCommand("seele dev motionlab weapon unit01 cannon");
        if(at(150)||at(265))send(ServerboundEvaControlPacket.ACTION_CHARGE_START);
        if(at(215)||at(330))send(ServerboundEvaControlPacket.ACTION_CHARGE_STOP);
        if(at(235)||at(350))send(ServerboundEvaControlPacket.ACTION_TOGGLE_PRONE);
        if(at(380))
        {
            mc.player.connection.sendCommand("seele dev motionlab enter unit02");
            mc.player.connection.sendCommand("seele dev motionlab weapon unit02 sword");
        }
        // Pressed every half second through the string, as a pilot mashing it would.
        if(at(400)||at(410)||at(420)||at(430)||at(440)||at(450)||at(520))send(ServerboundEvaControlPacket.ACTION_MELEE);
        if(at(462))send(ServerboundEvaControlPacket.ACTION_SMASH);
    }

    /** -Dprojectseele.fxFinaleOnly: start the effects script at its finale. */
    private static final int FX_OFFSET=Boolean.getBoolean("projectseele.fxFinaleOnly")?600:0;
    private static boolean fxAt(int scriptTick){return scriptTick>=FX_OFFSET&&at(scriptTick-FX_OFFSET);}
    private static boolean fxCapture(int t)
    {
        t+=FX_OFFSET;
        if(t>=90&&t<150)return true;
        if(t>=200&&t<620)return t%2==0;
        return t>=640&&t%2==0;
    }

    private static void fxR58(Minecraft mc,EvaUnit01Entity eva)
    {
        int t=tick+FX_OFFSET;
        mc.options.keyUp.setDown(false);mc.player.input.up=false;mc.player.input.forwardImpulse=0;mc.player.zza=0;mc.player.xxa=0;
        mc.player.setYRot(0);mc.player.setXRot(0);
        Vec3 fwd=Vec3.directionFromRotation(0,eva.getYRot()).multiply(1,0,1).normalize(),right=new Vec3(-fwd.z,0,fwd.x);
        if(fxAt(1))
        {
            // The review save keeps entities between runs.
            mc.player.connection.sendCommand("kill @e[type=projectseele:ramiel]");
            mc.player.connection.sendCommand("kill @e[type=projectseele:sachiel]");
            mc.player.connection.sendCommand("seele dev motionlab weapon unit01 cannon");
        }
        if(fxAt(30))send(ServerboundEvaControlPacket.ACTION_CHARGE_START);
        if(fxAt(100))send(ServerboundEvaControlPacket.ACTION_CHARGE_STOP);
        if(fxAt(180))mc.player.connection.sendCommand("seele dev motionlab weapon unit00 shield");
        if(t<200){camPos=eva.position().add(right.scale(-45)).add(fwd.scale(-75)).add(0,72,0);camAim=eva.position().add(fwd.scale(140)).add(0,22,0);return;}
        if(fxUnit00==null||!fxUnit00.isAlive())
            for(var e:mc.level.entitiesForRendering())if(e instanceof EvaUnit01Entity u&&u!=eva&&u.getUnitVariant()==0){fxUnit00=u;break;}
        if(fxUnit00==null)return;
        Vec3 f0=Vec3.directionFromRotation(0,fxUnit00.getYRot()).multiply(1,0,1).normalize(),r0=new Vec3(-f0.z,0,f0.x);
        if(fxAt(200))
        {
            fxRamiel=fxUnit00.position().add(f0.scale(170)).add(0,50,0);
            mc.player.connection.sendCommand(String.format(java.util.Locale.ROOT,"summon projectseele:ramiel %.1f %.1f %.1f {NoAI:1b,Silent:1b,PersistenceRequired:1b}",fxRamiel.x,fxRamiel.y,fxRamiel.z));
        }
        if(fxRamiel==null&&FX_OFFSET==0)return;
        if(t<400){camPos=fxRamiel.add(r0.scale(85)).add(f0.scale(-30)).add(0,4,0);camAim=fxRamiel.add(0,10,0);return;}
        if(t<520){camPos=fxUnit00.position().add(r0.scale(48)).add(f0.scale(30)).add(0,38,0);camAim=fxUnit00.position().add(f0.scale(6)).add(0,32,0);return;}
        if(t<620&&fxRamiel!=null){Vec3 mid=fxUnit00.position().lerp(fxRamiel,.5);camPos=mid.add(r0.scale(190)).add(0,10,0);camAim=mid;return;}
        if(fxAt(620))
        {
            mc.player.connection.sendCommand("kill @e[type=projectseele:ramiel]");
            mc.player.connection.sendCommand("kill @e[type=projectseele:sachiel]");
            mc.player.connection.sendCommand("seele dev motionlab weapon unit00 fists");
            mc.player.connection.sendCommand("seele dev motionlab weapon unit01 fists");
        }
        if(fxAt(645))
        {
            var server=mc.getSingleplayerServer();var id=eva.getUUID();
            server.execute(()->{
                var level=server.overworld();
                if(!(level.getEntity(id) instanceof EvaUnit01Entity hero))return;
                var angel=com.projectseele.registry.ModEntities.SACHIEL.get().create(level);if(angel==null)return;
                Vec3 at=hero.position().add(Vec3.directionFromRotation(0,hero.getYRot()).multiply(1,0,1).normalize().scale(34));
                angel.moveTo(at.x,at.y,at.z,hero.getYRot()+180,0);angel.setNoAi(true);angel.setSilent(true);angel.setPersistenceRequired();
                level.addFreshEntity(angel);
                boolean started=com.projectseele.event.FirstBattleDirector.tryStart(angel,hero,true);
                ProjectSeele.LOGGER.info("R58 FX REVIEW FINALE started={} hero={} angel={}",started,hero.position(),angel.position());
            });
            fxOrigin=eva.position();fxFront=fwd;
        }
        if(fxOrigin!=null)
        {
            Vec3 r=new Vec3(-fxFront.z,0,fxFront.x);
            // Follow the two fighters in profile, from the side away from Unit-00.
            Vec3 mid=fxOrigin.add(fxFront.scale(32));
            for(var e:mc.level.entitiesForRendering())
                if(e instanceof com.projectseele.entity.SachielEntity angel&&angel.isAlive()){mid=eva.position().lerp(angel.position(),.5);break;}
            camPos=mid.add(r.scale(-72)).add(0,26,0);camAim=mid.add(0,22,0);
        }
    }

    /** A tour event at its script tick, with -Dprojectseele.tourStart skipping the script's beginning. */
    private static boolean tourAt(int scriptTick)
    {
        return scriptTick>=TOUR_START&&at(scriptTick-TOUR_START);
    }

    private static void send(int action)
    {
        SeeleNetwork.CHANNEL.sendToServer(new ServerboundEvaControlPacket(action));
    }

    private static void positionCamera(Minecraft mc, EvaUnit01Entity eva)
    {
        if (camera == null)
        {
            camera = EntityType.ARMOR_STAND.create(mc.level);
            if (camera == null) throw new IllegalStateException("review camera");
            camera.setInvisible(true);
            camera.setNoGravity(true);
        }
        Vec3 target = eva.position().add(0, Double.parseDouble(System.getProperty("projectseele.reviewAimY","28")), 0);
        Vec3 position = eva.position().add(RIFLE && eva.getUnitVariant() == 0 ? -60 : Double.parseDouble(System.getProperty("projectseele.reviewCamX","60")), Double.parseDouble(System.getProperty("projectseele.reviewCamY","32")), Double.parseDouble(System.getProperty("projectseele.reviewCamZ","48")));
        if ((FX || ATF) && camPos != null) { position = camPos; target = camAim; }
        // Close follow of the fists: -Dprojectseele.reviewTrackHand=<distance>.
        double track=Double.parseDouble(System.getProperty("projectseele.reviewTrackHand","0"));
        if(track>0)
        {
            var hand=com.projectseele.entity.EvaGameplayMotionR32.hand(eva,"r",1);
            target=hand;position=hand.add(-track*.7,track*.15,track*.7);
        }
        Vec3 delta = target.subtract(position);
        camera.setPos(position.x, position.y - camera.getEyeHeight(), position.z);
        camera.setYRot((float)(Mth.atan2(delta.z, delta.x) * Mth.RAD_TO_DEG) - 90.0F);
        camera.setXRot((float)(-Mth.atan2(delta.y, delta.horizontalDistance()) * Mth.RAD_TO_DEG));
        camera.setYHeadRot(camera.getYRot());
        if (camera instanceof LivingEntity living) living.yHeadRotO = living.yHeadRot;
        camera.xo = camera.getX(); camera.yo = camera.getY(); camera.zo = camera.getZ();
        camera.xOld = camera.getX(); camera.yOld = camera.getY(); camera.zOld = camera.getZ();
        camera.yRotO = camera.getYRot(); camera.xRotO = camera.getXRot();
        mc.options.hideGui = true;
        mc.options.setCameraType(CameraType.FIRST_PERSON);
        mc.setCameraEntity(camera);
    }

    public static void recordPose(EvaUnit01Entity eva, BakedGeoModel model, float partialTick)
    {
        if (!ENABLED || finished || eva.getId() != entityId) return;
        if (serverStart < 0)
        {
            warmupFrames++;
            return;
        }
        // Past the script a terrain tour only waits for its cleanup, the ground gone from under the body.
        if (poses == null || !EVERY_FRAME && poseTick == tick || TOUR && !LAUNCH && tick >= TOUR_END) return;
        // A frame can draw the body more than once (shadow and main pass).
        if (EVERY_FRAME && eva.tickCount + partialTick == poseTime) return;
        poseTick = tick;poseTime = eva.tickCount + partialTick;
        JsonObject row = new JsonObject();
        row.addProperty("tick", tick);
        row.addProperty("variant", eva.getUnitVariant());
        row.addProperty("yaw", eva.getYRot());
        row.addProperty("image", frame + 1);
        row.addProperty("entityTick", eva.tickCount + partialTick);
        row.addProperty("key", eva.poseTransitionKey(partialTick));
        row.addProperty("heavyActive", eva.isHeavyMotionActive());
        if (TOUR) row.addProperty("writers", com.projectseele.client.render.EvaPoseGraph.traceWriters(eva));
        if (LAUNCH)
        {
            // Which part of the launch this frame belongs to, and what holds the body.
            JsonArray launch = new JsonArray();
            launch.add(eva.getLaunchPhase()); launch.add(eva.getLaunchTicks()); launch.add(eva.getActivationTicks());
            launch.add(eva.onGround() ? 1 : 0); launch.add(eva.isNoGravity() ? 1 : 0); launch.add(eva.isNervLogisticsLocked() ? 1 : 0);
            launch.add(eva.hasActiveCarrierMotion() ? 1 : 0); launch.add(eva.isVisuallyAirborneForRender() ? 1 : 0);
            launch.add(eva.isPoweredOn() ? 1 : 0); launch.add(eva.getDeltaMovement().y);
            launch.add(Minecraft.getInstance().gameRenderer.getMainCamera().getPosition().y);
            row.add("launch", launch);
        }
        if (eva.isHeavyMotionActive()) row.addProperty("heavyPhase", eva.heavyMotionProgress(partialTick));
        JsonArray world = new JsonArray();
        world.add(eva.getX()); world.add(eva.getY()); world.add(eva.getZ());
        row.add("world", world);
        // The drawn position and heading at this frame's partial tick.
        var drawn = eva.getPosition(partialTick).add(0, com.projectseele.client.EvaStepSmoothingR57.offset(eva, partialTick), 0);
        JsonArray position = new JsonArray();
        position.add(drawn.x); position.add(drawn.y); position.add(drawn.z);
        row.add("drawnPosition", position);
        row.addProperty("bodyYaw", net.minecraft.util.Mth.rotLerp(partialTick, eva.yBodyRotO, eva.yBodyRot));
        JsonObject transforms = new JsonObject();
        // Every bone, anatomical hand joints included, so offline renders can
        // skin the hands the game actually draws.
        java.util.ArrayDeque<software.bernie.geckolib.cache.object.GeoBone> open = new java.util.ArrayDeque<>(model.topLevelBones());
        while (!open.isEmpty())
        {
            var bone = open.pop();
            open.addAll(bone.getChildBones());
            JsonArray values = new JsonArray();
            values.add(bone.getRotX()); values.add(bone.getRotY()); values.add(bone.getRotZ());
            values.add(bone.getPosX()); values.add(bone.getPosY()); values.add(bone.getPosZ());
            // Hidden flag, then the scale when it is not one (weapons are
            // drawn at a fraction of their mesh size).
            boolean scaled = bone.getScaleX() != 1 || bone.getScaleY() != 1 || bone.getScaleZ() != 1;
            if (bone.isHidden() || scaled) values.add(bone.isHidden() ? 1 : 0);
            if (scaled) { values.add(bone.getScaleX()); values.add(bone.getScaleY()); values.add(bone.getScaleZ()); }
            transforms.add(bone.getName(), values);
        }
        row.add("bones", transforms);
        // What the terrain stages decided this frame (EvaFootPlacement.LAST and GROUNDING).
        for (var witness : new Object[][]{{"footPlacement", com.projectseele.client.render.EvaFootPlacement.LAST.get(eva.getId())},
                {"groundContact", com.projectseele.client.render.EvaFootPlacement.GROUNDING.get(eva.getId())}})
        {
            if (!(witness[1] instanceof double[] values)) continue;
            JsonArray list = new JsonArray();
            for (double value : values) list.add(Double.isFinite(value) ? (Number) value : null);
            row.add((String) witness[0], list);
        }
        if (RIFLE && eva.getWeapon() == EvaUnit01Entity.WEAPON_RIFLE)
        {
            var witness = com.projectseele.client.render.EvaRifleContactRig.LAST.get(eva.getId());
            if (witness != null)
            {
                row.addProperty("rightHandError", witness.rightError());
                row.addProperty("leftHandError", witness.leftError());
                if(witness.footDrift()>=0)row.addProperty("rifleFootDrift",witness.footDrift());
                Vec3 actual = com.projectseele.client.render.EvaUnit01Renderer.rifleMuzzleOrFallback(eva.getId(), witness.expectedMuzzle());
                row.addProperty("muzzleError", actual.distanceTo(witness.expectedMuzzle()));
            }
        }
        try
        {
            poses.write(row.toString());
            poses.newLine();
        }
        catch (Exception exception)
        {
            throw new IllegalStateException("review pose write", exception);
        }
    }

    @SubscribeEvent
    public static void render(TickEvent.RenderTickEvent event)
    {
        if (!ENABLED || finished || poses == null || event.phase != TickEvent.Phase.END
                || tick == capturedTick) return;
        // The tour measures per-frame continuity: a screenshot per tick would
        // halve the frame rate, so it keeps one still every two seconds.
        if (TOUR && !LAUNCH && tick >= TOUR_END) return;
        if (TOUR && FX) { if (!fxCapture(tick)) return; }
        else if (TOUR && ATF) { if (tick < 36) return; }
        else if (TOUR && !Boolean.getBoolean("projectseele.tourCapture") && tick % 40 != 0) return;
        Minecraft mc = Minecraft.getInstance();
        capturedTick = tick;
        frame++;
        Screenshot.grab(mc.gameDirectory, "projectseele_connected/" + BATCH
                        + String.format("/frame_%04d.png", frame), mc.getMainRenderTarget(), ignored -> {});
    }

    private static void finish(Minecraft mc, String reason)
    {
        finished = true;
        mc.options.keyUp.setDown(false);
        mc.options.keyDown.setDown(false);
        mc.options.keySprint.setDown(false);
        mc.options.keyJump.setDown(false);
        mc.setCameraEntity(mc.player);
        if(preferencesSaved){mc.options.pauseOnLostFocus=oldPause;mc.options.hideGui=oldGui;mc.options.setCameraType(oldCamera);}
        try
        {
            if (poses != null) poses.close();
        }
        catch (Exception exception)
        {
            ProjectSeele.LOGGER.error("Closing connected action review", exception);
        }
        ProjectSeele.LOGGER.info("Connected action review finished: batch={} reason={} ticks={} frames={}",
                BATCH, reason, tick, frame);
        mc.stop();
    }
}
