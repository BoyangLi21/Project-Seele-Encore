package com.projectseele.visual;

import com.projectseele.ProjectSeele;
import com.projectseele.world.NervTraversalPolicyR53;
import com.projectseele.world.NervTraversalPolicyR53.Mode;
import net.minecraft.ChatFormatting;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.network.chat.Component;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Explicit operator control of the current dimension's runtime traversal policy. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class NervTraversalDebugCommandsR53
{
    private NervTraversalDebugCommandsR53() {}

    @SubscribeEvent
    public static void register(RegisterCommandsEvent event)
    {
        event.getDispatcher().register(Commands.literal("nerv")
                .then(Commands.literal("debug")
                        .requires(source -> source.hasPermission(2))
                        .then(Commands.literal("sortie").executes(context -> {
                            var source=context.getSource();
                            for(var level:source.getServer().getAllLevels())
                                if(com.projectseele.world.NervRouteRuntimeR52.claimed(level))
                                    for(String line:com.projectseele.world.NervRouteRuntimeR52.sortieStatusR53(level))
                                        source.sendSuccess(()->Component.literal(line),false);
                            return 1;
                        }))
                        .then(Commands.literal("traversal")
                                .executes(context -> status(context.getSource()))
                                .then(Commands.literal("status")
                                        .executes(context -> status(context.getSource())))
                                .then(Commands.literal("normal")
                                        .executes(context -> set(context.getSource(), Mode.NORMAL)))
                                .then(Commands.literal("strict")
                                        .executes(context -> set(context.getSource(), Mode.STRICT)))
                                .then(Commands.literal("bypass")
                                        .executes(context -> set(context.getSource(), Mode.BYPASS))))));
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
        String description = switch (mode)
        {
            case NORMAL -> "正常模式：关闭全路线高精网格硬预检，保留运行时运动检查。";
            case STRICT -> "严格诊断：按需执行严格检查，会阻止不通过的运动。";
            case BYPASS -> "调试绕过已开启：绕过运动碰撞检查；身份、租约、原任务与设备动作仍保留。";
        };
        ChatFormatting color = switch (mode)
        {
            case NORMAL -> ChatFormatting.GREEN;
            case STRICT -> ChatFormatting.GOLD;
            case BYPASS -> ChatFormatting.RED;
        };
        return Component.literal("[NERV 运动调试 / " + source.getLevel().dimension().location() + "] ")
                .withStyle(color, ChatFormatting.BOLD)
                .append(Component.literal(description
                        + " 仅当前维度、本次运行有效；重启恢复 NORMAL。恢复命令：/nerv debug traversal normal")
                        .withStyle(style -> style.withBold(false)));
    }
}
