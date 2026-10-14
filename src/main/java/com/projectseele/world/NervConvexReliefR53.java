package com.projectseele.world;

import java.util.*;
import net.minecraft.world.phys.*;

/** Closed-solid subtraction on explicitly selected convex source primitives.
 * New pocket faces are real triangles shared by drawing and collision. */
final class NervConvexReliefR53
{
    private record Vertex(double[] v){}
    static double[] subtract(double[] original,List<AABB> cuts)
    {
        List<double[]> solids=new ArrayList<>();solids.add(original);
        for(var cut:cuts)
        {
            var next=new ArrayList<double[]>();for(var solid:solids)
            {
                var bounds=bounds(solid);if(!bounds.intersects(cut)){next.add(solid);continue;}
                double[] remainder=solid;int[] axis={0,0,1,1,2,2};double[] planes={cut.minX,cut.maxX,cut.minY,cut.maxY,cut.minZ,cut.maxZ};
                for(int i=0;i<6&&remainder.length>0;i++){boolean outsideAbove=(i&1)==1;var outside=clipClosed(remainder,axis[i],planes[i],outsideAbove);if(outside.length>0)next.add(outside);remainder=clipClosed(remainder,axis[i],planes[i],!outsideAbove);}
            }
            solids=next;
        }
        int count=solids.stream().mapToInt(a->a.length).sum();var result=new double[count];int at=0;for(var solid:solids){System.arraycopy(solid,0,result,at,solid.length);at+=solid.length;}return result;
    }
    /** Opens only intersected housing skin into its existing cassette interior.
     * The paired solid bottom plate supplies the complete finite port walls. */
    static double[] subtractSurface(double[] original,List<AABB> cuts)
    {
        var polygons=new ArrayList<List<double[]>>();for(int i=0;i<original.length;i+=18){var p=new ArrayList<double[]>();for(int n=0;n<3;n++)p.add(Arrays.copyOfRange(original,i+n*6,i+n*6+6));polygons.add(p);}
        for(var cut:cuts){var next=new ArrayList<List<double[]>>();for(var polygon:polygons){List<double[]> rest=polygon;int[] axis={0,0,1,1,2,2};double[] planes={cut.minX,cut.maxX,cut.minY,cut.maxY,cut.minZ,cut.maxZ};for(int i=0;i<6&&!rest.isEmpty();i++){boolean outside=(i&1)==1;var p=clipPolygon(rest,axis[i],planes[i],outside);if(p.size()>=3)next.add(p);rest=clipPolygon(rest,axis[i],planes[i],!outside);}}polygons=next;}var result=new ArrayList<Double>();for(var polygon:polygons)append(result,polygon);return result.stream().mapToDouble(Double::doubleValue).toArray();
    }
    private static List<double[]> clipPolygon(List<double[]> polygon,int axis,double plane,boolean above)
    {
        var result=new ArrayList<double[]>();if(polygon.isEmpty())return result;var a=polygon.get(polygon.size()-1);boolean old=above?a[axis]>=plane:a[axis]<=plane;
        for(var b:polygon){boolean now=above?b[axis]>=plane:b[axis]<=plane;if(old!=now){double t=(plane-a[axis])/(b[axis]-a[axis]);var p=new double[6];for(int c=0;c<6;c++)p[c]=a[c]+(b[c]-a[c])*t;p[axis]=plane;result.add(p);}if(now)result.add(b);a=b;old=now;}return result;
    }
    private static AABB bounds(double[] vertices)
    {double x=Double.POSITIVE_INFINITY,y=x,z=x,X=Double.NEGATIVE_INFINITY,Y=X,Z=X;for(int i=0;i<vertices.length;i+=6){x=Math.min(x,vertices[i]);y=Math.min(y,vertices[i+1]);z=Math.min(z,vertices[i+2]);X=Math.max(X,vertices[i]);Y=Math.max(Y,vertices[i+1]);Z=Math.max(Z,vertices[i+2]);}return new AABB(x,y,z,X,Y,Z);}
    private static double[] clipClosed(double[] vertices,int axis,double plane,boolean above)
    {
        boolean in=false,out=false;for(int i=axis;i<vertices.length;i+=6){double d=above?vertices[i]-plane:plane-vertices[i];in|=d>=0;out|=d<0;}if(!in)return new double[0];if(!out)return vertices;
        var result=new ArrayList<Double>();var cut=new ArrayList<double[]>();
        for(int i=0;i<vertices.length;i+=18)
        {
            var polygon=new ArrayList<double[]>();for(int v=0;v<3;v++)polygon.add(Arrays.copyOfRange(vertices,i+v*6,i+v*6+6));var clipped=new ArrayList<double[]>();
            var a=polygon.get(2);boolean old=above?a[axis]>=plane:a[axis]<=plane;
            for(var b:polygon){boolean now=above?b[axis]>=plane:b[axis]<=plane;if(old!=now){double t=(plane-a[axis])/(b[axis]-a[axis]);var p=new double[6];for(int c=0;c<6;c++)p[c]=a[c]+(b[c]-a[c])*t;p[axis]=plane;clipped.add(p);if(cut.stream().noneMatch(q->distance(p,q)<1e-18))cut.add(p);}if(now)clipped.add(b);a=b;old=now;}append(result,clipped);
        }
        if(cut.size()>=3)
        {
            int u=(axis+1)%3,v=(axis+2)%3;double U=cut.stream().mapToDouble(p->p[u]).average().orElseThrow(),V=cut.stream().mapToDouble(p->p[v]).average().orElseThrow();cut.sort(Comparator.comparingDouble(p->Math.atan2(p[v]-V,p[u]-U)));if(above)Collections.reverse(cut);append(result,cut);
        }
        var array=result.stream().mapToDouble(Double::doubleValue).toArray();if(array.length==0)return array;var b=bounds(array);return Math.min(b.getXsize(),Math.min(b.getYsize(),b.getZsize()))<=1e-9?new double[0]:array;
    }
    private static double distance(double[] a,double[] b){double x=a[0]-b[0],y=a[1]-b[1],z=a[2]-b[2];return x*x+y*y+z*z;}
    private static void append(List<Double> output,List<double[]> polygon)
    {
        for(int i=1;i+1<polygon.size();i++){var a=polygon.get(0);var b=polygon.get(i);var c=polygon.get(i+1);if(new Vec3(b[0]-a[0],b[1]-a[1],b[2]-a[2]).cross(new Vec3(c[0]-a[0],c[1]-a[1],c[2]-a[2])).lengthSqr()<1e-20)continue;for(var p:List.of(a,b,c))for(double x:p)output.add(x);}
    }
    private NervConvexReliefR53(){}
}
