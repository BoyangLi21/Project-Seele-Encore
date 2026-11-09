package com.projectseele.visual;

import java.util.List;
import java.util.stream.Stream;

import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import com.projectseele.world.NervWayfindingR24;
import com.projectseele.world.OperatorNavigationProductionR45;
import com.projectseele.world.StaffConversationR24;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.commands.SharedSuggestionProvider;
import net.minecraft.network.chat.Component;

/** Player commands for calling NERV staff and for walking guidance. */
public final class NervStaffCommands
{
    public static LiteralArgumentBuilder<CommandSourceStack> callCommand()
    {
        return Commands.literal("call")
                .executes(c -> StaffConversationR24.contact(c.getSource().getPlayerOrException(), "美里"))
                // Greedy so Chinese names parse unquoted; quotes left over from /nerv contact "美里" are dropped.
                .then(Commands.argument("person", StringArgumentType.greedyString())
                        .suggests((c, b) -> SharedSuggestionProvider.suggest(
                                List.of("misato", "ritsuko", "fuyutsuki", "maya", "美里", "律子", "冬月", "摩耶"), b))
                        .executes(c -> StaffConversationR24.contact(c.getSource().getPlayerOrException(),
                                StringArgumentType.getString(c, "person").replace("\"", ""))));
    }

    public static LiteralArgumentBuilder<CommandSourceStack> routeCommand()
    {
        return Commands.literal("route")
                .then(Commands.argument("destination", StringArgumentType.word())
                        .suggests((c, b) -> SharedSuggestionProvider.suggest(Stream.concat(Stream.concat(
                                NervWayfindingR24.GOALS.stream(),
                                OperatorNavigationProductionR45.availableGoals(c.getSource().getPlayer()).stream()),
                                Stream.of("stop")), b))
                        .executes(c ->
                        {
                            var player = c.getSource().getPlayerOrException();
                            player.sendSystemMessage(Component.literal(NervWayfindingR24.start(player,
                                    StringArgumentType.getString(c, "destination"))));
                            return 1;
                        }));
    }

    private NervStaffCommands() {}
}
