package com.projectseele.world;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.NbtIo;
import net.minecraft.nbt.Tag;

/** Execute the production span consumer against the exact candidate delta. */
public final class SurfaceRepairReplayTest
{
    public static void main(String[] args) throws Exception
    {
        if (args.length != 2) throw new IllegalArgumentException("candidate actual_world required");
        Path candidate = Path.of(args[0]), world = Path.of(args[1]);
        Path relative = Path.of("dimensions/projectseele/geofront/data/city_rigid_generation_r45");
        CompoundTag expected = NbtIo.readCompressed(candidate.resolve("recipe-replay-expected.dat").toFile());
        int chunks = 0, cells = 0;
        for (Tag raw : expected.getList("Chunks", Tag.TAG_COMPOUND))
        {
            CompoundTag row = (CompoundTag) raw;
            int x = row.getInt("X"), z = row.getInt("Z");
            String name = x + "_" + z + ".dat";
            // Surface is the final production stage only in these street chunks.
            // An active rigid recipe needs the complete Ground/Cargo replay.
            if (Files.exists(world.resolve(relative).resolve("chunks").resolve(name)))
                throw new IllegalStateException("Later rigid ownership requires a full replay: " + name);
            CompoundTag surface = NbtIo.readCompressed(candidate.resolve("after").resolve(relative)
                    .resolve("surface").resolve(name).toFile());
            var wanted = new HashMap<BlockPos, CompoundTag>();
            for (Tag cellRaw : row.getList("Cells", Tag.TAG_COMPOUND))
            {
                CompoundTag cell = (CompoundTag) cellRaw;
                wanted.put(BlockPos.of(cell.getLong("Pos")), cell.getCompound("State"));
            }
            var actual = new HashMap<BlockPos, Integer>();
            CityRigidGenerationR45.visitSurfaceSpans(surface, x, z, -1344, 320,
                    (pos, state) -> { if (wanted.containsKey(pos)) actual.put(pos, state); });
            var palette = surface.getList("Palette", Tag.TAG_COMPOUND);
            for (var cell : wanted.entrySet())
            {
                Integer state = actual.get(cell.getKey());
                if (state == null || !palette.getCompound(state).equals(cell.getValue()))
                    throw new AssertionError("Future surface differs at " + cell.getKey());
            }
            chunks++; cells += wanted.size();
        }
        if (chunks == 0 || cells == 0) throw new AssertionError("No candidate cells replayed");
        System.out.println("Production surface replay: " + chunks + " chunks, " + cells
                + " changed cells; no later Ground/Cargo recipes in this batch");
    }
}
