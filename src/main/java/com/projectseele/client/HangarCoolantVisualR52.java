package com.projectseele.client;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.NervCarrierPlatformEntity;
import com.projectseele.fluid.LclFluidType;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.core.BlockPos;
import net.minecraft.util.Mth;
import net.minecraft.world.level.BlockAndTintGetter;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.ClientPlayerNetworkEvent;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.entity.EntityJoinLevelEvent;
import net.minecraftforge.event.entity.EntityLeaveLevelEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.joml.Vector3f;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/** The physical blocks keep the fluid mechanics. A tracked restraint gantry owns the visible meniscus. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class HangarCoolantVisualR52
{
    public static final int TV_COOLANT_TINT = 0xFFE99152;
    private static final List<NervCarrierPlatformEntity> tracked = new ArrayList<>();
    private static final Tank[] tanks = new Tank[3];
    private static final Bounds[] liveBounds = new Bounds[3];
    // Chunk builders must never inspect tracked entities, which change on the main thread.
    private record Scope(Object world, Bounds[] bounds) {}
    private static final Scope EMPTY = new Scope(null, new Bounds[0]);
    private static volatile Scope scope = EMPTY;

    public record Bounds(int x, int floor, int z)
    {
        public boolean contains(int px, int py, int pz)
        {
            return Math.abs(px - x) <= 19 && Math.abs(pz - z) <= 26 && py >= floor && py < floor + 44;
        }
    }

    public static final class Tank
    {
        public final NervCarrierPlatformEntity gantry;
        public final Bounds bounds;
        private float lastLevel;
        private int lastDrainTick = Integer.MIN_VALUE / 2;
        private float recentHigh;

        Tank(NervCarrierPlatformEntity gantry)
        {
            this.gantry = gantry;
            bounds = new Bounds(gantry.getBlockX(), Mth.floor(gantry.getY() + 1), gantry.getBlockZ());
            lastLevel = gantry.getLclVisualLevel(1);
        }

        void tick()
        {
            float level = gantry.getLclVisualLevel(1);
            if (level < lastLevel - .001F)
            {
                if (!draining()) recentHigh = lastLevel;
                lastDrainTick = gantry.tickCount;
            }
            else if (level > lastLevel + .001F) lastDrainTick = Integer.MIN_VALUE / 2;
            lastLevel = level;
        }

        public boolean draining() { return gantry.tickCount - lastDrainTick < 16; }
        public float wetCeiling() { return bounds.floor + recentHigh; }
        public float surface(float partial)
        {
            float level = gantry.getLclVisualLevel(partial);
            return bounds.floor + level - Math.min(1, level) / 9F;
        }
    }

    public static Tank tank(int variant)
    {
        return variant >= 0 && variant < tanks.length ? tanks[variant] : null;
    }

    public static boolean owned(BlockAndTintGetter view, BlockPos pos)
    {
        return pos != null && owned(view, pos.getX(), pos.getY(), pos.getZ());
    }

    public static boolean owned(BlockAndTintGetter view, int x, int y, int z)
    {
        var snapshot = scope;
        if (snapshot.world == null || view == null || view.getModelDataManager() != snapshot.world) return false;
        for (var b : snapshot.bounds)
            if (b != null && b.contains(x, y, z)) return true;
        return false;
    }

    public static int tint(BlockAndTintGetter view, BlockPos pos)
    {
        return owned(view, pos) ? TV_COOLANT_TINT : LclFluidType.TINT;
    }

    public static Vector3f fogColor(ClientLevel level, BlockPos pos)
    {
        return owned(level, pos) ? new Vector3f(.60F, .24F, .075F) : new Vector3f(.86F, .33F, .125F);
    }

    @SubscribeEvent public static void join(EntityJoinLevelEvent event)
    {
        if (event.getLevel().isClientSide && event.getEntity() instanceof NervCarrierPlatformEntity gantry) tracked.add(gantry);
    }

    @SubscribeEvent public static void leave(EntityLeaveLevelEvent event)
    {
        if (event.getLevel().isClientSide && event.getEntity() instanceof NervCarrierPlatformEntity gantry) tracked.remove(gantry);
    }

    @SubscribeEvent public static void tick(TickEvent.ClientTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END) return;
        var mc = Minecraft.getInstance();
        var level = mc.level;
        boolean claimed = level != null && FacilityFrameClientR52.claimed(level);
        for (int i = 0; i < tanks.length; i++)
        {
            NervCarrierPlatformEntity first = null;
            if (claimed) for (var g : tracked)
                if (g.level() == level && !g.isRemoved() && g.isRestraintGantry() && g.hasDeclaredMachineFrameR52()
                        && g.getUnitVariant() == i && (first == null || g.getId() < first.getId())) first = g;
            Tank old = tanks[i];
            if (first == null) tanks[i] = null;
            else if (old == null || old.gantry != first) tanks[i] = new Tank(first);
            if (tanks[i] != null) tanks[i].tick();
            liveBounds[i] = tanks[i] == null ? null : tanks[i].bounds;
        }
        var old = scope;
        Object world = claimed ? level.getModelDataManager() : null;
        if (old.world == world && (world == null || Arrays.equals(liveBounds, old.bounds))) return;
        scope = world == null ? EMPTY : new Scope(world, liveBounds.clone());
        if (level != null)
        {
            if (old.world == level.getModelDataManager()) dirty(mc, old.bounds);
            dirty(mc, scope.bounds);
        }
    }

    private static void dirty(Minecraft mc, Bounds[] bounds)
    {
        for (var b : bounds) if (b != null)
            mc.levelRenderer.setBlocksDirty(b.x - 19, b.floor, b.z - 26, b.x + 19, b.floor + 43, b.z + 26);
    }

    @SubscribeEvent public static void logout(ClientPlayerNetworkEvent.LoggingOut event)
    {
        scope = EMPTY;
        tracked.clear();
        Arrays.fill(tanks, null);
        Arrays.fill(liveBounds, null);
    }

    private HangarCoolantVisualR52() {}
}