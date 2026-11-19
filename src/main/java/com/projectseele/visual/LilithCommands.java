package com.projectseele.visual;

import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import com.projectseele.entity.LilithEntity;
import com.projectseele.registry.ModEntities;
import com.projectseele.world.FacilitySchemaV2;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.commands.SharedSuggestionProvider;
import net.minecraft.network.chat.Component;

/** /seele lilith spear auto|present|removed: how Terminal Dogma's sealing spear is shown. */
public final class LilithCommands
{
    public static LiteralArgumentBuilder<CommandSourceStack> lilithCommand()
    {
        return Commands.literal("lilith")
                .then(Commands.literal("spear")
                        .executes(context -> report(context.getSource()))
                        .then(Commands.argument("mode", StringArgumentType.word())
                                .suggests((context, builder) ->
                                        SharedSuggestionProvider.suggest(LilithEntity.SPEAR_MODES, builder))
                                .executes(context -> set(context.getSource(),
                                        StringArgumentType.getString(context, "mode")))));
    }

    private static java.util.List<? extends LilithEntity> specimens(CommandSourceStack source)
    {
        var level = source.getServer().getLevel(FacilitySchemaV2.DIMENSION);
        if (level == null)
        {
            return java.util.List.of();
        }
        return level.getEntities(ModEntities.LILITH.get(), entity -> true);
    }

    private static int report(CommandSourceStack source)
    {
        var found = specimens(source);
        if (found.isEmpty())
        {
            source.sendFailure(Component.translatable("message.projectseele.lilith.unloaded"));
            return 0;
        }
        var lilith = found.get(0);
        source.sendSuccess(() -> Component.literal("朗基努斯之枪：" + lilith.getSpearMode()
                + (lilith.isSpearShown() ? "（显示）" : "（已取走）")), false);
        return found.size();
    }

    private static int set(CommandSourceStack source, String mode)
    {
        if (!LilithEntity.SPEAR_MODES.contains(mode))
        {
            source.sendFailure(Component.translatable("message.projectseele.lilith.usage"));
            return 0;
        }
        var found = specimens(source);
        if (found.isEmpty())
        {
            source.sendFailure(Component.translatable("message.projectseele.lilith.approach"));
            return 0;
        }
        found.forEach(lilith -> lilith.setSpearMode(mode));
        source.sendSuccess(() -> Component.literal("朗基努斯之枪已设为 " + mode + "。"), true);
        return found.size();
    }

    private LilithCommands()
    {
    }
}
