package com.projectseele.world;

import com.google.gson.JsonObject;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Proxy;
import java.util.*;
import java.util.function.Function;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.WorldGenLevel;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.EntityBlock;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.levelgen.feature.Feature;
import net.minecraft.world.level.levelgen.feature.FeaturePlaceContext;
import net.minecraft.world.level.levelgen.feature.ConfiguredFeature;
import net.minecraft.world.level.levelgen.feature.configurations.NoneFeatureConfiguration;
import net.minecraft.world.level.levelgen.placement.PlacedFeature;
import net.minecraft.world.level.levelgen.Heightmap;

/** Real native staging code against a detached controlled backing; never map quality evidence. */
final class NativeEcologyFeatureControlsR44
{
    static JsonObject verify(ServerLevel level)
    {
        var generator=level.getChunkSource().getGenerator();var source=(RegionalEcologyBiomeSourceR44)generator.getBiomeSource();
        List<BlockPos> free=new ArrayList<>();BlockPos origin=new BlockPos(-720,-450,656);
        for(int y=-512;y<=-405&&free.size()<65537;y++)
            for(int z=640;z<688&&free.size()<65537;z++)
                for(int x=-736;x<-688&&free.size()<65537;x++)
                {BlockPos p=new BlockPos(x,y,z);if(source.permitsVegetationAt(p))free.add(p);}
        if(free.size()!=65537)throw new IllegalStateException("Staging budget control lacks a complete permitted native test volume");
        int[] writes={0};BlockPos entityAt=free.get(1);var beState=Blocks.BEEHIVE.defaultBlockState();
        BlockEntity preserved=((EntityBlock)Blocks.BEEHIVE).newBlockEntity(entityAt,beState);
        preserved.getPersistentData().putString("R44NativeStagingOwner","baseline");String fullBefore=preserved.saveWithFullMetadata().toString();
        boolean[] exposeEntity={false},exposeFlower={false},exposeBridgeGround={false};
        var elevated=source.protectedVolumes().stream().filter(b->b.get(1)>80&&!source.reserved(b.get(0),b.get(2))).findFirst().orElseThrow();
        int bridgeX=elevated.get(0),bridgeZ=elevated.get(2),bridgeTop=elevated.get(1);
        WorldGenLevel backing=(WorldGenLevel)Proxy.newProxyInstance(WorldGenLevel.class.getClassLoader(),new Class<?>[]{WorldGenLevel.class},(self,method,args)->
        {
            args=args==null?new Object[0]:args;String n=method.getName();BlockPos at=args.length>0&&args[0] instanceof BlockPos p?p:null;
            if(n.equals("getLevel"))return level;
            if(n.equals("ensureCanWrite"))return true;
            if(n.equals("getBlockState"))
            {
                if(exposeBridgeGround[0]&&at.getX()==bridgeX&&at.getZ()==bridgeZ)
                {
                    if(at.getY()==bridgeTop)return Blocks.BLACK_CONCRETE.defaultBlockState();
                    if(at.getY()==68)return Blocks.GRASS_BLOCK.defaultBlockState();
                }
                return entityAt.equals(at)&&exposeEntity[0]?beState:entityAt.equals(at)&&exposeFlower[0]?Blocks.POPPY.defaultBlockState():Blocks.AIR.defaultBlockState();
            }
            if(n.equals("getHeight")&&exposeBridgeGround[0])return bridgeTop+1;
            if(n.equals("getFluidState"))return Blocks.AIR.defaultBlockState().getFluidState();
            if(n.equals("getBlockEntity"))return exposeEntity[0]&&entityAt.equals(at)?preserved:null;
            if(n.equals("setBlock")){writes[0]++;return true;}
            try{return method.invoke(level,args);}catch(InvocationTargetException error){throw error.getCause();}
        });
        Function<Function<WorldGenLevel,Boolean>,PlacedFeature> fixture=action->new PlacedFeature(Holder.direct(new ConfiguredFeature<>(
                new Feature<NoneFeatureConfiguration>(NoneFeatureConfiguration.CODEC)
                {
                    @Override public boolean place(FeaturePlaceContext<NoneFeatureConfiguration> context){return action.apply(context.level());}
                },NoneFeatureConfiguration.INSTANCE)),List.of());
        PlacedFeature good=fixture.apply(w->{w.setBlock(free.get(0),Blocks.OAK_LOG.defaultBlockState(),2);w.setBlock(free.get(1),Blocks.OAK_LEAVES.defaultBlockState(),2);return true;});
        boolean accepted=NativeEcologyFeatureProtectionR44.place(good,backing,generator,RandomSource.create(1),origin,source,null);
        if(!accepted||writes[0]!=2)throw new IllegalStateException("Native detached staging positive control failed");
        int positiveWrites=writes[0];writes[0]=0;
        PlacedFeature unsuccessful=fixture.apply(w->{w.setBlock(free.get(0),Blocks.OAK_LOG.defaultBlockState(),2);w.setBlock(free.get(1),Blocks.OAK_LEAVES.defaultBlockState(),2);return false;});
        boolean falseRejected=!NativeEcologyFeatureProtectionR44.place(unsuccessful,backing,generator,RandomSource.create(5),origin,source,null);
        if(!falseRejected||writes[0]!=0)throw new IllegalStateException("Native false result after staged writes committed a partial feature");
        var box=source.protectedVolumes().get(0);BlockPos forbidden=new BlockPos(box.get(0),box.get(1),box.get(2));
        PlacedFeature clipped=fixture.apply(w->{w.setBlock(free.get(0),Blocks.OAK_LOG.defaultBlockState(),2);w.setBlock(forbidden,Blocks.OAK_LEAVES.defaultBlockState(),2);return true;});
        // The denied member must remain in the same 3x3 feature neighbourhood.
        BlockPos protectedOrigin=new BlockPos(forbidden.getX(),-450,forbidden.getZ());
        BlockPos below=new BlockPos(forbidden.getX(),-450,forbidden.getZ());
        if(!source.permitsVegetationAt(below))throw new IllegalStateException("Native 3D control requires eligible habitat below the elevated protected road");
        clipped=fixture.apply(w->{w.setBlock(below,Blocks.OAK_LOG.defaultBlockState(),2);w.setBlock(forbidden,Blocks.OAK_LEAVES.defaultBlockState(),2);return true;});
        boolean rejected=!NativeEcologyFeatureProtectionR44.place(clipped,backing,generator,RandomSource.create(2),protectedOrigin,source,null);
        if(!rejected||writes[0]!=0)throw new IllegalStateException("Whole native feature did not reject its protected 3D member atomically");
        exposeEntity[0]=true;
        PlacedFeature nbt=fixture.apply(w->{w.setBlock(free.get(0),Blocks.OAK_LOG.defaultBlockState(),2);w.getBlockEntity(entityAt).getPersistentData().putString("R44NativeStagingOwner","changed-copy");w.setBlock(entityAt,Blocks.OAK_LOG.defaultBlockState(),2);return true;});
        boolean nbtRejected=!NativeEcologyFeatureProtectionR44.place(nbt,backing,generator,RandomSource.create(3),origin,source,null);
        if(!nbtRejected||writes[0]!=0||!fullBefore.equals(preserved.saveWithFullMetadata().toString()))throw new IllegalStateException("Native complete block entity staging isolation failed");
        exposeEntity[0]=false;
        exposeFlower[0]=true;
        PlacedFeature flower=fixture.apply(w->{w.setBlock(free.get(0),Blocks.OAK_LOG.defaultBlockState(),2);w.setBlock(entityAt,Blocks.OAK_LOG.defaultBlockState(),2);return true;});
        boolean flowerRejected=!NativeEcologyFeatureProtectionR44.place(flower,backing,generator,RandomSource.create(6),origin,source,null);
        if(!flowerRejected||writes[0]!=0||!backing.getBlockState(entityAt).is(Blocks.POPPY))throw new IllegalStateException("Native old flower protection committed a partial feature");
        exposeFlower[0]=false;
        exposeBridgeGround[0]=true;
        int[] projectedHeight={Integer.MIN_VALUE};
        PlacedFeature underBridge=fixture.apply(w->{projectedHeight[0]=w.getHeight(Heightmap.Types.MOTION_BLOCKING,bridgeX,bridgeZ);
            w.setBlock(new BlockPos(bridgeX,projectedHeight[0],bridgeZ),Blocks.OAK_LOG.defaultBlockState(),2);return true;});
        boolean underAccepted=NativeEcologyFeatureProtectionR44.place(underBridge,backing,generator,RandomSource.create(7),new BlockPos(bridgeX,69,bridgeZ),source,null);
        if(!underAccepted||projectedHeight[0]!=69||writes[0]!=1)throw new IllegalStateException("Native surface placement used the bridge top instead of the eligible lower natural soil");
        writes[0]=0;exposeBridgeGround[0]=false;
        PlacedFeature budget=fixture.apply(w->{for(BlockPos p:free)w.setBlock(p,Blocks.OAK_LOG.defaultBlockState(),2);return true;});
        boolean budgetFailed=false;
        try{NativeEcologyFeatureProtectionR44.place(budget,backing,generator,RandomSource.create(4),origin,source,null);}
        catch(IllegalStateException error){budgetFailed=error.getMessage().contains("65536 staged cells");}
        if(!budgetFailed||writes[0]!=0)throw new IllegalStateException("Native staging budget failure committed a partial feature");
        JsonObject result=new JsonObject();result.addProperty("passed",true);result.addProperty("native_staging_positive_commits",positiveWrites);
        result.addProperty("control_cases",7);result.addProperty("false_after_staged_write_commits",0);result.addProperty("existing_flower_reject_commits",0);
        result.addProperty("surface_under_bridge_projected_height",projectedHeight[0]);result.addProperty("surface_under_bridge_positive_commits",1);
        result.addProperty("surface_under_bridge_original_heightmap",bridgeTop+1);result.addProperty("surface_under_bridge_real_soil",68);
        result.addProperty("whole_3d_reject_commits",0);result.addProperty("full_nbt_reject_commits",0);result.addProperty("budget_failure_commits",0);
        result.addProperty("complete_original_nbt_unchanged",true);result.addProperty("detached_controlled_backing",true);result.addProperty("world_written",false);
        result.addProperty("actual_future_chunk_generation_verified",false);result.addProperty("protected_volume_count",source.protectedVolumes().size());return result;
    }
    private NativeEcologyFeatureControlsR44(){}
}
