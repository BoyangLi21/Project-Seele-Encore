package com.projectseele.world;

import com.projectseele.ProjectSeele;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.util.List;

/** Native lift controls are enabled only after the matching civil patch exists. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class FacilityLiftsR25
{
    public static final String EAST = "r25-east-command-gallery";
    public static final String OBSERVATION = "r25-west-observation";

    public static List<S20PhysicalElevatorDirector.LiftSpec> installed(ServerLevel level)
    {
        if (!level.dimension().equals(FacilitySchemaV2.DIMENSION)
                || !FacilityWorldPolicy.markerPresent(level.getServer(), "facility_lifts_r25.json")) return List.of();
        boolean internal=FacilityWorldPolicy.markerPresent(level.getServer(), "facility_lifts_r26.json");
        var east = new S20PhysicalElevatorDirector.LiftSpec(EAST,
                java.util.Arrays.stream(internal?new int[]{-461,-448,-434,-420,-406,-392,-378,-364}:new int[]{-448,-434,-420,-406,-392}).mapToObj(y ->
                        new S20PhysicalElevatorDirector.Landing(floorName(y),
                                new BlockPos(internal?66:73,y,internal?302:253),Direction.SOUTH)).toList());
        var west = new S20PhysicalElevatorDirector.LiftSpec(OBSERVATION,
                new S20PhysicalElevatorDirector.Landing("机库登机层",new BlockPos(-29,-394,-278),Direction.NORTH),
                new S20PhysicalElevatorDirector.Landing("三机观察廊",new BlockPos(-29,-367,-278),Direction.NORTH));
        return List.of(east,west);
    }

    public static String floorName(int y)
    {
        return switch(y)
        {
            case -461 -> "B1 交通接驳层";
            case -448 -> "1F 总部门厅";
            case -434 -> "2F 勤务联络层";
            case -420 -> "3F 科研联络层";
            case -406 -> "4F 作战指挥室";
            case -392 -> "5F 指挥室上层";
            case -378 -> "6F 上部办公层";
            case -364 -> "7F 上部观察层";
            default -> "设施联络层";
        };
    }

    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END) return;
        for (var level : event.getServer().getAllLevels()) for (var spec : installed(level))
        {
            if (!level.hasChunkAt(spec.lower().cabinCentre())) continue;
            S20MovingElevatorsAdapter.reconcile(level,spec);
        }
    }
    private FacilityLiftsR25() {}
}
