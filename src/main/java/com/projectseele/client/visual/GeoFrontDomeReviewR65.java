package com.projectseele.client.visual;

import com.projectseele.ProjectSeele;
import com.projectseele.config.SeeleConfig;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;
import net.minecraft.world.level.GameType;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/**
 * R65 review of the GeoFront far view, in disposable saves only. -Dprojectseele.domeReviewR65=x,y,z,yaw,pitch[,dimension[,field]];... (or @command,yaw,pitch) names
 * the places. The watcher (an operator, in spectator) goes to each place in turn and waits for the chunks and the far
 * view to load; first every place is seen as before (the baked silhouette off, Distant Horizons as it was), then every
 * place again with the silhouette on, so the mesh is not loaded while the before figures are taken. At each place and
 * state: the frame rate averaged over ten seconds, then a screenshot under screenshots/projectseele_dome/ (named
 * place, state and time). The log says dome_review ... for each; an outside sampler reads the private memory against
 * those lines. The client stops at the end.
 */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class GeoFrontDomeReviewR65
{
    private static final String PLACES = System.getProperty("projectseele.domeReviewR65");
    private static final boolean ENABLED = PLACES != null && !PLACES.isBlank();
    private static final int SETTLE = Integer.getInteger("projectseele.domeReviewSettleR65", 1800);
    private static final int MEASURE = 200, SWITCH = 200;

    /** A place by coordinates, or by a server command run as the watcher (command set: x, y, z unused). */
    private record Place(double x, double y, double z, float yaw, float pitch, String dimension, boolean field, String command) {}
    private static final List<Place> list = new ArrayList<>();
    private static int warm, step, ticks, fpsSum, fpsCount;
    private static boolean finished;
    private static String batch;

    private GeoFrontDomeReviewR65() {}

    @SubscribeEvent
    public static void tick(TickEvent.ClientTickEvent event)
    {
        if (!ENABLED || finished || event.phase != TickEvent.Phase.END) return;
        Minecraft mc = Minecraft.getInstance();
        var server = mc.getSingleplayerServer();
        if (mc.level == null || mc.player == null || server == null) return;
        String world = server.getWorldPath(net.minecraft.world.level.storage.LevelResource.ROOT).normalize().getFileName().toString();
        if (!world.startsWith("SEELE_DOME_REVIEW") && !world.startsWith("SEELE_LAUNCH_REVIEW"))
        {
            ProjectSeele.LOGGER.error("dome_review refuses a world that is not a disposable review copy: {}", world);
            finish(mc);
            return;
        }
        if (list.isEmpty())
        {
            for (String part : PLACES.split(";"))
            {
                String[] v = part.trim().split(",");
                if (v[0].startsWith("@"))
                {
                    list.add(new Place(0, 0, 0, Float.parseFloat(v[1]), Float.parseFloat(v[2]), null, false, v[0].substring(1)));
                    continue;
                }
                list.add(new Place(Double.parseDouble(v[0]), Double.parseDouble(v[1]), Double.parseDouble(v[2]),
                        Float.parseFloat(v[3]), Float.parseFloat(v[4]), v.length > 5 && !v[5].isEmpty() ? v[5] : null,
                        v.length > 6 && v[6].equals("field"), null));
            }
            batch = java.time.LocalDateTime.now().format(java.time.format.DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss"));
        }
        // a fresh player (the review copy carries no player data) can die at the spawn before anything else happens
        if (mc.player.isDeadOrDying())
        {
            mc.player.respawn();
            return;
        }
        if (warm == 0)
            server.execute(() -> server.getPlayerList().getPlayers().forEach(p -> p.setGameMode(GameType.SPECTATOR)));
        if (++warm < 200) return;
        if (warm == 200)
        {
            mc.options.hideGui = true;
            mc.options.pauseOnLostFocus = false;
            SeeleConfig.GEOFRONT_FAR_VIEW.set(false);
            server.execute(() -> {
                var player = server.getPlayerList().getPlayers().get(0);
                server.getPlayerList().op(player.getGameProfile());
                player.setGameMode(GameType.SPECTATOR);
                // the same light at every place and in every run: noon, clear, the clock stopped
                var source = server.createCommandSourceStack().withSuppressedOutput();
                for (String command : new String[]{"time set 6000", "weather clear 1000000", "gamerule doDaylightCycle false",
                        "gamerule doWeatherCycle false"})
                    server.getCommands().performPrefixedCommand(source, command);
            });
            ProjectSeele.LOGGER.info("dome_review started: {} places, settle {} ticks, batch {}", list.size(), SETTLE, batch);
            return;
        }
        int total = list.size() * 2;
        if (step >= total)
        {
            finish(mc);
            return;
        }
        boolean after = step >= list.size();
        Place place = list.get(step % list.size());
        int settle = SETTLE;
        if (ticks == 0)
        {
            SeeleConfig.GEOFRONT_FAR_VIEW.set(after);
            server.execute(() -> {
                var player = server.getPlayerList().getPlayers().get(0);
                if (place.command != null)
                {
                    server.getCommands().performPrefixedCommand(player.createCommandSourceStack(), place.command);
                    return;
                }
                var level = place.dimension == null ? player.serverLevel()
                        : server.getLevel(net.minecraft.resources.ResourceKey.create(net.minecraft.core.registries.Registries.DIMENSION,
                                new net.minecraft.resources.ResourceLocation(place.dimension)));
                player.teleportTo(level == null ? player.serverLevel() : level, place.x, place.y, place.z, place.yaw, place.pitch);
            });
            ProjectSeele.LOGGER.info("dome_review place {} {} going to {} {} {}", step % list.size() + 1, after ? "after" : "before",
                    place.x, place.y, place.z);
        }
        // the view holds still (a spectator's head drifts with mouse input otherwise)
        mc.player.setYRot(place.yaw);
        mc.player.setXRot(place.pitch);
        mc.player.yRotO = place.yaw;
        mc.player.xRotO = place.pitch;
        ticks++;
        if (place.field && ticks % 20 == 0)
        {
            // an A.T. Field 48 blocks ahead, facing the watcher (the shader-pack clouds and fog must stay behind it)
            var look = mc.player.getViewVector(1F);
            var eye = mc.player.getEyePosition(1F);
            com.projectseele.client.fx.AtFieldEffects.impact(eye.add(look.scale(48)),
                    new org.joml.Vector3f((float) -look.x, (float) -look.y, (float) -look.z), 24F, 1F);
        }
        if (ticks > settle && ticks <= settle + MEASURE && ticks % 20 == 0)
        {
            fpsSum += mc.getFps();
            fpsCount++;
        }
        if (ticks == settle + MEASURE + 1)
        {
            String name = String.format(Locale.ROOT, "projectseele_dome/%s/place%d_%s.png", batch, step % list.size() + 1, after ? "after" : "before");
            new java.io.File(mc.gameDirectory, "screenshots/projectseele_dome/" + batch).mkdirs();
            Screenshot.grab(mc.gameDirectory, name, mc.getMainRenderTarget(), ignored -> {});
            ProjectSeele.LOGGER.info("dome_review place {} {} fps {} over {} s, far view active {}, screenshot {}, {}",
                    step % list.size() + 1, after ? "after" : "before",
                    fpsCount == 0 ? 0 : fpsSum / fpsCount, fpsCount,
                    com.projectseele.client.GeoFrontDomeFarViewR65.suppressDistantHorizons(), name, com.projectseele.client.GeoFrontDomeFarViewR65.stats());
        }
        if (ticks > settle + MEASURE + 20)
        {
            step++;
            ticks = 0;
            fpsSum = 0;
            fpsCount = 0;
        }
    }

    private static void finish(Minecraft mc)
    {
        finished = true;
        ProjectSeele.LOGGER.info("dome_review_finished batch {}", batch);
        mc.stop();
    }
}
