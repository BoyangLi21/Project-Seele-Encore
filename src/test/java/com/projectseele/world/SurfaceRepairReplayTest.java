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
    private static final java.util.Map<String, java.util.Map<Long, int[]>> CARGO_COLUMNS = new HashMap<>();
    public static void main(String[] args) throws Exception
    {
        if (args.length != 2) throw new IllegalArgumentException("candidate actual_world required");
        verifyCargoSweepRegression();
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
            {
                // Surface work below a tower's full movement volume is disjoint,
                // even when it occupies the same XZ chunk. Include the original
                // cargo and every retained matching journey inventory, including
                // AIR cells; checking just the current endpoint is insufficient.
                var columns = cargoColumns(root, rigidFile.getParent().getParent(),
                        recipe.getString("WorldUUID"), tower.index());
                for (BlockPos pos : wanted.keySet())
                {
                    long column = BlockPos.asLong(pos.getX()-tower.centre().getX(), 0,
                            pos.getZ()-tower.centre().getZ());
                    int[] local = columns.get(column);
                    if (local != null && intersectsSweep(pos.getY(), local[0], local[1],
                            tower.centre().getY(), tower.retractedY()))
                        throw new IllegalStateException("Later Cargo swept ownership requires a full replay at " + pos);
                }
            }
        }
    }

    static boolean intersectsSweep(int y, int localMin, int localMax, int raised, int retracted)
    {
        return y >= Math.min(raised, retracted) + localMin
                && y <= Math.max(raised, retracted) + localMax;
    }

    private static void verifyCargoSweepRegression()
    {
        // A basement below both endpoints is safe; an intermediate travel
        // position remains owned even if neither endpoint currently touches it.
        if (intersectsSweep(-559, -3, 40, 80, -120)
                || !intersectsSweep(-123, -3, 40, 80, -120)
                || !intersectsSweep(-60, -3, 40, 80, -120)
                || !intersectsSweep(120, -3, 40, 80, -120)
                || intersectsSweep(121, -3, 40, 80, -120))
            throw new AssertionError("Cargo three-dimensional sweep regression");
        var columns=new HashMap<Long,int[]>();
        for (int y : new int[]{4,-7,2})
        {
            var cell=new CompoundTag();cell.putLong("Pos",new BlockPos(2,y,-3).asLong());
            var cells=new net.minecraft.nbt.ListTag();cells.add(cell);addCargoColumns(columns,cells);
        }
        int[] merged=columns.get(BlockPos.asLong(2,0,-3));
        if (columns.size()!=1 || merged[0]!=-7 || merged[1]!=4)
            throw new AssertionError("Retained journey cargo did not expand ownership");
    }

    private static java.util.Map<Long, int[]> cargoColumns(Path root, Path generation, String world,
                                                          int index) throws Exception
    {
        String key = root.toAbsolutePath().normalize() + "/" + index;
        var cached = CARGO_COLUMNS.get(key);
        if (cached != null) return cached;
        var columns = new HashMap<Long, int[]>();
        CompoundTag cargo = NbtIo.readCompressed(generation.resolve("cargo").resolve(index+".dat").toFile())
                .getCompound("data");
        if (!world.equals(cargo.getString("WorldUUID")) || cargo.getList("Buildings",Tag.TAG_COMPOUND).size()!=1)
            throw new IllegalStateException("Missing/foreign full cargo inventory");
        addCargoColumns(columns,cargo.getList("Buildings",Tag.TAG_COMPOUND).getCompound(0)
                .getList("Cargo",Tag.TAG_COMPOUND));
        Path journals = root.resolve("city_rigid_journal_r45");
        if (Files.isDirectory(journals)) try (var directories = Files.list(journals))
        {
            for (Path directory : directories.filter(Files::isDirectory).toList())
            {
                Path file = directory.resolve(index+".dat");
                if (!Files.isRegularFile(file)) continue;
                CompoundTag plan = NbtIo.readCompressed(file.toFile());
                if (!world.equals(plan.getString("WorldUUID")))
                    throw new IllegalStateException("Foreign retained journey inventory");
                addCargoColumns(columns,plan.getList("Cells",Tag.TAG_COMPOUND));
            }
        }
        CARGO_COLUMNS.put(key,columns);
        return columns;
    }

    private static void addCargoColumns(java.util.Map<Long,int[]> columns, net.minecraft.nbt.ListTag cells)
    {
        if (cells.isEmpty()) throw new IllegalStateException("Unmeasured empty cargo inventory");
        for (Tag raw : cells)
        {
            CompoundTag cell=(CompoundTag)raw;
            if (!cell.contains("Pos",Tag.TAG_LONG)) throw new IllegalStateException("Cargo cell lacks position");
            BlockPos local=BlockPos.of(cell.getLong("Pos"));
            long key=BlockPos.asLong(local.getX(),0,local.getZ());
            int[] bound=columns.computeIfAbsent(key,k->new int[]{local.getY(),local.getY()});
            bound[0]=Math.min(bound[0],local.getY()); bound[1]=Math.max(bound[1],local.getY());
        }
    }
}
