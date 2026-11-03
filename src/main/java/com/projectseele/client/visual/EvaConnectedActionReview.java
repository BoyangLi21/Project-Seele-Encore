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
    private static final boolean ENABLED = Boolean.getBoolean("projectseele.connectedActionReview");
    private static final boolean RIFLE = Boolean.getBoolean("projectseele.rifleActionReview");
    private static final boolean R05 = Boolean.getBoolean("projectseele.motionReviewR05");
    private static final boolean R06 = Boolean.getBoolean("projectseele.motionReviewR06");
    private static final boolean R10="r10-motion".equals(System.getProperty("projectseele.regionalBuild",""));
    /** Transition tour: every stance/weapon change the pilot can make, back to back (pose continuity review). */
    private static final boolean TOUR=Boolean.getBoolean("projectseele.transitionTour");
    private static final int TOUR_START=Integer.getInteger("projectseele.tourStart",0);
    private static final boolean COMBO=Boolean.getBoolean("projectseele.tourComboR57");
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
    private static net.minecraft.world.entity.animal.IronGolem heavyProbe;
    private static float heavyProbeHealth;
    private static volatile int heavyProbeFailures;
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
            if(R05)
            {
                if(R06)
                {
                    if(R10&&tick>=1000)controlsR10(mc,eva);else controlsR06(mc,eva);previousTick=tick;
                    if(tick>=(R10?1400:Boolean.getBoolean("projectseele.motionReviewR05All")?3000:1000))finish(mc,"complete");
                    return;
                }
                controlsR05(mc,eva);previousTick=tick;if(tick>=(Boolean.getBoolean("projectseele.motionReviewR05All")?1950:650))finish(mc,"complete");return;
            }
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
        int t=tick+TOUR_START;
        boolean move=t>=40&&t<140||t>=360&&t<420||t>=500&&t<580||t>=720&&t<800
                ||t>=840&&t<900||t>=1000&&t<1060||t>=1270&&t<1330||t>=1470&&t<1530;
        mc.options.keyUp.setDown(move);mc.player.input.up=move;mc.player.input.forwardImpulse=move?1:0;mc.player.zza=move?1:0;mc.player.xxa=0;
        // Turn about between the bare-hand and rifle parts so the long walk
        // stays inside the open review ground, then back for the knife.
        // (A tour started part-way has room ahead and does not turn.)
        mc.player.setYRot(TOUR_START==0&&t>=610&&t<1085?180:0);mc.player.setXRot(0);
        if(tourAt(70))send(ServerboundEvaControlPacket.ACTION_SPRINT_START);
        if(tourAt(110))send(ServerboundEvaControlPacket.ACTION_SPRINT_STOP);
        if(tourAt(170)||tourAt(182)||!COMBO&&(tourAt(194)||tourAt(206)))send(ServerboundEvaControlPacket.ACTION_MELEE);
        if(tourAt(240))send(ServerboundEvaControlPacket.ACTION_SMASH);
        // Optional chain check: the heavy pressed during the punch string.
        if(COMBO&&tourAt(193))send(ServerboundEvaControlPacket.ACTION_SMASH);
        if(tourAt(290))send(ServerboundEvaControlPacket.ACTION_STOMP);
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

    /** A tour event at its script tick, with -Dprojectseele.tourStart skipping the script's beginning. */
    private static boolean tourAt(int scriptTick)
    {
        return scriptTick>=TOUR_START&&at(scriptTick-TOUR_START);
    }

    private static void controlsR05(Minecraft mc,EvaUnit01Entity eva)
    {
        int local=tick%650,offset=tick-local;String unit=tick>=1300?"unit02":tick>=650?"unit00":"unit01";
        if(at(650)||at(1300))
        {
            mc.player.connection.sendCommand("seele motionlab enter "+unit);
            mc.player.connection.sendCommand("seele motionlab weapon "+unit+" rifle");
        }
        boolean moving=local>=50&&local<200;
        mc.options.keyUp.setDown(moving);mc.player.input.up=moving;mc.player.input.forwardImpulse=moving?1:0;mc.player.zza=moving?1:0;mc.player.xxa=0;
        mc.player.setYRot(0);mc.player.setXRot(local>=290&&local<310?15:local>=310&&local<330?-20:local>=600&&local<612?-30:local>=612&&local<622?-45:local>=622&&local<632?-60:local>=632&&local<644?60:0);
        if(at(offset+65))send(ServerboundEvaControlPacket.ACTION_SPRINT_START);
        if(at(offset+80))send(ServerboundEvaControlPacket.ACTION_SPRINT_STOP);
        if(at(offset+85))send(ServerboundEvaControlPacket.ACTION_CROUCH_START);
        if(at(offset+205))send(ServerboundEvaControlPacket.ACTION_CROUCH_STOP);
        if(at(offset+230)||at(offset+330))send(ServerboundEvaControlPacket.ACTION_TOGGLE_PRONE);
        if((local>=25&&local<350||local>=600&&local<646)&&tick/4!=previousTick/4)send(ServerboundEvaControlPacket.ACTION_RIFLE_FIRE);
        if(at(offset+365))mc.player.connection.sendCommand("seele motionlab weapon "+unit+" fists");
        if(at(offset+380))heavyProbe(mc,eva,false);
        if(at(offset+385))send(ServerboundEvaControlPacket.ACTION_SMASH);
        if(at(offset+400))send(ServerboundEvaControlPacket.ACTION_MELEE);
        if(at(offset+402))heavyProbe(mc,eva,true);
        if(at(offset+430))send(ServerboundEvaControlPacket.ACTION_STOMP);
        if(at(offset+460))mc.player.connection.sendCommand("seele motionlab weapon "+unit+" knife");
        if(at(offset+480))send(ServerboundEvaControlPacket.ACTION_MELEE);
        if(at(offset+495))send(ServerboundEvaControlPacket.ACTION_SMASH);
        if(at(offset+585))mc.player.connection.sendCommand("seele motionlab weapon "+unit+" rifle");
        positionCamera(mc,eva);
    }

    private static void heavyProbe(Minecraft mc,EvaUnit01Entity eva,boolean check)
    {
        int id=eva.getId();
        mc.getSingleplayerServer().execute(()->{
            if(check)
            {
                float damage=heavyProbe==null?0:heavyProbeHealth-heavyProbe.getHealth();
                if(damage<=0)heavyProbeFailures++;
                ProjectSeele.LOGGER.info("R05 forward heavy target: damage={} passed={}",damage,damage>0);
                if(heavyProbe!=null)heavyProbe.discard();heavyProbe=null;return;
            }
            var level=mc.getSingleplayerServer().overworld();
            if(!(level.getEntity(id) instanceof EvaUnit01Entity serverEva))return;
            heavyProbe=EntityType.IRON_GOLEM.create(level);if(heavyProbe==null)return;
            Vec3 point=serverEva.position().add(serverEva.getForward().multiply(1,0,1).normalize().scale(30)).add(0,46,0);
            heavyProbe.setPos(point.x,point.y,point.z);heavyProbe.setNoAi(true);heavyProbe.setNoGravity(true);heavyProbe.setSilent(true);
            heavyProbeHealth=heavyProbe.getHealth();level.addFreshEntity(heavyProbe);
        });
    }

    private static void controlsR06(Minecraft mc,EvaUnit01Entity eva)
    {
        int local=tick%1000,offset=tick-local;String unit=tick>=2000?"unit02":tick>=1000?"unit00":"unit01";
        if(at(1000)||at(2000))
        {
            mc.player.connection.sendCommand("seele motionlab enter "+unit);
            mc.player.connection.sendCommand("seele motionlab weapon "+unit+" rifle");
        }
        boolean moving=local>=35&&local<70||local>=155&&local<250;
        mc.options.keyUp.setDown(moving);mc.player.input.up=moving;mc.player.input.forwardImpulse=moving?1:0;mc.player.zza=moving?1:0;mc.player.xxa=0;
        mc.player.setYRot(0);mc.player.setXRot(local>=365&&local<380?12:local>=380&&local<400?-15:0);
        if(at(offset+45))send(ServerboundEvaControlPacket.ACTION_SPRINT_START);
        if(at(offset+70))send(ServerboundEvaControlPacket.ACTION_SPRINT_STOP);
        if(at(offset+85)||at(offset+430))send(ServerboundEvaControlPacket.ACTION_CROUCH_START);
        if(at(offset+510))send(ServerboundEvaControlPacket.ACTION_CROUCH_STOP);
        if(at(offset+275)||at(offset+590)||at(offset+730))send(ServerboundEvaControlPacket.ACTION_TOGGLE_PRONE);
        if(local>=25&&local<805&&tick/4!=previousTick/4)send(ServerboundEvaControlPacket.ACTION_RIFLE_FIRE);
        if(at(offset+805))mc.player.connection.sendCommand("seele motionlab weapon "+unit+" fists");
        if(at(offset+830))heavyProbe(mc,eva,false);
        if(at(offset+835))send(ServerboundEvaControlPacket.ACTION_SMASH);
        if(at(offset+845))send(ServerboundEvaControlPacket.ACTION_MELEE);
        if(at(offset+852))heavyProbe(mc,eva,true);
        if(at(offset+890))mc.player.connection.sendCommand("seele motionlab weapon "+unit+" knife");
        if(at(offset+910))send(ServerboundEvaControlPacket.ACTION_MELEE);
        if(at(offset+935))send(ServerboundEvaControlPacket.ACTION_SMASH);
        positionCamera(mc,eva);
    }

    private static void controlsR10(Minecraft mc,EvaUnit01Entity eva)
    {
        int local=tick-1000;
        if(at(1000))mc.player.connection.sendCommand("seele motionlab weapon unit01 fists");
        boolean walking=local>=10&&local<120||local>=145&&local<240||local>=340&&local<390,back=local>=200&&local<240;
        mc.options.keyUp.setDown(walking&&!back);mc.options.keyDown.setDown(walking&&back);mc.options.keyJump.setDown(local>=125&&local<128||local>=345&&local<348);
        mc.player.input.up=walking&&!back;mc.player.input.down=walking&&back;mc.player.input.forwardImpulse=walking?(back?-1:1):0;mc.player.zza=mc.player.input.forwardImpulse;mc.player.xxa=0;mc.player.setYRot(0);mc.player.setXRot(0);
        if(at(1050))send(ServerboundEvaControlPacket.ACTION_SPRINT_START);if(at(1100))send(ServerboundEvaControlPacket.ACTION_SPRINT_STOP);
        if(at(1260))send(ServerboundEvaControlPacket.ACTION_MELEE);if(at(1300))send(ServerboundEvaControlPacket.ACTION_SMASH);
        positionCamera(mc,eva);
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
        Vec3 position = eva.position().add(RIFLE && eva.getUnitVariant() == 0 ? -60 : 60, 32, 48);
        if(R06)
        {
            double lower=Mth.clamp(eva.rifleStanceLevel(1)/3,0,1);
            target=eva.position().add(0,28-21*lower,8*lower);
            position=eva.position().add(eva.getUnitVariant()==0?-64:64,32-19*lower,48);
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
        if (poses == null || poseTick == tick) return;
        poseTick = tick;
        JsonObject row = new JsonObject();
        row.addProperty("tick", tick);
        row.addProperty("variant", eva.getUnitVariant());
        if(R06)row.addProperty("stanceLevel",eva.rifleStanceLevel(partialTick));
        if(R05)
        {
            row.addProperty("gaitPhase",eva.rifleGaitPhase(partialTick));
            row.addProperty("crouchBlend",eva.rifleCrouchBlend(partialTick));
            row.addProperty("proneBlend",eva.rifleProneBlend(partialTick));
            JsonArray position=new JsonArray();var v=eva.getPosition(partialTick);position.add(v.x);position.add(v.y);position.add(v.z);row.add("renderPosition",position);
        }
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
        var drawn = eva.getPosition(partialTick);
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
                if(R05){row.addProperty("stock",witness.stock().toString());row.addProperty("shoulder",witness.shoulder().toString());}
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
        if(R05&&poses!=null&&!finished)
        {
            if(event.phase==TickEvent.Phase.START)EvaMeshAuditR05.begin(tick,entityId,Minecraft.getInstance().gameDirectory.toPath().resolve("screenshots/projectseele_connected/"+BATCH+"/geometry"));
            else EvaMeshAuditR05.end();
        }
        if (!ENABLED || finished || poses == null || event.phase != TickEvent.Phase.END
                || tick == capturedTick) return;
        // The tour measures per-frame continuity: a screenshot per tick would
        // halve the frame rate, so it keeps one still every two seconds.
        if (TOUR && !Boolean.getBoolean("projectseele.tourCapture") && tick % 40 != 0) return;
        Minecraft mc = Minecraft.getInstance();
        capturedTick = tick;
        frame++;
        Screenshot.grab(mc.gameDirectory, "projectseele_connected/" + BATCH
                        + String.format("/frame_%04d.png", frame), mc.getMainRenderTarget(), ignored -> {});
    }

    private static void finish(Minecraft mc, String reason)
    {
        if(R05&&reason.equals("complete")&&heavyProbeFailures>0)reason="forward_heavy_target_failed";
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
