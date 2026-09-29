package com.projectseele.visual;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.context.CommandContext;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.NervArmamentStationEntity;
import com.projectseele.registry.ModEntities;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Reversible test controls for the blockless armament-building prototype. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID,
        bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class ArmamentStationCommands
{
    private static final double COMMAND_RANGE = 128.0D;

    private ArmamentStationCommands()
    {
    }

    @SubscribeEvent
    public static void register(RegisterCommandsEvent event)
    {
        CommandDispatcher<CommandSourceStack> dispatcher =
                event.getDispatcher();
        if(!DevelopmentCommandsR43.enabled())
        {
            dispatcher.register(Commands.literal("seele").then(Commands.literal("armament").requires(s->s.hasPermission(2))
                    .then(Commands.literal("deploy").executes(c->change(c,true)))
                    .then(Commands.literal("recall").executes(c->change(c,false)))
                    .then(Commands.literal("status").executes(ArmamentStationCommands::status))));
            return;
        }
        dispatcher.register(Commands.literal("seele")
                .then(Commands.literal("armament")
                        .requires(source -> source.hasPermission(2))
                        .then(Commands.literal("spawn_here")
                                .executes(ArmamentStationCommands::spawnHere))
                        .then(Commands.literal("deploy")
                                .executes(context -> change(context, true)))
                        .then(Commands.literal("recall")
                                .executes(context -> change(context, false)))
                        .then(Commands.literal("status")
                                .executes(ArmamentStationCommands::status))
                        .then(Commands.literal("remove")
                                .executes(ArmamentStationCommands::remove))));
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
        NervArmamentStationEntity station = nearest(
                context.getSource().getPlayerOrException());
        if (station == null)
        {
            context.getSource().sendFailure(Component.translatable(
                    "msg.projectseele.armament_missing"));
            return 0;
        }
        context.getSource().sendSuccess(() -> Component.literal(
                "NERV ARMAMENT: " + station.stateName()
                        + " / stocked=" + station.isStocked()
                        + " / " + station.blockPosition().toShortString()),
                false);
        return 1;
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
