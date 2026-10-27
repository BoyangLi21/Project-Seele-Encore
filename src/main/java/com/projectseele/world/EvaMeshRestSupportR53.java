package com.projectseele.world;

import java.util.*;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.*;

/** One final rest handoff against the actual skin and native supporting tops. */
public final class EvaMeshRestSupportR53
{
    public record Result(AABB bounds,double lift) {}
    private static long column(int x,int z){return ((long)x<<32)^(z&0xffffffffL);}
    public static Result solve(EvaOriginalMeshGeometryR52.Geometry geometry,RigidTransform root,List<AABB> supports,double gap)
    {
        if(!Double.isFinite(gap)||gap<0)throw new IllegalArgumentException("Finite nonnegative rest gap required");
        var columns=new HashMap<Long,List<AABB>>();
        for(var box:supports)
            for(int x=Mth.floor(box.minX);x<=Mth.floor(box.maxX);x++)
                for(int z=Mth.floor(box.minZ);z<=Mth.floor(box.maxZ);z++)
                    columns.computeIfAbsent(column(x,z),k->new ArrayList<>()).add(box);
        AABB bounds=null;double lift=0;
        for(var part:geometry.parts())
        {
            var vertices=part.triangles();
            for(int i=0;i<vertices.length;i+=9)
            {
                var triangle=new ArrayList<Vec3>(3);AABB extent=null;
                for(int j=0;j<9;j+=3)
                {
                    var point=root.transformPoint(new Vec3(vertices[i+j],vertices[i+j+1],vertices[i+j+2]));
                    triangle.add(point);var box=new AABB(point,point);extent=extent==null?box:extent.minmax(box);
                }
                bounds=bounds==null?extent:bounds.minmax(extent);
                var visited=Collections.newSetFromMap(new IdentityHashMap<AABB,Boolean>());
                for(int x=Mth.floor(extent.minX);x<=Mth.floor(extent.maxX);x++)
                    for(int z=Mth.floor(extent.minZ);z<=Mth.floor(extent.maxZ);z++)
                        for(var support:columns.getOrDefault(column(x,z),List.of()))
                        {
                            if(!visited.add(support)||support.maxY+gap<=extent.minY+lift
                                    ||extent.maxX<support.minX||extent.minX>support.maxX
                                    ||extent.maxZ<support.minZ||extent.minZ>support.maxZ)continue;
                            List<Vec3> polygon=triangle;
                            polygon=clip(polygon,0,support.minX,true);polygon=clip(polygon,0,support.maxX,false);
                            polygon=clip(polygon,2,support.minZ,true);polygon=clip(polygon,2,support.maxZ,false);
                            for(var point:polygon)lift=Math.max(lift,support.maxY+gap-point.y);
                        }
            }
        }
        if(bounds==null)throw new IllegalArgumentException("Complete source triangles required");
        return new Result(bounds.move(0,lift,0),lift);
    }
    private static List<Vec3> clip(List<Vec3> polygon,int axis,double plane,boolean above)
    {
        if(polygon.isEmpty())return polygon;
        var result=new ArrayList<Vec3>();var previous=polygon.get(polygon.size()-1);
        double before=(axis==0?previous.x:previous.z)-plane;
        for(var current:polygon)
        {
            double after=(axis==0?current.x:current.z)-plane;
            boolean wasInside=above?before>=0:before<=0,inside=above?after>=0:after<=0;
            if(wasInside!=inside)result.add(previous.lerp(current,before/(before-after)));
            if(inside)result.add(current);
            previous=current;before=after;
        }
        return result;
    }
    private EvaMeshRestSupportR53(){}
}
