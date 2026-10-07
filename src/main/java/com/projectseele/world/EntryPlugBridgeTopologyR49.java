package com.projectseele.world;

import com.projectseele.registry.ModBlocks;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.StairBlock;
import net.minecraft.world.level.block.SlabBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.Half;
import net.minecraft.world.level.block.state.properties.StairsShape;
import net.minecraft.world.level.block.state.properties.SlabType;
import net.minecraft.world.phys.AABB;
import java.util.*;

/** Finite retractable through galleries and two one-metre boarding stairways. */
final class EntryPlugBridgeTopologyR49
{
    static boolean panel(int x,int z)
    {
        int side=Math.abs(x);
        return z>=19&&z<=21&&side<=16
                ||z>=14&&z<=24&&side>=3&&side<=6
                ||(z==14||z==15||z==23||z==24)&&side>=3&&side<=16
                ||z>=16&&z<=18&&side==2;
    }
    private static int threshold(int z){return Math.min(9,25-z);}
    private static BlockState stair()
    {
        return Blocks.POLISHED_ANDESITE_STAIRS.defaultBlockState().setValue(StairBlock.FACING,Direction.NORTH)
                .setValue(StairBlock.HALF,Half.BOTTOM).setValue(StairBlock.SHAPE,StairsShape.STRAIGHT)
                .setValue(StairBlock.WATERLOGGED,false);
    }
    private static BlockState halfStep()
    {return Blocks.POLISHED_ANDESITE_SLAB.defaultBlockState().setValue(SlabBlock.TYPE,SlabType.BOTTOM).setValue(SlabBlock.WATERLOGGED,false);}
    private static boolean upper(int x,int z){return Math.abs(x)==2&&z>=16&&z<=18;}
    private static boolean floorOwned(BlockState s)
    {return s.isAir()||s.is(ModBlocks.ENTRY_PLUG_BRIDGE_DECK_R48.get());}
    private static boolean guardOwned(BlockState s)
    {return s.isAir()||s.is(Blocks.LIGHT)||s.is(ModBlocks.NERV_EDGE_RAIL.get())||s.is(ModBlocks.ENTRY_PLUG_BRIDGE_GUARD_R48.get());}
    private static boolean upperOwned(BlockState s,int z)
    {return s.isAir()||s.is(ModBlocks.ENTRY_PLUG_BRIDGE_GUARD_R48.get())||s.is(ModBlocks.NERV_EDGE_RAIL.get())
            ||(z==18?s.equals(halfStep()):z==17?s.equals(stair()):s.is(ModBlocks.ENTRY_PLUG_BRIDGE_DECK_R48.get()));}
    private static boolean sturdy(ServerLevel level,Map<BlockPos,BlockState> cells,BlockPos p)
    {return cells.getOrDefault(p,level.getBlockState(p)).isFaceSturdy(level,p,Direction.UP);}

    private static Map<BlockPos,BlockState> wanted(ServerLevel level,BlockPos bed,int amount)
    {
        var cells=new LinkedHashMap<BlockPos,BlockState>();
        for(int x=-16;x<=16;x++)for(int z=14;z<=24;z++)
            cells.put(bed.offset(x,48,z),panel(x,z)&&amount>=threshold(z)?ModBlocks.ENTRY_PLUG_BRIDGE_DECK_R48.get().defaultBlockState():Blocks.AIR.defaultBlockState());
        for(int x:new int[]{-2,2})for(int z=16;z<=18;z++)
            cells.put(bed.offset(x,49,z),amount==9?(z==18?halfStep():z==17?stair():ModBlocks.ENTRY_PLUG_BRIDGE_DECK_R48.get().defaultBlockState()):Blocks.AIR.defaultBlockState());
        for(int x=-19;x<=19;x++)for(int z=14;z<=24;z++)
        {
            var floor=bed.offset(x,48,z);var at=floor.above();
            if(PilotRestroomsR47.ownsRoomMaintenanceSpaceR47(level,at)||upper(x,z)&&amount==9)continue;
            var actual=level.getBlockState(at);if(!guardOwned(actual)&&!upper(x,z))continue;
            var next=cells.getOrDefault(floor,level.getBlockState(floor));
            if(!sturdy(level,cells,floor))
            {cells.put(at,actual.is(Blocks.LIGHT)?actual:Blocks.AIR.defaultBlockState());continue;}
            var guard=FacilityEdgeRailR41.empty(ModBlocks.ENTRY_PLUG_BRIDGE_GUARD_R48.get());boolean edge=false;
            for(var direction:Direction.Plane.HORIZONTAL)
            {
                boolean exposed=!sturdy(level,cells,floor.relative(direction));
                guard=guard.setValue(FacilityEdgeRailR41.side(direction),exposed);edge|=exposed;
                if(next.is(ModBlocks.ENTRY_PLUG_BRIDGE_DECK_R48.get()))next=next.setValue(FacilityEdgeRailR41.side(direction),exposed);
            }
            if(cells.containsKey(floor))cells.put(floor,next);
            cells.put(at,edge?guard:actual.is(Blocks.LIGHT)?actual:Blocks.AIR.defaultBlockState());
        }
        // Both stair mouths stay open north/south. Upper side rails are at
        // the landing height; the old lower guard must not fence the ascent.
        for(int x:new int[]{-2,2})for(int z=16;z<=18;z++)
        {
            var p=bed.offset(x,49,z);var at=p.above();
            if(amount!=9){cells.put(at,Blocks.AIR.defaultBlockState());continue;}
            var flags=FacilityEdgeRailR41.empty(ModBlocks.ENTRY_PLUG_BRIDGE_GUARD_R48.get())
                    .setValue(FacilityEdgeRailR41.WEST,true).setValue(FacilityEdgeRailR41.EAST,true)
                    .setValue(FacilityEdgeRailR41.NORTH,z==16);
            cells.put(at,flags);
            if(z==16)
            {
                var deck=FacilityEdgeRailR41.empty(ModBlocks.ENTRY_PLUG_BRIDGE_DECK_R48.get())
                        .setValue(FacilityEdgeRailR41.WEST,true).setValue(FacilityEdgeRailR41.EAST,true)
                        .setValue(FacilityEdgeRailR41.NORTH,z==16);
                cells.put(p,deck);
            }
        }
        return cells;
    }

    private static Optional<String> geometryFault(ServerLevel level,BlockPos bed)
    {
        for(int cx=(bed.getX()-19)>>4;cx<=(bed.getX()+19)>>4;cx++)
            for(int cz=(bed.getZ()+14)>>4;cz<=(bed.getZ()+24)>>4;cz++)
                if(!level.hasChunk(cx,cz)||!level.areEntitiesLoaded(net.minecraft.world.level.ChunkPos.asLong(cx,cz)))
                    return Optional.of("R49贯穿后桥实体段未加载，暂停撤收。");
        for(int x=-16;x<=16;x++)for(int z=14;z<=24;z++)
        {
            var p=bed.offset(x,48,z);
            if(level.getBlockEntity(p)!=null||!floorOwned(level.getBlockState(p)))return Optional.of("R49后桥完整桥面存在人工/设备改动："+p.toShortString());
        }
        for(int x=-19;x<=19;x++)for(int z=14;z<=24;z++)
        {
            var p=bed.offset(x,49,z);
            if(PilotRestroomsR47.ownsRoomMaintenanceSpaceR47(level,p))continue;
            if(level.getBlockEntity(p)!=null||(upper(x,z)?!upperOwned(level.getBlockState(p),z):!guardOwned(level.getBlockState(p))))
                return Optional.of("R49后桥围护/楼梯存在未知改动："+p.toShortString());
        }
        for(int x:new int[]{-2,2})for(int z=16;z<=18;z++)
        {
            var p=bed.offset(x,50,z);
            if(level.getBlockEntity(p)!=null||!guardOwned(level.getBlockState(p)))return Optional.of("R49上舱楼梯护栏存在设备/人工改动："+p.toShortString());
        }
        for(int amount=0;amount<=9;amount++)
        {
            var map=wanted(level,bed,amount);
            if(map.entrySet().stream().allMatch(e->level.getBlockState(e.getKey()).equals(e.getValue())))return Optional.empty();
        }
        return Optional.of("R49双侧贯穿桥/上舱阶梯非同一撤收段，保留原状态。");
    }
    static Optional<String> fault(ServerLevel level,int variant)
    {
        if(variant<0||variant>2)return Optional.of("R49后桥编号无效。");
        var bed=EvaLogisticsDirector.assignedHangarBedR33(level,variant);
        if(!bed.equals(new BlockPos(-12+42*variant,-443,-240)))return Optional.of("R49后桥原机床身份不符。");
        var geometry=geometryFault(level,bed);if(geometry.isPresent())return geometry;
        var fleet=EvaFleetSavedData.get(level.getServer()).entry(variant).orElse(null);
        if(fleet==null||fleet.entryPlugId()==null)return Optional.of("R49原机/原栓身份未加载。");
        var bounds=new AABB(bed.getX()-16,-394,bed.getZ()+14,bed.getX()+17,-389,bed.getZ()+25);
        for(var actor:level.getEntities((net.minecraft.world.entity.Entity)null,bounds,e->e.isAlive()&&!e.isSpectator()))
        {
            var root=actor.getRootVehicle().getUUID();
            if(actor.getUUID().equals(fleet.canonicalId())||actor.getUUID().equals(fleet.entryPlugId())
                    ||root.equals(fleet.canonicalId())||root.equals(fleet.entryPlugId()))continue;
            if(actor instanceof net.minecraft.world.entity.decoration.ArmorStand stand&&stand.isMarker())continue;
            if(actor instanceof net.minecraft.world.entity.LivingEntity||actor.canBeCollidedWith())
                return Optional.of("R49后桥/上舱阶梯仍有人或载具："+actor.getName().getString());
        }
        return Optional.empty();
    }
    static boolean apply(ServerLevel level,BlockPos bed,int extension)
    {
        var failure=fault(level,(bed.getX()+12)/42);if(failure.isPresent())return false;
        int amount=Math.max(0,Math.min(9,extension));var desired=wanted(level,bed,amount);
        desired.forEach((p,s)->{if(!level.getBlockState(p).equals(s))level.setBlock(p,s,2);});
        return true;
    }
    private EntryPlugBridgeTopologyR49() { }
}
