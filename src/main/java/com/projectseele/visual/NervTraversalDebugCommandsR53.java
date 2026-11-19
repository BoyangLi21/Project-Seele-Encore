package com.projectseele.visual;

import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import com.projectseele.world.NervTraversalPolicyR53;
import com.projectseele.world.NervTraversalPolicyR53.Mode;
import net.minecraft.ChatFormatting;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.network.chat.Component;

/** Development control of the current dimension's runtime traversal policy and sortie state (/seele dev). */
public final class NervTraversalDebugCommandsR53
{
    private NervTraversalDebugCommandsR53() {}

    public static LiteralArgumentBuilder<CommandSourceStack> sortieCommand()
    {
        return Commands.literal("sortie").executes(context -> {
            var source=context.getSource();
            for(var level:source.getServer().getAllLevels())
                if(com.projectseele.world.NervRouteRuntimeR52.claimed(level))
                    for(String line:com.projectseele.world.NervRouteRuntimeR52.sortieStatusR53(level))
                        source.sendSuccess(()->Component.literal(line),false);
            return 1;
        });
    }

    public static LiteralArgumentBuilder<CommandSourceStack> traversalCommand()
    {
        return Commands.literal("traversal")
                .executes(context -> status(context.getSource()))
                .then(Commands.literal("status")
                        .executes(context -> status(context.getSource())))
                .then(Commands.literal("normal")
                        .executes(context -> set(context.getSource(), Mode.NORMAL)))
                .then(Commands.literal("strict")
                        .executes(context -> set(context.getSource(), Mode.STRICT)))
                .then(Commands.literal("bypass")
                        .executes(context -> set(context.getSource(), Mode.BYPASS)));
    }

    private static int status(CommandSourceStack source)
    {
        source.sendSuccess(() -> message(source, NervTraversalPolicyR53.mode(source.getLevel())), false);
        return 1;
    }

    private static int set(CommandSourceStack source, Mode mode)
    {
        NervTraversalPolicyR53.setMode(source.getLevel(), mode);
        source.sendSuccess(() -> message(source, mode), true);
        return 1;
    }

    private static Component message(CommandSourceStack source, Mode mode)
    {
        Component description = switch (mode)
        {
            case NORMAL -> Component.translatable("ops.projectseele.debug.traversal.normal");
            case STRICT -> Component.translatable("ops.projectseele.debug.traversal.strict");
            case BYPASS -> Component.translatable("ops.projectseele.debug.traversal.bypass");
        };
        ChatFormatting color = switch (mode)
        {
            case NORMAL -> ChatFormatting.GREEN;
            case STRICT -> ChatFormatting.GOLD;
            case BYPASS -> ChatFormatting.RED;
        };
        return Component.translatable("ops.projectseele.debug.traversal.prefix", source.getLevel().dimension().location().toString())
                .withStyle(color, ChatFormatting.BOLD)
                .append(Component.translatable("ops.projectseele.debug.traversal.scope", description)
                        .withStyle(style -> style.withBold(false)));
    }
}
