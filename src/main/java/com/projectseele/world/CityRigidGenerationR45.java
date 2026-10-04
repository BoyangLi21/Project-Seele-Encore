package com.projectseele.world;

import com.projectseele.ProjectSeele;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.WeakHashMap;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.NbtIo;
import net.minecraft.nbt.NbtUtils;
import net.minecraft.nbt.Tag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.chunk.ChunkAccess;
import net.minecraft.world.level.chunk.ChunkGenerator;
import net.minecraft.world.level.chunk.ChunkStatus;
import net.minecraftforge.event.level.LevelEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Exact approved future-chunk overlay, bound to its actual level/generator, never FULL repairs. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class CityRigidGenerationR45
{
    private static final Map<ChunkGenerator, Binding> BINDINGS = java.util.Collections.synchronizedMap(new WeakHashMap<>());
    private CityRigidGenerationR45() {}

    @SubscribeEvent
    public static void load(LevelEvent.Load event)
    {
        if (!(event.getLevel() instanceof ServerLevel level) || !level.dimension().equals(FacilitySchemaV2.DIMENSION)) return;
        BlockPos origin = IntegratedNervMapBuilder.tokyo3Origin(level);
        if (!CityRigidTopologyR45.owns(level, origin)) return;
        if (!"INSTALLED".equals(CityRigidTopologyR45.declared(level, origin).getString("Stage"))) return;
        try
        {
            CompoundTag topology = CityRigidTopologyR45.installed(level, origin);
            String folder = topology.getString("GenerationFolder");
            if (folder.isBlank()) throw new IllegalStateException("Installed rigid topology lacks its complete96 future recipe");
            Path root = CityRigidTopologyR45.file(level, origin).getParent().toAbsolutePath().normalize();
            Path directory = root.resolve(folder).normalize();
            if (!directory.startsWith(root)) throw new IllegalStateException("Generation recipe escapes this world/dimension");
            List<CityRigidTopologyR45.Tower> towers = CityRigidTopologyR45.towers(level, origin);
            BINDINGS.put(level.getChunkSource().getGenerator(), new Binding(root, directory, level, origin,
                    topology.getString("WorldUUID"), towers));
        }
        catch (Exception failure) { throw new IllegalStateException("Do not regenerate legacy city terrain under installed ownership", failure); }
    }

    @SubscribeEvent
    public static void unload(LevelEvent.Unload event)
    {
        if (event.getLevel() instanceof ServerLevel level) BINDINGS.remove(level.getChunkSource().getGenerator());
    }

    /** Call after biome decoration, on newly generated chunks only. */
    public static void apply(ChunkGenerator generator, ChunkAccess chunk)
    {
        Binding binding = BINDINGS.get(generator);
        if (binding == null || chunk.getStatus().isOrAfter(ChunkStatus.FULL)) return;
        Path file = binding.recipe.resolve("chunks").resolve(chunk.getPos().x + "_" + chunk.getPos().z + ".dat");
        if (!Files.exists(file)) return;
        try
        {
            CompoundTag data = NbtIo.readCompressed(file.toFile());
            if (data.getInt("Version") != 1 || !binding.world.equals(data.getString("WorldUUID")))
                throw new IllegalStateException("Foreign future-city chunk recipe");
            // Static contains the complete desired mask, including unchanged
            // supports and the declared AIR shaft. Sparse changed-cell patches
            // cannot safely define future generation on their own.
            Path ledgerFile = binding.root.resolve("projectseele_city_rigid_control_r45_" + Long.toUnsignedString(binding.origin.asLong()) + ".dat");
            CompoundTag ledger = Files.isRegularFile(ledgerFile) ? NbtIo.readCompressed(ledgerFile.toFile()).getCompound("data") : new CompoundTag();
            if (!ledger.isEmpty() && !binding.world.equals(ledger.getString("WorldUUID"))) throw new IllegalStateException("Foreign future-cargo ledger");
            int depth = ledger.isEmpty() ? data.getInt("InitialDepth") : ledger.getInt("Depth");
            boolean detached = !ledger.isEmpty() && ledger.getBoolean("WorldTouched") && !ledger.getString("Phase").equals("IDLE");
            var palette = data.getList("Palette", Tag.TAG_COMPOUND);
            BlockState[] statePalette = new BlockState[palette.size()];
            for (int i = 0; i < statePalette.length; i++) statePalette[i] = NbtUtils.readBlockState(BuiltInRegistries.BLOCK.asLookup(), palette.getCompound(i));
            for (Tag raw : data.getList("Static", Tag.TAG_COMPOUND))
            {
                CompoundTag cell = ((CompoundTag) raw).copy();
                if (cell.contains("StateId") && !palette.getCompound(cell.getInt("StateId")).getString("Name").equals("projectseele:retractable_building_core"))
                { write(chunk, cell, statePalette[cell.getInt("StateId")]); continue; }
                if (cell.contains("StateId")) cell.put("State", palette.getCompound(cell.getInt("StateId")).copy());
                if (cell.getCompound("State").getString("Name").equals("projectseele:retractable_building_core"))
                    cell.getCompound("State").getCompound("Properties").putString("armed", Boolean.toString(depth > 0));
                write(chunk, cell);
            }
            if (detached) return; // Source/target chunks are leased during travel; never duplicate held cargo.
            for (Tag raw : data.getList("Ground", Tag.TAG_COMPOUND))
            {
                CompoundTag cell = ((CompoundTag) raw).copy();
                if (depth > 0 || cell.getInt("Object") >= 93)
                { write(chunk, cell, statePalette[cell.getInt("StateId")]); }
            }
            for (int index = 0; index < binding.towers.size(); index++)
            {
                var tower = binding.towers.get(index);
                if (tower.centre().getX() + tower.maxX() < chunk.getPos().getMinBlockX()
                        || tower.centre().getX() + tower.minX() > chunk.getPos().getMaxBlockX()
                        || tower.centre().getZ() + tower.maxZ() < chunk.getPos().getMinBlockZ()
                        || tower.centre().getZ() + tower.minZ() > chunk.getPos().getMaxBlockZ()) continue;
                Path cargoFile = binding.recipe.resolve("cargo").resolve(index + ".dat");
                CompoundTag cargo = NbtIo.readCompressed(cargoFile.toFile()).getCompound("data");
                if (!binding.world.equals(cargo.getString("WorldUUID"))) throw new IllegalStateException("Foreign future full cargo");
                CompoundTag building = cargo.getList("Buildings", Tag.TAG_COMPOUND).getCompound(0);
                // After a completed trip, use its immutable last observed full
                // cells rather than restoring an older install inventory.
                if (!ledger.isEmpty() && ledger.getInt("SavedPlans") == 96)
                {
                    Path journal = binding.root.resolve("city_rigid_journal_r45").resolve(ledger.getUUID("Journey").toString()).resolve(index + ".dat");
                    CompoundTag plan = NbtIo.readCompressed(journal.toFile());
                    if (!binding.world.equals(plan.getString("WorldUUID"))) throw new IllegalStateException("Foreign future journey cargo");
                    List<CompoundTag> converted = new java.util.ArrayList<>();
                    for (Tag raw : plan.getList("Cells", Tag.TAG_COMPOUND))
                    {
                        CompoundTag value = ((CompoundTag) raw).copy();
                        if (value.contains("Data")) value.put("NBT", value.getCompound("Data").copy());
                        converted.add(value);
                    }
                    net.minecraft.nbt.ListTag cells = new net.minecraft.nbt.ListTag(); cells.addAll(converted); building.put("Cargo", cells);
                }
                int base = depth == 0 ? tower.centre().getY() : tower.retractedY();
                for (Tag raw : building.getList("Cargo", Tag.TAG_COMPOUND))
                {
                    CompoundTag cell = (CompoundTag) raw; BlockPos local = BlockPos.of(cell.getLong("Pos"));
                    BlockPos pos = new BlockPos(tower.centre().getX() + local.getX(), base + local.getY(), tower.centre().getZ() + local.getZ());
                    if ((pos.getX() >> 4) != chunk.getPos().x || (pos.getZ() >> 4) != chunk.getPos().z) continue;
                    CompoundTag value = cell.copy(); value.putLong("Pos", pos.asLong()); write(chunk, value);
                }
            }
            chunk.setUnsaved(true);
        }
        catch (Exception failure) { throw new IllegalStateException("Failed exact future96 topology/cargo; no legacy generation fallback", failure); }
    }

    private static void write(ChunkAccess chunk, CompoundTag cell)
    {
        write(chunk, cell, NbtUtils.readBlockState(BuiltInRegistries.BLOCK.asLookup(), cell.getCompound("State")));
    }

    private static void write(ChunkAccess chunk, CompoundTag cell, BlockState state)
    {
        BlockPos pos = BlockPos.of(cell.getLong("Pos"));
        if ((pos.getX() >> 4) != chunk.getPos().x || (pos.getZ() >> 4) != chunk.getPos().z) throw new IllegalStateException("Future shard crosses chunk identity");
        chunk.removeBlockEntity(pos);
        chunk.setBlockState(pos, state, false);
        if (cell.contains("NBT", Tag.TAG_COMPOUND))
        {
            CompoundTag nbt = cell.getCompound("NBT").copy(); nbt.putInt("x", pos.getX()); nbt.putInt("y", pos.getY()); nbt.putInt("z", pos.getZ());
            chunk.setBlockEntityNbt(nbt);
        }
    }

    private record Binding(Path root, Path recipe, ServerLevel level, BlockPos origin, String world, List<CityRigidTopologyR45.Tower> towers) {}
}
