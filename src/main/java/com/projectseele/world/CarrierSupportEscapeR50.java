package com.projectseele.world;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

/** Pure upward egress whose existing overlap with each solid cannot increase. */
final class CarrierSupportEscapeR50
{
    private record Point(double x,double z){}
    // Below this extent, the 1e-9 witness-coordinate tolerance can span the
    // entire hull and turn a nearby high vertex into a false inner witness.
    // This is far below the 1mm query skin; degenerate inputs must fail closed.
    private static final double MIN_WITNESS_EXTENT=1e-7;
    private final List<Point> footprint;
    private final List<Vec3> vertices;
    private final boolean measurable;

    CarrierSupportEscapeR50(List<Vec3> vertices)
    {
        if(vertices.size()<4||vertices.stream().anyMatch(v->!Double.isFinite(v.x)||!Double.isFinite(v.y)||!Double.isFinite(v.z)))
        {this.vertices=List.of();footprint=List.of();measurable=false;return;}
        double minX=Double.POSITIVE_INFINITY,minY=minX,minZ=minX,maxX=Double.NEGATIVE_INFINITY,maxY=maxX,maxZ=maxX;
        for(var v:vertices){minX=Math.min(minX,v.x);minY=Math.min(minY,v.y);minZ=Math.min(minZ,v.z);maxX=Math.max(maxX,v.x);maxY=Math.max(maxY,v.y);maxZ=Math.max(maxZ,v.z);}
        boolean extents=maxX-minX>MIN_WITNESS_EXTENT&&maxY-minY>MIN_WITNESS_EXTENT&&maxZ-minZ>MIN_WITNESS_EXTENT;
        if(!extents){this.vertices=List.of();footprint=List.of();measurable=false;return;}
        this.vertices=vertices.stream().sorted(Comparator.comparingDouble((Vec3 v)->v.y).reversed()).toList();
        var points=vertices.stream().map(v->new Point(v.x,v.z)).distinct()
                .sorted(Comparator.comparingDouble(Point::x).thenComparingDouble(Point::z)).toList();
        var hull=new ArrayList<Point>();
        for(var p:points){while(hull.size()>1&&cross(hull.get(hull.size()-2),hull.get(hull.size()-1),p)<=1e-12)hull.remove(hull.size()-1);hull.add(p);}
        int lower=hull.size();
        for(int i=points.size()-2;i>=0;i--){var p=points.get(i);while(hull.size()>lower&&cross(hull.get(hull.size()-2),hull.get(hull.size()-1),p)<=1e-12)hull.remove(hull.size()-1);hull.add(p);}
        if(hull.size()>1)hull.remove(hull.size()-1);footprint=List.copyOf(hull);
        measurable=measurableFootprint(footprint);
    }
    private static double cross(Point a,Point b,Point c)
    {return (b.x-a.x)*(c.z-a.z)-(b.z-a.z)*(c.x-a.x);}
    private static boolean measurableFootprint(List<Point> hull)
    {
        if(hull.size()<3)return false;
        // Axis spans alone miss a needle rotated diagonally. A convex polygon's
        // minimum width occurs along an edge normal; reject every such narrow
        // projection before the coordinate tolerance can bridge its thickness.
        for(int i=0;i<hull.size();i++)
        {
            var a=hull.get(i);var b=hull.get((i+1)%hull.size());
            double length=Math.hypot(b.x-a.x,b.z-a.z),width=0;
            if(!(length>0)||!Double.isFinite(length))return false;
            for(var p:hull)width=Math.max(width,Math.abs(cross(a,b,p))/length);
            if(!(width>MIN_WITNESS_EXTENT)||!Double.isFinite(width))return false;
        }
        return true;
    }
    private static List<Point> clip(List<Point> source,boolean x,double edge,boolean greater)
    {
        var out=new ArrayList<Point>();if(source.isEmpty())return out;
        Point before=source.get(source.size()-1);double a=x?before.x:before.z;
        boolean previous=greater?a>=edge:a<=edge;
        for(var current:source)
        {
            double b=x?current.x:current.z;boolean inside=greater?b>=edge:b<=edge;
            if(previous!=inside)
            {double t=(edge-a)/(b-a);out.add(new Point(before.x+(current.x-before.x)*t,before.z+(current.z-before.z)*t));}
            if(inside)out.add(current);before=current;a=b;previous=inside;
        }
        return out;
    }
    boolean separatesUp(AABB obstacle,Vec3 delta)
    {
        if(!measurable||!pureUp(delta)||footprint.size()<3)return false;
        // The caller has already found an initial near-contact. If every
        // body slice starts above the solid's bottom, its overlap length is
        // max(0,min(U-L,solidTop-L-t)), which is nonincreasing for upward t.
        // This permits a shallow existing support intrusion to leave; it
        // does not claim that all intermediate occupied positions are old.
        if(vertices.get(vertices.size()-1).y>=obstacle.minY+.005)return true;
        var polygon=clip(clip(clip(clip(footprint,true,obstacle.minX,true),true,obstacle.maxX,false),false,obstacle.minZ,true),false,obstacle.maxZ,false);
        if(polygon.isEmpty())return true;
        // At each X/Z the convex body is a vertical interval. An upward
        // translation creates new occupied volume only above its old upper
        // surface, which is concave over the footprint. At each clipped vertex
        // find a convex combination of the actual hull vertices above the
        // obstacle. This is an inner witness, not a potentially loose plane
        // bound. Three vertices suffice for a fixed-X/Z linear optimum.
        for(var p:polygon)if(!witnessAbove(p,obstacle.maxY+.005))return false;
        return true;
    }
    static boolean pureUp(Vec3 delta)
    {return Double.isFinite(delta.y)&&delta.y>0&&delta.x==0&&delta.z==0;}
    private static boolean witness(Point point,double x,double y,double z,double top)
    {return y>=top&&Math.abs(x-point.x)<=1e-9&&Math.abs(z-point.z)<=1e-9;}
    private boolean witnessAbove(Point p,double top)
    {
        if(vertices.isEmpty()||vertices.get(0).y<top)return false;
        for(var a:vertices)if(witness(p,a.x,a.y,a.z,top))return true;
        int size=vertices.size();
        for(int i=0;i<size&&vertices.get(i).y>=top;i++)for(int j=i+1;j<size;j++)
        {
            var a=vertices.get(i);var b=vertices.get(j);double dx=b.x-a.x,dz=b.z-a.z;
            if(Math.max(Math.abs(dx),Math.abs(dz))<1e-12)continue;
            double t=Math.abs(dx)>=Math.abs(dz)?(p.x-a.x)/dx:(p.z-a.z)/dz;
            if(t>=0&&t<=1&&witness(p,a.x+t*dx,a.y+t*(b.y-a.y),a.z+t*dz,top))return true;
        }
        for(int i=0;i<size&&vertices.get(i).y>=top;i++)for(int j=i+1;j<size;j++)for(int k=j+1;k<size;k++)
        {
            var a=vertices.get(i);var b=vertices.get(j);var c=vertices.get(k);
            double bx=b.x-a.x,bz=b.z-a.z,cx=c.x-a.x,cz=c.z-a.z;
            double determinant=bx*cz-bz*cx;if(Math.abs(determinant)<1e-12)continue;
            double px=p.x-a.x,pz=p.z-a.z;
            double u=(px*cz-pz*cx)/determinant,v=(bx*pz-bz*px)/determinant;
            if(u<0||v<0||u+v>1)continue;
            if(witness(p,a.x+u*bx+v*cx,a.y+u*(b.y-a.y)+v*(c.y-a.y),a.z+u*bz+v*cz,top))return true;
        }
        return false;
    }
}
