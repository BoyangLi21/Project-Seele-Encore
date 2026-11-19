package com.projectseele.visual;

import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import com.mojang.brigadier.exceptions.SimpleCommandExceptionType;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.world.EvaHangarBuilder;
import com.projectseele.world.EvaLogisticsDirector;
import com.projectseele.world.EvaLogisticsDirector.ActionResult;
import com.projectseele.world.EvaLogisticsDirector.Status;
import com.projectseele.world.FacilityV2EvaRuntime;
import com.projectseele.world.FacilityWorldPolicy;
import com.projectseele.world.IntegratedNervMapBuilder;
import com.projectseele.world.NervRouteRuntimeR52;
import com.projectseele.world.TrainingPilotDirector;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;

import java.util.Locale;

/** Operator commands for canonical EVA wet-cage logistics and recovery (/seele eva, /seele dev eva dummy). */
public final class EvaLogisticsCommands
{
    private static final SimpleCommandExceptionType UNKNOWN_VARIANT = new SimpleCommandExceptionType(
            Component.translatable("message.projectseele.eva_unit_argument"));
    private static final SimpleCommandExceptionType NO_GEOFRONT = new SimpleCommandExceptionType(
            Component.translatable("message.projectseele.geofront_unloaded"));
    /** The status line's key. Its arguments: the Unit's label, its phase's name, loaded or not, then what a pilot need not see. */
    public static final String STATUS_KEY = "message.projectseele.eva_status";
    /** The third argument of a Unit that is not loaded. */
    public static final String STATUS_UNLOADED = "message.projectseele.eva_unloaded";

    private EvaLogisticsCommands() {}

    public static LiteralArgumentBuilder<CommandSourceStack> evaCommand()
    {
        return Commands.literal("eva")
                .then(Commands.literal("status")
                        .executes(context -> status(context.getSource(), "all"))
                        .then(Commands.argument("variant", StringArgumentType.word())
                                .executes(context -> status(context.getSource(),
                                        StringArgumentType.getString(context, "variant")))))
                .then(Commands.literal("prepare")
                        .then(Commands.argument("variant", StringArgumentType.word())
                                .executes(context -> prepare(context.getSource(),
                                        StringArgumentType.getString(context, "variant")))
                                .then(Commands.argument("destination", StringArgumentType.word())
                                        .suggests((context, builder) -> net.minecraft.commands.SharedSuggestionProvider.suggest(
                                                java.util.List.of("geofront", "surface", "hakone"), builder))
                                        .executes(context -> prepare(context.getSource(),
                                                StringArgumentType.getString(context, "variant"),
                                                StringArgumentType.getString(context, "destination"))))))
                .then(Commands.literal("cancel")
                        .then(Commands.argument("variant", StringArgumentType.word())
                                .executes(context -> cancel(context.getSource(),
                                        StringArgumentType.getString(context, "variant")))))
                .then(Commands.literal("launch")
                        .then(Commands.argument("variant", StringArgumentType.word())
                                .executes(context -> launch(context.getSource(),
                                        StringArgumentType.getString(context, "variant")))))
                .then(Commands.literal("recover")
                        .then(Commands.argument("variant", StringArgumentType.word())
                                .executes(context -> recover(context.getSource(),
                                        StringArgumentType.getString(context, "variant")))))
                .then(Commands.literal("reset")
                        .then(Commands.argument("variant", StringArgumentType.word())
                                .executes(context -> reset(context.getSource(),
                                        StringArgumentType.getString(context, "variant")))));
    }

    public static LiteralArgumentBuilder<CommandSourceStack> dummyCommand()
    {
        return Commands.literal("dummy")
                .then(Commands.literal("start")
                        .then(Commands.argument("variant", StringArgumentType.word())
                                .executes(context -> dummyStart(
                                        context.getSource(),
                                        StringArgumentType.getString(context, "variant")))))
                .then(Commands.literal("stop")
                        .then(Commands.argument("variant", StringArgumentType.word())
                                .executes(context -> dummyStop(
                                        context.getSource(),
                                        StringArgumentType.getString(context, "variant")))))
                .then(Commands.literal("status")
                        .executes(context -> dummyStatus(
                                context.getSource())));
    }

    private static int status(CommandSourceStack source, String raw)
            throws CommandSyntaxException
    {
        ServerLevel level = geoFront(source);
        int requested = parseVariant(raw);
        int loaded = 0;
        for (int variant = 0; variant < 3; variant++)
        {
            if (requested >= 0 && requested != variant)
            {
                continue;
            }
            Status status = EvaLogisticsDirector.status(level, variant);
            if (status.loaded())
            {
                loaded++;
            }
            source.sendSuccess(() -> Component.translatable(STATUS_KEY,
                    String.format(Locale.ROOT, "EVA-%02d", status.variant()), status.phase(),
                    Component.translatable(status.loaded() ? "message.projectseele.eva_loaded" : STATUS_UNLOADED),
                    status.canonicalId() == null ? Component.translatable("message.projectseele.eva_unregistered") : status.canonicalId().toString(),
                    String.valueOf(status.lclLayers()), String.valueOf(EvaHangarBuilder.LCL_SHOULDER_LAYERS),
                    String.valueOf(status.ticks())), false);
        }
        return loaded;
    }

    private static int prepare(CommandSourceStack source, String raw)
            throws CommandSyntaxException
    {
        return prepare(source, raw, null);
    }

    private static int prepare(CommandSourceStack source, String raw, String destination)
            throws CommandSyntaxException
    {
        if (destination != null && !java.util.Set.of("geofront", "surface", "hakone").contains(destination))
        {
            source.sendFailure(Component.translatable("message.projectseele.eva_exit_argument"));
            return 0;
        }
        ServerLevel level = geoFront(source);
        int requested = parseVariant(raw);
        int accepted = 0;
        for (int variant = 0; variant < 3; variant++)
        {
            if (requested >= 0 && requested != variant)
            {
                continue;
            }
            if(source.getEntity() instanceof ServerPlayer caller&&NervRouteRuntimeR52.claimed(level)
                    &&!NervRouteRuntimeR52.pending(level,variant))
            {
                var eva=EvaLogisticsDirector.canonicalUnit(level,variant);
                if(eva!=null&&EvaLogisticsDirector.inAssignedHangarR33(level,eva))
                    eva.getPersistentData().putUUID("R32SortieCommander",caller.getUUID());
            }
            ActionResult result = destination == null
                    ? EvaLogisticsDirector.requestPrepare(level, variant)
                    : NervRouteRuntimeR52.prepare(level, variant, destination);
            int current = variant;
            source.sendSuccess(() -> Component.translatable("ops.projectseele.un.unit_reply", String.format(Locale.ROOT, "EVA-%02d", current), com.projectseele.world.OperationText.read(result.message())), false);
            if (result.accepted())
            {
                accepted++;
            }
        }
        return accepted;
    }

    private static int cancel(CommandSourceStack source, String raw)
            throws CommandSyntaxException
    {
        ServerLevel level = geoFront(source);
        int requested = parseVariant(raw);
        int accepted = 0;
        for (int variant = 0; variant < 3; variant++)
        {
            if (requested >= 0 && requested != variant) continue;
            ActionResult result = EvaLogisticsDirector.requestCancel(level, variant);
            int current = variant;
            source.sendSuccess(() -> Component.translatable("ops.projectseele.un.unit_reply", String.format(Locale.ROOT, "EVA-%02d", current), com.projectseele.world.OperationText.read(result.message())), false);
            if (result.accepted()) accepted++;
        }
        return accepted;
    }

    private static int reset(CommandSourceStack source, String raw)
            throws CommandSyntaxException
    {
        ServerLevel level = geoFront(source);
        if (FacilityWorldPolicy.legacyGenerationAllowed(level.getServer()))
        {
            EvaHangarBuilder.ensure(
                    level, IntegratedNervMapBuilder.GEOFRONT_ORIGIN);
        }
        int requested = parseVariant(raw);
        if(NervRouteRuntimeR52.claimed(level))return com.projectseele.world.EvaMaintenanceResetR53.request(source,level,requested);
        int reset = 0;
        for (int variant = 0; variant < 3; variant++)
        {
            if (requested >= 0 && requested != variant)
            {
                continue;
            }
            EvaUnit01Entity unit;
            try{unit=EvaLogisticsDirector.forceReset(level,variant);}
            catch(IllegalStateException held){source.sendFailure(com.projectseele.world.OperationText.read(held.getMessage()));continue;}
            int current = variant;
            source.sendSuccess(() -> Component.translatable("message.projectseele.eva_reset", String.format(Locale.ROOT, "EVA-%02d", current)), false);
            reset++;
        }
        return reset;
    }

    private static int launch(CommandSourceStack source, String raw)
            throws CommandSyntaxException
    {
        return requestForVariants(source, raw, true);
    }

    private static int recover(CommandSourceStack source, String raw)
            throws CommandSyntaxException
    {
        return requestForVariants(source, raw, false);
    }

    private static int requestForVariants(CommandSourceStack source, String raw,
                                          boolean launch)
            throws CommandSyntaxException
    {
        ServerLevel level = geoFront(source);
        int requested = parseVariant(raw);
        int accepted = 0;
        for (int variant = 0; variant < 3; variant++)
        {
            if (requested >= 0 && requested != variant)
            {
                continue;
            }
            ActionResult result = launch
                    ? EvaLogisticsDirector.requestLaunch(level, variant)
                    : EvaLogisticsDirector.requestRecovery(level, variant);
            int current = variant;
            source.sendSuccess(() -> Component.translatable("ops.projectseele.un.unit_reply", String.format(Locale.ROOT, "EVA-%02d", current), com.projectseele.world.OperationText.read(result.message())), false);
            if (result.accepted())
            {
                accepted++;
            }
        }
        return accepted;
    }

    private static int dummyStart(CommandSourceStack source, String raw)
            throws CommandSyntaxException
    {
        ServerLevel level = geoFront(source);
        int variant = parseVariant(raw);
        if (variant < 0)
        {
            throw new IllegalArgumentException(
                    "Start one dummy at a time: unit00, unit01 or unit02.");
        }
        TrainingPilotDirector.ActionResult result =
                TrainingPilotDirector.start(level, variant);
        source.sendSuccess(() -> com.projectseele.world.OperationText.read(result.message()), false);
        return result.accepted() ? 1 : 0;
    }

    private static int dummyStop(CommandSourceStack source, String raw)
            throws CommandSyntaxException
    {
        ServerLevel level = geoFront(source);
        int accepted = TrainingPilotDirector.stop(level, parseVariant(raw));
        source.sendSuccess(() -> accepted > 0
                ? Component.translatable("message.projectseele.eva_standby_accepted", accepted)
                : Component.translatable("message.projectseele.eva_standby_refused"), false);
        return accepted;
    }

    private static int dummyStatus(CommandSourceStack source)
            throws CommandSyntaxException
    {
        ServerLevel level = geoFront(source);
        int count = 0;
        for (com.projectseele.entity.TrainingPilotEntity pilot
                : TrainingPilotDirector.pilots(level))
        {
            source.sendSuccess(() -> Component.literal(String.format(Locale.ROOT,
                    "DUMMY EVA-%02d stage=%s vehicle=%s position=%s",
                    pilot.getAssignedVariant(),
                    switch(pilot.getTrainingStage())
                    {
                        case com.projectseele.entity.TrainingPilotEntity.STAGE_LINKED -> "LINKED";
                        case com.projectseele.entity.TrainingPilotEntity.STAGE_IN_PLUG -> "IN_PLUG";
                        case com.projectseele.entity.TrainingPilotEntity.STAGE_STANDBY -> pilot.getPersistentData().getString("SeelePilotRouteR30").equals("hold")?"ROUTE_HELD":"STANDBY";
                        default -> "WALKING";
                    },
                    pilot.getVehicle() == null ? "none"
                            : pilot.getVehicle().getStringUUID(),
                    pilot.blockPosition().toShortString())), false);
            source.sendSuccess(()->Component.translatable("message.projectseele.eva_logistics_commands.dummy_path_s", TrainingPilotDirector.routeTraceR47(level,pilot)),false);
            String fault=pilot.getPersistentData().getString("SeelePilotLastRouteFaultR47");
            if(!fault.isEmpty())source.sendSuccess(()->Component.translatable("message.projectseele.eva_logistics_commands.dummy_last_fault_s", fault),false);
            String nativeFault=pilot.getPersistentData().getString("SeelePilotNativePathFailureR47");
            if(!nativeFault.isEmpty())source.sendSuccess(()->Component.translatable("message.projectseele.eva_logistics_commands.dummy_last_native_path_s", nativeFault),false);
            count++;
        }
        if (count == 0)
        {
            source.sendSuccess(() -> Component.translatable("message.projectseele.eva_no_pilots"), false);
        }
        return count;
    }

    public static int enterHangar(CommandSourceStack source)
            throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        ServerLevel level = geoFront(source);
        if(com.projectseele.world.NervTravelDirectoryR52.applies(level))
            return SeeleTravelCommandsR43.teleport(source,"hangar");
        EvaLogisticsDirector.ensureFleet(level);
        BlockPos target;
        if (FacilityWorldPolicy.isS20Rebuild(level.getServer()))
        {
            target = com.projectseele.world.RegionalFacilityLayout.evaOrigin(level).offset(
                    0, EvaHangarBuilder.GALLERY_Y + 1,
                    EvaHangarBuilder.GALLERY_Z);
        }
        else if (FacilityV2EvaRuntime.ready(level, 1))
        {
            target = FacilityV2EvaRuntime.statusControl(level, 1)
                    .above();
        }
        else
        {
            IntegratedNervMapBuilder.prepareRuntime(level);
            target = IntegratedNervMapBuilder.GEOFRONT_ORIGIN.offset(
                    0, EvaHangarBuilder.GALLERY_Y + 1,
                    EvaHangarBuilder.GALLERY_Z - 1);
        }
        player.stopRiding();
        player.teleportTo(level, target.getX() + 0.5D, target.getY(),
                target.getZ() + 0.5D, 0.0F, 4.0F);
        player.fallDistance=0;player.setDeltaMovement(net.minecraft.world.phys.Vec3.ZERO);
        source.sendSuccess(() -> Component.translatable("message.projectseele.eva_hangar_arrival"), false);
        return 1;
    }

    private static ServerLevel geoFront(CommandSourceStack source)
            throws CommandSyntaxException
    {
        ServerLevel level = source.getServer().getLevel(GeoFrontCommands.GEOFRONT);
        if (level == null)
        {
            throw NO_GEOFRONT.create();
        }
        return level;
    }

    /** Returns -1 for all. */
    private static int parseVariant(String raw) throws CommandSyntaxException
    {
        String normalized = raw.toLowerCase(Locale.ROOT)
                .replace("eva", "").replace("unit", "")
                .replace("-", "").replace("_", "");
        return switch (normalized)
        {
            case "all", "fleet" -> -1;
            case "0", "00", "rei" -> 0;
            case "1", "01", "shinji" -> 1;
            case "2", "02", "asuka" -> 2;
            default -> throw UNKNOWN_VARIANT.create();
        };
    }
}
