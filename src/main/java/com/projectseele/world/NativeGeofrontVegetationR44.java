package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.WorldGenLevel;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.levelgen.placement.PlacedFeature;

/** Native forest/meadow features projected onto the already carved cavern floor. */
final class NativeGeofrontVegetationR44
{
    static void decorate(WorldGenLevel world,GeoFrontBoundedChunkGenerator generator,ChunkPos chunk,
                         RegionalEcologyBiomeSourceR44 source)
    {
        int x=chunk.getMinBlockX(),z=chunk.getMinBlockZ();
        if(!generator.hasEcologicalCavernR44(chunk)||source.reservedBelow(x+8,z+8))return;
        var sampler=world.getLevel().getChunkSource().randomState().sampler();
        Holder<Biome> biome=source.ecologicalBiomeBelow(x+8,z+8,sampler);
        var features=biome.value().getGenerationSettings().features().get(9);
        int index=0;
        for(Holder<PlacedFeature> feature:features)
        {
            long seed=world.getSeed()^chunk.x*341873128712L^chunk.z*132897987541L^index++*0x9e3779b97f4a7c15L;
            NativeEcologyFeatureProtectionR44.place(feature.value(),world,generator,RandomSource.create(seed),
                    new BlockPos(x,generator.ecologicalFloorR44(x,z)+1,z),source,biome);
        }
    }
    private NativeGeofrontVegetationR44(){}
}
