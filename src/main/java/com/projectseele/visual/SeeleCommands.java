package com.projectseele.visual;

import java.util.function.Predicate;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import com.mojang.brigadier.tree.CommandNode;
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
        registerDeprecatedAliases(dispatcher, dispatcher.getRoot().getChild("seele"));
    }

    /**
     * Deprecated: the names used up to R61, kept for one version after the 2026-11 command
     * cleanup so saved worlds, manuals and habits keep working. Remove this method next round.
     */
    private static void registerDeprecatedAliases(CommandDispatcher<CommandSourceStack> dispatcher,
                                                  CommandNode<CommandSourceStack> seele)
    {
        LiteralArgumentBuilder<CommandSourceStack> nerv = Commands.literal("nerv")
                .executes(child(seele, "crew").getCommand())
                .then(alias("route", seele, "route"))
                .then(alias("contact", seele, "call"))
                .then(alias("crew", seele, "crew"))
                .then(alias("synch", seele, "synch"))
                .then(Commands.literal("hangar").then(alias("emergency", seele, "hangar", "door")))
                .then(Commands.literal("underground").then(alias("recover", seele, "recover")))
                .then(alias("server", seele, "admin", "server"))
                .then(alias("transport", seele, "admin", "transport"))
                .then(alias("npc", seele, "admin", "npc"))
                .then(alias("transit", seele, "admin", "transit"))
                .then(Commands.literal("r52").requires(ADMIN)
                        .then(alias("install", seele, "admin", "install"))
                        .then(alias("install_cancel", seele, "admin", "install_cancel"))
                        .then(alias("equipment_update", seele, "admin", "equipment_update")));
        if (DevelopmentCommandsR43.enabled())
        {
            nerv.then(Commands.literal("debug").requires(ADMIN)
                    .then(alias("sortie", seele, "dev", "sortie"))
                    .then(alias("traversal", seele, "dev", "traversal")));
        }
        dispatcher.register(nerv);

        LiteralArgumentBuilder<CommandSourceStack> un = Commands.literal("un").requires(UNCommandR29::canUse);
        for (String action : new String[] {"phone", "status", "deliver", "recover", "dock", "cancel", "board"})
        {
            un.then(alias(action, seele, "un", action));
        }
        for (String action : new String[] {"drain", "door", "fill"})
        {
            un.then(alias(action, seele, "un", "hangar", action));
        }
        dispatcher.register(un);

        LiteralArgumentBuilder<CommandSourceStack> tv = Commands.literal("tv");
        for (String action : new String[] {"status", "begin", "select", "retry", "cancel", "support"})
        {
            tv.then(alias(action, seele, "sortie", action));
        }
        tv.then(alias("collect_equipment", seele, "sortie", "collect"))
                .then(alias("raise_cannon", seele, "cannon", "raise"))
                .then(alias("leave_cannon", seele, "cannon", "release"));
        seele.addChild(tv.build());

        seele.addChild(Commands.literal("tokyo3").requires(ADMIN)
                .then(alias("status", seele, "city", "status"))
                .then(alias("retract", seele, "city", "lower"))
                .then(alias("restore", seele, "city", "raise"))
                .build());

        // The old UN-00 and un01 wet-cell spellings had no unit argument, so they call the same handler.
        LiteralArgumentBuilder<CommandSourceStack> military = Commands.literal("military").requires(ADMIN)
                .then(alias("defense", seele, "un", "defense"))
                .then(alias("power", seele, "un", "power"))
                .then(alias("recover", seele, "un", "recover"))
                .then(alias("reset", seele, "un", "reset"));
        LiteralArgumentBuilder<CommandSourceStack> un01 = Commands.literal("un01");
        for (String action : new String[] {"status", "drain", "door", "fill"})
        {
            military.then(Commands.literal(action).executes(c -> UNCommandR29.hangar(c.getSource(), action, 0)));
            un01.then(Commands.literal(action).executes(c -> UNCommandR29.hangar(c.getSource(), action, 1)));
        }
        seele.addChild(military.then(un01).build());
    }

    private static LiteralArgumentBuilder<CommandSourceStack> alias(String name, CommandNode<CommandSourceStack> seele,
                                                                   String... path)
    {
        CommandNode<CommandSourceStack> target = seele;
        Predicate<CommandSourceStack> requirement = seele.getRequirement();
        for (String step : path)
        {
            target = child(target, step);
            requirement = requirement.and(target.getRequirement());
        }
        // A redirect skips the requirements above its target, so the alias carries the whole path's.
        return Commands.literal(name).requires(requirement).executes(target.getCommand()).redirect(target);
    }

    private static CommandNode<CommandSourceStack> child(CommandNode<CommandSourceStack> parent, String name)
    {
        CommandNode<CommandSourceStack> child = parent.getChild(name);
        if (child == null)
        {
            throw new IllegalStateException("No /seele command node '" + name + "' under '" + parent.getName() + "'");
        }
        return child;
    }
}
