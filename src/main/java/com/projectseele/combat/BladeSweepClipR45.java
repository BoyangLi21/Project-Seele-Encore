package com.projectseele.combat;

import java.util.ArrayList;
import java.util.List;

/** Clip an actual swept blade triangle against the target's existing convex planes. */
public final class BladeSweepClipR45
{
    public static double[] triangle(double[][] points,double[][] planes)
    {
        List<double[]> polygon=new ArrayList<>();
        for(double[] p:points)polygon.add(p.clone());
        for(double[] plane:planes)
        {
            if(polygon.isEmpty())return null;
            List<double[]> next=new ArrayList<>();
            double[] previous=polygon.get(polygon.size()-1);double before=value(plane,previous);
            for(double[] current:polygon)
            {
                double after=value(plane,current);
                if((before<=0)!=(after<=0))
                {
                    double t=before/(before-after);
                    next.add(new double[]{previous[0]+t*(current[0]-previous[0]),
                            previous[1]+t*(current[1]-previous[1]),previous[2]+t*(current[2]-previous[2])});
                }
                if(after<=0)next.add(current);
                previous=current;before=after;
            }
            polygon=next;
        }
        return polygon.isEmpty()?null:polygon.get(0).clone();
    }
    private static double value(double[] plane,double[] point)
    {return plane[0]*point[0]+plane[1]*point[1]+plane[2]*point[2]+plane[3];}
    private BladeSweepClipR45() {}
}
