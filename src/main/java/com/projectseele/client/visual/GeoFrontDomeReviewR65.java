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
 * R65 review of the GeoFront far view, in disposable saves only. -Dprojectseele.domeReviewR65=x,y,z,yaw,pitch;... names
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

    private record Place(double x, double y, double z, float yaw, float pitch) {}
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
                list.add(new Place(Double.parseDouble(v[0]), Double.parseDouble(v[1]), Double.parseDouble(v[2]),
                        Float.parseFloat(v[3]), Float.parseFloat(v[4])));
            }
            batch = java.time.LocalDateTime.now().format(java.time.format.DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss"));
        }
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
                player.teleportTo(player.serverLevel(), place.x, place.y, place.z, place.yaw, place.pitch);
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
            ProjectSeele.LOGGER.info("dome_review place {} {} fps {} over {} s, far view active {}, screenshot {}",
                    step % list.size() + 1, after ? "after" : "before",
                    fpsCount == 0 ? 0 : fpsSum / fpsCount, fpsCount,
                    com.projectseele.client.GeoFrontDomeFarViewR65.suppressDistantHorizons(), name);
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
