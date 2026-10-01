package com.projectseele.fx;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

import com.projectseele.ProjectSeele;
import com.projectseele.config.SeeleConfig;
import com.projectseele.world.PerformanceCounters;
import net.minecraft.core.BlockPos;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.server.ServerStoppedEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/**
 * Mountain-scale terrain destruction without a single catastrophic tick.
 * Living-target damage is immediate; crater columns are opened outward under
 * one global block budget. World writes always remain on the server thread.
 */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class StrategicExplosionDirector
{
    private static final List<CraterTask> ACTIVE = new ArrayList<>();
    private static final int UPDATE_FLAGS = Block.UPDATE_CLIENTS
            | Block.UPDATE_KNOWN_SHAPE | Block.UPDATE_SUPPRESS_DROPS;

    private StrategicExplosionDirector() {}

    public static void startCannon(ServerLevel level, Vec3 impact, Entity source)
    {
        int radius = SeeleConfig.CANNON_TERRAIN_RADIUS.get();
        int depth = SeeleConfig.CANNON_CRATER_DEPTH.get();
        applyBlast(level, impact, source, SeeleConfig.CANNON_EXPLOSION_RADIUS.get(),
                SeeleConfig.CANNON_BLAST_DAMAGE.get().floatValue());
        ACTIVE.add(new CraterTask("POSITRON", level.dimension(), BlockPos.containing(impact),
                radius, depth));
        ProjectSeele.LOGGER.info("Strategic POSITRON crater queued at {} radius={} depth={}",
                BlockPos.containing(impact).toShortString(), radius, depth);
    }

    public static void startN2(ServerLevel level, Vec3 impact, Entity source)
    {
        // N2 is an exact threefold strategic effect in radius, depth, damage
        // and client FX scale. Radius multiplication makes volume much larger
        // than threefold, which is why the same staged edit budget is vital.
        int radius = SeeleConfig.CANNON_TERRAIN_RADIUS.get() * 3;
        int depth = SeeleConfig.CANNON_CRATER_DEPTH.get() * 3;
        applyBlast(level, impact, source, SeeleConfig.CANNON_EXPLOSION_RADIUS.get() * 3.0D,
                SeeleConfig.CANNON_BLAST_DAMAGE.get().floatValue() * 3.0F);
        ACTIVE.add(new CraterTask("N2", level.dimension(), BlockPos.containing(impact),
                radius, depth));
        ProjectSeele.LOGGER.warn("Strategic N2 crater queued at {} radius={} depth={}",
                BlockPos.containing(impact).toShortString(), radius, depth);
    }

    private static void applyBlast(ServerLevel level, Vec3 impact, Entity source,
                                   double radius, float maximumDamage)
    {
        if (radius <= 0.0D || maximumDamage <= 0.0F)
        {
            return;
        }
        DamageSource damage = level.damageSources().explosion(source, source);
        AABB area = new AABB(impact, impact).inflate(radius);
        for (Entity target : com.projectseele.physics.CombatDamageTargetsR44.candidates(level,area,source,null))
        {
            Vec3 centre = com.projectseele.physics.CombatDamageTargetsR44.nearestSurface(target,impact);
            double distance = centre.distanceTo(impact);
            if (distance > radius)
            {
                continue;
            }
            float exposure = (float) (1.0D - distance / radius);
            float dealt = Math.max(1.0F, maximumDamage * exposure * exposure);
            target.hurt(damage, dealt);
            Vec3 away = centre.subtract(impact);
            if (target instanceof LivingEntity && away.lengthSqr() > 1.0E-4D)
            {
                Vec3 impulse = away.normalize().scale(0.8D + exposure * 4.2D);
                target.push(impulse.x, Math.max(0.25D, impulse.y + exposure), impulse.z);
            }
        }
    }

    @SubscribeEvent
    public static void onServerTick(TickEvent.ServerTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END || ACTIVE.isEmpty())
        {
            return;
        }
        int remaining = SeeleConfig.STRATEGIC_BLOCKS_PER_TICK.get();
        int tasksRemaining = ACTIVE.size();
        Iterator<CraterTask> iterator = ACTIVE.iterator();
        while (iterator.hasNext() && remaining > 0)
        {
            CraterTask task = iterator.next();
            ServerLevel level = event.getServer().getLevel(task.dimension);
            if (level == null)
            {
                iterator.remove();
                tasksRemaining--;
                continue;
            }
            int allowance = Math.max(64, remaining / Math.max(1, tasksRemaining));
            int used = task.process(level, allowance);
            remaining -= used;
            tasksRemaining--;
            if (task.complete)
            {
                ProjectSeele.LOGGER.info("Strategic {} crater complete at {}",
                        task.name, task.centre.toShortString());
                iterator.remove();
            }
        }
    }

    @SubscribeEvent
    public static void onServerStopped(ServerStoppedEvent event)
    {
        ACTIVE.clear();
    }

    private static boolean protectedBlock(ServerLevel level, BlockPos position, BlockState state)
    {
        return state.hasBlockEntity() || state.getDestroySpeed(level, position) < 0.0F
                || state.is(Blocks.BEDROCK) || state.is(Blocks.BARRIER)
                || state.is(Blocks.END_PORTAL) || state.is(Blocks.END_PORTAL_FRAME)
                || state.is(Blocks.NETHER_PORTAL) || state.is(Blocks.COMMAND_BLOCK)
                || state.is(Blocks.CHAIN_COMMAND_BLOCK) || state.is(Blocks.REPEATING_COMMAND_BLOCK)
                || state.is(Blocks.STRUCTURE_BLOCK) || state.is(Blocks.JIGSAW);
    }

    private static final class CraterTask
    {
        private final String name;
        private final ResourceKey<Level> dimension;
        private final BlockPos centre;
        private final int radius;
        private final int depth;
        private int ring;
        private int perimeterIndex;
        private int columnX;
        private int columnZ;
        private int columnY;
        private int columnFloor;
        private double columnNormalisedRadius;
        private boolean columnActive;
        private boolean complete;

        private CraterTask(String name, ResourceKey<Level> dimension, BlockPos centre,
                           int radius, int depth)
        {
            this.name = name;
            this.dimension = dimension;
            this.centre = centre.immutable();
            this.radius = radius;
            this.depth = depth;
        }

        private int process(ServerLevel level, int budget)
        {
            int used = 0;
            while (used < budget && !this.complete)
            {
                if (!this.columnActive)
                {
                    if (!this.beginNextColumn(level))
                    {
                        this.complete = true;
                        break;
                    }
                }
                if (this.columnY <= this.columnFloor)
                {
                    this.scorchFloor(level);
                    this.columnActive = false;
                    continue;
                }
                BlockPos position = new BlockPos(this.columnX, this.columnY--, this.columnZ);
                used++;
                BlockState state = level.getBlockState(position);
                if (!state.isAir() && !protectedBlock(level, position, state))
                {
                    level.setBlock(position, Blocks.AIR.defaultBlockState(), UPDATE_FLAGS);
                    PerformanceCounters.recordWorldBlockWrites(1);
                }
            }
            return used;
        }

        private boolean beginNextColumn(ServerLevel level)
        {
            while (this.ring <= this.radius)
            {
                int dx;
                int dz;
                if (this.ring == 0)
                {
                    dx = 0;
                    dz = 0;
                    this.ring = 1;
                    this.perimeterIndex = 0;
                }
                else
                {
                    int side = this.ring * 2;
                    int index = this.perimeterIndex++;
                    if (index < side)
                    {
                        dx = -this.ring + index;
                        dz = -this.ring;
                    }
                    else if (index < side * 2)
                    {
                        dx = this.ring;
                        dz = -this.ring + index - side;
                    }
                    else if (index < side * 3)
                    {
                        dx = this.ring - (index - side * 2);
                        dz = this.ring;
                    }
                    else
                    {
                        dx = -this.ring;
                        dz = this.ring - (index - side * 3);
                    }
                    if (this.perimeterIndex >= this.ring * 8)
                    {
                        this.ring++;
                        this.perimeterIndex = 0;
                    }
                }

                double radialSqr = (dx * (double) dx + dz * (double) dz)
                        / (this.radius * (double) this.radius);
                if (radialSqr > 1.0D)
                {
                    continue;
                }
                int x = this.centre.getX() + dx;
                int z = this.centre.getZ() + dz;
                BlockPos loadedProbe = new BlockPos(x, this.centre.getY(), z);
                if (!level.hasChunkAt(loadedProbe))
                {
                    continue;
                }
                // WORLD_SURFACE deliberately includes leaves, snow and fluid
                // caps. Starting below foliage left intact tree crowns and
                // water sheets floating over an otherwise convincing crater.
                int top = Math.min(level.getMaxBuildHeight() - 1,
                        level.getHeight(Heightmap.Types.WORLD_SURFACE, x, z) - 1);
                double radial = Math.sqrt(radialSqr);
                int bowlDepth = (int) Math.ceil(this.depth * Math.pow(1.0D - radial, 0.68D));
                int floor = Math.max(level.getMinBuildHeight() + 1,
                        this.centre.getY() - bowlDepth);
                if (top <= floor)
                {
                    continue;
                }
                this.columnX = x;
                this.columnZ = z;
                this.columnY = top;
                this.columnFloor = floor;
                this.columnNormalisedRadius = radial;
                this.columnActive = true;
                return true;
            }
            return false;
        }

        private void scorchFloor(ServerLevel level)
        {
            BlockPos floor = new BlockPos(this.columnX, this.columnFloor, this.columnZ);
            BlockState state = level.getBlockState(floor);
            if (state.isAir() || protectedBlock(level, floor, state))
            {
                return;
            }
            BlockState scorched = this.columnNormalisedRadius < 0.72D
                    ? Blocks.BASALT.defaultBlockState() : Blocks.BLACKSTONE.defaultBlockState();
            level.setBlock(floor, scorched, UPDATE_FLAGS);
            PerformanceCounters.recordWorldBlockWrites(1);
        }
    }
}
