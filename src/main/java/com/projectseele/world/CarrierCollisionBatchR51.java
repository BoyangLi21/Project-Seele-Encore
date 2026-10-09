package com.projectseele.world;

import java.util.*;
import java.util.function.Function;
import net.minecraft.world.phys.AABB;

/** One synchronous clearance query shares overlapping world reads. Shapes and
 * results never survive that invocation; every narrow phase stays per piece. */
final class CarrierCollisionBatchR51
{
    record Group(AABB bounds,List<Integer> parts){}
    static long voxelEstimate(AABB box)
    {
        // The iterator also reads neighbour cells for shapes protruding out of
        // their block. This halo estimate chooses merges, never skips a cell.
        return (long)(Math.ceil(box.getXsize())+3)*(long)(Math.ceil(box.getYsize())+3)*(long)(Math.ceil(box.getZsize())+3);
    }
    static List<Group> groups(List<AABB> sweeps)
    {
        var groups=new ArrayList<Group>();for(int i=0;i<sweeps.size();i++)groups.add(new Group(sweeps.get(i),List.of(i)));
        while(true)
        {
            int first=-1,second=-1;long saving=0;AABB merged=null;
            for(int a=0;a<groups.size();a++)for(int b=a+1;b<groups.size();b++)
            {
                var x=groups.get(a).bounds();var y=groups.get(b).bounds();
                if(x.minX>=y.maxX+2||x.maxX<=y.minX-2||x.minY>=y.maxY+2||x.maxY<=y.minY-2||x.minZ>=y.maxZ+2||x.maxZ<=y.minZ-2)continue;
                var union=x.minmax(y);long gain=voxelEstimate(x)+voxelEstimate(y)-voxelEstimate(union);
                if(gain>saving){saving=gain;first=a;second=b;merged=union;}
            }
            if(first<0)break;
            var parts=new ArrayList<>(groups.get(first).parts());parts.addAll(groups.get(second).parts());parts.sort(Integer::compareTo);
            groups.set(first,new Group(merged,List.copyOf(parts)));groups.remove(second);
        }
        return List.copyOf(groups);
    }
    static final class Query
    {
        private final List<Group> groups;
        private final int[] groupOf;
        private final List<List<AABB>> fetched;
        private final Function<AABB,List<AABB>> currentWorld;
        private int reads;
        Query(List<AABB> sweeps,Function<AABB,List<AABB>> currentWorld)
        {
            this.groups=groups(sweeps);this.currentWorld=currentWorld;groupOf=new int[sweeps.size()];fetched=new ArrayList<>(Collections.nCopies(groups.size(),null));
            for(int group=0;group<groups.size();group++)for(int part:groups.get(group).parts())groupOf[part]=group;
        }
        List<AABB> forPart(int part)
        {
            int group=groupOf[part];var known=fetched.get(group);
            // Lazy reads retain the old first-obstruction early exit. Reuse is
            // only inside this same call, on the same live world and context.
            if(known==null){known=List.copyOf(currentWorld.apply(groups.get(group).bounds()));fetched.set(group,known);reads++;}
            return known;
        }
        int reads(){return reads;}
    }
    private CarrierCollisionBatchR51(){}
}
