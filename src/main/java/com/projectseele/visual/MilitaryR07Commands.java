package com.projectseele.visual;

import java.util.function.Function;

import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import com.projectseele.world.FacilitySchemaV2;
import com.projectseele.world.FacilitySites;
import com.projectseele.world.MilitaryR07Director;
import com.projectseele.world.UNAnnexR20;
import com.projectseele.world.UNRecoveryR22;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.phys.Vec3;

/**
 * Development visit points at the UN base and the port (/seele dev visit). The points are the
 * original survey coordinates, moved by the saved site offsets, so they follow a relocated base.
 */
public final class MilitaryR07Commands
{
    public static LiteralArgumentBuilder<CommandSourceStack> visitCommand()
    {
        return Commands.literal("visit")
                .then(r07("port", 180, level -> FacilitySites.port(level, new Vec3(1264.5, 69, 504.5))))
                .then(r07("un_base", 180, level -> FacilitySites.un(level, new Vec3(6560.5, 75, -5968.5))))
                .then(r07("un0_hangar", 180, level -> FacilitySites.un(level, new Vec3(6402.5, 77, -6132.5))))
                .then(r07("un0_gantry", 90, level -> UNRecoveryR22.home(level, 0).add(4, 50, -12)))
                .then(annex("un1_control", 180, level -> FacilitySites.un(level, new Vec3(6242.5, 77, -6136.5))))
                .then(annex("un1_gantry", 90, level -> UNRecoveryR22.home(level, 1).add(4, 50, -12)));
    }

    private static LiteralArgumentBuilder<CommandSourceStack> r07(String name, float yaw, Function<ServerLevel, Vec3> point)
    {
        return Commands.literal(name).executes(c ->
        {
            var level = c.getSource().getServer().getLevel(FacilitySchemaV2.DIMENSION);
            if (level == null || !MilitaryR07Director.state(level).commissioned)
            {
                c.getSource().sendFailure(Component.literal("此存档尚未安装 R07 设施"));
                return 0;
            }
            return visit(c.getSource(), level, point.apply(level), yaw);
        });
    }

    private static LiteralArgumentBuilder<CommandSourceStack> annex(String name, float yaw, Function<ServerLevel, Vec3> point)
    {
        return Commands.literal(name).executes(c ->
        {
            var level = c.getSource().getServer().getLevel(FacilitySchemaV2.DIMENSION);
            if (level == null || !UNAnnexR20.installed(level))
            {
                c.getSource().sendFailure(Component.literal("此存档未安装 UN-01 试验舱"));
                return 0;
            }
            return visit(c.getSource(), level, point.apply(level), yaw);
        });
    }

    private static int visit(CommandSourceStack source, ServerLevel level, Vec3 p, float yaw)
            throws com.mojang.brigadier.exceptions.CommandSyntaxException
    {
        var player = source.getPlayerOrException();
        player.stopRiding();
        player.teleportTo(level, p.x, p.y, p.z, yaw, 0);
        player.fallDistance = 0;
        player.setDeltaMovement(Vec3.ZERO);
        return 1;
    }

    private MilitaryR07Commands() {}
}
