package com.projectseele.world;

import java.util.EnumSet;
import com.mojang.serialization.Lifecycle;
import net.minecraft.SharedConstants;
import net.minecraft.core.BlockPos;
import net.minecraft.core.MappedRegistry;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.core.registries.Registries;
import net.minecraft.data.registries.VanillaRegistries;
import net.minecraft.server.Bootstrap;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.LevelHeightAccessor;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.Biomes;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.chunk.ProtoChunk;
import net.minecraft.world.level.chunk.UpgradeData;
import net.minecraft.world.level.levelgen.Heightmap;

/** Regression for the photographed 125-block water wall; no client or save. */
public final class HakoneSurfaceFieldTest
{
    public static void main(String[] args) throws Exception
    {
        var field = HakoneSurfaceField.sample(2432, 1087, 50);
        if (field == null || field.ground() < -67 || field.ground() > -61
                || field.water() != HakoneSurfaceField.NO_WATER)
            throw new AssertionError("Photographed east boundary is surveyed land, not the legacy ocean");
        var coastGap = HakoneSurfaceField.sample(3148, 1088, 50);
        if (coastGap == null || coastGap.ground() > -60)
            throw new AssertionError("Missing coastal DEM sample became an elevated artificial island");
        SharedConstants.tryDetectVersion();
        var ready = Bootstrap.class.getDeclaredField("isBootstrapped");
        ready.setAccessible(true); ready.setBoolean(null, true);
        BuiltInRegistries.bootStrap();
        for (var block : BuiltInRegistries.BLOCK)
            for (var state : block.getStateDefinition().getPossibleStates()) state.initCache();
        var biome = VanillaRegistries.createLookup().lookupOrThrow(Registries.BIOME).getOrThrow(Biomes.PLAINS);
        var registry = new MappedRegistry<Biome>(Registries.BIOME, Lifecycle.stable());
        registry.register(Biomes.PLAINS, biome.value(), Lifecycle.stable()); registry.freeze();
        var chunk = new ProtoChunk(new ChunkPos(152, 67), UpgradeData.EMPTY,
                LevelHeightAccessor.create(-672, 992), registry, null);
        var p = new BlockPos.MutableBlockPos();
        for (int x = 2432; x < 2448; x++) for (int z = 1072; z < 1088; z++)
            for (int y = -128; y <= 62; y++)
                chunk.setBlockState(p.set(x,y,z), (y <= 50 ? Blocks.STONE : Blocks.WATER).defaultBlockState(), false);
        chunk.setBlockState(new BlockPos(2432,-129,1087), Blocks.GOLD_BLOCK.defaultBlockState(), false);
        Heightmap.primeHeightmaps(chunk, EnumSet.of(Heightmap.Types.WORLD_SURFACE_WG, Heightmap.Types.OCEAN_FLOOR_WG));
        TvWorldPreviewTerrain.shape(chunk);
        for (int x = 2432; x < 2448; x++) for (int z = 1072; z < 1088; z++)
        {
            var target = HakoneSurfaceField.sample(x,z,50);
            if (!chunk.getBlockState(p.set(x,target.ground(),z)).is(Blocks.GRASS_BLOCK))
                throw new AssertionError("Surveyed ground was not installed");
            for (int y = target.ground()+1; y <= 63; y++)
                if (!chunk.getBlockState(p.set(x,y,z)).isAir())
                    throw new AssertionError("Old ocean survived above the surveyed ground");
        }
        if (!chunk.getBlockState(new BlockPos(2432,-129,1087)).is(Blocks.GOLD_BLOCK))
            throw new AssertionError("Surface repair touched the underground");
        System.out.println("Hakone boundary PASS: real land elevation, DEM gap, 256 cleared old-water columns, underground retained");
    }
}
