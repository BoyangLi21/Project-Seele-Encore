package com.projectseele.visual;

import java.util.function.Predicate;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import com.projectseele.ProjectSeele;
import com.projectseele.event.FirstBattleMission;
import com.projectseele.event.TvCampaignDirector;
import com.projectseele.world.HangarEmergencyR47;
import com.projectseele.world.NervAirLiftR30;
import com.projectseele.world.NervNpcResetR53;
import com.projectseele.world.NervRootAssemblyInstallationR52;
import com.projectseele.world.NervTransitRecoveryR53;
import com.projectseele.world.SynchLabDirectorR47;
import com.projectseele.world.TvSortiesR32;
import com.projectseele.world.TvYashimaStationR52;
import com.projectseele.world.UNCommandR29;
import com.projectseele.world.UndergroundSortieR48;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/**
 * The only registration of /seele. Brigadier keeps the first requirement it sees when two
 * roots of the same name merge, so the root carries none and each first-level child carries
 * its own. The tree is listed in docs/COMMANDS.zh.md.
 */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class SeeleCommands
{
    private static final Predicate<CommandSourceStack> ADMIN = source -> source.hasPermission(2);

    private SeeleCommands() {}

    @SubscribeEvent
    public static void register(RegisterCommandsEvent event)
    {
        CommandDispatcher<CommandSourceStack> dispatcher = event.getDispatcher();
        LiteralArgumentBuilder<CommandSourceStack> seele = Commands.literal("seele")
                // Players: the handlers keep their own gameplay checks.
                .then(NervStaffCommands.callCommand())
                .then(NervStaffCommands.routeCommand())
                .then(TvCampaignDirector.sortieCommand().then(TvSortiesR32.supportCommand()))
                .then(TvYashimaStationR52.cannonCommand())
                .then(SynchLabDirectorR47.synchCommand())
                .then(Commands.literal("hangar").then(HangarEmergencyR47.doorCommand()))
                .then(UndergroundSortieR48.recoverCommand())
                .then(NervCrewCommands.crewCommand())
                .then(UNCommandR29.command().requires(UNCommandR29::canUse))
                // Administrators.
                .then(SeeleTravelCommandsR43.tpCommand().requires(ADMIN))
                .then(SeeleTravelCommandsR43.enterCommand().requires(ADMIN))
                .then(EvaLogisticsCommands.evaCommand().requires(ADMIN))
                .then(ArmamentStationCommands.armamentCommand().requires(ADMIN))
                .then(ThirdTokyoCommands.cityCommand().requires(ADMIN))
                .then(Commands.literal("admin").requires(ADMIN)
                        .then(NervCrewCommands.serverCommand())
                        .then(NervAirLiftR30.transportCommand())
                        .then(NervNpcResetR53.npcCommand())
                        .then(NervTransitRecoveryR53.transitCommand())
                        .then(NervRootAssemblyInstallationR52.installCommand())
                        .then(NervRootAssemblyInstallationR52.installCancelCommand())
                        .then(NervRootAssemblyInstallationR52.equipmentUpdateCommand()));
        if (DevelopmentCommandsR43.enabled())
        {
            seele.then(Commands.literal("dev").requires(ADMIN)
                    .then(PilotCommands.pilotCommand())
                    .then(Commands.literal("eva").then(EvaLogisticsCommands.dummyCommand()))
                    .then(NervTraversalDebugCommandsR53.traversalCommand())
                    .then(NervTraversalDebugCommandsR53.sortieCommand())
                    .then(ThirdTokyoCommands.devCityCommand())
                    .then(ThirdTokyoCommands.siegeCommand())
                    .then(GeoFrontCommands.geofrontCommand())
                    .then(FacilityV2Commands.facilityCommand())
                    .then(LaunchSiloCommands.siloCommand())
                    .then(EvaMotionLabCommands.motionLabCommand())
                    .then(FirstBattleMission.firstBattleCommand())
                    .then(ArmamentStationCommands.devArmamentCommand())
                    .then(MilitaryR07Commands.visitCommand())
                    .then(CoastalSeedScoutCommands.seedScoutCommand()));
        }
        dispatcher.register(seele);
    }
}
