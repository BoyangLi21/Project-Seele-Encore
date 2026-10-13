package com.projectseele.world;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import net.minecraft.world.phys.AABB;

/** Strict overlap validation without comparing every pair of distant cells. */
public final class NervSpacePartitionR52
{
    public static void requireDisjoint(List<AABB> boxes)
    {
        if(boxes.size()<2)return;
        double[] low={Double.POSITIVE_INFINITY,Double.POSITIVE_INFINITY,Double.POSITIVE_INFINITY};
        double[] high={Double.NEGATIVE_INFINITY,Double.NEGATIVE_INFINITY,Double.NEGATIVE_INFINITY};
        for(var box:boxes)for(int axis=0;axis<3;axis++)
        {low[axis]=Math.min(low[axis],min(box,axis));high[axis]=Math.max(high[axis],max(box,axis));}
        int chosen=0;for(int axis=1;axis<3;axis++)if(high[axis]-low[axis]>high[chosen]-low[chosen])chosen=axis;
        final int axis=chosen;
        var sorted=new ArrayList<>(boxes);sorted.sort(Comparator.comparingDouble(box->min(box,axis)));
        var active=new ArrayList<AABB>();
        for(var current:sorted)
        {
            double start=min(current,axis);
            active.removeIf(previous->max(previous,axis)<=start);
            for(var previous:active)if(previous.intersects(current))
                throw new IllegalArgumentException("Overlapping actual occupancy must use a shared resource ID");
            active.add(current);
        }
    }
    private static double min(AABB box,int axis){return axis==0?box.minX:axis==1?box.minY:box.minZ;}
    private static double max(AABB box,int axis){return axis==0?box.maxX:axis==1?box.maxY:box.maxZ;}
    private NervSpacePartitionR52(){}
}
