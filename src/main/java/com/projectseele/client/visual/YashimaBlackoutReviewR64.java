package com.projectseele.client.visual;

import com.projectseele.ProjectSeele;
import com.projectseele.client.TvYashimaNightClientR54;
import com.projectseele.network.ClientboundEncounterObserverPacket;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Locale;
import java.util.UUID;

/**
 * Review tool, R64: the Yashima blackout seen from given places, lit and dark, without playing the operation.
 * <p>
 * -Dprojectseele.blackoutReviewR64=x,y,z,yaw,pitch;x,y,z,yaw,pitch;... in a copy of the whole map (never the
 * formal world): the player is put at each place in turn as a spectator, the mission's night is put on for this
 * client alone (as the server's own night signal does), and two pictures are taken there: the night with the
 * blackout held off (YashimaBlackoutR64.held; the client's config is not touched), and with it on. They go to screenshots/projectseele_blackout/
 * &lt;time&gt;/ as &lt;n&gt;_lit.png and &lt;n&gt;_dark.png, with &lt;n&gt;_after_1s.png, _3s and _6s between them for how the change
 * itself looks. The game is closed at the end. (A place where the operation itself takes the player elsewhere is
 * no use: the pictures are then of where it took them.) With each picture the log says how often each of the
 * blackout's hooks has taken light out since the last one, and what light is stored and what is drawn at the places
 * named by -Dprojectseele.blackoutReviewProbeR64=x,y,z;x,y,z;...
 * -Dprojectseele.blackoutReviewSettleR64=&lt;ticks&gt; (240) is how long each place is given to load before its first
 * picture, -Dprojectseele.blackoutReviewDarkR64=&lt;ticks&gt; (300) how long the blackout is given before the second.
 */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class YashimaBlackoutReviewR64
{
    private static final String PLACES = System.getProperty("projectseele.blackoutReviewR64", "");
    private static final int SETTLE = Integer.getInteger("projectseele.blackoutReviewSettleR64", 240);
    /** How long after the blackout is switched on the dark picture is taken: the meshes and the far view are built again in that time. */
    private static final int DARK = Integer.getInteger("projectseele.blackoutReviewDarkR64", 300);
    private static final String PROBES = System.getProperty("projectseele.blackoutReviewProbeR64", "");
    private static final String BATCH = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss"));
    private static int age, place = -1, since;
    private static long night;
    private static boolean done;

    @SubscribeEvent
    public static void tick(TickEvent.ClientTickEvent event)
    {
        if (PLACES.isEmpty() || done || event.phase != TickEvent.Phase.END) return;
        Minecraft mc = Minecraft.getInstance();
        if (mc.player == null || mc.level == null || mc.screen != null) return;
        String[] places = PLACES.split(";");
        if (age++ < 100) return;
        if (place < 0)
        {
            mc.options.hideGui = true; mc.options.pauseOnLostFocus = false;
            try
            {
                // (The game's screenshot writer does not make the folders of a name with folders in it.)
                java.nio.file.Files.createDirectories(mc.gameDirectory.toPath().resolve("screenshots/projectseele_blackout/" + BATCH));
            }
            catch (java.io.IOException failure)
            {
                throw new IllegalStateException("blackout review output", failure);
            }
            mc.player.connection.sendCommand("gamemode spectator");
            ProjectSeele.LOGGER.info("Blackout review started: batch={} places={}", BATCH, places.length);
            place = 0; since = 0;
        }
        if (place >= places.length)
        {
            com.projectseele.client.YashimaBlackoutR64.held = false;
            ProjectSeele.LOGGER.info("Blackout review finished: batch={}", BATCH);
            done = true;
            mc.stop();
            return;
        }
        // The night, as the server's signal puts it on (again every second: nothing else sends one here).
        if (since % 20 == 0)
            TvYashimaNightClientR54.receive(new ClientboundEncounterObserverPacket(ClientboundEncounterObserverPacket.Kind.NIGHT, UUID.randomUUID(), 1,
                    mc.level.dimension().location(), ClientboundEncounterObserverPacket.RAMIEL, 0, ++night + mc.level.getGameTime() * 4, null));
        if (since == 0)
        {
            String[] at = places[place].split(",");
            com.projectseele.client.YashimaBlackoutR64.held = true;
            mc.player.connection.sendCommand(String.format(Locale.ROOT, "tp @s %s %s %s %s %s", at[0], at[1], at[2], at[3], at[4]));
        }
        if (since == SETTLE) shot(mc, place + "_lit.png");
        if (since == SETTLE + 10) com.projectseele.client.YashimaBlackoutR64.held = false;
        // How the change itself looks: one, three and six seconds after the blackout is switched on.
        for (int seconds : new int[]{1, 3, 6})
            if (since == SETTLE + 10 + seconds * 20 && seconds * 20 < DARK) shot(mc, place + "_after_" + seconds + "s.png");
        if (since == SETTLE + 10 + DARK) shot(mc, place + "_dark.png");
        if (since++ >= SETTLE + 10 + DARK + 10) { place++; since = 0; }
    }

    private static void shot(Minecraft mc, String name)
    {
        var told = com.projectseele.client.YashimaBlackoutR64.TOLD;
        StringBuilder hooks = new StringBuilder();
        String[] names = {"getLightColor", "entity", "embeddium read", "embeddium changed", "lamps kept from the pack", "far quads", "sections asked"};
        if (told != null) for (int i = 0; i < names.length; i++) hooks.append(' ').append(names[i]).append(' ').append(told.getAndSet(i, 0)).append(i < names.length - 1 ? "," : "");
        ProjectSeele.LOGGER.info("Blackout review: {} at {} blackout {} | hooks since the last picture:{}", name, mc.player.blockPosition().toShortString(), com.projectseele.client.YashimaBlackoutR64.far(), hooks);
        if (!PROBES.isEmpty() && mc.level != null) for (String probe : PROBES.split(";"))
        {
            String[] at = probe.split(",");
            var pos = new net.minecraft.core.BlockPos(Integer.parseInt(at[0].trim()), Integer.parseInt(at[1].trim()), Integer.parseInt(at[2].trim()));
            if (!mc.level.isLoaded(pos)) continue;
            int drawn = net.minecraft.client.renderer.LevelRenderer.getLightColor(mc.level, pos);
            ProjectSeele.LOGGER.info("Blackout review: probe {} {}: stored block {} sky {}, drawn block {} sky {}, in the zone {}", pos.toShortString(),
                    net.minecraftforge.registries.ForgeRegistries.BLOCKS.getKey(mc.level.getBlockState(pos).getBlock()), mc.level.getBrightness(net.minecraft.world.level.LightLayer.BLOCK, pos),
                    mc.level.getBrightness(net.minecraft.world.level.LightLayer.SKY, pos), drawn >> 4 & 15, drawn >> 20 & 15, com.projectseele.client.YashimaBlackoutR64.zone(pos.getX(), pos.getY(), pos.getZ()));
        }
        Screenshot.grab(mc.gameDirectory, "projectseele_blackout/" + BATCH + "/" + name, mc.getMainRenderTarget(), ignored -> {});
    }

    private YashimaBlackoutReviewR64() {}
}
