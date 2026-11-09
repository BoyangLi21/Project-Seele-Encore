package com.projectseele.visual;

import java.util.Arrays;
import java.util.Locale;
import java.util.Optional;

import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.network.ServerboundEvaVideoFramePacket;
import com.projectseele.world.IntegratedNervMapBuilder;
import com.projectseele.world.NervCommandTelemetry;
import com.projectseele.world.NervCrewSavedData;
import com.projectseele.world.NervCrewSavedData.Assignment;
import com.projectseele.world.NervCrewSavedData.ClaimResult;
import com.projectseele.world.NervCrewSavedData.CrewOverview;
import com.projectseele.world.NervCrewSavedData.Station;
import net.minecraft.ChatFormatting;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.commands.SharedSuggestionProvider;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Entity;
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
            player.displayClientMessage(Component.literal(
                    "NERV 岗位：" + name(station) + "，" + (ready ? "已就绪" : "待命")
                            + "（/seele crew status）")
                    .withStyle(ready ? ChatFormatting.GREEN
                            : ChatFormatting.GOLD), false);
        });
    }

    private static String name(Station station)
    {
        return switch (station)
        {
            case COMMANDER -> "司令";
            case OPERATIONS -> "作战指挥";
            case MAGI -> "MAGI";
            case UNIT_00 -> "零号机驾驶员";
            case UNIT_01 -> "初号机驾驶员";
            case UNIT_02 -> "二号机驾驶员";
        };
    }

    private static int claim(CommandSourceStack source, String raw)
            throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        Optional<Station> parsed = Station.parse(raw);
        if (parsed.isEmpty())
        {
            source.sendFailure(Component.literal(
                    "没有这个岗位。可选：" + String.join("、", STATION_IDS)));
            return 0;
        }
        NervCrewSavedData data = NervCrewSavedData.get(source.getServer());
        Station station = parsed.get();
        ClaimResult result = data.claim(station, player);
        if (result == ClaimResult.OCCUPIED)
        {
            String owner = data.assignment(station)
                    .map(Assignment::playerName).orElse("未知玩家");
            source.sendFailure(Component.literal(name(station) + "已由 " + owner
                    + " 认领。对方已不在时，请管理员执行 /seele crew clear " + station.id() + "。"));
            return 0;
        }
        source.sendSuccess(() -> Component.literal(
                result == ClaimResult.ALREADY_ASSIGNED
                        ? "仍保留岗位：" + name(station)
                        : "已认领岗位：" + name(station) + "。准备好后执行 /seele crew ready。"), false);
        return 1;
    }

    private static int ready(CommandSourceStack source, boolean ready)
            throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        NervCrewSavedData data = NervCrewSavedData.get(source.getServer());
        if (!data.setReady(player.getUUID(), ready))
        {
            source.sendFailure(Component.literal(
                    "请先认领岗位：/seele crew claim <岗位>"));
            return 0;
        }
        Station station = data.stationFor(player.getUUID()).orElseThrow();
        source.sendSuccess(() -> Component.literal(name(station) + "：" + (ready ? "已就绪" : "待命"))
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
            source.sendFailure(Component.literal("你还没有认领岗位。"));
            return 0;
        }
        source.sendSuccess(() -> Component.literal(
                "已释放岗位：" + name(released.get())), false);
        return 1;
    }

    private static int clear(CommandSourceStack source, String raw)
    {
        Optional<Station> parsed = Station.parse(raw);
        if (parsed.isEmpty())
        {
            source.sendFailure(Component.literal(
                    "没有这个岗位。可选：" + String.join("、", STATION_IDS)));
            return 0;
        }
        Optional<Assignment> removed = NervCrewSavedData.get(source.getServer())
                .clear(parsed.get());
        if (removed.isEmpty())
        {
            source.sendFailure(Component.literal(name(parsed.get()) + "当前无人认领。"));
            return 0;
        }
        source.sendSuccess(() -> Component.literal("已清除 " + removed.get().playerName()
                + " 认领的" + name(parsed.get()) + "岗位。"), true);
        return 1;
    }

    private static int crewStatus(CommandSourceStack source)
    {
        MinecraftServer server = source.getServer();
        NervCrewSavedData data = NervCrewSavedData.get(server);
        CrewOverview overview = data.overview(server);
        source.sendSuccess(() -> Component.literal(String.format(Locale.ROOT,
                        "NERV 岗位：已认领 %d/6，在线 %d，就绪 %d，在线且就绪 %d",
                        overview.assigned(), overview.online(), overview.ready(),
                        overview.onlineReady()))
                .withStyle(overview.allAssignedOnlineReady()
                        ? ChatFormatting.GREEN : ChatFormatting.GOLD), false);
        for (Station station : Station.values())
        {
            Optional<Assignment> assignment = data.assignment(station);
            String line;
            ChatFormatting colour;
            if (assignment.isEmpty())
            {
                line = name(station) + "（" + station.id() + "）：空缺";
                colour = ChatFormatting.DARK_GRAY;
            }
            else
            {
                Assignment value = assignment.get();
                boolean online = server.getPlayerList()
                        .getPlayer(value.playerId()) != null;
                line = name(station) + "（" + station.id() + "）：" + value.playerName()
                        + "，" + (online ? "在线" : "离线") + "，" + (value.ready() ? "已就绪" : "待命");
                colour = !online ? ChatFormatting.DARK_RED
                        : value.ready() ? ChatFormatting.GREEN
                        : ChatFormatting.YELLOW;
            }
            ChatFormatting finalColour = colour;
            source.sendSuccess(() -> Component.literal(line)
                    .withStyle(finalColour), false);
        }
        return overview.assigned();
    }

    private static int serverStatus(CommandSourceStack source)
    {
        MinecraftServer server = source.getServer();
        ServerLevel level = server.getLevel(GeoFrontCommands.GEOFRONT);
        source.sendSuccess(() -> Component.literal(String.format(Locale.ROOT,
                        "Project SEELE 服务器：%s，玩家 %d/%d",
                        server.isDedicatedServer() ? "专用服务器" : "单人内置服务器",
                        server.getPlayerCount(), server.getMaxPlayers()))
                .withStyle(ChatFormatting.GOLD), false);
        if (level == null)
        {
            source.sendFailure(Component.literal(
                    "GeoFront 维度未加载，请检查模组和数据包是否正常加载。"));
            return 0;
        }
        boolean installed = IntegratedNervMapBuilder.isInstalled(level);
        AABB area = new AABB(
                IntegratedNervMapBuilder.GEOFRONT_ORIGIN.getX() - 360.0D,
                level.getMinBuildHeight(),
                IntegratedNervMapBuilder.GEOFRONT_ORIGIN.getZ() - 360.0D,
                IntegratedNervMapBuilder.GEOFRONT_ORIGIN.getX() + 360.0D,
                level.getMaxBuildHeight(),
                IntegratedNervMapBuilder.GEOFRONT_ORIGIN.getZ() + 360.0D);
        int airframes = level.getEntitiesOfClass(EvaUnit01Entity.class, area,
                Entity::isAlive).size();
        int screens = installed ? NervCommandTelemetry.countScreens(level,
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
        boolean finalInstalled = installed;
        int finalFeeds = feeds;
        source.sendSuccess(() -> Component.literal(String.format(Locale.ROOT,
                        "地图：%s，已加载 EVA %d/3，遥测屏 %d/%d，驾驶舱画面 %d/3",
                        finalInstalled ? "已接入" : "缺失",
                        airframes, screens, NervCommandTelemetry.SCREEN_COUNT,
                        finalFeeds))
                .withStyle(finalInstalled ? ChatFormatting.GREEN
                        : ChatFormatting.RED), false);
        source.sendSuccess(() -> Component.literal(String.format(Locale.ROOT,
                        "岗位：已认领 %d/6，在线 %d，在线且就绪 %d",
                        crew.assigned(), crew.online(), crew.onlineReady()))
                .withStyle(crew.allAssignedOnlineReady()
                        ? ChatFormatting.GREEN : ChatFormatting.YELLOW), false);
        source.sendSuccess(() -> Component.literal(
                "出击前的有界检查用 /seele admin server audit，不会重建整张地图。")
                .withStyle(ChatFormatting.GRAY), false);
        return installed ? 1 : 0;
    }

    private static int serverAudit(CommandSourceStack source)
    {
        ServerLevel level = source.getServer().getLevel(GeoFrontCommands.GEOFRONT);
        if (level == null)
        {
            source.sendFailure(Component.literal("GeoFront 维度未加载。"));
            return 0;
        }
        IntegratedNervMapBuilder.RuntimeAudit audit =
                IntegratedNervMapBuilder.prepareRuntime(level);
        if (!audit.valid())
        {
            source.sendFailure(Component.literal(
                    "NERV 运行检查未通过：" + audit.summary()));
            return 0;
        }
        source.sendSuccess(() -> Component.literal(
                        "NERV 运行检查通过：" + audit.summary())
                .withStyle(ChatFormatting.GREEN), true);
        return 1;
    }
}
