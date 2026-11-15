package com.projectseele.visual;

import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import com.projectseele.config.SeeleConfig;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.network.chat.Component;

/**
 * /seele combat: which combat core piloted EVAs fight with on this server, and how the pause at a hit is sized,
 * so the two can be tried against each other in one sitting. It writes the server's [eva_combat] keys; every
 * Unit follows on its next tick and tells its clients.
 */
public final class EvaCombatCommandsR64
{
    private EvaCombatCommandsR64() {}

    public static LiteralArgumentBuilder<CommandSourceStack> combatCommand()
    {
        var combat = Commands.literal("combat").executes(context -> status(context.getSource()));
        for (String model : new String[] {"legacy", "frames"})
        {
            combat.then(Commands.literal(model).executes(context -> set(context.getSource(), model, null)));
        }
        var stop = Commands.literal("hitstop");
        for (String name : new String[] {"tiered", "flat"})
        {
            stop.then(Commands.literal(name).executes(context -> set(context.getSource(), null, name)));
        }
        return combat.then(stop);
    }

    private static int status(CommandSourceStack source)
    {
        source.sendSuccess(() -> Component.literal("EVA combat: " + SeeleConfig.EVA_COMBAT_MODEL.get()
                + ", hit-stop " + SeeleConfig.EVA_HIT_STOP.get()
                + " (frames is Unit-01 with bare hands or the knife for now; /seele combat legacy|frames, /seele combat hitstop tiered|flat)"), false);
        return 1;
    }

    private static int set(CommandSourceStack source, String model, String stop)
    {
        if (model != null)
        {
            SeeleConfig.EVA_COMBAT_MODEL.set(model);
        }
        if (stop != null)
        {
            SeeleConfig.EVA_HIT_STOP.set(stop);
        }
        return status(source);
    }
}
