package com.projectseele.world;

import com.google.gson.JsonParser;
import net.minecraft.core.BlockPos;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.storage.LevelResource;
import java.nio.file.Files;
import java.util.Map;
import java.util.WeakHashMap;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import com.projectseele.ProjectSeele;

/** The EVA sector has its own frame; the accepted headquarters never moves with it. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class RegionalFacilityLayout
{
    private static final Map<MinecraftServer,Boolean> ACTIVE=new WeakHashMap<>();
    public static boolean migrated(MinecraftServer server)
    {
        return ACTIVE.computeIfAbsent(server,s -> {
            var file=s.getWorldPath(LevelResource.ROOT).resolve("regional_plan.json");
            if(!Files.isRegularFile(file))return false;
            try
            {
                var data=JsonParser.parseString(Files.readString(file)).getAsJsonObject();
                return data.has("eva_migrated")&&data.get("eva_migrated").getAsBoolean();
            }
            catch(Exception exception){throw new IllegalStateException("Invalid regional layout",exception);}
        });
    }
    public static BlockPos evaOrigin(ServerLevel level)
    {
        return shiftEva(level,IntegratedNervMapBuilder.geoFrontOrigin(level))
                .offset(0,0,FacilityLayoutR20.cageShiftZ(level.getServer()));
    }
    public static BlockPos launchOrigin(ServerLevel level)
    {
        return shiftEva(level,IntegratedNervMapBuilder.geoFrontOrigin(level))
                .above(FacilityLayoutR20.launchRise(level.getServer()));
    }
    public static BlockPos shiftEva(ServerLevel level,BlockPos original)
    {
        return migrated(level.getServer())?original.offset(0,0,-256):original;
    }
    public static S20PhysicalElevatorDirector.LiftSpec personnelLift(ServerLevel level,S20PhysicalElevatorDirector.LiftSpec spec)
    {
        if(!migrated(level.getServer()) || !(spec.id().equals(S20PhysicalElevatorDirector.OBSERVATION_HANGAR_LIFT_ID)
                ||spec.id().equals(S20PhysicalElevatorDirector.COMPACT_CAGE_LIFT_ID)))return spec;
        return new S20PhysicalElevatorDirector.LiftSpec(spec.id(),spec.stops().stream()
                .map(stop->stop.relocated(shiftEva(level,stop.cabinCentre()))).toList());
    }
    @SubscribeEvent
    public static void maintainRemoteControls(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END || event.getServer().getTickCount()%40!=0 || !migrated(event.getServer()))return;
        ServerLevel level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);
        if(level==null)return;
        boolean viewers=level.players().stream().anyMatch(p->p.getY()<-300
                && Math.abs(p.getX()-30)<200 && Math.abs(p.getZ()-327)<200);
        if(viewers)
        {
            for(int variant=0;variant<3;variant++)EvaLogisticsDirector.loadControlTarget(level,variant);
            if(FacilityLayoutR21.active(level))com.projectseele.entity.NervArmamentStationEntity.keepCommandStationLoaded(level,FacilityLayoutR21.ARMAMENT);
        }
    }
}
