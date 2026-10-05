package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.registry.ModBlocks;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.DoorBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.DoubleBlockHalf;
import net.minecraft.world.level.storage.LevelResource;
import java.nio.file.Files;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;
import java.util.WeakHashMap;

/** Finite installed vertical-cabin finish contract; no moving-door/model owner. */
public final class TvLiftFinishR45
{
    public static final String MARKER=".projectseele_tv_lifts_r45.json";
    public static final int MAX_FLOOR_REPAIR_CELLS=1;
    private static final Set<String> IDS=Set.of(NervLiftPassengerSync.GATEWAY,
            FacilityLiftsR25.OBSERVATION,FacilityLiftsR25.EAST,
            S20PhysicalElevatorDirector.COMMAND_REAR_LIFT_ID,
            S20PhysicalElevatorDirector.COMMANDER_OFFICE_LIFT_ID,
            S20PhysicalElevatorDirector.COMPACT_CAGE_LIFT_ID,
            S20PhysicalElevatorDirector.SURFACE_TRANSIT_LIFT_ID);
    private static final Set<String> STYLES=Set.of("tv22_staff","tv22_command_suite",
            "tv12_large_utility","tv12_secure_service","tv12_hangar_utility","tv12_surface_utility");
    private static final Map<MinecraftServer,Map<String,String>> CACHE=new WeakHashMap<>();

    private static Map<String,String> styles(ServerLevel level)
    {
        return CACHE.computeIfAbsent(level.getServer(),server ->
        {
            var path=server.getWorldPath(LevelResource.ROOT).resolve(MARKER);
            if(!Files.isRegularFile(path))return Map.of();
            try
            {
                var json=JsonParser.parseString(Files.readString(path)).getAsJsonObject();
                if(json.get("schema").getAsInt()!=45||!json.get("dimension").getAsString().equals("projectseele:geofront"))
                    throw new IllegalArgumentException("TV vertical-cabin contract identity");
                var rows=json.getAsJsonObject("styles");var result=new HashMap<String,String>();
                for(var entry:rows.entrySet())
                {
                    String id=entry.getKey(),style=entry.getValue().getAsString();
                    if(!IDS.contains(id)||!STYLES.contains(style))throw new IllegalArgumentException("Unknown TV vertical-cabin owner/style");
                    result.put(id,style);
                }
                if(!result.keySet().equals(IDS))throw new IllegalArgumentException("Incomplete seven-cabin finish contract");
                return Map.copyOf(result);
            }
            catch(Exception failure)
            {
                ProjectSeele.LOGGER.error("TV vertical-cabin finish rejected; existing native car and hardware retained",failure);
                return Map.of();
            }
        });
    }

    /** Only new fallback non-door wall blocks use this palette; no live repaint. */
    public static BlockState cabinWall(ServerLevel level,S20PhysicalElevatorDirector.LiftSpec spec,
            int heightAboveFeet,BlockPos position,BlockPos centre,BlockState original)
    {
        String style=styles(level).get(spec.id());if(style==null)return original;
        if(spec.id().equals(S20PhysicalElevatorDirector.COMPACT_CAGE_LIFT_ID)
                &&position.getZ()==centre.getZ()+2)return ModBlocks.CLEAR_GLASS.get().defaultBlockState();
        if(style.startsWith("tv22"))return heightAboveFeet==1
                ?ModBlocks.TV_STAFF_LIFT_BAND_R45.get().defaultBlockState():ModBlocks.TV_STAFF_LIFT_PANEL_R45.get().defaultBlockState();
        return heightAboveFeet==2?ModBlocks.NERV_STRUCTURAL_PANEL.get().defaultBlockState()
                :ModBlocks.NERV_MACHINE_PANEL.get().defaultBlockState();
    }

    public static BlockState cabinRoof(ServerLevel level,S20PhysicalElevatorDirector.LiftSpec spec,BlockState original)
    {
        String style=styles(level).get(spec.id());if(style==null)return original;
        return (style.startsWith("tv22")?ModBlocks.TV_STAFF_LIFT_PANEL_R45.get():ModBlocks.TV_UTILITY_LIFT_CEILING_R45.get()).defaultBlockState();
    }

    /** Registered dedicated textures share the full original roof/ownership checks. */
    public static boolean recognizedCabinRoof(ServerLevel level,S20PhysicalElevatorDirector.LiftSpec spec,BlockState state)
    {
        if(state.is(Blocks.SMOOTH_QUARTZ))return true;
        String style=styles(level).get(spec.id());if(style==null)return false;
        return state.is(ModBlocks.NERV_MACHINE_EDGE.get())
                ||(style.startsWith("tv22")?state.is(ModBlocks.TV_STAFF_LIFT_PANEL_R45.get()):state.is(ModBlocks.TV_UTILITY_LIFT_CEILING_R45.get()));
    }

    /** The regional gate has its own nine-block car and roof sensor. */
    public static boolean recognizedGatewayRoof(ServerLevel level,BlockState state)
    {
        if(state.is(Blocks.POLISHED_DEEPSLATE))return true;
        return "tv12_large_utility".equals(styles(level).get(NervLiftPassengerSync.GATEWAY))
                &&state.is(ModBlocks.TV_UTILITY_LIFT_CEILING_R45.get());
    }

    public static boolean compactWindowContract(ServerLevel level,S20PhysicalElevatorDirector.LiftSpec spec)
    {
        return spec.id().equals(S20PhysicalElevatorDirector.COMPACT_CAGE_LIFT_ID)
                &&"tv12_hangar_utility".equals(styles(level).get(spec.id()));
    }

    public static BlockState cabinDoor(ServerLevel level,BlockPos centre,
            net.minecraft.core.Direction exit,BlockState original)
    {
        if(exit!=net.minecraft.core.Direction.SOUTH)return original;
        for(var spec:S20PhysicalElevatorDirector.s20Lifts(level))
            if(compactWindowContract(level,spec)&&spec.stops().stream()
                    .anyMatch(stop->stop.cabinCentre().equals(centre)))
                return ModBlocks.CLEAR_GLASS.get().defaultBlockState();
        return original;
    }

    /** A single interior hole is distinct from an absent/misidentified platform. */
    public static boolean mayRepairSingleInteriorFloorHole(int missing,boolean completeRoof,
            boolean originalLinkedSelector,boolean clearRegisteredDoorway,boolean foreignFloor,
            boolean interiorHole)
    {
        return missing==MAX_FLOOR_REPAIR_CELLS&&completeRoof&&originalLinkedSelector
                &&clearRegisteredDoorway&&!foreignFloor&&interiorHole;
    }

    /** Optional post-import hook for three measured free-latch interior doors.
     * It changes neither the accepted room layout nor any redstone-only door.
     * The existing CityPersonnelDoorR44 hand latch preserves ordinary egress.
     */
    public static void finishImportedCommandDoors(ServerLevel level)
    {
        if(!level.dimension().equals(FacilitySchemaV2.DIMENSION)||styles(level).isEmpty())return;
        for(var lower:java.util.List.of(new BlockPos(24,-423,254),new BlockPos(28,-448,282),new BlockPos(48,-448,282)))
        {
            var low=level.getBlockState(lower);var high=level.getBlockState(lower.above());
            if(!low.is(Blocks.SPRUCE_DOOR)||!high.is(Blocks.SPRUCE_DOOR)
                    ||low.getValue(DoorBlock.HALF)!=DoubleBlockHalf.LOWER||high.getValue(DoorBlock.HALF)!=DoubleBlockHalf.UPPER
                    ||level.getBlockEntity(lower)!=null||level.getBlockEntity(lower.above())!=null)continue;
            if(low.getValue(DoorBlock.FACING)!=high.getValue(DoorBlock.FACING)
                    ||low.getValue(DoorBlock.HINGE)!=high.getValue(DoorBlock.HINGE)
                    ||low.getValue(DoorBlock.OPEN)!=high.getValue(DoorBlock.OPEN)
                    ||low.getValue(DoorBlock.POWERED)!=high.getValue(DoorBlock.POWERED))continue;
            for(var at:java.util.List.of(lower,lower.above()))
            {
                var before=level.getBlockState(at);
                var after=ModBlocks.CITY_PERSONNEL_DOOR.get().defaultBlockState()
                        .setValue(DoorBlock.FACING,before.getValue(DoorBlock.FACING))
                        .setValue(DoorBlock.HINGE,before.getValue(DoorBlock.HINGE))
                        .setValue(DoorBlock.OPEN,before.getValue(DoorBlock.OPEN))
                        .setValue(DoorBlock.POWERED,before.getValue(DoorBlock.POWERED))
                        .setValue(DoorBlock.HALF,before.getValue(DoorBlock.HALF));
                level.setBlock(at,after,Block.UPDATE_CLIENTS|Block.UPDATE_KNOWN_SHAPE);
            }
        }
    }

    private TvLiftFinishR45(){}
}
