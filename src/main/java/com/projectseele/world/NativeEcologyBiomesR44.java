package com.projectseele.world;

import com.google.gson.*;
import java.util.ArrayList;
import java.util.List;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.core.registries.Registries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.NbtOps;
import net.minecraft.nbt.Tag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.Biomes;
import net.minecraft.world.level.chunk.PalettedContainer;
import net.minecraft.world.level.chunk.storage.ChunkSerializer;
import net.minecraft.world.level.levelgen.Heightmap;

/** Exact native quart-holder migration, serialized by the vanilla biome codec. */
final class NativeEcologyBiomesR44
{
    static String encodeNames(ServerLevel level,JsonArray names)
    {
        var registry=level.registryAccess().registryOrThrow(Registries.BIOME);
        var codec=PalettedContainer.codecRW(registry.asHolderIdMap(),registry.holderByNameCodec(),PalettedContainer.Strategy.SECTION_BIOMES,registry.getHolderOrThrow(Biomes.PLAINS));
        PalettedContainer<Holder<Biome>> container=new PalettedContainer<>(registry.asHolderIdMap(),registry.getHolderOrThrow(Biomes.PLAINS),PalettedContainer.Strategy.SECTION_BIOMES);
        for(int qy=0;qy<4;qy++)for(int qz=0;qz<4;qz++)for(int qx=0;qx<4;qx++)
            container.set(qx,qy,qz,registry.getHolderOrThrow(net.minecraft.resources.ResourceKey.create(Registries.BIOME,new net.minecraft.resources.ResourceLocation(names.get(qy*16+qz*4+qx).getAsString()))));
        return codec.encodeStart(NbtOps.INSTANCE,container).getOrThrow(false,error->{throw new IllegalStateException(error);}).toString();
    }
    static void plan(ServerLevel level,JsonObject tile,List<int[]> surfaceBounds,List<int[]> belowBounds,JsonArray output)
    {
        int cx=tile.get("x").getAsInt(),cz=tile.get("z").getAsInt();boolean below=tile.get("layer").getAsString().equals("geofront");
        var chunk=level.getChunk(cx,cz);var registry=level.registryAccess().registryOrThrow(Registries.BIOME);
        if(!(level.getChunkSource().getGenerator().getBiomeSource() instanceof RegionalEcologyBiomeSourceR44 source))
            throw new IllegalStateException("Quart migration requires the installed measured ecology source");
        var codec=PalettedContainer.codecRW(registry.asHolderIdMap(),registry.holderByNameCodec(),
                PalettedContainer.Strategy.SECTION_BIOMES,registry.getHolderOrThrow(Biomes.PLAINS));
        int[][] soils=new int[4][4];for(int[] row:soils)java.util.Arrays.fill(row,Integer.MIN_VALUE);
        for(int qz=0;qz<4;qz++)for(int qx=0;qx<4;qx++)
        {
            int x=cx*16+qx*4,z=cz*16+qz*4;
            boolean safe=true;for(int[] r:below?belowBounds:surfaceBounds)if(intersects(x,z,x+3,z+3,r))safe=false;
            if(!safe)continue;
            int top=Integer.MIN_VALUE;
            for(int dz=0;dz<4&&safe;dz++)for(int dx=0;dx<4&&safe;dx++)
            {
                int start=below?-430:Math.min(310,level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES,x+dx,z+dz)-1);
                int stop=below?-512:Math.max(60,start-40),soil=Integer.MIN_VALUE;
                for(int y=start;y>=stop;y--)
                    if(level.getBlockState(new BlockPos(x+dx,y,z+dz)).is(net.minecraft.world.level.block.Blocks.GRASS_BLOCK)){soil=y;break;}
                if(soil==Integer.MIN_VALUE){safe=false;break;}
                for(int y=soil-3;y<=soil+24;y++)
                {
                    BlockPos p=new BlockPos(x+dx,y,z+dz);var state=level.getBlockState(p);var name=BuiltInRegistries.BLOCK.getKey(state.getBlock());
                    if(level.getBlockEntity(p)!=null||!state.isAir()&&(!name.getNamespace().equals("minecraft")
                            ||!(name.getPath().equals("grass_block")||name.getPath().equals("dirt")||name.getPath().equals("coarse_dirt")
                            ||name.getPath().equals("rooted_dirt")||name.getPath().equals("podzol")||name.getPath().endsWith("_log")
                            ||name.getPath().endsWith("_leaves")||name.getPath().equals("grass")||name.getPath().equals("tall_grass")
                            ||name.getPath().equals("fern")||name.getPath().equals("large_fern")||name.getPath().equals("dandelion")
                            ||name.getPath().equals("poppy")||name.getPath().equals("cornflower")||name.getPath().equals("snow")
                            ||name.getPath().equals("allium")||name.getPath().equals("azure_bluet")||name.getPath().equals("oxeye_daisy")
                            ||name.getPath().equals("lily_of_the_valley")||name.getPath().endsWith("_tulip")
                            ||name.getPath().equals("brown_mushroom")||name.getPath().equals("red_mushroom"))))
                    {safe=false;break;}
                }
                top=Math.max(top,soil);
            }
            if(safe)soils[qz][qx]=top;
        }
        CompoundTag raw=ChunkSerializer.write(level,chunk);
        var sections=chunk.getSections();for(int sectionIndex=0;sectionIndex<sections.length;sectionIndex++)
        {
            int sy=level.getSectionYFromSectionIndex(sectionIndex);boolean relevant=false;
            for(int[] row:soils)for(int soil:row)if(soil!=Integer.MIN_VALUE&&sy*16<=soil+24&&sy*16+15>=soil-4)relevant=true;
            if(!relevant)continue;
            var old=sections[sectionIndex].getBiomes();
            PalettedContainer<Holder<Biome>> next=new PalettedContainer<>(registry.asHolderIdMap(),registry.getHolderOrThrow(Biomes.PLAINS),PalettedContainer.Strategy.SECTION_BIOMES);
            JsonArray changed=new JsonArray(),beforeNames=new JsonArray(),afterNames=new JsonArray();
            for(int qy=0;qy<4;qy++)for(int qz=0;qz<4;qz++)for(int qx=0;qx<4;qx++)
            {
                Holder<Biome> before=old.get(qx,qy,qz),after=before;int y=sy*16+qy*4,soil=soils[qz][qx];
                String id=before.unwrapKey().orElseThrow().location().toString();
                if(soil!=Integer.MIN_VALUE&&y>=soil-4&&y<=soil+24&&id.equals("projectseele:geofront_surface"))
                    after=below?source.ecologicalBiomeBelow(cx*16+qx*4,cz*16+qz*4,level.getChunkSource().randomState().sampler())
                            :source.ecologicalBiome(cx*16+qx*4,soil,cz*16+qz*4,level.getChunkSource().randomState().sampler());
                next.set(qx,qy,qz,after);beforeNames.add(id);afterNames.add(after.unwrapKey().orElseThrow().location().toString());
                if(!before.equals(after))changed.add(qy*16+qz*4+qx);
            }
            if(changed.isEmpty())continue;
            CompoundTag beforeTag=null;for(Tag t:raw.getList("sections",Tag.TAG_COMPOUND))
            {CompoundTag s=(CompoundTag)t;if(s.getInt("Y")==sy){beforeTag=s.getCompound("biomes").copy();break;}}
            if(beforeTag==null)throw new IllegalStateException("Native biome section was not serialized");
            Tag afterTag=codec.encodeStart(NbtOps.INSTANCE,next).getOrThrow(false,error->{throw new IllegalStateException(error);});
            JsonObject record=new JsonObject();JsonArray position=new JsonArray();position.add(cx);position.add(cz);record.add("chunk",position);
            record.addProperty("section_y",sy);record.addProperty("before_snbt",beforeTag.toString());record.addProperty("after_snbt",afterTag.toString());
            record.add("quart_indices",changed);record.add("before_names",beforeNames);record.add("after_names",afterNames);
            record.addProperty("owner","r44/native_natural_biomes");record.addProperty("layer",below?"geofront":"surface");output.add(record);
        }
    }
    private static boolean intersects(int x0,int z0,int x1,int z1,int[] r){return x0<=r[2]&&x1>=r[0]&&z0<=r[3]&&z1>=r[1];}
    private NativeEcologyBiomesR44(){}
}
