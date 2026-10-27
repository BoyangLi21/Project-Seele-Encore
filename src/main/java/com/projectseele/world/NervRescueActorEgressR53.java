package com.projectseele.world;

import java.util.*;
import net.minecraft.world.phys.*;

/** Immutable source-only vertical exit intervals for already intersecting frozen bodies. */
final class NervRescueActorEgressR53
{
    private static final double EPS=1e-9;
    private final RigidTransform captured;
    private final Vec3 direction;
    private final boolean completeSourceExit;
    private final List<Span> forbidden=new ArrayList<>();
    private double exitHeight=Double.NEGATIVE_INFINITY;
    private record Vertex(double x,double y,double z){}
    private record Span(double low,double high){}
    private static final class Triangle
    {
        final Vec3[] points,edges;final Vec3 normal;final AABB box;
        Triangle(Vec3 a,Vec3 b,Vec3 c)
        {
            points=new Vec3[]{a,b,c};edges=new Vec3[]{b.subtract(a),c.subtract(b),a.subtract(c)};
            normal=edges[0].cross(edges[1]);box=new AABB(a,a).minmax(new AABB(b,b)).minmax(new AABB(c,c));

        }
    }
    private static final class Node
    {
        final Triangle[] triangles;final int from,to;final AABB box;final Node left,right;
        Node(Triangle[] triangles,int from,int to)
        {
            this.triangles=triangles;this.from=from;this.to=to;AABB bounds=triangles[from].box;
            for(int i=from+1;i<to;i++)bounds=bounds.minmax(triangles[i].box);box=bounds;
            if(to-from<=8){left=null;right=null;return;}
            boolean x=box.getXsize()>=box.getZsize();
            Arrays.sort(triangles,from,to,Comparator.comparingDouble(t->x?t.box.minX+t.box.maxX:t.box.minZ+t.box.maxZ));
            int mid=(from+to)>>>1;left=new Node(triangles,from,mid);right=new Node(triangles,mid,to);
        }
    }
    NervRescueActorEgressR53(EvaOriginalMeshGeometryR52.Geometry movingBody,RigidTransform captured,
            List<NervRigidMeshSweepR52> obstacleBody,RigidTransform obstacleFrame)
    {
        this(movingBody,captured,obstacleBody,obstacleFrame,new Vec3(0,1,0),false);
    }
    NervRescueActorEgressR53(EvaOriginalMeshGeometryR52.Geometry movingBody,RigidTransform captured,
            List<NervRigidMeshSweepR52> obstacleBody,RigidTransform obstacleFrame,Vec3 direction,boolean completeSourceExit)
    {
        double length=direction.length();
        if(!Double.isFinite(length)||length==0)throw new IllegalArgumentException("Finite extraction direction required");
        this.captured=Objects.requireNonNull(captured);this.direction=direction.scale(1/length);this.completeSourceExit=completeSourceExit;
        var u=Math.abs(this.direction.z)<.9?new Vec3(this.direction.y,-this.direction.x,0).normalize():new Vec3(0,this.direction.z,-this.direction.y).normalize();
        var axes=new Vec3[]{u,this.direction,u.cross(this.direction)};
        var moving=new ArrayList<Node>();var fixed=new ArrayList<Node>();
        for(var part:movingBody.parts())moving.addAll(components(part.triangles(),captured,axes));
        for(var part:obstacleBody)fixed.addAll(components(part.triangles(),obstacleFrame,axes));
        for(var a:moving)for(var b:fixed)
        {
            if(!overlapXZ(a.box,b.box))continue;
            var intervals=new ArrayList<Span>();boolean[] initialContact={false};pairs(a,b,intervals,initialContact);
            if(intervals.isEmpty())continue;
            intervals.sort(Comparator.comparingDouble(Span::low));
            var merged=new ArrayList<Span>();
            for(var span:intervals)
            {
                if(!merged.isEmpty()&&span.low()<=merged.get(merged.size()-1).high())
                {var previous=merged.remove(merged.size()-1);merged.add(new Span(previous.low(),Math.max(previous.high(),span.high())));}
                else merged.add(span);
            }
            // Preserve initial contact seeds and all remaining intervals.
            // separates joins the complete body's continuous initial overlap.
            for(var span:merged)
            {
                if(initialContact[0]&&span.low()<0&&span.high()>0)
                {exitHeight=Math.max(exitHeight,span.high());}
                else if(span.high()>=0)forbidden.add(span);
            }
        }
        forbidden.sort(Comparator.comparingDouble(Span::low));
    }
    boolean separates(RigidTransform from,RigidTransform to)
    {
        if(!Double.isFinite(exitHeight)||!sameRotation(captured,from)||!sameRotation(from,to))return false;
        var a=from.translation().subtract(captured.translation());var b=to.translation().subtract(captured.translation());
        double start=a.dot(direction),end=b.dot(direction);
        if(a.subtract(direction.scale(start)).lengthSqr()>.005*.005||b.subtract(direction.scale(end)).lengthSqr()>.005*.005)return false;
        // One frozen body may be exported as many parts. Continue its initial
        // overlap until the complete pair first separates; a later disjoint
        // contact interval still cannot be entered.
        double completeExit=exitHeight;
        for(var span:forbidden)
        {if(!completeSourceExit&&span.low()>completeExit)break;completeExit=Math.max(completeExit,span.high());}
        if(!Double.isFinite(start+end)||start<0||end<start||start>completeExit)return false;
        for(var span:forbidden)
        {if(span.high()<=completeExit)continue;if(span.low()>end)break;if(span.high()>=start)return false;}
        return true;
    }
    private static boolean sameRotation(RigidTransform a,RigidTransform b)
    {return a.qx()==b.qx()&&a.qy()==b.qy()&&a.qz()==b.qz()&&a.qw()==b.qw();}
    private static boolean overlapXZ(AABB a,AABB b)
    {return a.minX<=b.maxX+EPS&&a.maxX+EPS>=b.minX&&a.minZ<=b.maxZ+EPS&&a.maxZ+EPS>=b.minZ;}
    private static int find(int[] parent,int i)
    {while(parent[i]!=i){parent[i]=parent[parent[i]];i=parent[i];}return i;}
    private static List<Node> components(double[] xyz,RigidTransform frame,Vec3[] axes)
    {
        if(xyz.length==0||xyz.length%9!=0)throw new IllegalArgumentException("Complete frozen source triangles required");
        int count=xyz.length/9;int[] parent=new int[count];var shared=new HashMap<Vertex,Integer>();
        for(int i=0;i<count;i++)parent[i]=i;
        for(int i=0;i<count;i++)for(int c=0;c<3;c++)
        {
            int n=i*9+c*3;double x=xyz[n],y=xyz[n+1],z=xyz[n+2];
            if(!Double.isFinite(x+y+z))throw new IllegalArgumentException("Finite frozen source required");
            var prior=shared.putIfAbsent(new Vertex(x==0?0:x,y==0?0:y,z==0?0:z),i);
            if(prior!=null)parent[find(parent,i)]=find(parent,prior);
        }
        var groups=new LinkedHashMap<Integer,List<Triangle>>();
        for(int i=0;i<count;i++)
        {
            Vec3[] v=new Vec3[3];for(int c=0;c<3;c++){int n=i*9+c*3;var world=frame.transformPoint(new Vec3(xyz[n],xyz[n+1],xyz[n+2]));v[c]=new Vec3(world.dot(axes[0]),world.dot(axes[1]),world.dot(axes[2]));}
            groups.computeIfAbsent(find(parent,i),unused->new ArrayList<>()).add(new Triangle(v[0],v[1],v[2]));
        }
        var nodes=new ArrayList<Node>();for(var values:groups.values()){var triangles=values.toArray(Triangle[]::new);nodes.add(new Node(triangles,0,triangles.length));}return nodes;
    }
    private static void pairs(Node a,Node b,List<Span> out,boolean[] initial)
    {
        NervGeometryWorkR53.check();if(!overlapXZ(a.box,b.box)||a.box.minY>b.box.maxY+EPS)return;
        if(a.left!=null&&(b.left==null||a.to-a.from>=b.to-b.from))
        {pairs(a.left,b,out,initial);pairs(a.right,b,out,initial);return;}
        if(b.left!=null){pairs(a,b.left,out,initial);pairs(a,b.right,out,initial);return;}
        for(int i=a.from;i<a.to;i++)for(int j=b.from;j<b.to;j++)
        {
            var x=a.triangles[i];var y=b.triangles[j];if(!overlapXZ(x.box,y.box)||x.box.minY>y.box.maxY+EPS)continue;
            var interval=new Interval();if(!interval.axis(new Vec3(1,0,0),x,y)||!interval.axis(new Vec3(0,1,0),x,y)||!interval.axis(new Vec3(0,0,1),x,y)||!interval.axis(x.normal,x,y)||!interval.axis(y.normal,x,y))continue;
            boolean separated=false;
            for(var edge:x.edges){for(var other:y.edges)if(!interval.axis(edge.cross(other),x,y)){separated=true;break;}if(separated)break;}
            if(separated)continue;
            // Coplanar triangles also need their in-plane edge normals, just
            // as the existing convex SAT includes axes for degenerate chords.
            for(var edge:x.edges)if(!interval.axis(x.normal.cross(edge),x,y)){separated=true;break;}
            if(separated)continue;
            for(var edge:y.edges)if(!interval.axis(y.normal.cross(edge),x,y)){separated=true;break;}
            if(separated||interval.high<0||interval.high<=interval.low)continue;
            if(!Double.isFinite(interval.low)||!Double.isFinite(interval.high))throw new IllegalArgumentException("Unbounded actor contact interval");
            // Initial admission uses the same triangle SAT as native mesh
            // collision, not an overlapping AABB or a sampled approximation.
            if(interval.low<0&&interval.high>0&&TriangleSweepMeshR52.convexSweepPair(
                    new Vec3[]{x.points[0],x.points[1],x.points[2],x.points[0],x.points[1],x.points[2]},
                    new Vec3[]{y.points[0],y.points[1],y.points[2],y.points[0],y.points[1],y.points[2]},Vec3.ZERO))initial[0]=true;
            out.add(new Span(interval.low,interval.high));
        }
    }
    private static final class Interval
    {
        double low=Double.NEGATIVE_INFINITY,high=Double.POSITIVE_INFINITY;
        boolean axis(Vec3 raw,Triangle a,Triangle b)
        {
            double length=raw.length();if(length<1e-12)return true;var axis=raw.scale(1/length);
            double amin=Double.POSITIVE_INFINITY,amax=Double.NEGATIVE_INFINITY,bmin=amin,bmax=amax;
            for(var p:a.points){double v=p.dot(axis);amin=Math.min(amin,v);amax=Math.max(amax,v);}
            for(var p:b.points){double v=p.dot(axis);bmin=Math.min(bmin,v);bmax=Math.max(bmax,v);}
            // Solve the existing SAT projection overlap inequalities for the
            // common upward translation, rather than sampling intermediate poses.
            if(Math.abs(axis.y)<1e-12)return amin<bmax&&amax>bmin;
            double first=(bmin-amax)/axis.y,last=(bmax-amin)/axis.y;
            low=Math.max(low,Math.min(first,last));high=Math.min(high,Math.max(first,last));return low<=high;
        }
    }
}
