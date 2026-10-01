package com.projectseele.world;

import java.lang.reflect.InvocationHandler;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Proxy;
import java.util.*;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.WorldGenLevel;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.block.EntityBlock;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.chunk.ChunkGenerator;
import net.minecraft.world.level.chunk.LevelChunk;
import net.minecraft.world.level.levelgen.placement.PlacedFeature;
import net.minecraft.world.level.levelgen.Heightmap;
import java.util.function.Function;

/** Every native surface/cavern feature is staged before one complete protection decision. */
public final class NativeEcologyFeatureProtectionR44
{
    private static final int CELL_LIMIT=65536,SCRATCH_LIMIT=16;
    private static final Set<String> SOIL=Set.of("grass_block","dirt","coarse_dirt","rooted_dirt","podzol","mud","mycelium","sand","gravel");
    private static final Set<String> PLANTS=Set.of("grass","tall_grass","fern","large_fern","dandelion","poppy","allium","azure_bluet","oxeye_daisy","cornflower",
            "lily_of_the_valley","brown_mushroom","red_mushroom","dead_bush","snow");
    public static synchronized boolean place(PlacedFeature feature,WorldGenLevel world,ChunkGenerator generator,
            RandomSource random,BlockPos origin,RegionalEcologyBiomeSourceR44 source,Holder<Biome> cavernBiome)
    {
        Map<BlockPos,BlockState> pending=new LinkedHashMap<>(),baseline=new HashMap<>();
        Map<BlockPos,BlockEntity> entities=new HashMap<>();Map<Long,LevelChunk> scratch=new HashMap<>();
        boolean[] blocked={false};ChunkPos centre=new ChunkPos(origin);
        class Layer
        {
            void measured(BlockPos p)
            {
                if(p==null||Math.abs((p.getX()>>4)-centre.x)>1||Math.abs((p.getZ()>>4)-centre.z)>1)throw new Clipped();
            }
            BlockState read(BlockPos p){measured(p);return pending.getOrDefault(p,world.getBlockState(p));}
            boolean allowed(BlockPos p)
            {
                measured(p);
                if(!source.permitsVegetationAt(p)||!world.ensureCanWrite(p))return false;
                if(cavernBiome!=null)
                {
                    var bounded=(GeoFrontBoundedChunkGenerator)generator;
                    int floor=bounded.ecologicalFloorR44(p.getX(),p.getZ()),roof=bounded.ecologicalRoofR44(p.getX(),p.getZ());
                    return p.getY()>=floor-3&&p.getY()<=floor+28&&p.getY()<roof-4&&!bounded.ecologicalLakeR44(p.getX(),p.getZ());
                }
                return true;
            }
            boolean write(BlockPos p,BlockState state)
            {
                BlockState old=read(p);
                if(!allowed(p)||!naturalSource(old)||world.getBlockEntity(p)!=null
                        ||!pending.containsKey(p)&&protectedExistingPlant(old))
                {blocked[0]=true;return false;}
                if(!pending.containsKey(p)&&pending.size()>=CELL_LIMIT)throw new IllegalStateException("Future native ecology feature exceeded 65536 staged cells; no feature cell committed");
                BlockPos key=p.immutable();baseline.putIfAbsent(key,world.getBlockState(key));pending.put(key,state);
                if(state.hasBlockEntity())
                {
                    BlockEntity copy=((EntityBlock)state.getBlock()).newBlockEntity(key,state);
                    if(copy==null)throw new IllegalStateException("Future native feature block entity cannot be staged");
                    entities.put(key,copy);
                }
                else entities.remove(key);
                return true;
            }
            BlockEntity entity(BlockPos p)
            {
                measured(p);if(entities.containsKey(p))return entities.get(p);
                BlockState state=read(p);if(!state.hasBlockEntity())return null;
                BlockEntity actual=world.getBlockEntity(p);
                BlockEntity copy=actual==null?((EntityBlock)state.getBlock()).newBlockEntity(p,state)
                        :BlockEntity.loadStatic(p,state,actual.saveWithFullMetadata().copy());
                if(copy==null){blocked[0]=true;return null;}entities.put(p.immutable(),copy);return copy;
            }
        }
        Layer layer=new Layer();
        WorldGenLevel proxy=(WorldGenLevel)Proxy.newProxyInstance(WorldGenLevel.class.getClassLoader(),new Class<?>[]{WorldGenLevel.class},(self,method,args)->
        {
            args=args==null?new Object[0]:args;String name=method.getName();BlockPos at=args.length>0&&args[0] instanceof BlockPos p?p:null;
            if(name.equals("getLevel"))return world.getLevel();
            if(cavernBiome!=null&&(name.equals("getBiome")||name.equals("getNoiseBiome")))return cavernBiome;
            if(name.equals("getBlockState"))return layer.read(at);
            if(name.equals("getFluidState"))return layer.read(at).getFluidState();
            if(name.equals("getBlockEntity")&&args.length==1)return layer.entity(at);
            if(name.equals("ensureCanWrite")){boolean safe=layer.allowed(at);if(!safe)blocked[0]=true;return safe;}
            if(name.equals("setBlock"))return layer.write(at,(BlockState)args[1]);
            if(name.equals("getHeight"))
            {
                if(args.length==3&&args[0] instanceof net.minecraft.world.level.levelgen.Heightmap.Types)
                {
                    int x=(Integer)args[1],z=(Integer)args[2];layer.measured(new BlockPos(x,origin.getY(),z));
                    int floor=cavernBiome!=null?((GeoFrontBoundedChunkGenerator)generator).ecologicalFloorR44(x,z)
                            :surfaceGround(x,z,world.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES,x,z)-1,layer::read,source);
                    return floor==Integer.MIN_VALUE?world.getMinBuildHeight():floor+1;
                }
            }
            if(name.equals("getChunk")&&args.length>0&&(at!=null||args.length>=2&&args[0] instanceof Integer&&args[1] instanceof Integer))
            {
                int cx=at!=null?at.getX()>>4:(Integer)args[0],cz=at!=null?at.getZ()>>4:(Integer)args[1];layer.measured(new BlockPos(cx*16,origin.getY(),cz*16));
                long key=((long)cx<<32)^(cz&0xffffffffL);
                if(!scratch.containsKey(key)&&scratch.size()>=SCRATCH_LIMIT)throw new IllegalStateException("Future native feature exceeded 16 detached chunks; no feature cell committed");
                return scratch.computeIfAbsent(key,k->new LevelChunk(world.getLevel(),new ChunkPos(cx,cz))
                {
                    @Override public BlockState getBlockState(BlockPos p){return layer.read(p);}
                    @Override public net.minecraft.world.level.material.FluidState getFluidState(BlockPos p){return layer.read(p).getFluidState();}
                    @Override public BlockEntity getBlockEntity(BlockPos p){return layer.entity(p);}
                    @Override public BlockState setBlockState(BlockPos p,BlockState state,boolean moving){BlockState old=layer.read(p);return layer.write(p,state)?old:null;}
                    @Override public void setBlockEntity(BlockEntity entity){throw new Clipped();}
                    @Override public void removeBlockEntity(BlockPos p){throw new Clipped();}
                });
            }
            if(name.equals("addFreshEntity")||name.equals("destroyBlock")||name.equals("removeBlock")||name.equals("setBlockEntity")||name.equals("removeBlockEntity"))throw new Clipped();
            if(name.equals("setCurrentlyGenerating")||name.equals("scheduleTick")||name.equals("blockUpdated")||name.equals("levelEvent")||name.equals("gameEvent"))return null;
            if(method.isDefault())return InvocationHandler.invokeDefault(self,method,args);
            try{return method.invoke(world,args);}catch(InvocationTargetException error){throw error.getCause();}
        });
        try
        {
            boolean placed=feature.placeWithBiomeCheck(proxy,generator,random,origin);
            if(!acceptsCompletedFeature(placed,blocked[0]))return false;
            for(var entry:baseline.entrySet())if(!entry.getValue().equals(world.getBlockState(entry.getKey()))||world.getBlockEntity(entry.getKey())!=null)return false;
            for(var entry:pending.entrySet())
            {
                BlockPos p=entry.getKey();BlockState state=entry.getValue();
                if(state.equals(baseline.get(p)))continue;
                world.setBlock(p,state,2|16);
                if(state.hasBlockEntity())
                {
                    BlockEntity actual=world.getBlockEntity(p);if(actual==null)throw new IllegalStateException("Native ecology new block entity missing after commit");
                    actual.load(entities.get(p).saveWithFullMetadata().copy());actual.setChanged();
                }
            }
            return true;
        }
        catch(Clipped ignored){return false;}
    }
    public static boolean acceptsCompletedFeature(boolean placed,boolean rejected){return placed&&!rejected;}
    public static int surfaceGround(int x,int z,int top,Function<BlockPos,BlockState> reader,RegionalEcologyBiomeSourceR44 source)
    {
        if(source.reserved(x,z))return Integer.MIN_VALUE;
        BlockPos.MutableBlockPos point=new BlockPos.MutableBlockPos(x,0,z);
        for(int y=Math.min(310,top);y>=60;y--)
        {
            point.setY(y);BlockState state=reader.apply(point);var id=BuiltInRegistries.BLOCK.getKey(state.getBlock());
            if(id.getNamespace().equals("minecraft")&&SOIL.contains(id.getPath())&&source.permitsVegetationAt(point))return y;
        }
        return Integer.MIN_VALUE;
    }
    public static boolean naturalSource(BlockState state)
    {
        if(state.isAir())return true;var id=BuiltInRegistries.BLOCK.getKey(state.getBlock());String n=id.getPath();
        return id.getNamespace().equals("minecraft")&&(SOIL.contains(n)||PLANTS.contains(n)||n.endsWith("_leaves")||n.endsWith("_log")||n.endsWith("_tulip"));
    }
    public static boolean protectedExistingPlant(BlockState state)
    {
        String id=BuiltInRegistries.BLOCK.getKey(state.getBlock()).getPath();
        return id.endsWith("_log")||id.endsWith("_leaves")||id.endsWith("_tulip")
                ||PLANTS.contains(id)&&!id.equals("grass")&&!id.equals("tall_grass")&&!id.equals("snow");
    }
    private static final class Clipped extends RuntimeException{}
    private NativeEcologyFeatureProtectionR44(){}
}
