package com.projectseele.world;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import net.minecraft.world.phys.AABB;

/** Checks exact contact/overlap semantics and adversarial unordered widths. */
public final class NervSpacePartitionR52Test
{
    public static void main(String[] args)
    {
        int checks=0;
        NervSpacePartitionR52.requireDisjoint(List.of(new AABB(-32,-32,-32,0,0,0),new AABB(0,-32,-32,32,0,0)));checks++;
        var grid=new ArrayList<AABB>();for(int x=-20;x<20;x++)for(int y=-8;y<8;y++)for(int z=-20;z<20;z++)grid.add(new AABB(x*32,y*32,z*32,x*32+32,y*32+32,z*32+32));
        java.util.Collections.shuffle(grid,new Random(52));NervSpacePartitionR52.requireDisjoint(grid);checks++;
        grid.add(new AABB(-.01,-.01,-.01,.01,.01,.01));mustReject(grid);checks++;
        mustReject(List.of(new AABB(0,0,0,1000,1,1),new AABB(3,3,3,4,4,4),new AABB(900,.2,.2,901,.8,.8)));checks++;
        var random=new Random(5201);
        for(int trial=0;trial<300;trial++)
        {
            var rows=new ArrayList<AABB>();boolean overlap=false;
            for(int i=0;i<40;i++){double x=random.nextInt(80)-40,y=random.nextInt(80)-40,z=random.nextInt(80)-40;rows.add(new AABB(x,y,z,x+random.nextInt(8)+.01,y+random.nextInt(8)+.01,z+random.nextInt(8)+.01));}
            for(int i=0;i<rows.size();i++)for(int j=0;j<i;j++)overlap|=rows.get(i).intersects(rows.get(j));
            boolean rejected=false;try{NervSpacePartitionR52.requireDisjoint(rows);}catch(IllegalArgumentException expected){rejected=true;}
            if(rejected!=overlap)throw new AssertionError("Sweep disagrees with exact AABB predicate");checks++;
        }
        System.out.println("Space partition checks="+checks+"; 25600 touching cells admitted, real overlaps rejected");
    }
    private static void mustReject(List<AABB> boxes)
    {try{NervSpacePartitionR52.requireDisjoint(boxes);}catch(IllegalArgumentException expected){return;}throw new AssertionError("Overlap was admitted");}
}
