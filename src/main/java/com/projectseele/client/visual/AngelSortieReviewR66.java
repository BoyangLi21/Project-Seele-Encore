package com.projectseele.client.visual;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.Angel;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.world.TvCampaignSavedData;
import com.projectseele.world.TvSortiesR32;
import net.minecraft.client.CameraType;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.decoration.ArmorStand;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
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
 * R66 review of an Angel operation from the sortie to the kill, in disposable saves only (the world folder name must
 * start with SEELE_LAUNCH_REVIEW). Nothing here changes the game: it types the operation's own commands and watches.
 * <p>
 * -Dprojectseele.angelReviewR66=&lt;chapter&gt; selects the operation and sends unit 1 (or the units listed in
 * -Dprojectseele.angelReviewUnitsR66, comma separated) as NPC sorties. A camera follows the unit until the Angel is
 * known, then frames both. Every drawn frame becomes a picture under screenshots/projectseele_angels/&lt;batch&gt;/ with
 * its game time in frames.csv, so a video can be laid out on game time; status.csv records the operation once a
 * second. The client stops a few seconds after the operation reports the target down, or at
 * -Dprojectseele.angelReviewTimeoutR66 ticks (default 24000), and the log says angel_review_finished reason=...
 */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class AngelSortieReviewR66
{
    private static final String CHAPTER = System.getProperty("projectseele.angelReviewR66");
    private static final boolean ENABLED = CHAPTER != null && !CHAPTER.isBlank();
    private static final String UNITS = System.getProperty("projectseele.angelReviewUnitsR66", "1");
    private static final int TIMEOUT = Integer.getInteger("projectseele.angelReviewTimeoutR66", 24000);
    private static final boolean CAPTURE = !Boolean.getBoolean("projectseele.angelReviewNoCaptureR66");
    private static final int CAPTURE_FROM = Integer.getInteger("projectseele.angelReviewCaptureFromR66", 0);

    private static int ticks, frame, doneAt = -1, warm, lastSparseTick = -1;
    private static boolean started, finished, close;
    private static ArmorStand camera;
    private static Path folder;
    private static BufferedWriter frames, status;
    private static String batch;
    private static Vec3 camPos, camAim;

    private AngelSortieReviewR66() {}

    @SubscribeEvent
    public static void tick(TickEvent.ClientTickEvent event)
    {
        if (!ENABLED || finished || event.phase != TickEvent.Phase.END) return;
        Minecraft mc = Minecraft.getInstance();
        if (mc.level == null || mc.player == null || mc.getSingleplayerServer() == null) return;
        Path world = mc.getSingleplayerServer().getWorldPath(LevelResource.ROOT).normalize();
        if (!world.getFileName().toString().startsWith("SEELE_LAUNCH_REVIEW"))
        {
            ProjectSeele.LOGGER.error("Angel review refuses a world that is not a disposable launch review: {}", world);
            finish(mc, "wrong_world");
            return;
        }
        if (!started)
        {
            if (++warm < 200) return;
            begin(mc);
            return;
        }
        ticks++;
        if (ticks == 20) command(mc, "seele sortie select " + CHAPTER);
        if (ticks >= 60 && ticks <= 60 + 40 * 4 && (ticks - 60) % 40 == 0)
        {
            String[] units = UNITS.split(",");
            int index = (ticks - 60) / 40;
            if (index < units.length) command(mc, "seele sortie support " + units[index].trim() + " npc");
        }
        if (ticks % 200 == 100) command(mc, "seele sortie status");

        var server = mc.getSingleplayerServer();
        ServerLevel level = campaignLevel(server);
        if (level == null) return;
        var data = TvCampaignSavedData.get(level);
        EvaUnit01Entity unit = null;
        for (var sortie : data.sorties.values())
        {
            var e = TvSortiesR32.unit(level, sortie.unit);
            if (e != null) { unit = e; break; }
        }
        LivingEntity angel = data.angel != null && level.getEntity(data.angel) instanceof LivingEntity a ? a : null;
        frameShot(mc, unit, angel);
        boolean near = unit != null && angel != null && unit.distanceToSqr(angel) < 160 * 160;
        if (near && !close) ProjectSeele.LOGGER.info("angel_review contact at tick {}: every frame from here", ticks);
        close |= near || data.phase.equals("combat");
        // keep the watched area loaded: the spectating player rides along with the camera
        if (ticks % 40 == 0 && camPos != null)
        {
            Vec3 at = camPos;
            server.execute(() -> {
                var player = server.getPlayerList().getPlayers().isEmpty() ? null : server.getPlayerList().getPlayers().get(0);
                if (player != null && player.level() == level) player.teleportTo(level, at.x, at.y, at.z, player.getYRot(), player.getXRot());
            });
        }
        if (ticks % 20 == 0) writeStatus(level, data, unit, angel);
        boolean down = data.phase.equals("combat_victory") || data.phase.equals("episode_archived") || data.targetDeathConfirmedR45;
        if (down && doneAt < 0)
        {
            doneAt = ticks;
            ProjectSeele.LOGGER.info("angel_review target down at tick {} phase {}", ticks, data.phase);
        }
        if (data.phase.equals("failure") && doneAt < 0)
        {
            ProjectSeele.LOGGER.info("angel_review operation failed at tick {}: {}", ticks, data.notice);
            finish(mc, "failure");
            return;
        }
        if (doneAt >= 0 && ticks >= doneAt + 120) finish(mc, "complete");
        else if (ticks > TIMEOUT) finish(mc, "timeout");
    }

    /** Runs a command as the watching player, on the server thread, with operator rights. */
    private static void command(Minecraft mc, String text)
    {
        var server = mc.getSingleplayerServer();
        server.execute(() -> {
            var player = server.getPlayerList().getPlayers().get(0);
            ProjectSeele.LOGGER.info("angel_review command /{}", text);
            server.getCommands().performPrefixedCommand(player.createCommandSourceStack().withPermission(4), text);
        });
    }

    private static ServerLevel campaignLevel(net.minecraft.server.MinecraftServer server)
    {
        for (var level : server.getAllLevels())
        {
            var data = TvCampaignSavedData.get(level);
            if (!data.active.isEmpty()) return level;
        }
        return null;
    }

    private static void begin(Minecraft mc)
    {
        started = true;
        batch = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss")) + "_" + CHAPTER;
        folder = mc.gameDirectory.toPath().resolve("screenshots/projectseele_angels/" + batch);
        try
        {
            Files.createDirectories(folder);
            frames = Files.newBufferedWriter(folder.resolve("frames.csv"), StandardCharsets.UTF_8);
            frames.write("frame,review_tick,game_time,partial\n");
            status = Files.newBufferedWriter(folder.resolve("status.csv"), StandardCharsets.UTF_8);
            status.write("review_tick,phase,unit_health,unit_power,angel,angel_health,angel_field,notice\n");
        }
        catch (Exception error) { throw new IllegalStateException("angel review folder", error); }
        mc.options.pauseOnLostFocus = false;
        mc.options.hideGui = true;
        // the watcher is an operator in creative, invisible: it can order sorties and nothing aims at it
        var server = mc.getSingleplayerServer();
        server.execute(() -> {
            var player = server.getPlayerList().getPlayers().get(0);
            server.getPlayerList().op(player.getGameProfile());
            // NPC sorties are ordered from inside the operation's own dimension
            var operation = com.projectseele.event.TvCampaignDirector.level(player);
            if (operation != null && player.level() != operation)
            {
                var spawn = operation.getSharedSpawnPos();
                player.teleportTo(operation, spawn.getX() + .5, spawn.getY() + 2, spawn.getZ() + .5, 0, 0);
            }
            ProjectSeele.LOGGER.info("angel_review watcher in {} at {}", player.level().dimension().location(), player.blockPosition());
            player.setGameMode(net.minecraft.world.level.GameType.CREATIVE);
            player.getAbilities().flying = true;
            player.onUpdateAbilities();
            player.addEffect(new net.minecraft.world.effect.MobEffectInstance(net.minecraft.world.effect.MobEffects.INVISIBILITY, 1000000, 0, false, false));
        });
        command(mc, "time set 6000");
        command(mc, "weather clear");
        ProjectSeele.LOGGER.info("angel_review started chapter={} units={} batch={}", CHAPTER, UNITS, batch);
    }

    /** Frames the unit alone, or the unit and the Angel together, from the unit's side, a little above. */
    private static void frameShot(Minecraft mc, EvaUnit01Entity unit, LivingEntity angel)
    {
        Entity subject = unit != null ? unit : angel;
        if (subject == null) return;
        if (camera == null)
        {
            camera = EntityType.ARMOR_STAND.create(mc.level);
            if (camera == null) return;
            camera.setInvisible(true);
            camera.setNoGravity(true);
        }
        Vec3 aim, pos;
        if (unit != null && angel != null && unit.distanceToSqr(angel) < 600 * 600)
        {
            Vec3 a = unit.position().add(0, 30, 0), b = angel.position().add(0, angel.getBbHeight() * .5, 0);
            aim = a.lerp(b, .5);
            Vec3 across = b.subtract(a).multiply(1, 0, 1);
            if (across.lengthSqr() < 1e-4) across = new Vec3(1, 0, 0);
            Vec3 side = new Vec3(-across.z, 0, across.x).normalize();
            double reach = Math.max(110, a.distanceTo(b) * 1.15);
            pos = aim.add(side.scale(reach)).add(0, reach * .32, 0);
        }
        else
        {
            aim = subject.position().add(0, 30, 0);
            float yaw = subject.getYRot() * Mth.DEG_TO_RAD;
            pos = aim.add(Math.cos(yaw) * 100, 40, Math.sin(yaw) * 100);
        }
        // ease the camera so cuts between the two framings do not jump
        camPos = camPos == null ? pos : camPos.lerp(pos, .06);
        camAim = camAim == null ? aim : camAim.lerp(aim, .12);
        Vec3 d = camAim.subtract(camPos);
        camera.setPos(camPos.x, camPos.y - camera.getEyeHeight(), camPos.z);
        camera.setYRot((float) (Mth.atan2(d.z, d.x) * Mth.RAD_TO_DEG) - 90.0F);
        camera.setXRot((float) (-Mth.atan2(d.y, d.horizontalDistance()) * Mth.RAD_TO_DEG));
        camera.yRotO = camera.getYRot();
        camera.xRotO = camera.getXRot();
        camera.xo = camera.getX(); camera.yo = camera.getY(); camera.zo = camera.getZ();
        camera.xOld = camera.getX(); camera.yOld = camera.getY(); camera.zOld = camera.getZ();
        if (mc.getCameraEntity() != camera) mc.setCameraEntity(camera);
        mc.options.setCameraType(CameraType.FIRST_PERSON);
    }

    @SubscribeEvent
    public static void render(TickEvent.RenderTickEvent event)
    {
        if (!ENABLED || !CAPTURE || finished || !started || event.phase != TickEvent.Phase.END || camera == null) return;
        if (ticks < CAPTURE_FROM) return;
        Minecraft mc = Minecraft.getInstance();
        if (mc.level == null || mc.getCameraEntity() != camera) return;
        // the approach is kept as a time-lapse (one picture a second); the fight from first contact, every frame
        if (!close)
        {
            if (ticks == lastSparseTick || ticks % 20 != 0) return;
            lastSparseTick = ticks;
        }
        frame++;
        Screenshot.grab(mc.gameDirectory, "projectseele_angels/" + batch + String.format(Locale.ROOT, "/frame_%06d.png", frame),
                mc.getMainRenderTarget(), ignored -> {});
        try
        {
            frames.write(frame + "," + ticks + "," + mc.level.getGameTime() + "," + String.format(Locale.ROOT, "%.4f", event.renderTickTime) + "\n");
        }
        catch (Exception ignored) {}
    }

    private static void writeStatus(ServerLevel level, TvCampaignSavedData data, EvaUnit01Entity unit, LivingEntity angel)
    {
        try
        {
            String unitHealth = unit == null ? "" : String.format(Locale.ROOT, "%.1f", unit.getHealth());
            String power = unit == null ? "" : unit.isUmbilicalConnected() ? "cable" : String.valueOf(unit.getPowerTicks());
            String angelName = angel == null ? "" : angel.getType().toShortString();
            String angelHealth = angel == null ? "" : String.format(Locale.ROOT, "%.1f", angel.getHealth());
            String field = angel instanceof Angel a ? String.format(Locale.ROOT, "%.1f", a.getAtField()) : "";
            status.write(ticks + "," + data.phase + "," + unitHealth + "," + power + "," + angelName + "," + angelHealth + "," + field + ","
                    + data.notice.replace(',', ';').replace('\n', ' ') + "\n");
            status.flush();
            if (ticks % 200 == 0)
                ProjectSeele.LOGGER.info("angel_review tick {} phase {} unit {} power {} angel {} health {} field {}",
                        ticks, data.phase, unitHealth, power, angelName, angelHealth, field);
        }
        catch (Exception ignored) {}
    }

    private static void finish(Minecraft mc, String reason)
    {
        finished = true;
        try
        {
            if (frames != null) frames.close();
            if (status != null) status.close();
        }
        catch (Exception ignored) {}
        ProjectSeele.LOGGER.info("angel_review_finished reason={} ticks={} frames={} batch={}", reason, ticks, frame, batch);
        mc.setCameraEntity(mc.player);
        mc.stop();
    }
}
