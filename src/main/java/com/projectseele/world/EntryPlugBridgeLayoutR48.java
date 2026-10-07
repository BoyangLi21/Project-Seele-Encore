package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.registry.ModBlocks;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.storage.LevelResource;
import java.nio.file.Files;
import java.util.*;

/** Installed rear bridge: three-metre crosswalk plus two short capsule-side branches. */
public final class EntryPlugBridgeLayoutR48
{
    private static final Map<ServerLevel,Boolean> ENABLED=new WeakHashMap<>();
    private static final Set<ServerLevel> THROUGH_R49=Collections.newSetFromMap(new WeakHashMap<>());
    public static boolean enabled(ServerLevel level)
    {
        if(!level.dimension().equals(FacilitySchemaV2.DIMENSION))return false;
        return ENABLED.computeIfAbsent(level,l->{
            var path=l.getServer().getWorldPath(LevelResource.ROOT).resolve("r48_entry_plug_bridge.json");
            if(!Files.isRegularFile(path))return false;
            try
            {
                var d=JsonParser.parseString(Files.readString(path)).getAsJsonObject();
                if(d.get("schema").getAsInt()!=48||!d.get("installed").getAsBoolean())return false;
                String layout=d.get("layout").getAsString();
                if(layout.equals("rear_crosswalk_19_21_through_sides_14_24_boarding_stairs_r49"))
                {
                    if(!d.has("topology_revision")||d.get("topology_revision").getAsInt()!=49)return false;
                    THROUGH_R49.add(l);return true;
                }
                return layout.equals("rear_crosswalk_19_21_capsule_branches_16_18");
            }
            catch(Exception failure){ProjectSeele.LOGGER.error("R48 rear bridge installation record rejected",failure);return false;}
        });
    }
    public static boolean panel(int x,int z)
    {
        int side=Math.abs(x);
        return z>=19&&z<=21&&side<=16
                ||z>=16&&z<=17&&side>=3&&side<=6
                ||z==18&&side>=2&&side<=6;
    }
    private static boolean knownFloor(BlockState state)
    {
        return state.isAir()||state.is(ModBlocks.NERV_MACHINE_PANEL.get())||state.is(ModBlocks.NERV_MACHINE_EDGE.get())
                ||state.is(ModBlocks.ENTRY_PLUG_BRIDGE_DECK_R48.get());
    }
    private static boolean knownGuard(BlockState state)
    {return state.isAir()||state.is(Blocks.LIGHT)||state.is(ModBlocks.NERV_EDGE_RAIL.get())||state.is(ModBlocks.ENTRY_PLUG_BRIDGE_GUARD_R48.get());}
    /** Read-only whole rear component check; source mismatch/absent entity sections cannot grant motion. */
    public static Optional<String> retractionFaultR48(ServerLevel level,int variant)
    {
        if(!enabled(level))return Optional.empty();
        if(THROUGH_R49.contains(level))return EntryPlugBridgeTopologyR49.fault(level,variant);
        if(variant<0||variant>2)return Optional.of("原后桥编号无效。");
        var bed=EvaLogisticsDirector.assignedHangarBedR33(level,variant);
        if(bed.getX()!=-12+42*variant||bed.getY()!=-443||bed.getZ()!=-240)
            return Optional.of("后桥不属于当前原机床，未操作其他布局。");
        for(int x=(bed.getX()-16)>>4;x<=(bed.getX()+16)>>4;x++)
            for(int z=(bed.getZ()+16)>>4;z<=(bed.getZ()+24)>>4;z++)
                if(!level.hasChunk(x,z)||!level.areEntitiesLoaded(net.minecraft.world.level.ChunkPos.asLong(x,z)))
                    return Optional.of("后桥实体段尚未加载，暂停原撤收时钟。");
        boolean coherent=false;
        for(int amount=0;amount<=9&&!coherent;amount++)
        {
            boolean matches=true;
            for(int x=-16;x<=16&&matches;x++)for(int z=16;z<=24;z++)
            {
                var p=bed.offset(x,48,z);var actual=level.getBlockState(p);
                if(level.getBlockEntity(p)!=null){matches=false;break;}
                boolean expected=25-z<=amount&&panel(x,z);
                if(!expected){if(!actual.isAir()){matches=false;break;}continue;}
                if(!actual.is(ModBlocks.ENTRY_PLUG_BRIDGE_DECK_R48.get())){matches=false;break;}
                for(Direction direction:Direction.Plane.HORIZONTAL)
                {
                    var adjacent=p.relative(direction);boolean exposed=!level.getBlockState(adjacent).isFaceSturdy(level,adjacent,Direction.UP);
                    if(actual.getValue(FacilityEdgeRailR41.side(direction))!=exposed){matches=false;break;}
                }
                if(!matches)break;
            }
            coherent=matches;
        }
        if(!coherent)return Optional.of("后桥完整桥面偏离已记录布局，暂停原撤收时钟并保留人工修改。");
        for(int x=-19;x<=19;x++)for(int z=16;z<=24;z++)
        {
            var floor=bed.offset(x,48,z);var at=floor.above();
            if(PilotRestroomsR47.ownsRoomMaintenanceSpaceR47(level,at))continue;
            var actual=level.getBlockState(at);
            if(level.getBlockEntity(at)!=null)return Optional.of("后桥围护位置出现完整设备NBT，保留原状态。");
            if(!knownGuard(actual))return Optional.of("后桥围护位置出现未知完整方块，保留原状态。");
            if(!level.getBlockState(floor).isFaceSturdy(level,floor,Direction.UP))
            {
                if(!actual.isAir()&&!actual.is(Blocks.LIGHT))return Optional.of("无桥面位置留有旧围护，暂停撤收。");
                continue;
            }
            var expected=FacilityEdgeRailR41.empty(ModBlocks.ENTRY_PLUG_BRIDGE_GUARD_R48.get());boolean edge=false;
            for(Direction side:Direction.Plane.HORIZONTAL)
            {
                var adjacent=floor.relative(side);boolean exposed=!level.getBlockState(adjacent).isFaceSturdy(level,adjacent,Direction.UP);
                expected=expected.setValue(FacilityEdgeRailR41.side(side),exposed);edge|=exposed;
            }
            if(edge&&!actual.equals(expected)||!edge&&!actual.isAir()&&!actual.is(Blocks.LIGHT))
                return Optional.of("后桥完整围护偏离已记录布局，暂停原撤收时钟。");
        }
        var fleet=EvaFleetSavedData.get(level.getServer()).entry(variant).orElse(null);
        if(fleet==null||fleet.entryPlugId()==null)return Optional.of("原机体/胶囊身份未接通，暂停撤收。");
        var area=new net.minecraft.world.phys.AABB(bed.getX()-16,-394,bed.getZ()+16,bed.getX()+17,-390,bed.getZ()+25);
        for(var actor:level.getEntities((net.minecraft.world.entity.Entity)null,area,e->e.isAlive()&&!e.isSpectator()))
        {
            var root=actor.getRootVehicle().getUUID();
            if(actor.getUUID().equals(fleet.canonicalId())||actor.getUUID().equals(fleet.entryPlugId())
                    ||root.equals(fleet.canonicalId())||root.equals(fleet.entryPlugId()))continue;
            if(actor instanceof net.minecraft.world.entity.decoration.ArmorStand stand&&stand.isMarker())continue;
            if(actor instanceof net.minecraft.world.entity.LivingEntity||actor.canBeCollidedWith())
                return Optional.of("后桥仍有人或载具："+actor.getName().getString()+"。暂停原撤收时钟。");
        }
        return Optional.empty();
    }

    public static boolean apply(ServerLevel level,BlockPos bed,int extension)
    {
        if(!enabled(level)||bed.getY()!=-443||bed.getZ()!=-240
                ||!Set.of(-12,30,72).contains(bed.getX()))return false;
        if(THROUGH_R49.contains(level))return EntryPlugBridgeTopologyR49.apply(level,bed,extension);
        int amount=Math.max(0,Math.min(9,extension));
        var fault=retractionFaultR48(level,(bed.getX()+12)/42);
        if(fault.isPresent()){ProjectSeele.LOGGER.warn("R48 original rear bridge held {}: {}",bed,fault.get());return false;}
        Map<BlockPos,BlockState> floors=new LinkedHashMap<>();
        for(int x=-16;x<=16;x++)for(int z=16;z<=24;z++)
        {
            var position=bed.offset(x,48,z);
            if(!level.hasChunkAt(position)||level.getBlockEntity(position)!=null||!knownFloor(level.getBlockState(position)))
            {ProjectSeele.LOGGER.warn("R48 rear bridge retained unknown source floor at {}",position);return false;}
            floors.put(position,25-z<=amount&&panel(x,z)?ModBlocks.ENTRY_PLUG_BRIDGE_DECK_R48.get().defaultBlockState():Blocks.AIR.defaultBlockState());
        }
        // Compute all edge ownership from the complete next footprint, never
        // from a partly-written row. The original pilot rooms are out of scope.
        Map<BlockPos,BlockState> changes=new LinkedHashMap<>();
        for(int x=-19;x<=19;x++)for(int z=16;z<=24;z++)
        {
            var floor=bed.offset(x,48,z);var at=floor.above();
            if(PilotRestroomsR47.ownsRoomMaintenanceSpaceR47(level,at))continue;
            BlockState actual=level.getBlockState(at);
            if(!knownGuard(actual))continue;
            BlockState next=floors.getOrDefault(floor,level.getBlockState(floor));
            if(!next.isFaceSturdy(level,floor,Direction.UP))
            {
                if(actual.is(ModBlocks.NERV_EDGE_RAIL.get())||actual.is(ModBlocks.ENTRY_PLUG_BRIDGE_GUARD_R48.get()))changes.put(at,Blocks.AIR.defaultBlockState());
                continue;
            }
            BlockState guard=FacilityEdgeRailR41.empty(ModBlocks.ENTRY_PLUG_BRIDGE_GUARD_R48.get());
            BlockState deck=next;boolean edge=false;
            for(Direction direction:Direction.Plane.HORIZONTAL)
            {
                var adjacent=floor.relative(direction);
                var neighbour=floors.getOrDefault(adjacent,level.getBlockState(adjacent));
                boolean exposed=!neighbour.isFaceSturdy(level,adjacent,Direction.UP);
                guard=guard.setValue(FacilityEdgeRailR41.side(direction),exposed);edge|=exposed;
                if(deck.is(ModBlocks.ENTRY_PLUG_BRIDGE_DECK_R48.get()))deck=deck.setValue(FacilityEdgeRailR41.side(direction),exposed);
            }
            if(floors.containsKey(floor))floors.put(floor,deck);
            if(edge)changes.put(at,guard);
            else if(actual.is(ModBlocks.NERV_EDGE_RAIL.get())||actual.is(ModBlocks.ENTRY_PLUG_BRIDGE_GUARD_R48.get()))changes.put(at,Blocks.AIR.defaultBlockState());
        }
        floors.forEach((position,state)->{if(!level.getBlockState(position).equals(state))level.setBlock(position,state,2);});
        changes.forEach((position,state)->{if(!level.getBlockState(position).equals(state))level.setBlock(position,state,2);});
        return true;
    }
    private EntryPlugBridgeLayoutR48() { }
}
