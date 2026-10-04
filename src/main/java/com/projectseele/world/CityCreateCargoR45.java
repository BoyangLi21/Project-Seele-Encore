package com.projectseele.world;

import java.io.IOException;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.FloatTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.NbtIo;
import net.minecraft.nbt.NbtUtils;
import net.minecraft.nbt.Tag;

/** Pure, lossless cargo adapter; no assembly search, world edits or Create dependency. */
public final class CityCreateCargoR45
{
    private CityCreateCargoR45() {}

    public static Cargo read(Path file, String expectedWorld) throws IOException
    {
        CompoundTag wrapper = NbtIo.readCompressed(file.toFile());
        CompoundTag root = wrapper.getCompound("data");
        require(root.getInt("Version") == 1, "Unknown cargo archive version");
        require(expectedWorld.equals(root.getString("WorldUUID")), "Foreign cargo WorldUUID");
        ListTag buildings = root.getList("Buildings", Tag.TAG_COMPOUND);
        require(buildings.size() == 1, "Exactly one complete tower archive required");
        CompoundTag building = buildings.getCompound(0).copy();
        require(building.contains("FixedStreetCore"), "Unmigrated controller ownership");
        require(building.getInt("Height") > 0 && building.getInt("Half") > 0, "Invalid cargo envelope");
        require(!building.contains("Transaction"), "Prototype requires a settled capture, without an in-flight or historical journal");
        ListTag cells = building.getList("Cargo", Tag.TAG_COMPOUND);
        Set<Long> positions = new HashSet<>();
        int entities = 0;
        for (Tag raw : cells)
        {
            CompoundTag cell = (CompoundTag) raw;
            BlockPos pos = BlockPos.of(cell.getLong("Pos"));
            require(positions.add(pos.asLong()), "Duplicate cargo coordinate");
            require(Math.abs(pos.getX()) <= building.getInt("Half")
                    && Math.abs(pos.getZ()) <= building.getInt("Half")
                    && pos.getY() >= 0 && pos.getY() <= building.getInt("Height") + 3,
                    "Cargo outside measured full envelope");
            require(!building.getBoolean("FixedStreetCore") || !pos.equals(BlockPos.ZERO),
                    "Fixed street core must not become moving cargo");
            require(cell.contains("State", Tag.TAG_COMPOUND), "Missing exact cargo state");
            if (cell.contains("NBT", Tag.TAG_COMPOUND)) entities++;
        }
        require(!cells.isEmpty(), "Empty cargo");
        return new Cargo(building, cells.size(), entities);
    }

    public static CompoundTag pulley(Cargo cargo, BlockPos anchor)
    {
        CompoundTag result = new CompoundTag();
        result.putString("Type", "create:pulley");
        if (!cargo.building.getCompound("R45Footprint").isEmpty() && !cargo.building.getBoolean("FixedStreetCore"))
            result.putBoolean(CityExactShapeUnionR45.MARKER, true);
        result.putInt("InitialOffset", 0);
        result.put("Anchor", NbtUtils.writeBlockPos(anchor));
        CompoundTag blocks = new CompoundTag();
        ListTag palette = new ListTag(), entries = new ListTag();
        Map<CompoundTag, Integer> states = new HashMap<>();
        for (Tag raw : cargo.building.getList("Cargo", Tag.TAG_COMPOUND))
        {
            CompoundTag cell = (CompoundTag) raw;
            CompoundTag state = cell.getCompound("State");
            Integer id = states.get(state);
            if (id == null)
            {
                id = palette.size();
                require(id < 65536, "Create 16-bit palette exceeded");
                states.put(state.copy(), id);
                palette.add(state.copy());
            }
            CompoundTag entry = new CompoundTag();
            entry.putLong("Pos", cell.getLong("Pos"));
            entry.putInt("State", id);
            if (cell.contains("NBT", Tag.TAG_COMPOUND))
            {
                // Full server metadata is the preservation source. Actors,
                // storage transfer and interaction are intentionally not armed
                // in this mechanical transport probe; endpoint ownership is
                // still the original journal, never Create's generic disassembly.
                entry.put("Data", cell.getCompound("NBT").copy());
                entry.put("UpdateTag", cell.getCompound("NBT").copy());
            }
            entries.add(entry);
        }
        blocks.put("Palette", palette);
        blocks.put("BlockList", entries);
        result.put("Blocks", blocks);
        int half = cargo.building.getInt("Half"), height = cargo.building.getInt("Height");
        CompoundTag footprint = cargo.building.getCompound("R45Footprint");
        int minX = footprint.isEmpty() ? -half : footprint.getInt("MinX");
        int maxX = footprint.isEmpty() ? half : footprint.getInt("MaxX");
        int minZ = footprint.isEmpty() ? -half : footprint.getInt("MinZ");
        int maxZ = footprint.isEmpty() ? half : footprint.getInt("MaxZ");
        ListTag bounds = new ListTag();
        for (float value : new float[] {minX, 0, minZ, maxX + 1, height + 4, maxZ + 1})
            bounds.add(FloatTag.valueOf(value));
        result.put("BoundsFront", bounds);
        return result;
    }

    /** Compare complete state/NBT after Create palette renumbering and entity save/load. */
    public static void verify(Cargo cargo, CompoundTag contraption)
    {
        require("create:pulley".equals(contraption.getString("Type")), "Different contraption type");
        CompoundTag blocks = contraption.getCompound("Blocks");
        ListTag palette = blocks.getList("Palette", Tag.TAG_COMPOUND);
        ListTag actual = blocks.getList("BlockList", Tag.TAG_COMPOUND);
        require(actual.size() == cargo.cells, "Create changed cargo count");
        Map<Long, CompoundTag> expected = new HashMap<>();
        for (Tag raw : cargo.building.getList("Cargo", Tag.TAG_COMPOUND))
        {
            CompoundTag cell = (CompoundTag) raw;
            expected.put(cell.getLong("Pos"), cell);
        }
        Set<Long> seen = new HashSet<>();
        for (Tag raw : actual)
        {
            CompoundTag cell = (CompoundTag) raw;
            long pos = cell.getLong("Pos");
            CompoundTag before = expected.get(pos);
            require(before != null && seen.add(pos), "Unknown or duplicate Create cargo coordinate");
            int state = cell.getInt("State");
            require(state >= 0 && state < palette.size() && before.getCompound("State").equals(palette.getCompound(state)),
                    "Create changed exact cargo state at " + BlockPos.of(pos));
            require(before.contains("NBT", Tag.TAG_COMPOUND) == cell.contains("Data", Tag.TAG_COMPOUND),
                    "Create lost/added a cargo block entity");
            if (before.contains("NBT", Tag.TAG_COMPOUND))
                require(before.getCompound("NBT").equals(cell.getCompound("Data")), "Create changed full BE NBT");
        }
    }

    private static void require(boolean passed, String fault)
    {
        if (!passed) throw new IllegalStateException(fault);
    }

    public record Cargo(CompoundTag building, int cells, int blockEntities) {}
}
