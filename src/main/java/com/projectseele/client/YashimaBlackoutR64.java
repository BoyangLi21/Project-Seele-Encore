package com.projectseele.client;

import com.projectseele.ProjectSeele;
import com.projectseele.config.SeeleConfig;
import com.projectseele.entity.YashimaCannonEntityR52;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.world.level.BlockAndTintGetter;
import net.minecraft.world.level.LightLayer;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

import java.lang.ref.WeakReference;

/**
 * R64: the Yashima operation's night is a blackout. In the original the whole country's power is switched to the
 * gun, and the cities go dark; here the mission's night only darkened the sky (TvYashimaNightClientR54), and every
 * lamp and lit window burned on under it.
 * <p>
 * For as long as that night lasts, this client draws the open surface as if no block gave light: wherever the
 * sky's light reaches at all (the streets, and a room as far in as daylight would come through its windows), what
 * the renderers read as a block's light, and as the light a block gives off itself, is nothing. Three things keep
 * their light: the position, within {@link #LIT} blocks of the emplaced gun, which has its own supply and whose
 * lighting towers stay on; everything under {@link #SURFACE_FROM} (the launch shafts, the underground lines, the
 * GeoFront); and whatever the sky does not reach (a hall without windows, a tunnel), which is NERV's or nobody's
 * to see from outside. Nothing of the world is changed and nothing is asked of the server: the light the server
 * sent is all still there, and is drawn again when the night ends.
 * <p>
 * The light is read as out in four places: LevelRenderer.getLightColor (the game's own meshing, block entities,
 * particles), EntityRenderer.getBlockLightLevel (entities), Embeddium's LightDataAccess (its meshing: the block's
 * own emission and emissive flag are packed there apart from the light), and Distant Horizons' quad builder (the
 * far view, where every block's light and the "illuminated" material go: the position itself is never that far
 * from whoever looks at it from the position). When the blackout begins and ends the near meshes are built again
 * section by section, each standing as it was until its new one is ready, and the far view is built again from its
 * stored data; when the gun's place first becomes known, only the position's own sections are.
 * <p>
 * Two things more make it seen. Without a shader pack this dimension's light map is all but white whatever light a
 * block has (its ambient light is 0.62), so a lamp out looked like a lamp lit: for the blackout the light map is
 * brought down to a moonlit night where the sky reaches and no lamp does (YashimaBlackoutLightmapR64Mixin,
 * {@link #depth}). Under a shader pack a lamp glows by what kind of block it is, whatever light it has: a lamp that
 * is out is not named to the pack ({@link Lamp}).
 */
@Mod.EventBusSubscriber(modid = "projectseele", value = Dist.CLIENT)
public final class YashimaBlackoutR64
{
    /** So far round the emplaced gun, level, the position keeps its light (its outermost lighting towers stand 204 from it). */
    public static final double LIT = 240;
    /** Under this height nothing is part of it: the sea lies at 63, and no open ground is lower. */
    public static final int SURFACE_FROM = 60;

    // Written on the client thread, read by the mesh builders' threads.
    private static volatile boolean dark, centred;
    private static volatile double centreX, centreZ;
    private static WeakReference<ClientLevel> world = new WeakReference<>(null);
    private static int sought;
    /** The dark comes on and goes over this many client ticks in the light map (YashimaBlackoutLightmapR64Mixin). */
    public static final int FADE = 40;
    private static volatile int depth;

    /** How far the dark has come on, 0..1: the share of the night that the light map shows where no lamp reaches. */
    public static float depth()
    {
        return depth / (float) FADE;
    }

    /**
     * Review only (YashimaBlackoutReviewR64): the blackout is held off although the night is on, for the picture
     * that shows the night as it was. Nothing is written to the client's config for it.
     */
    public static volatile boolean held;
    /**
     * Review only (-Dprojectseele.blackoutReviewR64): how often each hook has taken light out, so that a review can
     * tell a hook that never ran from one that had nothing to take. 0 getLightColor, 1 an entity, 2 Embeddium's light
     * words read where the blackout reaches, 3 those changed, 4 lamps kept from the shader pack, 5 far-view quads, 6
     * sections asked to mesh again.
     */
    public static final java.util.concurrent.atomic.AtomicIntegerArray TOLD =
            System.getProperty("projectseele.blackoutReviewR64", "").isEmpty() ? null : new java.util.concurrent.atomic.AtomicIntegerArray(7);

    public static void told(int which)
    {
        if (TOLD != null) TOLD.incrementAndGet(which);
    }

    /** The blackout is on: the far view has no lights at all. */
    public static boolean far()
    {
        if (dark) told(5);
        return dark;
    }

    /** The blackout is on and this place is on the surface, outside the position: whether it is dark here is the sky's to say. */
    public static boolean zone(int x, int y, int z)
    {
        if (y < SURFACE_FROM) return false;
        boolean city = CityLightWavesR65.contains(x, z);
        if (!(city ? CityLightWavesR65.dark(x,z) : dark)) return false;
        if (!centred) return true;
        double dx = x + .5 - centreX, dz = z + .5 - centreZ;
        return dx * dx + dz * dz > LIT * LIT;
    }

    /**
     * For a block in the {@link #zone} that gives light and that the sky does not reach itself (a solid lamp): the
     * sky reaches a block beside it, so the lamp is one of those that are out.
     */
    public static boolean skyBeside(BlockAndTintGetter level, int x, int y, int z)
    {
        BlockPos.MutableBlockPos beside = new BlockPos.MutableBlockPos();
        for (Direction side : Direction.values())
            if (level.getBrightness(LightLayer.SKY, beside.set(x + side.getStepX(), y + side.getStepY(), z + side.getStepZ())) > 0) return true;
        return false;
    }

    /**
     * Under a shader pack a lamp glows by what kind of block it is, whatever light it is given: Oculus hands the
     * pack each block's number from the pack's own table, and its emission, with the block's vertices. This is
     * the holder of those two for the block a mesh builder's thread is on (YashimaBlackoutOculusR64Mixin).
     */
    public interface Lamp
    {
        /** The block now being meshed goes to the pack as no block it knows, giving no light. */
        void seele$lampOut();
    }

    private static final ThreadLocal<Lamp> LAMP = new ThreadLocal<>();

    /** A mesh builder's thread has just named a block that gives light to the shader pack. */
    public static void lamp(Lamp holder)
    {
        LAMP.set(holder);
    }

    /**
     * That block, a lamp in the {@link #zone}, is about to be meshed (YashimaBlackoutEmbeddiumBlockR64Mixin): where
     * the sky reaches it or a block beside it, the pack is not told what it is.
     */
    public static void lampOut(BlockAndTintGetter level, BlockPos pos)
    {
        Lamp lamp = LAMP.get();
        if (lamp == null || level == null) return;
        if (level.getBrightness(LightLayer.SKY, pos) > 0 || skyBeside(level, pos.getX(), pos.getY(), pos.getZ()))
        {
            lamp.seele$lampOut(); told(4);
        }
    }

    @SubscribeEvent
    public static void tick(TickEvent.ClientTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END) return;
        Minecraft mc = Minecraft.getInstance();
        ClientLevel level = mc.level;
        if (level != world.get())
        {
            // Another world (or none): its renderer starts from nothing by itself.
            world = new WeakReference<>(level);
            dark = false; centred = false; sought = 0; depth = 0;
        }
        if (level == null) { CityLightWavesR65.update(null, false); return; }
        depth = dark ? Math.min(FADE, depth + 1) : Math.max(0, depth - 1);
        // The server says when: the operation's night, from the moment the power is switched to the gun.
        boolean wanted = !held && SeeleConfig.YASHIMA_BLACKOUT.get() && TvYashimaNightClientR54.blackout(level);
        int changed = CityLightWavesR65.update(level, wanted);
        if (changed != 0) remeshCityWave(mc, level, changed);
        boolean known = centred, moved = false;
        double x = centreX, z = centreZ;
        // The gun's place: looked for once a second (it does not move level; it is there whenever its chunk is).
        if (sought-- <= 0)
        {
            sought = 20;
            for (var entity : level.entitiesForRendering())
                if (entity instanceof YashimaCannonEntityR52 gun)
                {
                    moved = !known || Math.abs(gun.getX() - x) + Math.abs(gun.getZ() - z) > .5;
                    known = true; x = gun.getX(); z = gun.getZ();
                    break;
                }
        }
        if (wanted == dark)
        {
            if (!moved) return;
            double oldX = centreX, oldZ = centreZ;
            boolean had = centred;
            centreX = x; centreZ = z; centred = true;
            if (!dark) return;
            ProjectSeele.LOGGER.info("Yashima blackout: the position is at {}, {}", Math.round(x), Math.round(z));
            // Only the position's own sections were read otherwise (and those of where it was taken to be).
            remesh(mc, level, x, z);
            if (had) remesh(mc, level, oldX, oldZ);
            return;
        }
        centreX = x; centreZ = z; centred = known;
        dark = wanted;
        ProjectSeele.LOGGER.info("Yashima blackout {} (the position {})", wanted ? "on" : "off", known ? "at " + Math.round(x) + ", " + Math.round(z) : "not seen yet");
        // Every mesh of the surface was built with the light as it was read then.
        remesh(mc, level, Double.NaN, Double.NaN);
        rebuildFarView();
    }

    /** Refresh loaded city sections whose service area crossed half brightness. */
    private static void remeshCityWave(Minecraft mc, ClientLevel level, int districts)
    {
        BlockPos eye = mc.gameRenderer.getMainCamera().getBlockPosition();
        int reach = mc.options.getEffectiveRenderDistance() + 1;
        for (int sx=Math.max(-22,(eye.getX()>>4)-reach); sx<=Math.min(19,(eye.getX()>>4)+reach); sx++)
            for (int sz=Math.max(-2,(eye.getZ()>>4)-reach); sz<=Math.min(36,(eye.getZ()>>4)+reach); sz++)
            {
                int lo=CityLightWavesR65.district(sx*16-1,sz*16-1);
                int hi=CityLightWavesR65.district(sx*16+16,sz*16+16);
                int mask=((2<<hi)-1) & ~((1<<lo)-1);
                if ((districts & mask)==0) continue;
                for (int sy=3; sy<=13; sy++) mc.levelRenderer.setSectionDirty(sx,sy,sz);
            }
    }

    /**
     * Has the surface's sections meshed again, each keeping its old mesh until the new one is ready (so nothing
     * blinks out): all those in view of the camera, or with a place given only those within {@link #LIT} of it.
     */
    private static void remesh(Minecraft mc, ClientLevel level, double x, double z)
    {
        BlockPos camera = mc.gameRenderer.getMainCamera().getBlockPosition();
        int reach = mc.options.getEffectiveRenderDistance() + 1;
        int x0 = (camera.getX() >> 4) - reach, x1 = (camera.getX() >> 4) + reach, z0 = (camera.getZ() >> 4) - reach, z1 = (camera.getZ() >> 4) + reach;
        if (!Double.isNaN(x))
        {
            int edge = (int) LIT + 16;
            x0 = Math.max(x0, ((int) Math.floor(x) - edge) >> 4); x1 = Math.min(x1, ((int) Math.floor(x) + edge) >> 4);
            z0 = Math.max(z0, ((int) Math.floor(z) - edge) >> 4); z1 = Math.min(z1, ((int) Math.floor(z) + edge) >> 4);
        }
        // (A section just under the surface's lowest height reads the light of the blocks over it at its top.)
        int y0 = Math.max(level.getMinSection(), (SURFACE_FROM >> 4) - 1), y1 = level.getMaxSection() - 1;
        for (int sx = x0; sx <= x1; sx++)
            for (int sz = z0; sz <= z1; sz++)
                for (int sy = y0; sy <= y1; sy++)
                {
                    mc.levelRenderer.setSectionDirty(sx, sy, sz); told(6);
                }
    }

    /**
     * Distant Horizons' tree of far-view sections (YashimaBlackoutDhTreeR64Mixin): it can have every section's
     * picture made again while the old one stays up, so that the far view never goes blank.
     */
    public interface FarView
    {
        /** Every section is queued to be built again; false when this tree could not do it. */
        boolean seele$relight();
    }

    private static final java.util.Set<FarView> FAR_VIEWS = java.util.Collections.newSetFromMap(new java.util.WeakHashMap<>());

    /** A far-view tree has been made (any thread). */
    public static void farView(FarView tree)
    {
        synchronized (FAR_VIEWS) { FAR_VIEWS.add(tree); }
    }

    /**
     * The far view is built again with the light as it is now read: section by section where Distant Horizons'
     * trees are known, each keeping its old picture until the new one is ready; otherwise, or if one of them
     * cannot, all at once from its stored data (DhApi.Delayed.renderProxy.clearRenderDataCache), which leaves the
     * far view blank for some seconds.
     */
    private static void rebuildFarView()
    {
        FarView[] trees;
        synchronized (FAR_VIEWS) { trees = FAR_VIEWS.toArray(new FarView[0]); }
        boolean all = trees.length > 0;
        for (FarView tree : trees) all &= tree.seele$relight();
        ProjectSeele.LOGGER.info("Yashima blackout: far view built again {} ({} trees)", all ? "section by section" : "all at once", trees.length);
        if (all) return;
        try
        {
            Object proxy = Class.forName("com.seibel.distanthorizons.api.DhApi$Delayed").getField("renderProxy").get(null);
            if (proxy != null) Class.forName("com.seibel.distanthorizons.api.interfaces.render.IDhApiRenderProxy").getMethod("clearRenderDataCache").invoke(proxy);
        }
        catch (ClassNotFoundException absent) { }
        catch (ReflectiveOperationException | RuntimeException failure)
        {
            ProjectSeele.LOGGER.warn("Could not ask Distant Horizons to build the far view again for the blackout", failure);
        }
    }

    private YashimaBlackoutR64() {}
}
