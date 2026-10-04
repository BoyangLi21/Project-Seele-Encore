package com.projectseele.visual;

import com.projectseele.ProjectSeele;
import com.projectseele.world.NervStaffDialogue;
import com.mojang.brigadier.arguments.StringArgumentType;
import net.minecraft.commands.Commands;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class NervStaffCommands
{
    @SubscribeEvent public static void register(RegisterCommandsEvent event)
    {
        event.getDispatcher().register(Commands.literal("nerv").then(Commands.literal("route")
                .then(Commands.argument("destination",StringArgumentType.word())
                        .suggests((c,b)->net.minecraft.commands.SharedSuggestionProvider.suggest(java.util.stream.Stream.concat(java.util.stream.Stream.concat(com.projectseele.world.NervWayfindingR24.GOALS.stream(),com.projectseele.world.OperatorNavigationProductionR45.availableGoals(c.getSource().getPlayer()).stream()),java.util.stream.Stream.of("stop")),b))
                        .executes(c->{var player=c.getSource().getPlayerOrException();player.sendSystemMessage(net.minecraft.network.chat.Component.literal(com.projectseele.world.NervWayfindingR24.start(player,StringArgumentType.getString(c,"destination"))));return 1;}))));
        event.getDispatcher().register(Commands.literal("nerv").then(Commands.literal("contact")
                .executes(c->com.projectseele.world.StaffConversationR24.contact(c.getSource().getPlayerOrException(),"美里"))
                .then(Commands.argument("person",StringArgumentType.string())
                        .suggests((c,b)->net.minecraft.commands.SharedSuggestionProvider.suggest(java.util.List.of("美里","律子","冬月","misato","ritsuko","fuyutsuki"),b))
                        .executes(c->com.projectseele.world.StaffConversationR24.contact(c.getSource().getPlayerOrException(),StringArgumentType.getString(c,"person"))))));
        event.getDispatcher().register(Commands.literal("nerv").then(Commands.literal("talk")
                .then(Commands.argument("person",StringArgumentType.string()).then(Commands.argument("message",StringArgumentType.greedyString())
                        .executes(c->NervStaffDialogue.talk(c.getSource().getPlayerOrException(),StringArgumentType.getString(c,"person"),StringArgumentType.getString(c,"message")))))));
    }
    private NervStaffCommands() {}
}
