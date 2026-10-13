package com.projectseele.world;
import java.util.*;
import net.minecraft.world.phys.AABB;

/** Exact union coverage for adjacent physical SPACE bindings. Their IDs stay
 * shared/disjoint in the original broker; a boundary is not a new resource. */
public final class NervAirspaceCoverageR52
{
    public static boolean covered(AABB query,List<AABB> spaces)
    {
        if(!Double.isFinite(query.minX)||!Double.isFinite(query.minY)||!Double.isFinite(query.minZ)
                ||!Double.isFinite(query.maxX)||!Double.isFinite(query.maxY)||!Double.isFinite(query.maxZ)
                ||query.maxX<=query.minX||query.maxY<=query.minY||query.maxZ<=query.minZ)return false;
        if(spaces.stream().anyMatch(s->contains(s,query)))return true;
        // A route can reserve thousands of remote cells. Only intersections
        // contribute to this body's exact union; retain their real boundaries.
        spaces=spaces.stream().filter(s->s.intersects(query)).toList();if(spaces.isEmpty())return false;
        var x=cuts(query.minX,query.maxX,spaces,0);var y=cuts(query.minY,query.maxY,spaces,1);var z=cuts(query.minZ,query.maxZ,spaces,2);
        for(int i=1;i<x.size();i++)for(int j=1;j<y.size();j++)for(int k=1;k<z.size();k++)
        {double xx=(x.get(i-1)+x.get(i))/2,yy=(y.get(j-1)+y.get(j))/2,zz=(z.get(k-1)+z.get(k))/2;boolean found=false;for(var s:spaces)if(xx>=s.minX&&xx<=s.maxX&&yy>=s.minY&&yy<=s.maxY&&zz>=s.minZ&&zz<=s.maxZ){found=true;break;}if(!found)return false;}return true;
    }
    private static List<Double> cuts(double low,double high,List<AABB> spaces,int axis)
    {var out=new TreeSet<Double>();out.add(low);out.add(high);for(var s:spaces){double a=axis==0?s.minX:axis==1?s.minY:s.minZ,b=axis==0?s.maxX:axis==1?s.maxY:s.maxZ;if(a>low&&a<high)out.add(a);if(b>low&&b<high)out.add(b);}return List.copyOf(out);}
    private static boolean contains(AABB a,AABB b){return a.minX<=b.minX&&a.minY<=b.minY&&a.minZ<=b.minZ&&a.maxX>=b.maxX&&a.maxY>=b.maxY&&a.maxZ>=b.maxZ;}
    private NervAirspaceCoverageR52(){}
}
