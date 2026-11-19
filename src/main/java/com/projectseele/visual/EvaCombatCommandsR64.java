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
        var flow = Commands.literal("flow");
        for (String name : new String[] {"on", "off", "clock", "stop", "curve", "fade", "stand", "kick"})
        {
            flow.then(Commands.literal(name).executes(context -> flow(context.getSource(), name)));
        }
        return combat.then(stop).then(flow);
    }

    private static int status(CommandSourceStack source)
    {
        source.sendSuccess(() -> Component.translatable("message.projectseele.eva_combat_commands_r64.eva_combat_s_hit_stop_s_flow",
                        SeeleConfig.EVA_COMBAT_MODEL.get(), SeeleConfig.EVA_HIT_STOP.get(), SeeleConfig.EVA_COMBAT_FLOW.get()), false);
        return 1;
    }

    /** on, off, or one part by name: that part is turned, the others stay. */
    private static int flow(CommandSourceStack source, String name)
    {
        if (name.equals("on") || name.equals("off"))
        {
            SeeleConfig.EVA_COMBAT_FLOW.set(name);
            return status(source);
        }
        var parts = new java.util.LinkedHashSet<String>();
        byte now = com.projectseele.entity.EvaCombatModelR64.flowParts(SeeleConfig.EVA_COMBAT_FLOW.get());
        for (String part : new String[] {"clock", "stop", "curve", "fade", "stand", "kick"})
        {
            boolean has = (now & com.projectseele.entity.EvaCombatModelR64.flowParts(part)) != 0;
            if (has != part.equals(name))
            {
                parts.add(part);
            }
        }
        SeeleConfig.EVA_COMBAT_FLOW.set(parts.isEmpty() ? "off" : parts.size() == 6 ? "on" : String.join(",", parts));
        return status(source);
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
