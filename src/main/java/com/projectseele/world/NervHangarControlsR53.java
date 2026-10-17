package com.projectseele.world;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.function.IntFunction;
import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.ButtonBlock;
import net.minecraft.world.level.block.state.properties.AttachFace;
import net.minecraft.world.phys.Vec3;

/** Original nine operator keys, carried by the installed static gantry frames. */
public final class NervHangarControlsR53
{
    public enum Action { PREPARE, STATUS, CANCEL }
    public record Control(int variant, Action action, BlockPos position, Direction facing)
    {
        public BlockPos backing() { return position.relative(facing.getOpposite()); }
    }
    enum Decision { LEGACY, NOT_CONTROL, HOLD, PREPARE, STATUS, CANCEL, EMERGENCY_HOLD }

    private static final String HOLD = "机库操作面板尚未就绪，当前操作保持不变。";

    /** Source button centres relative to the unchanged original gantry root.
     * Original gantry Y=-442.96, button centre Y=-392.5. These are local source
     * offsets, so a later whole-plant move needs no new global coordinate table. */
    public static List<Control> controls(int variant, RigidTransform gantry)
    {
        if (variant < 0 || variant > 2 || gantry == null)
            throw new IllegalArgumentException("Declared original gantry required");
        Vec3 outward = gantry.transformVector(new Vec3(1, 0, 0));
        Direction facing = Direction.getNearest((float) outward.x, (float) outward.y, (float) outward.z);
        if (facing.getAxis() == Direction.Axis.Y
                || outward.distanceToSqr(Vec3.atLowerCornerOf(facing.getNormal())) > 1e-8
                || gantry.transformVector(new Vec3(0, 1, 0)).distanceToSqr(new Vec3(0, 1, 0)) > 1e-8)
            throw new IllegalArgumentException("Original wall-button frame must remain cardinal and upright");
        var result = new ArrayList<Control>();
        for (Action action : Action.values())
        {
            Vec3 centre = gantry.transformPoint(new Vec3(-19, 50.46, -14 + 2 * action.ordinal()));
            if (!Double.isFinite(centre.x + centre.y + centre.z))
                throw new IllegalArgumentException("Finite operator centre required");
            BlockPos cell = BlockPos.containing(centre);
            if (Vec3.atCenterOf(cell).distanceToSqr(centre) > 1e-8)
                throw new IllegalArgumentException("Declared source key centre is not on its actual voxel");
            result.add(new Control(variant, action, cell, facing));
        }
        return List.copyOf(result);
    }

    static List<Control> controls(IntFunction<RigidTransform> frames)
    {
        var result = new ArrayList<Control>();
        for (int variant = 0; variant < 3; variant++) result.addAll(controls(variant, frames.apply(variant)));
        if (result.stream().map(Control::position).distinct().count() != 9)
            throw new IllegalArgumentException("Three distinct original operator panels required");
        return List.copyOf(result);
    }

    static boolean physicalMatch(Control control, boolean originalButton,
                                 AttachFace attachment, Direction facing, boolean supported)
    {
        return control != null && originalButton && attachment == AttachFace.WALL
                && control.facing() == facing && supported;
    }

    static Decision decision(boolean declared, boolean ready, Control control,
                             boolean physicallyBound, boolean sneaking)
    {
        if (!declared) return Decision.LEGACY;
        if (!ready) return Decision.HOLD;
        if (control == null) return Decision.NOT_CONTROL;
        if (!physicallyBound) return Decision.HOLD;
        if (sneaking && control.action() == Action.CANCEL) return Decision.EMERGENCY_HOLD;
        return Decision.valueOf(control.action().name());
    }

    /** -1 delegates an old world; 0/1 both consume the new-map logistics scope.
     * In particular, an unavailable new owner can never reach old-pool controls. */
    public static int handleUse(ServerPlayer player, BlockPos clicked)
    {
        var level = player.serverLevel();
        boolean declared = NervLegacyGenerationGuardR52.retired(level);
        if (!declared) return -1;
        if (player.isSpectator() || player.distanceToSqr(Vec3.atCenterOf(clicked)) > 36) return 0;
        var block = level.getBlockState(clicked);
        if (!block.is(Blocks.POLISHED_BLACKSTONE_BUTTON)) return 0;
        var context = NervRouteRuntimeR52.flightContext(level);
        boolean ready = context != null && context.owner() instanceof NervAssemblyOwnerR52;
        Control control = null;
        if (ready)
        {
            try
            {
                var owner = (NervAssemblyOwnerR52) context.owner();
                control = controls(owner::originalGantryFrameR53).stream()
                        .filter(c -> c.position().equals(clicked)).findFirst().orElse(null);
            }
            catch (IllegalArgumentException invalidFrame)
            {
                ready = false;
            }
        }
        boolean bound = control != null && level.hasChunkAt(control.backing())
                && physicalMatch(control, true, block.getValue(ButtonBlock.FACE),
                        block.getValue(ButtonBlock.FACING),
                        level.getBlockState(control.backing()).isFaceSturdy(level, control.backing(), control.facing()));
        Decision selected = decision(true, ready, control, bound, player.isShiftKeyDown());
        if (selected == Decision.NOT_CONTROL) return 0;
        if (selected == Decision.HOLD || selected == Decision.EMERGENCY_HOLD)
        {
            player.displayClientMessage(Component.literal(selected == Decision.HOLD ? HOLD
                    : "新机库后门由整备与回库流程联锁控制；旧紧急开门快捷键未执行。")
                    .withStyle(ChatFormatting.YELLOW), false);
            return 1;
        }
        int variant = control.variant();
        if (selected == Decision.STATUS)
        {
            var state = NervRouteRuntimeR52.status(level, variant);
            player.displayClientMessage(Component.literal(String.format(Locale.ROOT,
                    "[NERV 机库] EVA-%02d phase=%s loaded=%s LCL=%d/%d ticks=%d",
                    variant, state.phase(), state.loaded(), state.lclLayers(),
                    EvaHangarBuilder.LCL_SHOULDER_LAYERS, state.ticks())).withStyle(ChatFormatting.AQUA), false);
            return 1;
        }
        if(selected==Decision.PREPARE&&!NervRouteRuntimeR52.pending(level,variant))
        {
            var eva=EvaLogisticsDirector.canonicalUnit(level,variant);
            if(eva!=null&&EvaLogisticsDirector.inAssignedHangarR33(level,eva))
                eva.getPersistentData().putUUID("R32SortieCommander",player.getUUID());
        }
        var result = selected == Decision.PREPARE ? NervRouteRuntimeR52.prepare(level, variant)
                : NervRouteRuntimeR52.cancel(level, variant);
        player.displayClientMessage(Component.literal("[NERV 机库] " + result.message())
                .withStyle(result.accepted() ? ChatFormatting.GREEN : ChatFormatting.RED), false);
        return 1;
    }

    private NervHangarControlsR53() {}
}
