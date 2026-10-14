package com.projectseele.world;

import java.util.HashSet;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.world.level.block.state.properties.AttachFace;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;

/** Original-key identity, actual rigid-frame centres and no legacy fallthrough. */
public final class NervHangarControlsR53Test
{
    private static int checks;
    private static void check(boolean value, String message)
    { checks++; if (!value) throw new AssertionError(message); }
    private static void rejected(Runnable action, String message)
    {
        boolean failed = false;
        try { action.run(); } catch (IllegalArgumentException expected) { failed = true; }
        check(failed, message);
    }
    public static void main(String[] args)
    {
        check(NervHangarControlsR53.decision(false, false, null, false, false)
                == NervHangarControlsR53.Decision.LEGACY, "Unclaimed old maps lost their original handler");
        check(NervHangarControlsR53.decision(true, false, null, false, false)
                == NervHangarControlsR53.Decision.HOLD, "Incomplete declared map fell into the old pool");
        var all = NervHangarControlsR53.controls(v -> new RigidTransform(
                new Vec3(new double[] {72.5, 30.5, -11.5}[v], -1062.96, 328.5), 0, 1, 0, 0));
        check(all.size() == 9 && new HashSet<>(all.stream().map(NervHangarControlsR53.Control::position).toList()).size() == 9,
                "Original three panels/nine distinct inputs were not preserved");
        for (var c : all)
        {
            check(c.position().equals(new BlockPos(new int[] {91, 49, 7}[c.variant()], -1013,
                    342 - 2 * c.action().ordinal())), "180-degree centre transform has a one-voxel offset");
            check(c.facing() == Direction.WEST && c.backing().equals(c.position().east()),
                    "Moved wall input did not rotate its face and backing together");
            check(NervHangarControlsR53.physicalMatch(c, true, AttachFace.WALL, Direction.WEST, true),
                    "Actual supported new wall input was rejected");
            check(!NervHangarControlsR53.physicalMatch(c, true, AttachFace.WALL, Direction.EAST, true),
                    "Old facing remained valid on the rotated plant");
            check(!NervHangarControlsR53.physicalMatch(c, true, AttachFace.WALL, Direction.WEST, false),
                    "Floating input without a real backing was admitted");
            check(!NervHangarControlsR53.physicalMatch(c, true, AttachFace.FLOOR, Direction.WEST, true),
                    "Wrong attachment was admitted as an original wall key");
            check(!NervHangarControlsR53.physicalMatch(c, false, AttachFace.WALL, Direction.WEST, true),
                    "A different block gained logistics authority");
            check(NervHangarControlsR53.decision(true, true, c, true, false).name().equals(c.action().name()),
                    "Original variant/action identity changed");
            check(NervHangarControlsR53.decision(true, false, c, true, false) == NervHangarControlsR53.Decision.HOLD,
                    "Present physical key bypassed unavailable declared machinery");
            check(NervHangarControlsR53.decision(true, true, c, false, false) == NervHangarControlsR53.Decision.HOLD,
                    "Misbound physical key bypassed readiness");
            if (c.action() == NervHangarControlsR53.Action.CANCEL)
                check(NervHangarControlsR53.decision(true, true, c, true, true) == NervHangarControlsR53.Decision.EMERGENCY_HOLD,
                        "Shift-cancel could reach the retired emergency pool gate");
        }
        check(NervHangarControlsR53.decision(true, true, null, false, false)
                == NervHangarControlsR53.Decision.NOT_CONTROL, "Unrelated inputs were rebound to legacy actions");
        var original = NervHangarControlsR53.controls(1, RigidTransform.of(new Vec3(30.5, -442.96, -239.5), new Quaternionf()));
        for (var c : original)
            check(c.position().equals(new BlockPos(11, -393, -254 + 2 * c.action().ordinal()))
                    && c.facing() == Direction.EAST, "Local source layout no longer matches the original R50 keys");
        var shifted = NervHangarControlsR53.controls(1, new RigidTransform(new Vec3(130.5, -962.96, 428.5), 0, 1, 0, 0));
        check(shifted.get(0).position().equals(new BlockPos(149, -913, 442)), "Controls still depend on a global new-map coordinate table");
        rejected(() -> NervHangarControlsR53.controls(v -> null), "Partial original panel set was accepted");
        rejected(() -> NervHangarControlsR53.controls(v -> RigidTransform.of(new Vec3(30.5, -442.96, -239.5), new Quaternionf())),
                "Three plants aliased the same physical keys");
        rejected(() -> NervHangarControlsR53.controls(0, RigidTransform.of(new Vec3(72.5, -1062.96, 328.5),
                new Quaternionf().rotateY((float) Math.PI / 4))), "Oblique grid buttons were guessed");
        rejected(() -> NervHangarControlsR53.controls(0, new RigidTransform(new Vec3(72.75, -1062.96, 328.5), 0, 1, 0, 0)),
                "A centre off the measured voxel grid was silently rounded");
        System.out.println("R53 original hangar controls PASS checks=" + checks + "; frame/guard contract only, native click review remains required");
    }
    private NervHangarControlsR53Test() {}
}
