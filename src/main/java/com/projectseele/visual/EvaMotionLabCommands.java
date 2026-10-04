package com.projectseele.visual;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.network.ClientboundEvaPoseRecorderPacket;
import com.projectseele.network.SeeleNetwork;
import com.projectseele.world.EvaMotionLabDirector;
import com.projectseele.world.EvaPilotResolver;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.network.PacketDistributor;

/** Operator shortcuts for the isolated EVA motion laboratory. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID,
        bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class EvaMotionLabCommands
{
    private EvaMotionLabCommands() {}

    @SubscribeEvent
    public static void register(RegisterCommandsEvent event)
    {
        if(!DevelopmentCommandsR43.enabled())return;
        CommandDispatcher<CommandSourceStack> dispatcher =
                event.getDispatcher();
        dispatcher.register(Commands.literal("seele")
                .requires(source -> source.hasPermission(2))
                .then(Commands.literal("motionlab")
                        .then(Commands.literal("setup")
                                .executes(context -> setup(
                                        context.getSource(), false)))
                        .then(Commands.literal("reset")
                                .executes(context -> setup(
                                        context.getSource(), true)))
                        .then(Commands.literal("enter")
                                .then(Commands.argument("variant",
                                                StringArgumentType.word())
                                        .executes(context -> enter(
                                                context.getSource(),
                                                StringArgumentType.getString(
                                                        context, "variant")))))
                        .then(Commands.literal("weapon")
                                .then(Commands.argument("variant",
                                                StringArgumentType.word())
                                        .then(Commands.argument("weapon",
                                                        StringArgumentType.word())
                                                .executes(context -> weapon(
                                                        context.getSource(),
                                                        StringArgumentType.getString(
                                                                context, "variant"),
                                                        StringArgumentType.getString(
                                                                context, "weapon"))))))
                        .then(Commands.literal("demo")
                                .then(Commands.argument("variant",
                                                StringArgumentType.word())
                                        .then(Commands.argument("mode",
                                                        StringArgumentType.word())
                                                .executes(context -> demo(
                                                        context.getSource(),
                                                        StringArgumentType.getString(
                                                                context, "variant"),
                                                        StringArgumentType.getString(
                                                                context, "mode"))))))
                        .then(Commands.literal("camera")
                                .executes(context -> camera(
                                        context.getSource())))
                        .then(Commands.literal("record")
                                .then(Commands.literal("start")
                                        .executes(context -> recordStart(
                                                context.getSource(), "manual"))
                                        .then(Commands.argument("label",
                                                        StringArgumentType.word())
                                                .executes(context -> recordStart(
                                                        context.getSource(),
                                                        StringArgumentType.getString(
                                                                context, "label")))))
                                .then(Commands.literal("stop")
                                        .executes(context -> recordControl(
                                                context.getSource(),
                                                ClientboundEvaPoseRecorderPacket.STOP)))
                                .then(Commands.literal("status")
                                        .executes(context -> recordControl(
                                                context.getSource(),
                                                ClientboundEvaPoseRecorderPacket.STATUS))))));
    }

    private static int setup(CommandSourceStack source, boolean force)
            throws CommandSyntaxException
    {
        ServerLevel level = source.getLevel();
        if (!EvaMotionLabDirector.setup(level, force))
        {
            source.sendFailure(Component.literal(
                    "This command is restricted to SEELE_EVA_MOTION_LAB."));
            return 0;
        }
        if (source.getEntity() instanceof ServerPlayer player)
        {
            player.teleportTo(level, 0.5D, -59.0D, -150.5D,
                    0.0F, 0.0F);
        }
        source.sendSuccess(() -> Component.literal(
                force ? "EVA motion lab rebuilt and fleet reset."
                        : "EVA motion lab ready."), false);
        return 1;
    }

    private static int enter(CommandSourceStack source, String raw)
            throws CommandSyntaxException
    {
        int variant = variant(raw);
        if (variant < 0 || !EvaMotionLabDirector.enter(
                source.getPlayerOrException(), variant))
        {
            source.sendFailure(Component.literal(
                    "Motion-lab EVA boarding failed."));
            return 0;
        }
        source.sendSuccess(() -> Component.literal(String.format(
                "Motion-lab pilot linked to EVA-%02d.", variant)), false);
        return 1;
    }

    private static int weapon(CommandSourceStack source, String rawVariant,
                              String rawWeapon)
    {
        int variant = variant(rawVariant);
        int weapon = weapon(rawWeapon);
        if (variant < 0 || weapon < 0
                || !EvaMotionLabDirector.isMotionLab(source.getLevel())
                || !EvaMotionLabDirector.selectWeapon(source.getLevel(),
                variant, weapon))
        {
            source.sendFailure(Component.literal(
                    "Motion-lab weapon selection failed."));
            return 0;
        }
        source.sendSuccess(() -> Component.literal(
                "Motion-lab loadout changed."), false);
        return 1;
    }

    private static int camera(CommandSourceStack source)
            throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        if (!EvaMotionLabDirector.isMotionLab(player.serverLevel()))
        {
            source.sendFailure(Component.literal(
                    "This command is restricted to SEELE_EVA_MOTION_LAB."));
            return 0;
        }
        if (player.isPassenger())
        {
            player.stopRiding();
        }
        EvaMotionLabDirector.teleportCamera(player);
        return 1;
    }

    private static int demo(CommandSourceStack source, String rawVariant,
                            String mode)
    {
        int variant = variant(rawVariant);
        if (variant < 0 || !EvaMotionLabDirector.setDemo(
                source.getLevel(), variant, mode))
        {
            source.sendFailure(Component.literal(
                    "Usage: /seele motionlab demo unit01 "
                            + "walk|run|jump|attack_a|attack_b|attack_c|"
                            + "attack_combo|"
                            + "live|livepush|physics|recovery|stop"));
            return 0;
        }
        boolean physicsPreview = mode.equalsIgnoreCase("physics")
                || mode.equalsIgnoreCase("physics_walk")
                || mode.equalsIgnoreCase("preview")
                || mode.equalsIgnoreCase("physics_recovery")
                || mode.equalsIgnoreCase("recovery")
                || mode.equalsIgnoreCase("live")
                || mode.equalsIgnoreCase("physics_live")
                || mode.equalsIgnoreCase("policy")
                || mode.equalsIgnoreCase("livereset")
                || mode.equalsIgnoreCase("livepush")
                || mode.equalsIgnoreCase("attack_a")
                || mode.equalsIgnoreCase("attack_b")
                || mode.equalsIgnoreCase("attack_c")
                || mode.equalsIgnoreCase("attack_jab")
                || mode.equalsIgnoreCase("attack_cross")
                || mode.equalsIgnoreCase("attack_hook")
                || mode.equalsIgnoreCase("attack_combo")
                || mode.equalsIgnoreCase("combo")
                || mode.toLowerCase().startsWith("ordinary_attack_")
                || mode.equalsIgnoreCase("attack_right")
                || mode.equalsIgnoreCase("ordinary_attack_right")
                || mode.equalsIgnoreCase("batter_right")
                || mode.equalsIgnoreCase("ordinary_batter_right");
        source.sendSuccess(() -> Component.literal(physicsPreview
                ? ((mode.toLowerCase().startsWith("attack_")
                        || mode.toLowerCase().startsWith("ordinary_attack_")
                        || mode.equalsIgnoreCase("combo")
                        || mode.equalsIgnoreCase("ordinary_attack_right")
                        || mode.equalsIgnoreCase("batter_right")
                        || mode.equalsIgnoreCase("ordinary_batter_right"))
                        ? "ORDINARY ATTACK MOCAP REVIEW: EVA-"
                                + String.format("%02d", variant) + " " + mode
                        : (mode.equalsIgnoreCase("live")
                        || mode.equalsIgnoreCase("physics_live")
                        || mode.equalsIgnoreCase("policy")
                        || mode.equalsIgnoreCase("livereset")
                        || mode.equalsIgnoreCase("livepush"))
                        ? "LIVE TRAINED POLICY + MUJOCO: EVA-"
                                + String.format("%02d", variant)
                        : "OFFLINE MUJOCO REPLAY (NON-AUTHORITATIVE): EVA-"
                                + String.format("%02d", variant) + " " + mode)
                : "Motion-lab autonomous gait: EVA-"
                        + String.format("%02d", variant) + " " + mode), false);
        return 1;
    }

    private static int recordStart(CommandSourceStack source, String label)
            throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        if (!EvaMotionLabDirector.isMotionLab(player.serverLevel()))
        {
            source.sendFailure(Component.literal(
                    "This command is restricted to SEELE_EVA_MOTION_LAB."));
            return 0;
        }
        EvaUnit01Entity eva = EvaPilotResolver.controlTarget(player);
        if (eva == null || EvaPilotResolver.pilot(eva) != player)
        {
            source.sendFailure(Component.literal(
                    "Board a Motion Lab EVA through the normal enter command before recording."));
            return 0;
        }
        if (eva.getMotionLabPhysicsPreview() != 0
                || eva.getVisualPose() != EvaUnit01Entity.VISUAL_NORMAL)
        {
            source.sendFailure(Component.literal(
                    "Official pose recording rejects demo/preview authority; use normal pilot input."));
            return 0;
        }
        SeeleNetwork.CHANNEL.send(PacketDistributor.PLAYER.with(() -> player),
                new ClientboundEvaPoseRecorderPacket(
                        ClientboundEvaPoseRecorderPacket.START,
                        eva.getId(), label));
        source.sendSuccess(() -> Component.literal(
                "Final-matrix recording requested for the normally controlled EVA."), false);
        return 1;
    }

    private static int recordControl(CommandSourceStack source, int operation)
            throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        if (!EvaMotionLabDirector.isMotionLab(player.serverLevel()))
        {
            source.sendFailure(Component.literal(
                    "This command is restricted to SEELE_EVA_MOTION_LAB."));
            return 0;
        }
        SeeleNetwork.CHANNEL.send(PacketDistributor.PLAYER.with(() -> player),
                new ClientboundEvaPoseRecorderPacket(operation, -1, "manual"));
        return 1;
    }

    private static int variant(String raw)
    {
        String value = raw.toLowerCase();
        return switch (value)
        {
            case "0", "00", "unit00", "eva00" -> 0;
            case "1", "01", "unit01", "eva01" -> 1;
            case "2", "02", "unit02", "eva02" -> 2;
            default -> -1;
        };
    }

    private static int weapon(String raw)
    {
        return switch (raw.toLowerCase())
        {
            case "fist", "fists", "unarmed" -> EvaUnit01Entity.WEAPON_FISTS;
            case "knife" -> EvaUnit01Entity.WEAPON_KNIFE;
            case "cannon", "positron" -> EvaUnit01Entity.WEAPON_CANNON;
            case "rifle", "pallet" -> EvaUnit01Entity.WEAPON_RIFLE;
            case "n2" -> EvaUnit01Entity.WEAPON_N2;
            case "sword" -> EvaUnit01Entity.WEAPON_SWORD_R45;
            case "shield" -> EvaUnit01Entity.WEAPON_SHIELD_R45;
            default -> -1;
        };
    }
}
