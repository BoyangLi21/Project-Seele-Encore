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
        if (!world.getFileName().toString().startsWith("SEELE_EVA_CONNECTED_REVIEW"))
        {
            finished = true;
            ProjectSeele.LOGGER.error("Connected action review requires a disposable SEELE_EVA_CONNECTED_REVIEW save");
            return;
        }
        if(!preferencesSaved){preferencesSaved=true;oldPause=mc.options.pauseOnLostFocus;oldGui=mc.options.hideGui;oldCamera=mc.options.getCameraType();}
        mc.options.pauseOnLostFocus = false;
        if (++wait < 100) return;
        if (wait == 100)
        {
            mc.player.connection.sendCommand("seele motionlab reset");
            mc.player.connection.sendCommand("seele motionlab demo unit01 stop");
            mc.player.connection.sendCommand("seele motionlab enter unit01");
            mc.player.connection.sendCommand("seele motionlab weapon unit01 " + (RIFLE ? "rifle" : "fists"));
            return;
        }
        EvaUnit01Entity eva = EvaPilotResolver.controlTarget(mc.player);
        if (eva == null || eva.getActivationTicks() > 0 || !eva.isPoweredOn())
        {
            if (++missingPilotTicks > 400) finish(mc, "pilot_setup_timeout");
            return;
        }
        missingPilotTicks = 0;
        entityId = eva.getId();
        if (serverStart < 0)
        {
            positionCamera(mc, eva);
            if (warmupFrames < 10) return;
            serverStart = mc.getSingleplayerServer().getTickCount();
        }
        tick = mc.getSingleplayerServer().getTickCount() - serverStart;
        if (poses == null)
        {
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
        if (TOUR)
        {
            tour(mc, eva);
            previousTick = tick;
            if (tick >= TOUR_END) finish(mc, "complete");
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
        if (at(365)) mc.player.connection.sendCommand("seele motionlab weapon unit01 knife");
        if (at(380) || at(465) || at(550)) send(ServerboundEvaControlPacket.ACTION_MELEE);
        if (at(400)) send(ServerboundEvaControlPacket.ACTION_SMASH);
        if (at(558)) send(ServerboundEvaControlPacket.ACTION_CROUCH_START);
        positionCamera(mc, eva);
        previousTick = tick;
        if (tick >= 690) finish(mc, "complete");
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
            if(at(1670))mc.player.connection.sendCommand("seele motionlab weapon unit02 knife");
            if(at(1685))send(ServerboundEvaControlPacket.ACTION_MELEE);
            if(at(1705))send(ServerboundEvaControlPacket.ACTION_SMASH);
            if(at(1770))mc.player.connection.sendCommand("seele motionlab weapon unit02 fists");
            if(at(1805))send(ServerboundEvaControlPacket.ACTION_SMASH);
            positionCamera(mc,eva);
            return;
        }
        if (at(560) || at(1120))
        {
            String unit = tick >= 1120 ? "unit02" : "unit00";
            mc.player.connection.sendCommand("seele motionlab enter " + unit);
            mc.player.connection.sendCommand("seele motionlab weapon " + unit + " rifle");
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
        int t=tick+TOUR_START;
        boolean move=CLIMB?t>=40&&t<104||t>=134&&t<166||t>=222&&t<236
                :t>=40&&t<140||t>=360&&t<420||t>=500&&t<580||t>=720&&t<800
                ||t>=840&&t<900||t>=1000&&t<1060||t>=1270&&t<1330||t>=1470&&t<1530;
        mc.options.keyUp.setDown(move);mc.player.input.up=move;mc.player.input.forwardImpulse=move?1:0;mc.player.zza=move?1:0;mc.player.xxa=0;
        // Turn about between the bare-hand and rifle parts so the long walk
        // stays inside the open review ground, then back for the knife.
        // (A tour started part-way has room ahead and does not turn.)
        mc.player.setYRot(TOUR_START==0&&t>=610&&t<1085?180:0);mc.player.setXRot(0);
        // The ledge check walks onto the step, as a pilot usually does.
        if(tourAt(70)&&!CLIMB)send(ServerboundEvaControlPacket.ACTION_SPRINT_START);
        // Optional checks: a full sprint over the run, and kerbs on the walk.
        // The client re-syncs held sprint and dash to the real keys, so hold them.
        if(DASH)com.projectseele.client.Keybinds.EVA_DASH.setDown(t>=70&&t<110);
        mc.options.keySprint.setDown(!CLIMB&&t>=70&&t<110);
        if(STEPS&&at(1))
        {
            mc.player.connection.sendCommand("fill -30 -60 -88 30 -57 -78 minecraft:stone");
            mc.player.connection.sendCommand("fill -30 -60 -72 30 -54 -60 minecraft:stone");
        }
        // A kerb 20 high (walked up), on it a ledge 30 high, hip height (Space:
        // stepped up), and on that a wall 54 high, above the shoulders (Space: climbed).
        // A fill takes at most 32768 blocks: the ledge and the wall go in slices.
        if(CLIMB&&(at(1)||at(TOUR_END-2)))
        {
            String block=at(1)?" minecraft:stone":" minecraft:air";
            mc.player.connection.sendCommand("fill -24 -60 -66 24 -41 -41"+block);
            for(int z=-40;z<=-14;z+=10)mc.player.connection.sendCommand("fill -24 -40 "+z+" 24 -11 "+Math.min(-14,z+9)+block);
            for(int z=-13;z<=14;z+=10)mc.player.connection.sendCommand("fill -24 -10 "+z+" 24 43 "+Math.min(14,z+9)+block);
        }
        if(CLIMB)mc.options.keyJump.setDown(t>=100&&t<104||t>=166&&t<170);
        // A plain jump, then one with the hammer and one with the kick.
        if(JUMP)mc.options.keyJump.setDown(t>=50&&t<53||t>=100&&t<103||t>=150&&t<153);
        // The jump leaves the ground after its squat (seven ticks).
        if(JUMP&&tourAt(114))send(ServerboundEvaControlPacket.ACTION_MELEE);
        if(JUMP&&tourAt(164))send(ServerboundEvaControlPacket.ACTION_SMASH);
        if(STEPS&&at(TOUR_END-2))
        {
            mc.player.connection.sendCommand("fill -30 -60 -88 30 -57 -78 minecraft:air");
            mc.player.connection.sendCommand("fill -30 -60 -72 30 -54 -60 minecraft:air");
        }
        if(WEAPONS)weaponsR57(mc,tick);
        if(tourAt(110))send(ServerboundEvaControlPacket.ACTION_SPRINT_STOP);
        if(!CLIMB&&(tourAt(170)||tourAt(182)||!COMBO&&(tourAt(194)||tourAt(206))))send(ServerboundEvaControlPacket.ACTION_MELEE);
        if(!CLIMB&&tourAt(240))send(ServerboundEvaControlPacket.ACTION_SMASH);
        // Optional chain check: the heavy pressed during the punch string.
        if(COMBO&&tourAt(193))send(ServerboundEvaControlPacket.ACTION_SMASH);
        if(!CLIMB&&tourAt(290))send(ServerboundEvaControlPacket.ACTION_STOMP);
        if(tourAt(340)||tourAt(820))send(ServerboundEvaControlPacket.ACTION_CROUCH_START);
        if(tourAt(440)||tourAt(920))send(ServerboundEvaControlPacket.ACTION_CROUCH_STOP);
        if(tourAt(470)||tourAt(600)||tourAt(940)||tourAt(1080)||tourAt(1340)||tourAt(1550))send(ServerboundEvaControlPacket.ACTION_TOGGLE_PRONE);
        if(tourAt(660))mc.player.connection.sendCommand("seele motionlab weapon unit01 rifle");
        if((t>=680&&t<900||t>=970&&t<1000)&&tick/4!=previousTick/4)send(ServerboundEvaControlPacket.ACTION_RIFLE_FIRE);
        if(tourAt(1130))mc.player.connection.sendCommand("seele motionlab weapon unit01 knife");
        if(tourAt(1150)||tourAt(1165)||tourAt(1180)||tourAt(1370)||tourAt(1385)||tourAt(1400))send(ServerboundEvaControlPacket.ACTION_MELEE);
        if(tourAt(1220)||tourAt(1430))send(ServerboundEvaControlPacket.ACTION_SMASH);
        positionCamera(mc,eva);
    }

    private static void weaponsR57(Minecraft mc,int w)
    {
        boolean walk=w>=60&&w<100||w>=490&&w<530;
        mc.options.keyUp.setDown(walk);mc.player.input.up=walk;mc.player.input.forwardImpulse=walk?1:0;mc.player.zza=walk?1:0;mc.player.xxa=0;
        if(at(1))mc.player.connection.sendCommand("seele motionlab weapon unit01 rifle");
        if(w>=20&&w<116&&w%4==0)send(ServerboundEvaControlPacket.ACTION_RIFLE_FIRE);
        if(at(125))mc.player.connection.sendCommand("seele motionlab weapon unit01 cannon");
        if(at(150)||at(265))send(ServerboundEvaControlPacket.ACTION_CHARGE_START);
        if(at(215)||at(330))send(ServerboundEvaControlPacket.ACTION_CHARGE_STOP);
        if(at(235)||at(350))send(ServerboundEvaControlPacket.ACTION_TOGGLE_PRONE);
        if(at(380))
        {
            mc.player.connection.sendCommand("seele motionlab enter unit02");
            mc.player.connection.sendCommand("seele motionlab weapon unit02 sword");
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
            mc.player.connection.sendCommand("seele motionlab weapon unit01 cannon");
        }
        if(fxAt(30))send(ServerboundEvaControlPacket.ACTION_CHARGE_START);
        if(fxAt(100))send(ServerboundEvaControlPacket.ACTION_CHARGE_STOP);
        if(fxAt(180))mc.player.connection.sendCommand("seele motionlab weapon unit00 shield");
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
            mc.player.connection.sendCommand("seele motionlab weapon unit00 fists");
            mc.player.connection.sendCommand("seele motionlab weapon unit01 fists");
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
        Vec3 target = eva.position().add(0, 28, 0);
        Vec3 position = eva.position().add(RIFLE && eva.getUnitVariant() == 0 ? -60 : Double.parseDouble(System.getProperty("projectseele.reviewCamX","60")), 32, Double.parseDouble(System.getProperty("projectseele.reviewCamZ","48")));
        if (FX && camPos != null) { position = camPos; target = camAim; }
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
        if (poses == null || !EVERY_FRAME && poseTick == tick) return;
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
        if (TOUR && FX) { if (!fxCapture(tick)) return; }
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
