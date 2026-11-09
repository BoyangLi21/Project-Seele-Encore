package com.projectseele.visual;

import com.mojang.brigadier.arguments.DoubleArgumentType;
import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import com.projectseele.capability.EvaPilotCapability;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;

/** Development inspection and acceleration for synchronization testing (/seele dev pilot). */
public final class PilotCommands
{
    private PilotCommands() {}

    public static LiteralArgumentBuilder<CommandSourceStack> pilotCommand()
    {
        return Commands.literal("pilot")
                .then(Commands.literal("sync")
                        .executes(context -> status(context.getSource()))
                        .then(Commands.literal("set")
                                .then(Commands.argument("value",
                                                DoubleArgumentType.doubleArg(0.0D, 100.0D))
                                        .executes(context -> set(context.getSource(),
                                                DoubleArgumentType.getDouble(context,
                                                        "value"))))));
    }

    private static int status(CommandSourceStack source) throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        float value = EvaPilotCapability.synchronization(player);
        source.sendSuccess(() -> Component.literal(String.format(
                "Pilot synchronization: %.1f%%", value)), false);
        return Math.round(value * 10.0F);
    }

    private static int set(CommandSourceStack source, double value) throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        player.getCapability(EvaPilotCapability.DATA).ifPresent(
                data -> data.setSynchronization((float) value));
        float applied = EvaPilotCapability.synchronization(player);
        source.sendSuccess(() -> Component.literal(String.format(
                "Pilot synchronization set to %.1f%%", applied)), true);
        return Math.round(applied * 10.0F);
    }
}
