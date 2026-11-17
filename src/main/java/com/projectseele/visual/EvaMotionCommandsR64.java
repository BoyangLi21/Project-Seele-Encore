package com.projectseele.visual;

import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import com.projectseele.config.SeeleConfig;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.network.chat.Component;

/**
 * /seele motion: which movement model piloted EVAs run on this server and which gait tier, so the two models
 * and the three gaits can be tried against each other in one sitting. It writes the server's [eva_motion] keys;
 * every Unit follows on its next tick and tells its clients. /seele motion jump <blocks> sets how high a Unit of
 * the planted model jumps (0: as up to R63), so heights can be tried one after another.
 */
public final class EvaMotionCommandsR64
{
    private EvaMotionCommandsR64() {}

    public static LiteralArgumentBuilder<CommandSourceStack> motionCommand()
    {
        var motion = Commands.literal("motion").executes(context -> status(context.getSource()));
        for (String model : new String[] {"legacy", "planted"})
        {
            motion.then(Commands.literal(model).executes(context -> set(context.getSource(), model, null)));
        }
        var tier = Commands.literal("tier");
        for (String name : new String[] {"A", "B", "C"})
        {
            tier.then(Commands.literal(name).executes(context -> set(context.getSource(), null, name)));
            tier.then(Commands.literal(name.toLowerCase(java.util.Locale.ROOT)).executes(context -> set(context.getSource(), null, name)));
        }
        var jump = Commands.literal("jump").then(Commands.argument("blocks", IntegerArgumentType.integer(0, 120))
                .executes(context ->
                {
                    SeeleConfig.EVA_JUMP_HEIGHT.set((double) IntegerArgumentType.getInteger(context, "blocks"));
                    return status(context.getSource());
                }));
        return motion.then(tier).then(jump);
    }

    private static int status(CommandSourceStack source)
    {
        source.sendSuccess(() -> Component.literal("EVA movement: " + SeeleConfig.EVA_MOTION_MODEL.get()
                + ", gait tier " + SeeleConfig.EVA_GAIT_TIER.get()
                + ", jump " + Math.round(SeeleConfig.EVA_JUMP_HEIGHT.get()) + " blocks"
                + " (planted is Unit-01 only for now; /seele motion legacy|planted, /seele motion tier A|B|C,"
                + " /seele motion jump <0-120>, 0 = the old jump)"), false);
        return 1;
    }

    private static int set(CommandSourceStack source, String model, String tier)
    {
        if (model != null)
        {
            SeeleConfig.EVA_MOTION_MODEL.set(model);
        }
        if (tier != null)
        {
            SeeleConfig.EVA_GAIT_TIER.set(tier);
        }
        return status(source);
    }
}
