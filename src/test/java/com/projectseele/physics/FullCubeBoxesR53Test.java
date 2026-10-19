package com.projectseele.physics;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import net.minecraft.world.phys.shapes.Shapes;
import net.minecraft.world.phys.shapes.VoxelShape;

public final class FullCubeBoxesR53Test
{
    private static List<List<Double>> boxes(VoxelShape shape, boolean fast)
    {
        var result = new ArrayList<List<Double>>();
        Shapes.DoubleLineConsumer sink = (a,b,c,d,e,f) -> result.add(List.of(a,b,c,d,e,f));
        if(fast) FullCubeBoxesR53.visit(shape, sink);
        else shape.forAllBoxes(sink);
        return result;
    }

    public static void main(String[] args)
    {
        var shapes = new ArrayList<VoxelShape>();
        shapes.add(Shapes.empty());shapes.add(Shapes.block());
        shapes.add(Shapes.box(0,0,0,1,.5,1));
        shapes.add(Shapes.or(Shapes.box(0,0,0,1,.5,1), Shapes.box(0,.5,.5,1,1,1)));
        var random = new Random(53);
        for(int i=0;i<64;i++)
        {
            double x=random.nextDouble()*4-2,y=random.nextDouble()*4-2,z=random.nextDouble()*4-2;
            shapes.add(Shapes.box(x,y,z,x+random.nextDouble(),y+random.nextDouble(),z+random.nextDouble()));
        }
        for(var shape:shapes)
            if(!boxes(shape,false).equals(boxes(shape,true)))throw new AssertionError("Native box callbacks changed");
        System.out.println("Full cube, empty, stair, slab and 64 displaced shapes: ordered native callbacks identical");
    }
}
