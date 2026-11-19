package com.projectseele.visual;

import java.util.Arrays;
import java.util.Optional;

import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.network.ServerboundEvaVideoFramePacket;
import com.projectseele.world.FacilityWorldPolicy;
import com.projectseele.world.IntegratedNervMapBuilder;
import com.projectseele.world.NervCommandTelemetry;
import com.projectseele.world.NervCrewSavedData;
import com.projectseele.world.NervCrewSavedData.Assignment;
import com.projectseele.world.NervCrewSavedData.ClaimResult;
import com.projectseele.world.NervCrewSavedData.CrewOverview;
import com.projectseele.world.NervCrewSavedData.Station;
import com.projectseele.world.RegionalGatewayDirector;
import net.minecraft.ChatFormatting;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.commands.SharedSuggestionProvider;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.phys.AABB;
import net.minecraftforge.event.entity.player.PlayerEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Player-facing NERV crew coordination (/seele crew) and operator server diagnostics (/seele admin server). */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class NervCrewCommands
{
    private static final String[] STATION_IDS = Arrays.stream(Station.values())
            .map(Station::id).toArray(String[]::new);

    private NervCrewCommands() {}

    public static LiteralArgumentBuilder<CommandSourceStack> crewCommand()
    {
        return Commands.literal("crew")
                .executes(context -> crewStatus(context.getSource()))
                .then(Commands.literal("status")
                        .executes(context -> crewStatus(context.getSource())))
                .then(Commands.literal("claim")
                        .then(Commands.argument("station", StringArgumentType.word())
                                .suggests((context, builder) ->
                                        SharedSuggestionProvider.suggest(STATION_IDS, builder))
                                .executes(context -> claim(context.getSource(),
                                        StringArgumentType.getString(context, "station")))))
                .then(Commands.literal("ready")
                        .executes(context -> ready(context.getSource(), true)))
                .then(Commands.literal("standby")
                        .executes(context -> ready(context.getSource(), false)))
                .then(Commands.literal("release")
                        .executes(context -> release(context.getSource())))
                .then(Commands.literal("clear")
                        .requires(source -> source.hasPermission(2))
                        .then(Commands.argument("station", StringArgumentType.word())
                                .suggests((context, builder) ->
                                        SharedSuggestionProvider.suggest(STATION_IDS, builder))
                                .executes(context -> clear(context.getSource(),
                                        StringArgumentType.getString(context, "station")))));
    }

    public static LiteralArgumentBuilder<CommandSourceStack> serverCommand()
    {
        return Commands.literal("server")
                .executes(context -> serverStatus(context.getSource()))
                .then(Commands.literal("status")
                        .executes(context -> serverStatus(context.getSource())))
                .then(Commands.literal("audit")
                        .executes(context -> serverAudit(context.getSource())));
    }

    @SubscribeEvent
    public static void onPlayerLoggedIn(PlayerEvent.PlayerLoggedInEvent event)
    {
        if (!(event.getEntity() instanceof ServerPlayer player))
        {
            return;
        }
        NervCrewSavedData data = NervCrewSavedData.get(player.server);
        data.stationFor(player.getUUID()).ifPresent(station ->
        {
            boolean ready = data.assignment(station)
                    .map(Assignment::ready).orElse(false);
            player.displayClientMessage(Component.translatable("message.projectseele.multiplayer.login", name(station), readiness(ready))
                    .withStyle(ready ? ChatFormatting.GREEN
                            : ChatFormatting.GOLD), false);
        });
    }

    private static Component readiness(boolean ready)
    {
        return Component.translatable(ready ? "message.projectseele.multiplayer.ready"
                : "message.projectseele.multiplayer.standby");
    }

    private static Component name(Station station)
    {
        return switch (station)
        {
            case COMMANDER -> Component.translatable("message.projectseele.multiplayer.commander");
            case OPERATIONS -> Component.translatable("message.projectseele.multiplayer.operations");
            case MAGI -> Component.translatable("message.projectseele.multiplayer.magi");
            case UNIT_00 -> Component.translatable("message.projectseele.multiplayer.unit_00");
            case UNIT_01 -> Component.translatable("message.projectseele.multiplayer.unit_01");
            case UNIT_02 -> Component.translatable("message.projectseele.multiplayer.unit_02");
        };
    }

    private static int claim(CommandSourceStack source, String raw)
            throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        Optional<Station> parsed = Station.parse(raw);
        if (parsed.isEmpty())
        {
            source.sendFailure(Component.translatable("message.projectseele.multiplayer.unknown_post", String.join(", ", STATION_IDS)));
            return 0;
        }
        NervCrewSavedData data = NervCrewSavedData.get(source.getServer());
        Station station = parsed.get();
        ClaimResult result = data.claim(station, player);
        if (result == ClaimResult.OCCUPIED)
        {
            Component owner = data.assignment(station)
                    .<Component>map(value -> Component.literal(value.playerName()))
                    .orElseGet(() -> Component.translatable("message.projectseele.multiplayer.unknown_player"));
            source.sendFailure(Component.translatable("message.projectseele.multiplayer.occupied",
                    name(station), owner, station.id()));
            return 0;
        }
        source.sendSuccess(() -> Component.translatable(result == ClaimResult.ALREADY_ASSIGNED
                ? "message.projectseele.multiplayer.retained" : "message.projectseele.multiplayer.claimed",
                name(station)), false);
        return 1;
    }

    private static int ready(CommandSourceStack source, boolean ready)
            throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        NervCrewSavedData data = NervCrewSavedData.get(source.getServer());
        if (!data.setReady(player.getUUID(), ready))
        {
            source.sendFailure(Component.translatable("message.projectseele.crew.claim"));
            return 0;
        }
        Station station = data.stationFor(player.getUUID()).orElseThrow();
        source.sendSuccess(() -> Component.translatable("message.projectseele.multiplayer.readiness", name(station), readiness(ready))
                .withStyle(ready ? ChatFormatting.GREEN
                        : ChatFormatting.GOLD), false);
        return 1;
    }

    private static int release(CommandSourceStack source)
            throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        Optional<Station> released = NervCrewSavedData.get(source.getServer())
                .release(player.getUUID());
        if (released.isEmpty())
        {
            source.sendFailure(Component.translatable("message.projectseele.crew.no_post"));
            return 0;
        }
        source.sendSuccess(() -> Component.translatable("message.projectseele.multiplayer.released", name(released.get())), false);
        return 1;
    }

    private static int clear(CommandSourceStack source, String raw)
    {
        Optional<Station> parsed = Station.parse(raw);
        if (parsed.isEmpty())
        {
            source.sendFailure(Component.translatable("message.projectseele.multiplayer.unknown_post", String.join(", ", STATION_IDS)));
            return 0;
        }
        Optional<Assignment> removed = NervCrewSavedData.get(source.getServer())
                .clear(parsed.get());
        if (removed.isEmpty())
        {
            source.sendFailure(Component.translatable("message.projectseele.multiplayer.unclaimed", name(parsed.get())));
            return 0;
        }
        source.sendSuccess(() -> Component.translatable("message.projectseele.multiplayer.cleared", removed.get().playerName(), name(parsed.get())), true);
        return 1;
    }

    private static int crewStatus(CommandSourceStack source)
    {
        MinecraftServer server = source.getServer();
        NervCrewSavedData data = NervCrewSavedData.get(server);
        CrewOverview overview = data.overview(server);
        source.sendSuccess(() -> Component.translatable("message.projectseele.multiplayer.overview",
                        overview.assigned(), overview.online(), overview.ready(), overview.onlineReady())
                .withStyle(overview.allAssignedOnlineReady()
                        ? ChatFormatting.GREEN : ChatFormatting.GOLD), false);
        for (Station station : Station.values())
        {
            Optional<Assignment> assignment = data.assignment(station);
            Component line;
            ChatFormatting colour;
            if (assignment.isEmpty())
            {
                line = Component.translatable("message.projectseele.multiplayer.vacant", name(station), station.id());
                colour = ChatFormatting.DARK_GRAY;
            }
            else
            {
                Assignment value = assignment.get();
                boolean online = server.getPlayerList()
                        .getPlayer(value.playerId()) != null;
                line = Component.translatable("message.projectseele.multiplayer.assigned", name(station), station.id(),
                        value.playerName(), Component.translatable(online
                                ? "message.projectseele.multiplayer.online" : "message.projectseele.multiplayer.offline"),
                        readiness(value.ready()));
                colour = !online ? ChatFormatting.DARK_RED
                        : value.ready() ? ChatFormatting.GREEN
                        : ChatFormatting.YELLOW;
            }
            ChatFormatting finalColour = colour;
            source.sendSuccess(() -> line.copy().withStyle(finalColour), false);
        }
        return overview.assigned();
    }

    private static int serverStatus(CommandSourceStack source)
    {
        MinecraftServer server = source.getServer();
        ServerLevel level = server.getLevel(GeoFrontCommands.GEOFRONT);
        source.sendSuccess(() -> Component.translatable("message.projectseele.multiplayer.server",
                        Component.translatable(server.isDedicatedServer()
                                ? "message.projectseele.multiplayer.dedicated" : "message.projectseele.multiplayer.integrated"),
                        server.getPlayerCount(), server.getMaxPlayers())
                .withStyle(ChatFormatting.GOLD), false);
        if (level == null)
        {
            source.sendFailure(Component.translatable("message.projectseele.crew.no_geofront"));
            return 0;
        }
        // The current world retires the old map's installation receipt on purpose, so reading it
        // reported every such server's map as missing. Its facility is installed when its regional
        // plan is, the same test /seele tp uses. Its feeds are drawn on the command room's sloped
        // screens; the old text-display wall is never built in an S20 world.
        boolean s20 = FacilityWorldPolicy.isS20Rebuild(server);
        boolean regional = RegionalGatewayDirector.active(level);
        boolean installed = regional || IntegratedNervMapBuilder.isInstalled(level);
        AABB area = new AABB(
                IntegratedNervMapBuilder.GEOFRONT_ORIGIN.getX() - 360.0D,
                level.getMinBuildHeight(),
                IntegratedNervMapBuilder.GEOFRONT_ORIGIN.getZ() - 360.0D,
                IntegratedNervMapBuilder.GEOFRONT_ORIGIN.getX() + 360.0D,
                level.getMaxBuildHeight(),
                IntegratedNervMapBuilder.GEOFRONT_ORIGIN.getZ() + 360.0D);
        int airframes = level.getEntitiesOfClass(EvaUnit01Entity.class, area,
                eva -> eva.isAlive() && eva.getUnitVariant() >= EvaUnit01Entity.UNIT_00
                        && eva.getUnitVariant() <= EvaUnit01Entity.UNIT_02).size();
        int screens = installed && !s20 ? NervCommandTelemetry.countScreens(level,
                IntegratedNervMapBuilder.GEOFRONT_ORIGIN) : 0;
        int feeds = 0;
        for (int variant = EvaUnit01Entity.UNIT_00;
             variant <= EvaUnit01Entity.UNIT_02; variant++)
        {
            if (ServerboundEvaVideoFramePacket.isFeedActive(level, variant))
            {
                feeds++;
            }
        }
        CrewOverview crew = NervCrewSavedData.get(server).overview(server);
        Component facility = Component.translatable(!installed ? "message.projectseele.multiplayer.missing"
                : regional ? "message.projectseele.multiplayer.installed" : "message.projectseele.multiplayer.connected");
        int finalFeeds = feeds;
        source.sendSuccess(() -> (regional
                ? Component.translatable("message.projectseele.multiplayer.facility", facility, airframes, finalFeeds)
                : Component.translatable("message.projectseele.multiplayer.map", facility, airframes,
                        screens, NervCommandTelemetry.SCREEN_COUNT, finalFeeds))
                .withStyle(installed ? ChatFormatting.GREEN : ChatFormatting.RED), false);
        source.sendSuccess(() -> Component.translatable("message.projectseele.multiplayer.staffing",
                        crew.assigned(), crew.online(), crew.onlineReady())
                .withStyle(crew.allAssignedOnlineReady()
                        ? ChatFormatting.GREEN : ChatFormatting.YELLOW), false);
        source.sendSuccess(() -> Component.translatable("message.projectseele.crew.audit")
                .withStyle(ChatFormatting.GRAY), false);
        return installed ? 1 : 0;
    }

    private static int serverAudit(CommandSourceStack source)
    {
        ServerLevel level = source.getServer().getLevel(GeoFrontCommands.GEOFRONT);
        if (level == null)
        {
            source.sendFailure(Component.translatable("message.projectseele.geofront_unloaded"));
            return 0;
        }
        IntegratedNervMapBuilder.RuntimeAudit audit =
                IntegratedNervMapBuilder.prepareRuntime(level);
        if (!audit.valid())
        {
            source.sendFailure(Component.translatable("message.projectseele.multiplayer.audit_fail", audit.summary()));
            return 0;
        }
        source.sendSuccess(() -> Component.translatable("message.projectseele.multiplayer.audit_pass", audit.summary())
                .withStyle(ChatFormatting.GREEN), true);
        return 1;
    }
}
