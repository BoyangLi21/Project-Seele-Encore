package com.projectseele.visual;

import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import com.mojang.brigadier.context.CommandContext;
import com.projectseele.entity.NervArmamentStationEntity;
import com.projectseele.registry.ModEntities;
import com.projectseele.world.EvaPilotResolver;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.phys.Vec3;

/** Weapon-well controls (/seele armament) and the prototype's reversible test controls (/seele dev armament). */
public final class ArmamentStationCommands
{
    private static final double COMMAND_RANGE = 128.0D;

    private ArmamentStationCommands()
    {
    }

    public static LiteralArgumentBuilder<CommandSourceStack> armamentCommand()
    {
        return Commands.literal("armament")
                .then(payloadBranches("deploy",true))
                .then(payloadBranches("recall",false))
                .then(Commands.literal("status").executes(ArmamentStationCommands::status));
    }

    public static LiteralArgumentBuilder<CommandSourceStack> devArmamentCommand()
    {
        return Commands.literal("armament")
                .then(Commands.literal("spawn_here")
                        .executes(ArmamentStationCommands::spawnHere))
                .then(Commands.literal("remove")
                        .executes(ArmamentStationCommands::remove));
    }

    private static LiteralArgumentBuilder<CommandSourceStack> payloadBranches(String name,boolean deploy)
    {
        return Commands.literal(name).executes(c->change(c,deploy))
                .then(Commands.literal("rifle").executes(c->changePayload(c,deploy,4)))
                .then(Commands.literal("sword").executes(c->changePayload(c,deploy,6)))
                .then(Commands.literal("shield").executes(c->changePayload(c,deploy,7)));
    }

    private static int changePayload(CommandContext<CommandSourceStack> context,boolean deploy,int payload)
    {
        ServerLevel level=context.getSource().getServer().getLevel(GeoFrontCommands.GEOFRONT);
        // With spare-weapon towers armed, "rifle" is the tower nearest to whoever gives the order.
        NervArmamentStationEntity station=level==null?null:payload==4
                ?com.projectseele.world.ArmamentTowersR64.active(level)
                        ?com.projectseele.world.ArmamentTowersR64.nearest(level,context.getSource().getPosition())
                        :NervArmamentStationEntity.commandStation(level)
                :com.projectseele.world.EquipmentVaultsR47.recordedStationR47(level,payload);
        if(station==null||!(deploy?station.deploy():station.recall()))
        {
            context.getSource().sendFailure(Component.translatable("msg.projectseele.armament_command_rejected"));return 0;
        }
        if(station.towerR64()>=0)
        {
            // A tower called while the city moves does not start: the call is kept until the city rests.
            boolean kept=deploy&&station.getStationState()==NervArmamentStationEntity.STOWED;
            String key = kept ? "message.projectseele.station.tower_kept"
                    : deploy ? "message.projectseele.station.tower_deploy" : "message.projectseele.station.tower_recall";
            context.getSource().sendSuccess(() -> Component.translatable(key, station.towerR64(),
                    station.blockPosition().toShortString()), false);
            return 1;
        }
        Component cargo = Component.translatable(payload == 7 ? "message.projectseele.station.shield"
                : payload == 6 ? "message.projectseele.station.sword" : "message.projectseele.station.rifle");
        context.getSource().sendSuccess(() -> Component.translatable(deploy
                ? "message.projectseele.station.well_deploy" : "message.projectseele.station.well_recall",
                cargo, station.blockPosition().toShortString()), false);
        return 1;
    }

    private static int spawnHere(CommandContext<CommandSourceStack> context)
            throws com.mojang.brigadier.exceptions.CommandSyntaxException
    {
        ServerPlayer player = context.getSource().getPlayerOrException();
        ServerLevel level = player.serverLevel();
        NervArmamentStationEntity existing = nearest(player);
        if (existing != null && existing.distanceToSqr(player) < 16.0D * 16.0D)
        {
            context.getSource().sendFailure(Component.translatable(
                    "msg.projectseele.armament_spawn_exists"));
            return 0;
        }
        NervArmamentStationEntity station =
                ModEntities.NERV_ARMAMENT_STATION.get().create(level);
        if (station == null)
        {
            return 0;
        }
        station.setPos(Math.floor(player.getX()) + 0.5D,
                Math.floor(player.getY()),
                Math.floor(player.getZ()) + 0.5D);
        station.setYRot(player.getYRot());
        if (!level.addFreshEntity(station))
        {
            return 0;
        }
        context.getSource().sendSuccess(() -> Component.translatable(
                "msg.projectseele.armament_spawned",
                station.blockPosition().toShortString()), false);
        return 1;
    }

    private static int change(CommandContext<CommandSourceStack> context,
                              boolean deploy)
            throws com.mojang.brigadier.exceptions.CommandSyntaxException
    {
        ServerPlayer player = context.getSource().getPlayerOrException();
        NervArmamentStationEntity station = nearest(player);
        boolean changed = station != null
                && (deploy ? station.deploy() : station.recall());
        if (!changed)
        {
            context.getSource().sendFailure(Component.translatable(
                    "msg.projectseele.armament_command_rejected"));
            return 0;
        }
        context.getSource().sendSuccess(() -> Component.translatable(
                deploy ? "msg.projectseele.armament_deploying"
                        : "msg.projectseele.armament_recalling"), false);
        return 1;
    }

    private static int status(CommandContext<CommandSourceStack> context)
            throws com.mojang.brigadier.exceptions.CommandSyntaxException
    {
        ServerPlayer player = context.getSource().getPlayerOrException();
        var eva = EvaPilotResolver.controlTarget(player);
        // The pilot's seat can sit above the station search's vertical reach.
        Vec3 centre = eva == null ? player.position() : eva.position();
        NervArmamentStationEntity station = NervArmamentStationEntity.nearest(
                player.level(), centre, COMMAND_RANGE, false);
        if (station == null)
        {
            context.getSource().sendFailure(Component.translatable(
                    "msg.projectseele.armament_missing"));
            return 0;
        }
        Component label = station.towerR64() >= 0
                ? Component.translatable("message.projectseele.station.tower", station.towerR64())
                : Component.translatable("message.projectseele.station.well");
        context.getSource().sendSuccess(() -> Component.translatable("message.projectseele.station.status",
                label, stateName(station.stateName()), Component.translatable(station.isStocked()
                        ? "message.projectseele.station.loaded" : "message.projectseele.station.empty"),
                station.blockPosition().toShortString()), false);
        return 1;
    }

    private static Component stateName(String state)
    {
        return switch (state)
        {
            case "OPENING" -> Component.translatable("message.projectseele.station.opening");
            case "RISING" -> Component.translatable("message.projectseele.station.rising");
            case "READY" -> Component.translatable("message.projectseele.station.ready");
            case "EMPTY" -> Component.translatable("message.projectseele.station.collected");
            case "LOWERING" -> Component.translatable("message.projectseele.station.lowering");
            case "CLOSING" -> Component.translatable("message.projectseele.station.closing");
            case "DOOR_OPENING" -> Component.translatable("message.projectseele.station.door_opening");
            case "DOOR_CLOSING" -> Component.translatable("message.projectseele.station.door_closing");
            case "STOWED" -> Component.translatable("message.projectseele.station.stowed");
            default -> Component.literal(state);
        };
    }

    private static int remove(CommandContext<CommandSourceStack> context)
            throws com.mojang.brigadier.exceptions.CommandSyntaxException
    {
        NervArmamentStationEntity station = nearest(
                context.getSource().getPlayerOrException());
        if (station == null)
        {
            return 0;
        }
        if (station.towerR64() >= 0)
        {
            // A tower's station is recorded by the world and never made twice: it is not removed by hand.
            context.getSource().sendFailure(Component.translatable("message.projectseele.armament.reserve_station"));
            return 0;
        }
        station.discard();
        context.getSource().sendSuccess(() -> Component.translatable(
                "msg.projectseele.armament_removed"), false);
        return 1;
    }

    private static NervArmamentStationEntity nearest(ServerPlayer player)
    {
        Vec3 centre = player.position();
        return NervArmamentStationEntity.nearest(player.level(), centre,
                COMMAND_RANGE, false);
    }
}
