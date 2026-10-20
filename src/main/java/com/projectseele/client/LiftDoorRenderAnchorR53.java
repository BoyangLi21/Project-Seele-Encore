package com.projectseele.client;

import com.projectseele.entity.NervLiftDoorEntity;
import com.supermartijn642.movingelevators.elevator.ElevatorGroupCapability;
import net.minecraft.core.Direction;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;

/** Resolves cabin leaves against the same native cage sample as its block renderer. */
public final class LiftDoorRenderAnchorR53
{
    private LiftDoorRenderAnchorR53() {}

    public static Vec3 centre(NervLiftDoorEntity door, float partialTick)
    {
        var binding = door.cageBinding();
        if (!binding.isEmpty())
        {
            var group = ElevatorGroupCapability.get(door.level()).get(
                    binding.getInt("X"), binding.getInt("Z"),
                    Direction.from3DDataValue(binding.getInt("Facing")));
            if (group != null && group.isMoving() && group.getCage() != null)
            {
                // Horizontal transfers also consult this clock inside getCageAnchorPos.
                LiftTransferRenderClockR53.begin(partialTick);
                try
                {
                    return group.getCageAnchorPos(Mth.lerp(partialTick,
                                    group.getLastY(), group.getCurrentY()))
                            .add(binding.getDouble("LocalX"),
                                    binding.getDouble("LocalY"),
                                    binding.getDouble("LocalZ"));
                }
                finally
                {
                    LiftTransferRenderClockR53.end();
                }
            }
        }
        if (door.tickCount == 0) return door.position();
        return new Vec3(Mth.lerp(partialTick, door.xOld, door.getX()),
                Mth.lerp(partialTick, door.yOld, door.getY()),
                Mth.lerp(partialTick, door.zOld, door.getZ()));
    }
}
