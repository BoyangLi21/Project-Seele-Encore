package com.projectseele.world;

import java.util.*;
import net.minecraft.world.phys.*;

/** Bounded physical upward depenetration of one captured complete rigid body. */
final class NervRescueContactEgressR53
{
    private final List<double[]> components=new ArrayList<>();
    private record Vertex(double x,double y,double z){}
    private record WorldComponent(double[] xyz,AABB bounds){}
    private record Contact(boolean initial,double lowest,double[] ranges){}
    private final Set<AABB> capturedShapes;
    private RigidTransform capturedFrame;
    private List<WorldComponent> worldComponents=List.of();
    // Only immutable source clipping is retained; current native shapes and
    // protected passengers are still checked by FlightPickupPreview each step.
    // Keep the complete finite capture set: a smaller rotating cap thrashes
    // when each stationary scan visits more floor contacts than that cap.
    private final Map<AABB,List<Contact>> contacts=new LinkedHashMap<>()
    {
        @Override protected boolean removeEldestEntry(Map.Entry<AABB,List<Contact>> eldest)
        {return size()>(capturedShapes==null?128:capturedShapes.size());}
    };
    NervRescueContactEgressR53(EvaOriginalMeshGeometryR52.Geometry body)
    {this(body,null);}
    NervRescueContactEgressR53(EvaOriginalMeshGeometryR52.Geometry body,Set<AABB> capturedShapes)
    {
        this.capturedShapes=capturedShapes==null?null:Set.copyOf(capturedShapes);
        // Once airborne there are no captured terrain contacts to leave.
        // Pose updates must not rebuild triangle connectivity for an empty set.
        if(this.capturedShapes!=null&&this.capturedShapes.isEmpty())return;
        for(var part:body.parts())
        {
            var xyz=part.triangles();int count=xyz.length/9;var parent=new int[count];
            for(int i=0;i<count;i++)parent[i]=i;
            var vertices=new HashMap<Vertex,Integer>();
            for(int i=0;i<count;i++)for(int v=0;v<3;v++)
            {
                int n=i*9+v*3;var key=new Vertex(zero(xyz[n]),zero(xyz[n+1]),zero(xyz[n+2]));
                var previous=vertices.putIfAbsent(key,i);
                if(previous!=null)parent[find(parent,i)]=find(parent,previous);
            }
            var groups=new LinkedHashMap<Integer,List<Integer>>();
            for(int i=0;i<count;i++)groups.computeIfAbsent(find(parent,i),unused->new ArrayList<>()).add(i);
            for(var group:groups.values())
            {
                var joined=new double[group.size()*9];int n=0;
                for(int triangle:group){System.arraycopy(xyz,triangle*9,joined,n,9);n+=9;}
                components.add(joined);
            }
        }
    }
    private static double zero(double value){return value==0?0:value;}
    private static int find(int[] parent,int i)
    {while(parent[i]!=i){parent[i]=parent[parent[i]];i=parent[i];}return i;}

    boolean separates(RigidTransform captured,RigidTransform from,RigidTransform to,AABB obstacle)
    {
        if(capturedShapes!=null&&!capturedShapes.contains(obstacle))return false;
        if(!Double.isFinite(captured.translation().lengthSqr()+from.translation().lengthSqr()+to.translation().lengthSqr())
                ||!sameRotation(captured,from)||!sameRotation(from,to)
                ||from.translation().x!=captured.translation().x||from.translation().z!=captured.translation().z
                ||to.translation().x!=from.translation().x||to.translation().z!=from.translation().z
                ||from.translation().y<captured.translation().y||to.translation().y<from.translation().y)return false;
        double start=from.translation().y-captured.translation().y;
        double end=to.translation().y-captured.translation().y;
        if(!captured.equals(capturedFrame))capture(captured);
        var clipped=contacts.computeIfAbsent(obstacle,this::contacts);
        boolean initial=false,moving=false;double lowest=Double.POSITIVE_INFINITY;
        for(var component:clipped)
        {
            initial|=component.initial();lowest=Math.min(lowest,component.lowest());var ranges=component.ranges();
            for(int n=0;n<ranges.length;n+=2)
                if(ranges[n]+start<obstacle.maxY&&ranges[n+1]+end>obstacle.minY){moving=true;break;}
        }
        // Exported armour/sole patches are not separate physical payloads.
        // One initial intersection admits only this same captured native shape
        // until the complete body leaves it. The exit height comes from exact
        // triangles clipped to this obstacle's X/Z footprint, never its AABB
        // or an unrelated low vertex. New solids and protected loads are still
        // rejected by the caller; horizontal, downward and rotated paths above
        // remain inadmissible.
        // A fragmented sole may start entirely inside the captured floor,
        // below its top face. The pickup snapshot also contains the connected
        // floor under its actual upward sweep; it is still the same support,
        // even where no exported triangle crossed a particular voxel at t=0.
        boolean capturedFloor=capturedShapes!=null&&obstacle.maxY<=captured.translation().y+.005
                &&lowest<obstacle.maxY;
        return (initial||capturedFloor)&&moving&&Double.isFinite(lowest)&&start<obstacle.maxY-lowest+.005;
    }
    private void capture(RigidTransform frame)
    {
        contacts.clear();var transformed=new ArrayList<WorldComponent>();
        for(var source:components)
        {
            var xyz=new double[source.length];
            double x=Double.POSITIVE_INFINITY,y=x,z=x,X=Double.NEGATIVE_INFINITY,Y=X,Z=X;
            for(int n=0;n<source.length;n+=3)
            {
                var p=frame.transformPoint(point(source,n));xyz[n]=p.x;xyz[n+1]=p.y;xyz[n+2]=p.z;
                x=Math.min(x,p.x);y=Math.min(y,p.y);z=Math.min(z,p.z);
                X=Math.max(X,p.x);Y=Math.max(Y,p.y);Z=Math.max(Z,p.z);
            }
            transformed.add(new WorldComponent(xyz,new AABB(x,y,z,X,Y,Z)));
        }
        worldComponents=List.copyOf(transformed);capturedFrame=frame;
    }
    private List<Contact> contacts(AABB obstacle)
    {
        var result=new ArrayList<Contact>();
        for(var component:worldComponents)
        {
            var bounds=component.bounds();
            if(bounds.maxX<obstacle.minX||bounds.minX>obstacle.maxX||bounds.maxZ<obstacle.minZ||bounds.minZ>obstacle.maxZ)continue;
            var xyz=component.xyz();var ranges=new ArrayList<Double>();
            boolean initial=false;double lowest=Double.POSITIVE_INFINITY;
            for(int n=0;n<xyz.length;n+=9)
            {
                // Reject before allocating triangle points or clip polygons.
                if(Math.max(xyz[n],Math.max(xyz[n+3],xyz[n+6]))<obstacle.minX
                        ||Math.min(xyz[n],Math.min(xyz[n+3],xyz[n+6]))>obstacle.maxX
                        ||Math.max(xyz[n+2],Math.max(xyz[n+5],xyz[n+8]))<obstacle.minZ
                        ||Math.min(xyz[n+2],Math.min(xyz[n+5],xyz[n+8]))>obstacle.maxZ)continue;
                var polygon=clip(clip(clip(clip(List.of(point(xyz,n),point(xyz,n+3),point(xyz,n+6)),true,obstacle.minX,true),
                        true,obstacle.maxX,false),false,obstacle.minZ,true),false,obstacle.maxZ,false);
                if(polygon.isEmpty())continue;
                double low=Double.POSITIVE_INFINITY,high=Double.NEGATIVE_INFINITY;
                for(var p:polygon){low=Math.min(low,p.y);high=Math.max(high,p.y);}
                lowest=Math.min(lowest,low);initial|=low<obstacle.maxY&&high>obstacle.minY;
                ranges.add(low);ranges.add(high);
            }
            if(!ranges.isEmpty())result.add(new Contact(initial,lowest,ranges.stream().mapToDouble(Double::doubleValue).toArray()));
        }
        return List.copyOf(result);
    }
    private static boolean sameRotation(RigidTransform a,RigidTransform b)
    {return a.qx()==b.qx()&&a.qy()==b.qy()&&a.qz()==b.qz()&&a.qw()==b.qw();}
    private static Vec3 point(double[] xyz,int n){return new Vec3(xyz[n],xyz[n+1],xyz[n+2]);}
    private static List<Vec3> clip(List<Vec3> source,boolean x,double edge,boolean greater)
    {
        var out=new ArrayList<Vec3>();if(source.isEmpty())return out;
        var before=source.get(source.size()-1);double a=x?before.x:before.z;
        boolean previous=greater?a>=edge:a<=edge;
        for(var current:source)
        {
            double b=x?current.x:current.z;boolean inside=greater?b>=edge:b<=edge;
            if(previous!=inside)out.add(before.lerp(current,(edge-a)/(b-a)));
            if(inside)out.add(current);
            before=current;a=b;previous=inside;
        }
        return out;
    }
}
