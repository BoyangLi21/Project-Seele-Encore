package com.projectseele.world;

import java.util.ArrayList;
import java.util.List;
import net.minecraft.world.phys.shapes.BooleanOp;
import net.minecraft.world.phys.shapes.Shapes;
import net.minecraft.world.phys.shapes.VoxelShape;

/** Deterministic exact OR tree; runtime caller retains near-coordinate stock order. */
public final class ExactBalancedUnionCandidateR45
{
    private ExactBalancedUnionCandidateR45() {}


    public static VoxelShape stockLeftFold(List<VoxelShape> originalMovedShapes)
    {
        VoxelShape combined = Shapes.empty();
        for (VoxelShape shape : originalMovedShapes) combined = Shapes.joinUnoptimized(combined, shape, BooleanOp.OR);
        return combined.optimize();
    }

    public static VoxelShape balanced(List<VoxelShape> originalMovedShapes)
    {
        if (originalMovedShapes.isEmpty()) return Shapes.empty();
        List<VoxelShape> level = new ArrayList<>(originalMovedShapes);
        while (level.size() > 1)
        {
            List<VoxelShape> next = new ArrayList<>((level.size() + 1) / 2);
            for (int i = 0; i < level.size(); i += 2)
                next.add(i + 1 == level.size() ? level.get(i) : Shapes.joinUnoptimized(level.get(i), level.get(i + 1), BooleanOp.OR));
            level = next;
        }
        return level.get(0).optimize();
    }

    public static boolean exactNativeRegionEqual(VoxelShape stock, VoxelShape candidate)
    {
        return !Shapes.joinIsNotEmpty(stock, candidate, BooleanOp.NOT_SAME);
    }
}
