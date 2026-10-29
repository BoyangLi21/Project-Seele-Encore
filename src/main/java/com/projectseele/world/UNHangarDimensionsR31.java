package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.AABB;
import java.nio.file.Files;
import java.util.Map;
import java.util.WeakHashMap;

/** World marker owns the migrated gate and liquid envelope, not the airframe model. */
public final class UNHangarDimensionsR31
{
    private static final Map<ServerLevel, Boolean> INSTALLED = new WeakHashMap<>();

    public static boolean active(ServerLevel level)
    {
        return INSTALLED.computeIfAbsent(level, key -> Files.isRegularFile(
                level.getServer().getWorldPath(LevelResource.ROOT).resolve("un_hangars_r31.json")));
    }

    public static int width(ServerLevel level) { return active(level) ? 49 : 33; }
    public static int layer(ServerLevel level) { return width(level) * 90; }
    public static int total(ServerLevel level) { return layer(level) * 44; }
    private static int centre(int serial) { return serial == 1 ? 6282 : 6442; }
    public static BlockPos minimum(ServerLevel level, int serial)
    { return FacilitySites.un(level, centre(serial) - width(level) / 2, 77, -6226); }
    public static BlockPos maximum(ServerLevel level, int serial)
    { return FacilitySites.un(level, centre(serial) + width(level) / 2, 120, -6137); }
    public static AABB pit(ServerLevel level, int serial)
    { return new AABB(minimum(level, serial), maximum(level, serial).offset(1, 1, 1)); }
    public static AABB sweep(ServerLevel level, int serial)
    {
        int x = centre(serial);
        var bounds = active(level) ? new AABB(x-25,77,-6137,x+26,160,-6132)
                : new AABB(x-34,77,-6137,x+36,142,-6134);
        return bounds.move(FacilitySites.offset(level, FacilitySites.Site.UN_BASE));
    }

    private UNHangarDimensionsR31() {}
}
