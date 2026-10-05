package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.storage.LevelResource;
import java.nio.file.Files;
import java.util.*;

/** Activates two finite experimental landings only with their installed civil receipt. */
public final class ExperimentalLiftStopsR47
{
    public static final String MARKER="r47_experimental_lifts.json";
    private static final Map<MinecraftServer,Boolean> INSTALLED=new WeakHashMap<>();
    private static boolean installed(ServerLevel level)
    {
        return INSTALLED.computeIfAbsent(level.getServer(),server ->
        {
            var path=server.getWorldPath(LevelResource.ROOT).resolve(MARKER);
            if(!Files.isRegularFile(path))return false;
            try
            {
                var document=JsonParser.parseString(Files.readString(path)).getAsJsonObject();
                if(document.get("schema").getAsInt()!=47||!document.get("dimension").getAsString().equals("projectseele:geofront")
                        ||!document.get("geometry_installed").getAsBoolean())return false;
                var stops=document.getAsJsonArray("landings");
                if(stops.size()!=2)return false;
                var found=new HashSet<String>();
                for(var raw:stops)
                {
                    var stop=raw.getAsJsonObject();String id=stop.get("lift_id").getAsString();
                    var xyz=stop.getAsJsonArray("cabin_centre");
                    int x=id.equals(S20PhysicalElevatorDirector.COMPACT_CAGE_LIFT_ID)?93:-29;
                    int z=x==93?-52:-278;
                    if(!Set.of(S20PhysicalElevatorDirector.COMPACT_CAGE_LIFT_ID,FacilityLiftsR25.OBSERVATION).contains(id)
                            ||!found.add(id)||xyz.size()!=3||xyz.get(0).getAsInt()!=x||xyz.get(1).getAsInt()!=-468||xyz.get(2).getAsInt()!=z
                            ||!stop.get("exit").getAsString().equals(x==93?"south":"north"))return false;
                }
                return true;
            }
            catch(Exception failure)
            {
                ProjectSeele.LOGGER.error("R47 experimental lift receipt rejected; original stops retained",failure);
                return false;
            }
        });
    }
    public static List<S20PhysicalElevatorDirector.LiftSpec> augment(ServerLevel level,List<S20PhysicalElevatorDirector.LiftSpec> original)
    {
        if(!level.dimension().equals(FacilitySchemaV2.DIMENSION)||!installed(level))return original;
        return original.stream().map(spec ->
        {
            boolean compact=spec.id().equals(S20PhysicalElevatorDirector.COMPACT_CAGE_LIFT_ID);
            if(!compact&&!spec.id().equals(FacilityLiftsR25.OBSERVATION)
                    ||spec.stops().stream().anyMatch(stop->stop.walkY()==-468))return spec;
            var stops=new ArrayList<>(spec.stops());
            stops.add(new S20PhysicalElevatorDirector.Landing("LCL 同步实验层",new BlockPos(compact?93:-29,-468,compact?-52:-278),compact?Direction.SOUTH:Direction.NORTH));
            stops.sort(Comparator.comparingInt(S20PhysicalElevatorDirector.Landing::walkY));
            return new S20PhysicalElevatorDirector.LiftSpec(spec.id(),List.copyOf(stops));
        }).toList();
    }
    private ExperimentalLiftStopsR47() { }
}
