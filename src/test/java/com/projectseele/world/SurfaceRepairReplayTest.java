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
        java.util.List<Path> sources;
        if(Files.isDirectory(candidate.resolve("recipe-replay-expected")))
        {
            try(var files=Files.list(candidate.resolve("recipe-replay-expected")))
            { sources=files.filter(p->p.toString().endsWith(".dat")).sorted().toList(); }
        }
        else sources=java.util.List.of(candidate.resolve("recipe-replay-expected.dat"));
        int chunks = 0, cells = 0, retiredStaticChunks = 0;
        for(Path source:sources)
        {
        CompoundTag expected=NbtIo.readCompressed(source.toFile());
        for (Tag raw : expected.getList("Chunks", Tag.TAG_COMPOUND))
        {
            CompoundTag row = (CompoundTag) raw;
            int x = row.getInt("X"), z = row.getInt("Z");
            String name = x + "_" + z + ".dat";
            CompoundTag surface = NbtIo.readCompressed(candidate.resolve("after").resolve(relative)
                    .resolve("surface").resolve(name).toFile());
            var wanted = new HashMap<BlockPos, CompoundTag>();
            if(expected.getInt("Version")==2)
            {
                int[] offsets=row.getIntArray("Offsets"),states=row.getIntArray("StateIds");
                var sourcePalette=expected.getList("Palette",Tag.TAG_COMPOUND);
                if(offsets.length!=states.length)throw new AssertionError("Truncated replay expectation");
                for(int i=0;i<offsets.length;i++)
                {
                    int offset=offsets[i];
                    if(offset<0||offset>=448*256||states[i]<0||states[i]>=sourcePalette.size())
                        throw new AssertionError("Invalid replay expectation index");
                    wanted.put(new BlockPos(x*16+offset%16,offset/256-128,z*16+(offset/16)%16),sourcePalette.getCompound(states[i]));
                }
            }
            else for (Tag cellRaw : row.getList("Cells", Tag.TAG_COMPOUND))
            {
                CompoundTag cell = (CompoundTag) cellRaw;
                wanted.put(BlockPos.of(cell.getLong("Pos")), cell.getCompound("State"));
            }
            Path rigidFile = world.resolve(relative).resolve("chunks").resolve(name);
            if (Files.exists(rigidFile))
            {
                // Retired frames can retain Static recipes, which production applies BEFORE
                // Surface. Prove that neither later Ground nor ANY cargo footprint can
                // overlap this delta. An intersecting active owner still requires a full replay.
                requireNoLaterOverlap(world.resolve(relative).getParent(), rigidFile, x, z, wanted);
                retiredStaticChunks++;
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
        }
        if (chunks == 0 || cells == 0) throw new AssertionError("No candidate cells replayed");
        System.out.println("Production surface replay: " + chunks + " chunks, " + cells
                + " changed cells; " + retiredStaticChunks
                + " retained Static recipe chunks checked; later Ground/Cargo disjoint");
    }

    private static void requireNoLaterOverlap(Path root, Path rigidFile, int x, int z,
                                              java.util.Map<BlockPos, CompoundTag> wanted) throws Exception
    {
        CompoundTag recipe = NbtIo.readCompressed(rigidFile.toFile());
        CompoundTag topology = null;
        try (var files = Files.newDirectoryStream(root, "projectseele_city_rigid_topology_r45_*.dat"))
        {
            for (Path file : files)
            {
                CompoundTag data = NbtIo.readCompressed(file.toFile()).getCompound("data");
                if (!data.getString("WorldUUID").equals(recipe.getString("WorldUUID"))) continue;
                if (topology != null) throw new IllegalStateException("Ambiguous topology authority");
                topology = data;
            }
        }
        if (topology == null || recipe.getInt("Version") != 1
                || !topology.getString("Stage").equals("INSTALLED")
                || !topology.getString("GenerationFolder").equals(rigidFile.getParent().getParent().getFileName().toString()))
            throw new IllegalStateException("Missing/foreign installed generation authority");
        var towers = CityRigidTopologyR45.towers(topology);
        for (Tag raw : recipe.getList("Ground", Tag.TAG_COMPOUND))
        {
            CompoundTag cell = (CompoundTag) raw;
            if (cell.getInt("Object") < 0 || cell.getInt("Object") >= towers.size())
                throw new IllegalStateException("Foreign ground owner");
            // Include inactive endpoint covers too; this proof does not depend on travel state.
            if (wanted.containsKey(BlockPos.of(cell.getLong("Pos"))))
                throw new IllegalStateException("Later Ground ownership requires a full replay: " + rigidFile);
        }
        for (var tower : towers)
        {
            if (tower.centre().getX() + tower.maxX() >= x * 16
                    && tower.centre().getX() + tower.minX() <= x * 16 + 15
                    && tower.centre().getZ() + tower.maxZ() >= z * 16
                    && tower.centre().getZ() + tower.minZ() <= z * 16 + 15)
                throw new IllegalStateException("Later Cargo ownership requires a full replay: " + rigidFile);
        }
    }
}
