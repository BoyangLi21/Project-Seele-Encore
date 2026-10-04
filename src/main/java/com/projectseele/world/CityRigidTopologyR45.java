package com.projectseele.world;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.NbtIo;
import net.minecraft.nbt.Tag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.dimension.DimensionType;
import net.minecraft.world.level.storage.LevelResource;

/** Persistent topology authority. Installed layouts never revert to old generators. */
public final class CityRigidTopologyR45
{
    private static final String NAME = "projectseele_city_rigid_topology_r45_";
    private static final Map<Path, Cache> CACHE = new ConcurrentHashMap<>();
    private CityRigidTopologyR45() {}

    public static Path file(ServerLevel level, BlockPos origin)
    {
        return DimensionType.getStorageFolder(level.dimension(), level.getServer().getWorldPath(LevelResource.ROOT))
                .resolve("data").resolve(NAME + Long.toUnsignedString(origin.asLong()) + ".dat");
    }

    /** Gate legacy startup, generation, travel and maintenance even when Create is absent. */
    public static boolean owns(ServerLevel level, BlockPos origin)
    {
        return read(level, origin) != null;
    }

    /** Portable world setting; absent/false keeps all production candidates off. */
    public static boolean runtimeEnabled(ServerLevel level, BlockPos origin)
    {
        CompoundTag tag = read(level, origin);
        return tag != null && tag.getBoolean("RuntimeEnabled") && "INSTALLED".equals(tag.getString("Stage"))
                && tag.getBoolean("NativeStructurePassed") && tag.getBoolean("ExactCargoMigrationPassed");
    }

    public static void clearRuntimeCache() { CACHE.clear(); }

    public static CompoundTag declared(ServerLevel level, BlockPos origin)
    {
        CompoundTag tag = read(level, origin); return tag == null ? null : tag.copy();
    }

    public static CompoundTag installed(ServerLevel level, BlockPos origin)
    {
        CompoundTag tag = read(level, origin);
        if (tag != null && "CANDIDATE_DISABLED".equals(tag.getString("Stage"))
                && !tag.getBoolean("RuntimeEnabled") && tag.getBoolean("ExactStaticMigrationPassed")
                && tag.getBoolean("ExactCargoMigrationPassed")
                && !System.getProperty("projectseele.r45CityCreateDistrict", "").isEmpty()
                && CityAtomicCandidateBindingR45.candidateLeaseReady(level.getServer().getWorldPath(LevelResource.ROOT)))
            return tag;
        if (tag == null || !"INSTALLED".equals(tag.getString("Stage"))
                || !tag.getBoolean("NativeStructurePassed") || !tag.getBoolean("ExactCargoMigrationPassed"))
            throw new IllegalStateException("R45 topology still requires exact installation/native structural verification");
        return tag;
    }

    public static List<Tower> towers(ServerLevel level, BlockPos origin)
    {
        CompoundTag data = installed(level, origin);
        List<Tower> result = new ArrayList<>();
        for (Tag raw : data.getList("Towers", Tag.TAG_COMPOUND))
        {
            CompoundTag row = (CompoundTag) raw;
            BlockPos centre = BlockPos.of(row.getLong("Centre"));
            int height = row.getInt("Height"), half = row.getInt("Half");
            if (height < 1 || half < 1 || centre.getY() < 80 || centre.getY() > 81) throw new IllegalStateException("Invalid R45 city frame");
            BlockPos core = row.contains("FixedCorePos") ? BlockPos.of(row.getLong("FixedCorePos")) : null;
            if (core != null && (Math.abs(core.getX() - centre.getX()) <= half && Math.abs(core.getZ() - centre.getZ()) <= half))
                throw new IllegalStateException("Static controller inside rigid swept cargo");
            CompoundTag footprint = row.getCompound("Footprint");
            int minX = footprint.isEmpty() ? -half : footprint.getInt("MinX"), maxX = footprint.isEmpty() ? half : footprint.getInt("MaxX");
            int minZ = footprint.isEmpty() ? -half : footprint.getInt("MinZ"), maxZ = footprint.isEmpty() ? half : footprint.getInt("MaxZ");
            result.add(new Tower(result.size(), row.getString("Kind"), centre, height, half, core,
                    row.getLongArray("NegativeDomeAnchorMask"), minX, maxX, minZ, maxZ,
                    row.contains("RetractedBaseY") ? row.getInt("RetractedBaseY") : undergroundBaseY(height)));
        }
        if (result.size() != 96) throw new IllegalStateException("Production topology must own 93 generated plus all3 imported towers");
        return result;
    }

    public static BlockPos controllerPosition(BlockPos centre, int half)
    {
        return centre.offset(half + 3, 0, 0);
    }

    public static int undergroundBaseY(int height)
    {
        return 19 - height;
    }

    public static List<BlockPos> externalNegativeAnchors(BlockPos centre, int half)
    {
        int radius = half + 3;
        List<BlockPos> anchors = new ArrayList<>(64);
        for (int sx : new int[] {-1, 1}) for (int sz : new int[] {-1, 1})
            for (int x : new int[] {sx * radius, sx * (radius + 1)})
                for (int z : new int[] {sz * radius, sz * (radius + 1)})
                    for (int y = 21; y <= 24; y++) anchors.add(new BlockPos(centre.getX() + x, y, centre.getZ() + z));
        return anchors;
    }

    private static CompoundTag read(ServerLevel level, BlockPos origin)
    {
        Path path = file(level, origin).toAbsolutePath().normalize();
        if (!Files.isRegularFile(path)) return null;
        try
        {
            long modified = Files.getLastModifiedTime(path).toMillis(), size = Files.size(path);
            Cache cache = CACHE.get(path);
            if (cache == null || cache.modified != modified || cache.size != size)
            {
                CompoundTag tag = NbtIo.readCompressed(path.toFile()).getCompound("data");
                cache = new Cache(modified, size, tag); CACHE.put(path, cache);
            }
            CompoundTag tag = cache.tag;
            if (tag.getInt("Version") != 1 || tag.getLong("Origin") != origin.asLong()
                    || !Tokyo3BuildingWorldIdentityR44.get(level).equals(tag.getString("WorldUUID")))
                throw new IllegalStateException("Foreign/unknown city topology authority; legacy writes inhibited");
            return tag;
        }
        catch (IOException failure)
        {
            // A corrupted ownership marker must not unlock a destructive old
            // generator. Preserve it and require its backed-up explicit recovery.
            throw new IllegalStateException("Cannot read persistent R45 city topology; legacy writes inhibited", failure);
        }
    }

    private record Cache(long modified, long size, CompoundTag tag) {}
    public record Tower(int index, String kind, BlockPos centre, int height, int half, BlockPos core, long[] fixedAnchors,
                        int minX, int maxX, int minZ, int maxZ, int retractedY) {}
}
