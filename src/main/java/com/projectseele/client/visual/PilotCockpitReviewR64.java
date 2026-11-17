package com.projectseele.client.visual;

import com.projectseele.ProjectSeele;
import com.projectseele.client.cockpit.PilotViewSteadyR64;
import com.projectseele.entity.EntryPlugCarrierEntity;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.network.SeeleNetwork;
import com.projectseele.network.ServerboundEvaControlPacket;
import com.projectseele.world.EntryPlugKinematics;
import com.projectseele.world.EvaPilotResolver;
import net.minecraft.client.CameraType;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.ViewportEvent;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

import java.io.BufferedWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Locale;

/**
 * R64 review of the pilot's first person, in disposable saves only.
 * <p>
 * -Dprojectseele.cockpitReviewR64=true (a SEELE_EVA_CONNECTED_REVIEW save): Unit-01 is boarded in the motion lab,
 * left, boarded again with the whole cabin sequence, walked, run, struck with, jumped, looked about from and left,
 * always the same way. Every drawn frame's camera goes to view.csv (tools/cockpit_review/view_metrics.py reads it)
 * and every tick's picture to a frame, under screenshots/projectseele_cockpit/. Run it with
 * -Dprojectseele.cockpitR64=false for the same drive as up to R63.
 * <p>
 * -Dprojectseele.plugWatchR64=outside|cabin|inside (with the launch review's real sortie, a SEELE_LAUNCH_REVIEW
 * save): while the pilot rides the capsule outside its Unit, pictures of the capsule from beside it, of the pilot
 * from inside the cabin, or from the pilot's seat, and the client is stopped a few seconds after the capsule has
 * locked.
 */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class PilotCockpitReviewR64
{
    private static final boolean DRIVE = Boolean.getBoolean("projectseele.cockpitReviewR64");
    private static final String PLUG = System.getProperty("projectseele.plugWatchR64");
    private static final int PLUG_END = Integer.getInteger("projectseele.plugWatchEndR64", 160);
    /**
     * -Dprojectseele.plugWatchRecoverR64=<ticks of free control on the ground>: the Unit's recovery is asked then
     * ("/seele eva recover"); the watch runs through the way back and ends once the crane has drawn the capsule out
     * and set it at its dock. Calling a sortie off in the cage does not draw the capsule out, and the pilot's own
     * exit is refused there: the crane's extraction is the last part of a recovery and of nothing else.
     */
    private static final int PLUG_RECOVER = Integer.getInteger("projectseele.plugWatchRecoverR64", -1);
    /** -Dprojectseele.plugWatchExitR64=<ticks of free control on the ground>: the pilot's exit is asked then, and the watch ends 13 seconds later. */
    private static final int PLUG_EXIT = Integer.getInteger("projectseele.plugWatchExitR64", -1);
    /**
     * -Dprojectseele.plugWatchCancelR64=<ticks after the lock>: the operator calls the sortie off then (/seele eva
     * cancel: the Unit stops where it stands, its capsule in). -Dprojectseele.plugWatchAfterCancelR64=exit|abort|none
     * is what the pilot does forty ticks later: asks to leave (the exit key), aborts (the abort key), or nothing
     * (the launch review asks for the preparation again by itself, every five seconds). With exit or abort the watch
     * runs until the capsule is back at its dock and the pilot has climbed out.
     */
    private static final int PLUG_CANCEL = Integer.getInteger("projectseele.plugWatchCancelR64", -1);
    private static final String PLUG_AFTER_CANCEL = System.getProperty("projectseele.plugWatchAfterCancelR64", "none");
    private static boolean cancelSent;
    /** -Dprojectseele.plugWatchAfterDockR64=<ticks>: how long the recovered capsule is watched at its dock before the pilot climbs out (ten more seconds are watched after that). */
    private static final int PLUG_AFTER_DOCK = Integer.getInteger("projectseele.plugWatchAfterDockR64", 60);
    /** -Dprojectseele.plugWatchChatR64=true: lines of every source are sent to the pilot after the lock and after leaving the capsule, for the chat panel's pictures. */
    private static final boolean PLUG_CHAT = Boolean.getBoolean("projectseele.plugWatchChatR64");
    private static boolean recoverSent, exitSent, leaveAsked;
    private static int freeTicks, afterTicks, offTicks, lastStage = -1;
    private static final String BATCH = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss"));
    /**
     * -Dprojectseele.cockpitReviewScriptR64: "drive" (the default, described above), "stances" (crouched and at a
     * crouched walk, prone and crawling, the rifle carried, sighted and fired, the positron cannon charged and fired,
     * the knife), "look" (a short one for the other Units: stand, look down at the seat, walk, strike), or "chat"
     * (lines of every source sent to the pilot on foot, during the cabin sequence, in the seat, in third person,
     * with the chat opened and on foot again: what the chat panel does with them and where the game's chat stays).
     */
    private static final String SCRIPT = System.getProperty("projectseele.cockpitReviewScriptR64", "drive");
    /** -Dprojectseele.cockpitReviewUnitR64: unit00, unit01 (the default), unit02, un0 or un1. */
    private static final String UNIT = System.getProperty("projectseele.cockpitReviewUnitR64", "unit01");
    private static final boolean UN = UNIT.startsWith("un") && !UNIT.startsWith("unit");
    private static final int VARIANT = UNIT.endsWith("00") ? EvaUnit01Entity.UNIT_00 : UNIT.endsWith("02") ? EvaUnit01Entity.UNIT_02 : EvaUnit01Entity.UNIT_01;
    private static final String ARM = UN ? "seele dev motionlab un " + (UNIT.endsWith("1") ? 1 : 0) + " " : "seele dev motionlab weapon " + UNIT + " ";
    private static final int END = SCRIPT.equals("stances") ? 900 : SCRIPT.equals("look") ? 300 : SCRIPT.equals("chat") ? 660 : 1070;

    private static int wait, tick = -1, serverStart = -1, settledTicks, missing, frame, capturedTick = -1, lockedTicks, watchTicks;
    private static Vec3 settledAt;
    private static boolean finished, sprinting;
    private static BufferedWriter rows;
    private static Path directory;
    private static Entity camera;

    private PilotCockpitReviewR64() {}

    @SubscribeEvent
    public static void tick(TickEvent.ClientTickEvent event)
    {
        Minecraft mc = Minecraft.getInstance();
        if (!DRIVE && PLUG == null || finished || event.phase != TickEvent.Phase.END
                || mc.player == null || mc.level == null || mc.getSingleplayerServer() == null) return;
        String save = mc.getSingleplayerServer().getWorldPath(LevelResource.ROOT).normalize().getFileName().toString();
        if (PLUG != null)
        {
            if (!save.startsWith("SEELE_LAUNCH_REVIEW")) { finished = true; ProjectSeele.LOGGER.error("Plug watch requires a disposable SEELE_LAUNCH_REVIEW save"); return; }
            plugWatch(mc);
            return;
        }
        if (!save.startsWith("SEELE_EVA_CONNECTED_REVIEW")) { finished = true; ProjectSeele.LOGGER.error("Cockpit review requires a disposable SEELE_EVA_CONNECTED_REVIEW save"); return; }
        mc.options.pauseOnLostFocus = false;
        if (++wait < 100) return;
        var link = mc.player.connection;
        if (wait == 100)
        {
            // As the connected review does: every unit into the arena, the lab reset, Unit-01 boarded with bare hands;
            // and the movement and combat R64 ships with.
            for (String type : new String[]{"eva_unit00", "eva_unit01", "eva_unit02", "eva_prototype"})
                link.sendCommand("execute as @e[type=projectseele:" + type + "] run tp @s 0 -40 0");
            link.sendCommand("seele motion planted");
            link.sendCommand("seele combat frames");
            link.sendCommand("seele dev motionlab reset");
            if (UN) link.sendCommand("seele dev motionlab un " + (UNIT.endsWith("1") ? 1 : 0));
            else
            {
                link.sendCommand("seele dev motionlab demo " + UNIT + " stop");
                link.sendCommand("seele dev motionlab enter " + UNIT);
                link.sendCommand(ARM + "fists");
            }
            link.sendCommand("time set 6000");
            link.sendCommand("weather clear");
            return;
        }
        EvaUnit01Entity eva = EvaPilotResolver.controlTarget(mc.player);
        if (serverStart < 0)
        {
            if (eva == null || eva.getActivationTicks() > 0 || !eva.isPoweredOn()
                    || (UN ? !eva.isExperimentalUnit() : eva.isExperimentalUnit() || eva.getUnitVariant() != VARIANT))
            {
                if (++missing > 400) finish(mc, "pilot_setup_timeout");
                return;
            }
            // The lab reset carries the unit back to its pad over a second or two.
            if (settledAt == null || eva.position().distanceToSqr(settledAt) > .0001) { settledAt = eva.position(); settledTicks = 0; return; }
            if (++settledTicks < 20) return;
            // The setup's own lines of chat are gone after ten seconds: the drive starts on a clear picture.
            if (wait < 330) return;
            serverStart = mc.getSingleplayerServer().getTickCount();
            open(mc);
            ProjectSeele.LOGGER.info("Cockpit review started: batch={} script={} unit={} cockpit={}", BATCH, SCRIPT, UNIT, com.projectseele.client.cockpit.PilotCockpitR64.ON);
        }
        int previous = tick;
        tick = mc.getSingleplayerServer().getTickCount() - serverStart;
        mc.options.hideGui = false;
        mc.options.setCameraType(CameraType.FIRST_PERSON);
        if (mc.getCameraEntity() != mc.player) mc.setCameraEntity(mc.player);
        if (SCRIPT.equals("stances")) stances(mc, eva, previous);
        else if (SCRIPT.equals("look")) look(mc, eva, previous);
        else if (SCRIPT.equals("chat")) chat(mc, eva, previous);
        else drive(mc, eva, previous);
        if (tick >= END) finish(mc, "complete");
    }

    private static void walk(Minecraft mc, boolean move)
    {
        mc.options.keyUp.setDown(move);
        mc.player.input.up = move; mc.player.input.forwardImpulse = move ? 1 : 0; mc.player.zza = move ? 1 : 0; mc.player.xxa = 0;
    }

    /** The stances and the weapons, each long enough to be measured and seen. */
    private static void stances(Minecraft mc, EvaUnit01Entity eva, int previous)
    {
        int t = tick;
        if (eva == null) return;
        var link = mc.player.connection;
        walk(mc, t >= 40 && t < 100 || t >= 200 && t < 290 || t >= 430 && t < 490);
        mc.player.setYRot(t >= 180 && t < 420 ? 180 : 0); mc.player.setXRot(0);
        if (at(previous, 20)) send(ServerboundEvaControlPacket.ACTION_CROUCH_START);
        if (at(previous, 110)) send(ServerboundEvaControlPacket.ACTION_CROUCH_STOP);
        if (at(previous, 140) || at(previous, 300)) send(ServerboundEvaControlPacket.ACTION_TOGGLE_PRONE);
        if (at(previous, 400)) link.sendCommand(ARM + "rifle");
        // The sight is the use key held, the shots the attack key: as a pilot's own hands do it.
        boolean sight = t >= 500 && t < 570, charge = t >= 640 && t < 730;
        mc.options.keyUse.setDown(sight || charge || t >= 830 && t < 836);
        if (t >= 520 && t < 550 && previous / 4 != t / 4) send(ServerboundEvaControlPacket.ACTION_RIFLE_FIRE);
        mc.options.keyAttack.setDown(t >= 520 && t < 550 || t >= 790 && t < 794 || t >= 805 && t < 809);
        if (at(previous, 600)) link.sendCommand(ARM + "cannon");
        if (at(previous, 640)) send(ServerboundEvaControlPacket.ACTION_CHARGE_START);
        if (at(previous, 730)) send(ServerboundEvaControlPacket.ACTION_CHARGE_STOP);
        if (at(previous, 760)) link.sendCommand(ARM + "knife");
        if (at(previous, 790) || at(previous, 805)) send(ServerboundEvaControlPacket.ACTION_MELEE);
        if (at(previous, 830)) send(ServerboundEvaControlPacket.ACTION_SMASH);
        if (previous / 20 != t / 20)
            ProjectSeele.LOGGER.info("Cockpit review: tick {} {} weapon {} crouching {} prone {} sight {} scope {}", t, part(t), eva.getWeapon(), eva.isPilotCrouching(), eva.isPilotProne(),
                    com.projectseele.client.ClientForgeEvents.isRifleSightActive(eva), com.projectseele.client.ClientForgeEvents.isCannonScopeActive(eva));
    }

    /** The other Units' seats: a stand, a look down at the yokes and knees, a walk, two blows. */
    private static void look(Minecraft mc, EvaUnit01Entity eva, int previous)
    {
        int t = tick;
        if (eva == null) return;
        walk(mc, t >= 110 && t < 190);
        mc.player.setYRot(0);
        mc.player.setXRot(t >= 30 && t < 100 ? 55 * Mth.clamp(Math.min(t - 30, 100 - t) / 14F, 0, 1) : 0);
        if (at(previous, 210) || at(previous, 226)) send(ServerboundEvaControlPacket.ACTION_MELEE);
        mc.options.keyAttack.setDown(t >= 210 && t < 214 || t >= 226 && t < 230);
        if (at(previous, 250)) send(ServerboundEvaControlPacket.ACTION_SMASH);
        mc.options.keyUse.setDown(t >= 250 && t < 256);
        // A UN unit has its own display: where the chat panel stands beside it.
        if (UN && at(previous, 120)) speak(mc.getSingleplayerServer(), mc.player.getUUID(), "葛城美里 · 作战通信", "目标就在前方。先站稳，注意它两侧的手臂。");
        if (UN && at(previous, 135)) tell(mc.getSingleplayerServer(), mc.player.getUUID(), "[UN 运输管制 · 00] 运输机已到达接应点。");
    }

    /**
     * The chat panel's pictures. Every line goes the way the mod's own lines go (the server sends it to the
     * player), in the words of lines the code has; the status and launch replies are the commands' own.
     */
    private static void chat(Minecraft mc, EvaUnit01Entity eva, int previous)
    {
        int t = tick;
        var server = mc.getSingleplayerServer();
        var id = mc.player.getUUID();
        var link = mc.player.connection;
        mc.player.setYRot(0); mc.player.setXRot(0);
        // On foot beside the Unit: the game's chat as it is outside the plug.
        if (at(previous, 10) || at(previous, 550)) server.execute(() ->
        {
            var pilot = server.getPlayerList().getPlayer(id);
            if (pilot != null) pilot.stopRiding();
        });
        if (at(previous, 40) || at(previous, 580)) link.sendCommand("seele eva status unit01");
        if (at(previous, 50) || at(previous, 590)) speak(server, id, "葛城美里 · 作战通信", "目标就在前方。先站稳，注意它两侧的手臂。");
        if (at(previous, 60) || at(previous, 600)) tell(server, id, "[NERV 运输管制] 运输机已到达接应点。");
        // Into the seat with the whole cabin sequence: the lines come while the LCL rises.
        if (at(previous, 110) && eva == null) server.execute(() ->
        {
            var pilot = server.getPlayerList().getPlayer(id);
            if (pilot == null) return;
            var units = pilot.serverLevel().getEntitiesOfClass(EvaUnit01Entity.class, pilot.getBoundingBox().inflate(160),
                    unit -> !unit.isExperimentalUnit() && unit.getUnitVariant() == EvaUnit01Entity.UNIT_01);
            ProjectSeele.LOGGER.info("Cockpit review: boarded with the whole sequence: {}", !units.isEmpty() && units.get(0).boardFromExternalPlug(pilot, 0));
        });
        if (at(previous, 124)) link.sendCommand("seele eva status unit01");
        if (at(previous, 132)) tell(server, id, "[NERV 运输管制] 运输机已到达接应点。");
        if (at(previous, 142)) speak(server, id, "赤木律子 · 机体监视", "同步率稳定。LCL 电荷正常。");
        if (at(previous, 152)) link.sendChat("收到，准备出击");
        // In the seat: the same reply three times over, a long line, a name written short, a line that is not a name.
        if (at(previous, 290) || at(previous, 300) || at(previous, 310)) link.sendCommand("seele eva launch unit01");
        if (at(previous, 320) || at(previous, 335)) link.sendCommand("seele eva status unit01");
        if (at(previous, 345)) speak(server, id, "葛城美里 · 作战通信", "目标已确认消失。先别急着动，检查供电和机体状态，我们准备接你回来。");
        if (at(previous, 360)) tell(server, id, "律子：主电源切断。初号机停止活动。");
        if (at(previous, 375)) tell(server, id, "作战命令：驾驶初号机前往第三新东京市。目标区域 X 120 / Z -40");
        if (at(previous, 390)) link.sendChat("了解");
        // A player writing in the command post's hand: it stays the player's line.
        if (at(previous, 402)) link.sendChat("「葛城美里 · 作战通信」 全员撤退");
        // Third person: the game's chat again. Then the chat opened from the seat: its history, whole.
        if (t >= 420 && t < 470) mc.options.setCameraType(CameraType.THIRD_PERSON_BACK);
        if (at(previous, 430)) speak(server, id, "赤木律子 · 机体监视", "外部摄像确认，机体姿态正常。");
        if (at(previous, 480)) mc.setScreen(new net.minecraft.client.gui.screens.ChatScreen(""));
        if (at(previous, 530) && mc.screen instanceof net.minecraft.client.gui.screens.ChatScreen) mc.setScreen(null);
        if (previous / 20 != t / 20)
            ProjectSeele.LOGGER.info("Cockpit review: tick {} {} riding {} panel {}", t, part(t),
                    mc.player.getVehicle() == null ? "nothing" : mc.player.getVehicle().getType().toShortString(),
                    com.projectseele.client.cockpit.PilotChatPanelR64.active(mc));
    }

    /** A line of the staff's, as NervStaffDialogue sends them. */
    private static void speak(net.minecraft.server.MinecraftServer server, java.util.UUID id, String speaker, String line)
    {
        server.execute(() ->
        {
            var pilot = server.getPlayerList().getPlayer(id);
            if (pilot != null) com.projectseele.world.NervStaffDialogue.say(pilot, speaker, line);
        });
    }

    /** A plain system message to the pilot, as the control rooms and the Units send them. */
    private static void tell(net.minecraft.server.MinecraftServer server, java.util.UUID id, String line)
    {
        server.execute(() ->
        {
            var pilot = server.getPlayerList().getPlayer(id);
            if (pilot != null) pilot.sendSystemMessage(net.minecraft.network.chat.Component.literal(line));
        });
    }

    /** What the server answers over the hotbar during a plug watch goes into the log: the pictures are four ticks apart. */
    @SubscribeEvent
    public static void answered(net.minecraftforge.client.event.ClientChatReceivedEvent.System event)
    {
        if (PLUG != null && !finished && event.isOverlay()) ProjectSeele.LOGGER.info("Plug watch: over the hotbar: {}", event.getMessage().getString());
    }

    private static boolean at(int previous, int wanted)
    {
        return previous < wanted && tick >= wanted;
    }

    /** The part of the drive a tick belongs to: view.csv carries it, the metrics are taken part by part. */
    private static String part(int t)
    {
        if (SCRIPT.equals("stances"))
            return t < 40 ? "crouch" : t < 100 ? "crouchwalk" : t < 140 ? "stand" : t < 200 ? "prone" : t < 290 ? "crawl" : t < 400 ? "rise"
                    : t < 430 ? "stand" : t < 490 ? "riflewalk" : t < 500 ? "stand" : t < 570 ? "sight" : t < 640 ? "stand" : t < 730 ? "cannon"
                    : t < 790 ? "stand" : "knife";
        if (SCRIPT.equals("look")) return t < 30 ? "idle" : t < 100 ? "down" : t < 110 ? "stand" : t < 190 ? "walk" : "strike";
        if (SCRIPT.equals("chat")) return t < 110 ? "foot" : t < 250 ? "board" : t < 420 ? "seat" : t < 470 ? "third" : t < 530 ? "typing" : t < 550 ? "seat" : "foot";
        return t < 40 ? "idle" : t < 110 ? "leave" : t < 250 ? "board" : t < 260 ? "stand" : t < 390 ? "walk" : t < 430 ? "stand"
                : t < 540 ? "run" : t < 585 ? "stand" : t < 700 ? "strike" : t < 705 ? "stand" : t < 795 ? "jump" : t < 800 ? "stand"
                : t < 865 ? "look" : t < 945 ? "down" : t < 950 ? "stand" : "exit";
    }

    private static void drive(Minecraft mc, EvaUnit01Entity eva, int previous)
    {
        int t = tick;
        var server = mc.getSingleplayerServer();
        var id = mc.player.getUUID();
        // Out of the seat, and in again with the whole cabin sequence (the lab's own boarding skips it).
        if (at(previous, 40)) server.execute(() ->
        {
            var pilot = server.getPlayerList().getPlayer(id);
            if (pilot != null) pilot.stopRiding();
        });
        if (at(previous, 110) && eva == null)
        {
            server.execute(() ->
            {
                var pilot = server.getPlayerList().getPlayer(id);
                if (pilot == null) return;
                var units = pilot.serverLevel().getEntitiesOfClass(EvaUnit01Entity.class, pilot.getBoundingBox().inflate(160),
                        unit -> !unit.isExperimentalUnit() && unit.getUnitVariant() == EvaUnit01Entity.UNIT_01);
                boolean boarded = !units.isEmpty() && units.get(0).boardFromExternalPlug(pilot, 0);
                ProjectSeele.LOGGER.info("Cockpit review: boarded with the whole sequence: {}", boarded);
            });
        }
        boolean walk = t >= 260 && t < 390 || t >= 800 && t < 860, run = t >= 430 && t < 540, move = (walk || run) && eva != null;
        mc.options.keyUp.setDown(move);
        mc.player.input.up = move; mc.player.input.forwardImpulse = move ? 1 : 0; mc.player.zza = move ? 1 : 0; mc.player.xxa = 0;
        mc.options.keySprint.setDown(run);
        if (run && !sprinting && eva != null) { send(ServerboundEvaControlPacket.ACTION_SPRINT_START); sprinting = true; }
        if (!run && sprinting) { send(ServerboundEvaControlPacket.ACTION_SPRINT_STOP); sprinting = false; }
        // Back the way it came for the run, so that the drive stays on the lab's lane; a look to the side and down
        // at a walk; a look at the seat standing.
        float yaw = t >= 400 && t < 560 ? 180 : 0, pitch = 0;
        if (t >= 800 && t < 860) { float sweep = Mth.sin((t - 800) / 60F * Mth.PI); yaw = 50 * sweep; pitch = 25 * sweep; }
        if (t >= 870 && t < 940) pitch = 55 * Mth.clamp(Math.min(t - 870, 940 - t) / 14F, 0, 1);
        mc.player.setYRot(yaw); mc.player.setXRot(pitch);
        if (eva != null)
        {
            if (at(previous, 590) || at(previous, 604) || at(previous, 618)) send(ServerboundEvaControlPacket.ACTION_MELEE);
            if (at(previous, 650)) send(ServerboundEvaControlPacket.ACTION_SMASH);
            // The keys the hands follow are held as a pilot holds them.
            mc.options.keyAttack.setDown(t >= 590 && t < 594 || t >= 604 && t < 608 || t >= 618 && t < 622);
            mc.options.keyUse.setDown(t >= 650 && t < 656);
            mc.options.keyJump.setDown(t >= 710 && t < 714);
            if (at(previous, 950)) send(ServerboundEvaControlPacket.ACTION_EXIT);
        }
        // Whatever the exit did (a capsule thrown clear in the field, or refused in the lab): out of the seat by the end.
        if (at(previous, 1010) && mc.player.isPassenger()) server.execute(() ->
        {
            var pilot = server.getPlayerList().getPlayer(id);
            if (pilot != null) pilot.stopRiding();
        });
        if (previous / 20 != t / 20)
            ProjectSeele.LOGGER.info("Cockpit review: tick {} {} riding {} lcl {} level {}", t, part(t),
                    mc.player.getVehicle() == null ? "nothing" : mc.player.getVehicle().getType().toShortString(),
                    String.format(Locale.ROOT, "%.2f", com.projectseele.client.cockpit.PilotLclR64.fill()),
                    String.format(Locale.ROOT, "%.2f", com.projectseele.client.cockpit.PilotLclR64.level()));
    }

    private static void send(int action)
    {
        SeeleNetwork.CHANNEL.sendToServer(new ServerboundEvaControlPacket(action));
    }

    private static void open(Minecraft mc)
    {
        try
        {
            directory = mc.gameDirectory.toPath().resolve("screenshots/projectseele_cockpit/" + BATCH);
            Files.createDirectories(directory);
            if (DRIVE)
            {
                rows = Files.newBufferedWriter(directory.resolve("view.csv"), StandardCharsets.UTF_8);
                rows.write("nanos,tick,partial,part,cam_x,cam_y,cam_z,head_x,head_y,head_z,unit_x,unit_y,unit_z,body_yaw,yaw,pitch,roll,piloting\n");
            }
        }
        catch (Exception exception)
        {
            throw new IllegalStateException("cockpit review output", exception);
        }
    }

    /** Last of all the handlers: the angles are what the frame is drawn with. */
    @SubscribeEvent(priority = EventPriority.LOWEST)
    public static void camera(ViewportEvent.ComputeCameraAngles event)
    {
        if (!DRIVE || rows == null || finished || tick < 0) return;
        Minecraft mc = Minecraft.getInstance();
        if (mc.player == null) return;
        float partial = (float) event.getPartialTick();
        EvaUnit01Entity eva = EvaPilotResolver.controlTarget(mc.player);
        Vec3 cam = event.getCamera().getPosition();
        // The head's optical point as the camera was given it this frame; on foot, the camera itself.
        Vec3 head = eva == null ? cam : PilotViewSteadyR64.raw(), unit = eva == null ? mc.player.getPosition(partial) : eva.getPosition(partial);
        float bodyYaw = eva == null ? 0 : Mth.rotLerp(partial, eva.yBodyRotO, eva.yBodyRot);
        try
        {
            rows.write(String.format(Locale.ROOT, "%d,%d,%.3f,%s,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.3f,%.4f,%.4f,%.4f,%d%n",
                    System.nanoTime(), tick, partial, part(tick), cam.x, cam.y, cam.z, head.x, head.y, head.z, unit.x, unit.y, unit.z,
                    bodyYaw, event.getYaw(), event.getPitch(), event.getRoll(), eva == null ? 0 : 1));
        }
        catch (Exception exception)
        {
            throw new IllegalStateException("cockpit review row", exception);
        }
    }

    @SubscribeEvent
    public static void render(TickEvent.RenderTickEvent event)
    {
        if (finished || directory == null || event.phase != TickEvent.Phase.END) return;
        Minecraft mc = Minecraft.getInstance();
        if (DRIVE)
        {
            if (tick < 0 || tick == capturedTick || "false".equals(System.getProperty("projectseele.cockpitCaptureR64"))) return;
            capturedTick = tick;
            // Named by its tick: two drives are laid side by side tick for tick, whatever frames either dropped.
            frame++;
            Screenshot.grab(mc.gameDirectory, "projectseele_cockpit/" + BATCH + String.format("/frame_%04d.png", tick), mc.getMainRenderTarget(), ignored -> {});
            return;
        }
        else
        {
            // The plug watch: a picture every fourth tick while the pilot rides the capsule, and for ten seconds after leaving it.
            if (watchTicks == capturedTick || watchTicks % 4 != 0 || mc.player == null
                    || !(mc.player.getVehicle() instanceof EntryPlugCarrierEntity) && (offTicks <= 0 || offTicks >= 200)) return;
            capturedTick = watchTicks;
        }
        frame++;
        Screenshot.grab(mc.gameDirectory, "projectseele_cockpit/" + BATCH + String.format("/frame_%04d.png", frame), mc.getMainRenderTarget(), ignored -> {});
    }

    private static void plugWatch(Minecraft mc)
    {
        if (!(mc.player.getVehicle() instanceof EntryPlugCarrierEntity plug))
        {
            if (camera != null && mc.getCameraEntity() == camera) mc.setCameraEntity(mc.player);
            // Out of the capsule (thrown clear and left, or climbed out): the watch runs on for ten seconds, for
            // the LCL's going from the pilot's own view.
            if (directory != null && offTicks < 200) { offTicks++; watchTicks++; mc.options.hideGui = false; mc.options.setCameraType(CameraType.FIRST_PERSON); }
            if (exitSent && ++afterTicks >= 260) finish(mc, "capsule_thrown_clear");
            if (leaveAsked) { mc.options.keyShift.setDown(false); if (offTicks >= 200) finish(mc, "pilot_left_capsule"); }
            // Out of the plug the chat is the game's own again, and the status line is whole in it.
            if (PLUG_CHAT && offTicks == 40) mc.player.connection.sendCommand("seele eva status unit01");
            if (PLUG_CHAT && offTicks == 50) speak(mc.getSingleplayerServer(), mc.player.getUUID(), "赤木律子 · 回收联络", "机体已回到湿舱，驾驶员已离栓。后续出击请重新下达指令。");
            return;
        }
        offTicks = 0;
        if (directory == null) { open(mc); ProjectSeele.LOGGER.info("Plug watch started: batch={} view={} cockpit={}", BATCH, PLUG, com.projectseele.client.cockpit.PilotCockpitR64.ON); }
        watchTicks++;
        boolean locked = plug.isLockedToEva();
        lockedTicks = locked ? lockedTicks + 1 : 0;
        if (watchTicks % 20 == 0)
            ProjectSeele.LOGGER.info("Plug watch: tick {} stage {} cabin {} progress {} locked {} lcl {}", watchTicks, plug.getInsertionStage(), plug.getCabinStage(),
                    plug.getCabinProgress(), locked, String.format(Locale.ROOT, "%.2f", com.projectseele.client.cockpit.PilotLclR64.fill()));
        mc.options.setCameraType(CameraType.FIRST_PERSON);
        if (("outside".equals(PLUG) || "cabin".equals(PLUG)) && !locked && plug.hasCanonicalPose())
        {
            // Beside and below the capsule for two seconds, beside and above it for two: whatever of the pilot
            // came through the shell showed from below (the feet) or from above (the head).
            if (camera == null)
            {
                camera = EntityType.ARMOR_STAND.create(mc.level);
                if (camera == null) throw new IllegalStateException("plug watch camera");
                camera.setInvisible(true); camera.setNoGravity(true);
            }
            var pose = plug.getInterpolatedCanonicalTransform(1);
            boolean below = watchTicks / 40 % 2 == 0;
            Vec3 seat = EntryPlugKinematics.PILOT_SEAT_P;
            Vec3 target = pose.transformPoint(seat.add(0, 0, -.5));
            Vec3 position = pose.transformPoint(seat.add(below ? -3.6 : 3.6, below ? -2.4 : 2.6, -1.6));
            if ("cabin".equals(PLUG))
            {
                // Inside the cabin, before the pilot's feet, looking back along the seat: how the pilot lies in it.
                Vec3 eye = EntryPlugKinematics.PILOT_EYE_P;
                target = pose.transformPoint(eye.add(0, -.25, -.55));
                position = pose.transformPoint(eye.add(below ? .42 : -.42, .30, -2.75));
            }
            Vec3 delta = target.subtract(position);
            camera.setPos(position.x, position.y - camera.getEyeHeight(), position.z);
            camera.setYRot((float) (Mth.atan2(delta.z, delta.x) * Mth.RAD_TO_DEG) - 90F);
            camera.setXRot((float) (-Mth.atan2(delta.y, delta.horizontalDistance()) * Mth.RAD_TO_DEG));
            camera.setYHeadRot(camera.getYRot());
            camera.xo = camera.xOld = camera.getX(); camera.yo = camera.yOld = camera.getY(); camera.zo = camera.zOld = camera.getZ();
            camera.yRotO = camera.getYRot(); camera.xRotO = camera.getXRot();
            mc.options.hideGui = true;
            mc.setCameraEntity(camera);
        }
        else
        {
            if (mc.getCameraEntity() != mc.player) mc.setCameraEntity(mc.player);
            mc.options.hideGui = false;
        }
        EvaUnit01Entity eva = plug.getLinkedEva();
        if (PLUG_CHAT && locked)
        {
            // While the LCL rises and after: a line of each source beside the sortie's own status lines.
            var server = mc.getSingleplayerServer();
            var id = mc.player.getUUID();
            if (lockedTicks == 14) speak(server, id, "赤木律子 · 机体监视", "插入栓固定。LCL 注入开始。");
            if (lockedTicks == 26) tell(server, id, "[NERV 运输管制] 发射线路已预留。");
            if (lockedTicks == 38) mc.player.connection.sendChat("收到，准备出击");
            if (lockedTicks == 200) speak(server, id, "葛城美里 · 作战通信", "目标就在前方。先站稳，注意它两侧的手臂。");
        }
        boolean free = locked && eva != null && !eva.isNervLogisticsLocked() && !eva.isLaunchSequenceActive() && eva.getActivationTicks() == 0 && eva.onGround();
        // On the ground with control back: the recovery asked for; the Unit is taken back down and the crane draws the capsule out.
        if (PLUG_RECOVER >= 0 && !recoverSent)
        {
            freeTicks = free ? freeTicks + 1 : 0;
            if (freeTicks >= PLUG_RECOVER)
            {
                recoverSent = true;
                mc.player.connection.sendCommand("seele eva recover unit0" + Mth.clamp(plug.getAssignedVariant(), 0, 2));
                ProjectSeele.LOGGER.info("Plug watch: recovery asked at tick {}", watchTicks);
            }
        }
        // The sortie called off in the cage, and what the pilot then does about it.
        if (PLUG_CANCEL >= 0 && locked && !cancelSent && lockedTicks == PLUG_CANCEL)
        {
            cancelSent = true;
            mc.player.connection.sendCommand("seele eva cancel unit0" + Mth.clamp(plug.getAssignedVariant(), 0, 2));
            ProjectSeele.LOGGER.info("Plug watch: sortie called off at tick {}", watchTicks);
        }
        if (cancelSent && locked && lockedTicks == PLUG_CANCEL + 40 && !"none".equals(PLUG_AFTER_CANCEL))
        {
            boolean abort = "abort".equals(PLUG_AFTER_CANCEL);
            SeeleNetwork.CHANNEL.sendToServer(new ServerboundEvaControlPacket(abort ? ServerboundEvaControlPacket.ACTION_CANCEL_LAUNCH : ServerboundEvaControlPacket.ACTION_EXIT));
            ProjectSeele.LOGGER.info("Plug watch: {} asked at tick {}", abort ? "abort" : "exit", watchTicks);
        }
        if (recoverSent || cancelSent && !"none".equals(PLUG_AFTER_CANCEL))
        {
            int stage = plug.getInsertionStage();
            if (stage != lastStage) ProjectSeele.LOGGER.info("Plug watch: capsule stage {} at tick {}", stage, watchTicks);
            lastStage = stage;
            boolean docked = !locked && (stage == EntryPlugCarrierEntity.STAGE_SUSPENDED || stage == EntryPlugCarrierEntity.STAGE_OCCUPIED || stage == EntryPlugCarrierEntity.STAGE_ABORT_DOCKED);
            afterTicks = docked ? afterTicks + 1 : 0;
            // Docked for long enough (the cage refills and the bridge comes back in that time): the pilot climbs out.
            if (afterTicks >= PLUG_AFTER_DOCK) { leaveAsked = true; mc.options.keyShift.setDown(true); }
            if (afterTicks >= PLUG_AFTER_DOCK + 200) { finish(mc, "capsule_drawn_out"); return; }
        }
        // On the ground with control back: the pilot's own exit, which throws the capsule clear in the field.
        if (PLUG_EXIT >= 0 && !exitSent)
        {
            freeTicks = free ? freeTicks + 1 : 0;
            if (freeTicks >= PLUG_EXIT)
            {
                exitSent = true;
                SeeleNetwork.CHANNEL.sendToServer(new ServerboundEvaControlPacket(ServerboundEvaControlPacket.ACTION_EXIT));
                ProjectSeele.LOGGER.info("Plug watch: exit asked at tick {}", watchTicks);
            }
        }
        else if (exitSent && ++afterTicks >= 260) { finish(mc, "capsule_thrown_clear"); return; }
        if (lockedTicks >= PLUG_END) finish(mc, "plug_locked");
        else if (watchTicks > 12000) finish(mc, "plug_watch_timeout");
    }

    private static void finish(Minecraft mc, String reason)
    {
        finished = true;
        mc.options.keyUp.setDown(false); mc.options.keySprint.setDown(false); mc.options.keyJump.setDown(false);
        mc.options.keyAttack.setDown(false); mc.options.keyUse.setDown(false); mc.options.keyShift.setDown(false);
        mc.setCameraEntity(mc.player);
        try
        {
            if (rows != null) rows.close();
        }
        catch (Exception exception)
        {
            ProjectSeele.LOGGER.error("Closing cockpit review", exception);
        }
        ProjectSeele.LOGGER.info("Cockpit review finished: batch={} reason={} ticks={} frames={}", BATCH, reason, Math.max(tick, watchTicks), frame);
        mc.stop();
    }
}
