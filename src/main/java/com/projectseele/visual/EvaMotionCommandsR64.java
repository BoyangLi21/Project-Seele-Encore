package com.projectseele.visual;

import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import com.projectseele.config.SeeleConfig;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.network.chat.Component;

/**
 * /seele motion: which movement model piloted EVAs run on this server and which gait tier, so the two models
 * and the three gaits can be tried against each other in one sitting. It writes the server's [eva_motion] keys;
 * every Unit follows on its next tick and tells its clients.
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
        return motion.then(tier);
    }

    private static int status(CommandSourceStack source)
    {
        source.sendSuccess(() -> Component.literal("EVA movement: " + SeeleConfig.EVA_MOTION_MODEL.get()
                + ", gait tier " + SeeleConfig.EVA_GAIT_TIER.get()
                + " (planted is Unit-01 only for now; /seele motion legacy|planted, /seele motion tier A|B|C)"), false);
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
