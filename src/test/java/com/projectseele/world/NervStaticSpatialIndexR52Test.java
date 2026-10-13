package com.projectseele.world;

import java.util.*;
import net.minecraft.world.phys.AABB;

public final class NervStaticSpatialIndexR52Test
{
    private static int checks;
    private static void same(List<AABB> boxes,NervStaticSpatialIndexR52<AABB> index,AABB query)
    {
        var expected=boxes.stream().filter(b->b.intersects(query)).toList();var actual=index.query(query);
        if(!actual.equals(expected))throw new AssertionError("Exact source-order intersection mismatch: "+query+" expected="+expected.size()+" actual="+actual.size());
        checks++;
    }
    public static void main(String[] args)
    {
        var random=new Random(52);var boxes=new ArrayList<AABB>();
        for(int i=0;i<16000;i++)
        {double x=random.nextDouble()*2600-1400,y=random.nextDouble()*960-900,z=random.nextDouble()*2600-1000;boxes.add(new AABB(x,y,z,x+random.nextDouble()*18,y+random.nextDouble()*16,z+random.nextDouble()*18));}
        // Real triangle planes, negative cells, exact grid borders and an
        // oversized source are compared with the original brute-force rule.
        for(double x:new double[]{-64,-32,0,32,64})
        {boxes.add(new AABB(x,-.5,-.5,x,.5,.5));boxes.add(new AABB(x,0,0,x+1,1,1));}
        boxes.add(new AABB(-5000,-5000,-5000,5000,5000,5000));
        var index=new NervStaticSpatialIndexR52<>(boxes,b->b);
        for(int i=0;i<2200;i++)
        {double x=random.nextDouble()*3000-1600,y=random.nextDouble()*1200-1100,z=random.nextDouble()*3000-1200;double size=i%3==0?70:.005;same(boxes,index,new AABB(x,y,z,x+size,y+size,z+size));}
        for(double x:new double[]{-64,-32,0,32,64})for(double end:new double[]{Math.nextDown(x),x,Math.nextUp(x),x+.00001})
            same(boxes,index,new AABB(x-1,-1,-1,end,1,1));
        same(boxes,index,new AABB(-9000,-9000,-9000,9000,9000,9000));same(boxes,index,new AABB(32,0,0,32,1,1));
        if(!new NervStaticSpatialIndexR52<AABB>(List.of(),b->b).query(new AABB(0,0,0,1,1,1)).isEmpty())throw new AssertionError("Empty index");
        System.out.println("NervStaticSpatialIndexR52Test PASS "+checks+" exact brute-force/source-order comparisons");
    }
}
