package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.saveddata.SavedData;
import net.minecraft.world.phys.Vec3;
import java.util.EnumMap;

/** Offline component migration installs these offsets together with geometry and actor state. */
public final class FacilitySites
{
    public enum Site { UN_BASE, PORT }
    private static final String DATA = "projectseele_facility_sites";

    static final class Locations extends SavedData
    {
        private final EnumMap<Site, BlockPos> offsets = new EnumMap<>(Site.class);

        static Locations load(CompoundTag tag)
        {
            var result = new Locations();
            var saved = tag.getCompound("Offsets");
            for (var site : Site.values())
            {
                int[] xyz = saved.getIntArray(site.name());
                if (xyz.length == 3) result.offsets.put(site, new BlockPos(xyz[0], xyz[1], xyz[2]));
            }
            return result;
        }

        @Override public CompoundTag save(CompoundTag tag)
        {
            var saved = new CompoundTag();
            offsets.forEach((site, pos) -> saved.putIntArray(site.name(), new int[]{pos.getX(), pos.getY(), pos.getZ()}));
            tag.put("Offsets", saved);
            return tag;
        }
    }

    public static BlockPos offset(ServerLevel level, Site site)
    {
        // DataStorage caches this per dimension. No filesystem or geometry scan in tick callers.
        return level.getDataStorage().computeIfAbsent(Locations::load, Locations::new, DATA)
                .offsets.getOrDefault(site, BlockPos.ZERO);
    }

    public static BlockPos un(ServerLevel level, BlockPos original)
    { return original.offset(offset(level, Site.UN_BASE)); }

    public static BlockPos un(ServerLevel level, int x, int y, int z)
    { return un(level, new BlockPos(x, y, z)); }

    public static Vec3 un(ServerLevel level, Vec3 original)
    { return original.add(Vec3.atLowerCornerOf(offset(level, Site.UN_BASE))); }

    public static BlockPos port(ServerLevel level, BlockPos original)
    { return original.offset(offset(level, Site.PORT)); }

    public static Vec3 original(ServerLevel level, Site site, Vec3 position)
    { return position.subtract(Vec3.atLowerCornerOf(offset(level, site))); }

    private FacilitySites() {}
}
