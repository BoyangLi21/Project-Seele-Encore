package com.projectseele.world;

import java.util.*;
import net.minecraft.world.phys.*;

/** Exact selected triangles on one native canonical rigid interpolation.
 * Translation is affine and rotation is shortest-arc SLERP, as rendered by
 * the capsule. This proof cannot certify an arbitrary authored curve. */
public final class NervRigidMeshSweepR52
{
    private final double[] xyz;private final int[] order;private final Node root;
    private record LeafBounds(RigidTransform from,RigidTransform to,List<AABB> boxes) {}
    private volatile LeafBounds lastLeafBounds;
    private record Envelope(RigidTransform from,RigidTransform to,AABB bounds){}
    private volatile Envelope lastEnvelope;
    private static final class Node{AABB box;Node left,right;int start,end;double radius;}
    public NervRigidMeshSweepR52(double[] source)
    {if(source.length==0||source.length%9!=0||Arrays.stream(source).anyMatch(x->!Double.isFinite(x)))throw new IllegalArgumentException("Actual finite triangles required");xyz=source.clone();order=new int[xyz.length/9];for(int i=0;i<order.length;i++)order[i]=i;var bounds=new AABB[order.length];for(int i=0;i<bounds.length;i++)bounds[i]=box(i);root=build(0,order.length,bounds,new BuildBins());}
    public AABB bounds(){return root.box;}
    public int triangleCount(){return order.length;}
    public double[] triangles(){return xyz.clone();}
    public List<AABB> leafEnvelopes(RigidTransform from,RigidTransform to)
    {
        // Only immutable source geometry and exact transform values are cached.
        // Native world/actor occupancy is still read by each caller.
        var previous=lastLeafBounds;
        if(previous!=null&&previous.from().equals(from)&&previous.to().equals(to))return previous.boxes();
        var boxes=new ArrayList<AABB>();leafEnvelopes(root,from,to,angular(from,to),yawOnly(from,to),boxes);
        var result=List.copyOf(boxes);lastLeafBounds=new LeafBounds(from,to,result);return result;
    }
    private static void leafEnvelopes(Node node,RigidTransform from,RigidTransform to,double angle,boolean yaw,List<AABB> boxes)
    {if(node.left!=null){leafEnvelopes(node.left,from,to,angle,yaw,boxes);leafEnvelopes(node.right,from,to,angle,yaw,boxes);return;}double e=error(node.radius,angle,1);boxes.add(transformed(node.box,from).minmax(transformed(node.box,to)).inflate(e,yaw?0:e,e));}
    private Vec3 p(int tri,int c){int n=tri*9+c*3;return new Vec3(xyz[n],xyz[n+1],xyz[n+2]);}
    private AABB box(int tri)
    {
        int i=tri*9;
        return new AABB(Math.min(xyz[i],Math.min(xyz[i+3],xyz[i+6])),Math.min(xyz[i+1],Math.min(xyz[i+4],xyz[i+7])),Math.min(xyz[i+2],Math.min(xyz[i+5],xyz[i+8])),
                Math.max(xyz[i],Math.max(xyz[i+3],xyz[i+6])),Math.max(xyz[i+1],Math.max(xyz[i+4],xyz[i+7])),Math.max(xyz[i+2],Math.max(xyz[i+5],xyz[i+8])));
    }
    private double centre(int t,int axis){int n=t*9+axis;return (xyz[n]+xyz[n+3]+xyz[n+6])/3;}
    private void partition(int start,int end,int target,int axis)
    {int low=start,high=end-1;while(low<high){double pivot=centre(order[(low+high)>>>1],axis);int i=low,j=high;while(i<=j){while(centre(order[i],axis)<pivot)i++;while(centre(order[j],axis)>pivot)j--;if(i<=j){int old=order[i];order[i++]=order[j];order[j--]=old;}}if(target<=j)high=j;else if(target>=i)low=i;else break;}}
    /** One workspace per immutable mesh build. Parent partitioning finishes
     * before its children reuse these bins; no per-triangle union objects. */
    private static final class BuildBins
    {
        static final int COUNT=16;
        final double[] minX=new double[COUNT],minY=new double[COUNT],minZ=new double[COUNT],maxX=new double[COUNT],maxY=new double[COUNT],maxZ=new double[COUNT],leftCost=new double[COUNT];
        final int[] count=new int[COUNT],leftCount=new int[COUNT];
        void clear()
        {
            Arrays.fill(minX,Double.POSITIVE_INFINITY);Arrays.fill(minY,Double.POSITIVE_INFINITY);Arrays.fill(minZ,Double.POSITIVE_INFINITY);
            Arrays.fill(maxX,Double.NEGATIVE_INFINITY);Arrays.fill(maxY,Double.NEGATIVE_INFINITY);Arrays.fill(maxZ,Double.NEGATIVE_INFINITY);Arrays.fill(count,0);
        }
        void add(int i,AABB b)
        {
            minX[i]=Math.min(minX[i],b.minX);minY[i]=Math.min(minY[i],b.minY);minZ[i]=Math.min(minZ[i],b.minZ);
            maxX[i]=Math.max(maxX[i],b.maxX);maxY[i]=Math.max(maxY[i],b.maxY);maxZ[i]=Math.max(maxZ[i],b.maxZ);count[i]++;
        }
        void prefixes()
        {
            double x=Double.POSITIVE_INFINITY,y=x,z=x,X=Double.NEGATIVE_INFINITY,Y=X,Z=X;int total=0;
            for(int i=0;i<COUNT;i++)
            {
                x=Math.min(x,minX[i]);y=Math.min(y,minY[i]);z=Math.min(z,minZ[i]);X=Math.max(X,maxX[i]);Y=Math.max(Y,maxY[i]);Z=Math.max(Z,maxZ[i]);total+=count[i];
                leftCount[i]=total;leftCost[i]=total==0?0:area(X-x,Y-y,Z-z)*total;
            }
        }
    }
    private static double area(double x,double y,double z){return 2*(x*y+x*z+y*z);}
    private Node build(int start,int end,AABB[] bounds,BuildBins bins)
    {
        var node=new Node();node.start=start;node.end=end;
        double x=Double.POSITIVE_INFINITY,y=x,z=x,X=Double.NEGATIVE_INFINITY,Y=X,Z=X;
        for(int i=start;i<end;i++)
        {
            var b=bounds[order[i]];x=Math.min(x,b.minX);y=Math.min(y,b.minY);z=Math.min(z,b.minZ);X=Math.max(X,b.maxX);Y=Math.max(Y,b.maxY);Z=Math.max(Z,b.maxZ);
        }
        node.box=new AABB(x,y,z,X,Y,Z);node.radius=radius(node.box);
        if(end-start<=12)return node;
        // Surface area keeps long adjacent members in separate subtrees even
        // when their vertical extent is much larger than their separation.
        double best=Double.POSITIVE_INFINITY,bestMin=0,bestScale=0;int axis=-1,cut=-1,balance=-1;
        for(int dimension=0;dimension<3;dimension++)
        {
            double low=Double.POSITIVE_INFINITY,high=Double.NEGATIVE_INFINITY;
            for(int i=start;i<end;i++){double c=centre(order[i],dimension);low=Math.min(low,c);high=Math.max(high,c);}
            if(!(high>low))continue;
            double scale=BuildBins.COUNT/(high-low);bins.clear();
            for(int i=start;i<end;i++)bins.add(Math.min(BuildBins.COUNT-1,(int)((centre(order[i],dimension)-low)*scale)),bounds[order[i]]);
            bins.prefixes();
            x=Double.POSITIVE_INFINITY;y=x;z=x;X=Double.NEGATIVE_INFINITY;Y=X;Z=X;int total=0;
            for(int i=BuildBins.COUNT-1;i>0;i--)
            {
                x=Math.min(x,bins.minX[i]);y=Math.min(y,bins.minY[i]);z=Math.min(z,bins.minZ[i]);X=Math.max(X,bins.maxX[i]);Y=Math.max(Y,bins.maxY[i]);Z=Math.max(Z,bins.maxZ[i]);total+=bins.count[i];
                if(total==0||bins.leftCount[i-1]==0)continue;
                double cost=bins.leftCost[i-1]+area(X-x,Y-y,Z-z)*total;int balanced=Math.min(total,bins.leftCount[i-1]);
                if(cost<best||cost==best&&balanced>balance){best=cost;axis=dimension;cut=i-1;bestMin=low;bestScale=scale;balance=balanced;}
            }
        }
        int mid;
        if(axis>=0)
        {
            int i=start,j=end-1;
            while(i<=j){int bin=Math.min(BuildBins.COUNT-1,(int)((centre(order[i],axis)-bestMin)*bestScale));if(bin<=cut)i++;else{int old=order[i];order[i]=order[j];order[j--]=old;}}
            mid=i;
        }
        else{axis=node.box.getXsize()>node.box.getYsize()?0:1;if(node.box.getZsize()>(axis==0?node.box.getXsize():node.box.getYsize()))axis=2;mid=(start+end)>>>1;partition(start,end,mid,axis);}
        if(mid<=start||mid>=end)throw new IllegalStateException("Empty source BVH child");
        node.left=build(start,mid,bounds,bins);node.right=build(mid,end,bounds,bins);return node;
    }
    public static AABB transformed(AABB b,RigidTransform f)
    {
        double minX=Double.POSITIVE_INFINITY,minY=minX,minZ=minX,maxX=Double.NEGATIVE_INFINITY,maxY=maxX,maxZ=maxX;
        // Use the same eight corners and arithmetic as transformPoint. Avoid
        // constructing vectors and intermediate boxes for every BVH node.
        double qx=f.qx(),qy=f.qy(),qz=f.qz(),qw=f.qw();var t=f.translation();
        for(int corner=0;corner<8;corner++)
        {
            double x=(corner&4)==0?b.minX:b.maxX,y=(corner&2)==0?b.minY:b.maxY,z=(corner&1)==0?b.minZ:b.maxZ;
            double cx=(qy*z-qz*y)*2,cy=(qz*x-qx*z)*2,cz=(qx*y-qy*x)*2;
            double wx=(x+cx*qw)+(qy*cz-qz*cy)+t.x,wy=(y+cy*qw)+(qz*cx-qx*cz)+t.y,wz=(z+cz*qw)+(qx*cy-qy*cx)+t.z;
            minX=Math.min(minX,wx);minY=Math.min(minY,wy);minZ=Math.min(minZ,wz);
            maxX=Math.max(maxX,wx);maxY=Math.max(maxY,wy);maxZ=Math.max(maxZ,wz);
        }
        return new AABB(minX,minY,minZ,maxX,maxY,maxZ);
    }
    public static double radius(AABB b)
    {double r=0;for(double x:new double[]{b.minX,b.maxX})for(double y:new double[]{b.minY,b.maxY})for(double z:new double[]{b.minZ,b.maxZ})r=Math.max(r,new Vec3(x,y,z).length());return r;}
    public static double angular(RigidTransform from,RigidTransform to){return Math.toRadians(from.rotationErrorDegrees(to));}
    public static double error(double radius,double angle,int divisions){return angle==0?0:radius*angle*angle/(8D*divisions*divisions)+radius*8e-6;}
    public static int divisions(double radius,double angle,double maximumError)
    {
        if(!Double.isFinite(radius)||radius<0||!Double.isFinite(angle)||angle<0
                ||!Double.isFinite(maximumError)||maximumError<=0)
            throw new IllegalArgumentException("Finite nonnegative radius/angle and positive budget required");
        // A fixed rotation has no quaternion interpolation error, including
        // fixed rails whose source coordinates are far from their origin.
        if(angle==0)return 1;
        if(maximumError<=radius*8e-6)throw new IllegalArgumentException("Budget must cover real float quaternion error");
        int n=Math.max(1,(int)Math.ceil(Math.sqrt(radius*angle*angle/(8*(maximumError-radius*8e-6)))));
        if(n>4096)throw new IllegalArgumentException("Rigid motion subdivision budget exceeded");return n;
    }
    public static boolean yawOnly(RigidTransform a,RigidTransform b){return a.qx()==0&&a.qz()==0&&b.qx()==0&&b.qz()==0;}
    public AABB envelope(RigidTransform from,RigidTransform to)
    {
        var previous=lastEnvelope;
        if(previous!=null&&previous.from().equals(from)&&previous.to().equals(to))return previous.bounds();
        double e=error(root.radius,angular(from,to),1);
        var bounds=transformed(root.box,from).minmax(transformed(root.box,to)).inflate(e,yawOnly(from,to)?0:e,e);
        lastEnvelope=new Envelope(from,to,bounds);return bounds;
    }
    public boolean intersects(RigidTransform from,RigidTransform to,AABB obstacle,double maximumError)
    {return visit(root,from,to,angular(from,to),yawOnly(from,to),obstacle,maximumError);}
    /** Pair BVHs on the same physical time interval. Each narrow test is the
     * two real triangle chord hulls plus certified rotation errors. */
    public boolean intersects(RigidTransform from,RigidTransform to,NervRigidMeshSweepR52 other,RigidTransform otherFrom,RigidTransform otherTo,double maximumError,Vec3 extraError)
    {return intersects(from,to,other,otherFrom,otherTo,maximumError,extraError,null);}
    public boolean intersects(RigidTransform from,RigidTransform to,NervRigidMeshSweepR52 other,RigidTransform otherFrom,RigidTransform otherTo,double maximumError,Vec3 extraError,PairQuery query)
    {
        if(!Double.isFinite(extraError.lengthSqr())||extraError.x<0||extraError.y<0||extraError.z<0)throw new IllegalArgumentException("Finite curve certificate required");
        // Remove the peer's affine translation at the same physical instant.
        // Rotation remains in world axes, so both SLERP bounds and curve-error
        // padding are unchanged, including when either member rotates.
        var relativeFrom=new RigidTransform(from.translation().subtract(otherFrom.translation()),from.qx(),from.qy(),from.qz(),from.qw());
        var relativeTo=new RigidTransform(to.translation().subtract(otherTo.translation()),to.qx(),to.qy(),to.qz(),to.qw());
        var peerFrom=new RigidTransform(Vec3.ZERO,otherFrom.qx(),otherFrom.qy(),otherFrom.qz(),otherFrom.qw());
        var peerTo=new RigidTransform(Vec3.ZERO,otherTo.qx(),otherTo.qy(),otherTo.qz(),otherTo.qw());
        // The constructor normalizes float quaternions. Reuse this reference
        // frame only when it preserves every original rotation exactly.
        if(sameRotation(from,relativeFrom)&&sameRotation(to,relativeTo)
            &&sameRotation(otherFrom,peerFrom)&&sameRotation(otherTo,peerTo))
        {from=relativeFrom;to=relativeTo;otherFrom=peerFrom;otherTo=peerTo;}
        var a=query==null?new PairMotion(this,from,to,extraError):query.motion(this,from,to,extraError);
        var b=query==null?new PairMotion(other,otherFrom,otherTo,Vec3.ZERO):query.motion(other,otherFrom,otherTo,Vec3.ZERO);
        return pair(root,a,other.root,b,maximumError,extraError);
    }
    private record MotionKey(NervRigidMeshSweepR52 mesh,RigidTransform from,RigidTransform to,Vec3 extra){}
    /** Call-local geometry only: exact mesh identity, frames and padding.
     * Clear moving entries at each interval; stationary entries are bounded
     * and never retain a world occupancy result or collision decision. */
    public static final class PairQuery
    {
        private final Map<MotionKey,PairMotion> fixed=new LinkedHashMap<>(64,.75f,true);
        private final Map<MotionKey,PairMotion> moving=new LinkedHashMap<>(64,.75f,true);
        public void nextInterval(){moving.clear();}
        private PairMotion motion(NervRigidMeshSweepR52 mesh,RigidTransform from,RigidTransform to,Vec3 extra)
        {
            boolean stationary=from.equals(to);var cache=stationary?fixed:moving;
            var key=new MotionKey(mesh,from,to,extra);var result=cache.get(key);
            if(result==null)
            {
                result=new PairMotion(mesh,from,to,extra,true);cache.put(key,result);
                // A complete carried body, plug, rack and nearby rail groups
                // share stationary local projections across route intervals.
                if(cache.size()>(stationary?128:32))cache.remove(cache.keySet().iterator().next());
            }
            return result;
        }
    }
    private static boolean sameRotation(RigidTransform a,RigidTransform b)
    {return a.qx()==b.qx()&&a.qy()==b.qy()&&a.qz()==b.qz()&&a.qw()==b.qw();}
    /** A node can meet thousands of opposite nodes. Its world envelope and
     * triangle endpoints belong to this query's immutable transforms only. */
    private static final class PairMotion
    {
        final NervRigidMeshSweepR52 mesh;final RigidTransform from,to,chordFrom,chordTo;final double angle;final boolean yaw;final Vec3 extra;
        final Map<Node,AABB> boxes=new LinkedHashMap<>(64,.75f,true);
        final Map<Node,LeafHull> leafHulls=new LinkedHashMap<>(64,.75f,true);
        final TriangleChord[][] chords;
        final Map<Integer,ChordPage> boundedChords;
        int cachedChords;
        private static final class ChordPage{final TriangleChord[] entries=new TriangleChord[256];int count;}
        PairMotion(NervRigidMeshSweepR52 mesh,RigidTransform from,RigidTransform to,Vec3 extra)
        {this(mesh,from,to,extra,false);}
        PairMotion(NervRigidMeshSweepR52 mesh,RigidTransform from,RigidTransform to,Vec3 extra,boolean bounded)
        {this.mesh=mesh;this.from=from;this.to=to;this.extra=extra;angle=angular(from,to);yaw=yawOnly(from,to);chordFrom=from.interpolate(to,0);chordTo=from.interpolate(to,1);chords=bounded?null:new TriangleChord[(mesh.triangleCount()+255)>>>8][];boundedChords=bounded?new LinkedHashMap<>(32,.75f,true):null;}
        AABB box(Node node)
        {
            var bounds=boxes.get(node);
            if(bounds==null){double e=error(node.radius,angle,1);bounds=transformed(node.box,from).minmax(transformed(node.box,to)).inflate(e+extra.x,(yaw?0:e)+extra.y,e+extra.z);boxes.put(node,bounds);if(boundedChords!=null&&boxes.size()>2048)boxes.remove(boxes.keySet().iterator().next());}
            return bounds;
        }
        LeafHull leafHull(Node node)
        {
            var result=leafHulls.get(node);if(result!=null)return result;
            var points=new LinkedHashSet<Vec3>();var normals=new ArrayList<Vec3>();
            for(int i=node.start;i<node.end;i++)
            {
                var triangle=chord(mesh.order[i],1,0).points;Collections.addAll(points,triangle);
                var normal=triangle[1].subtract(triangle[0]).cross(triangle[2].subtract(triangle[0]));
                if(normal.lengthSqr()<1e-28)continue;normal=normal.normalize();boolean duplicate=false;
                for(var previous:normals)if(Math.abs(normal.dot(previous))>1-1e-12){duplicate=true;break;}
                if(!duplicate)normals.add(normal);
            }
            result=new LeafHull(points.toArray(Vec3[]::new),normals);
            leafHulls.put(node,result);
            // Fixed source joints have over a thousand leaves. Retain their
            // repeated projections within a bounded geometry working set.
            int limit=from.equals(to)?2048:256;
            if(boundedChords!=null&&leafHulls.size()>limit)leafHulls.remove(leafHulls.keySet().iterator().next());
            return result;
        }
        TriangleChord chord(int triangle,int divisions,int slice)
        {
            // Translation uses one interval. Do not retain a mesh-sized cache
            // for every subdivision of a large rotating assembly.
            if(divisions!=1)return new TriangleChord(mesh.corners(triangle,from.interpolate(to,(double)slice/divisions),from.interpolate(to,(double)(slice+1)/divisions)));
            // Source triangle IDs are dense. Allocate only the touched pages;
            // every leaf pair can then reuse endpoints without hashing IDs.
            int page=triangle>>>8,slot=triangle&255;
            if(boundedChords!=null)
            {
                var cached=boundedChords.get(page);
                if(cached!=null&&cached.entries[slot]!=null)return cached.entries[slot];
                // Keep the same 2048-chord/16-page bound, but let the cache
                // follow the touched source leaves instead of freezing full.
                while(cachedChords>=2048||cached==null&&boundedChords.size()>=16)
                {
                    var oldest=boundedChords.entrySet().iterator();var removed=oldest.next();
                    cachedChords-=removed.getValue().count;oldest.remove();cached=boundedChords.get(page);
                }
                if(cached==null){cached=new ChordPage();boundedChords.put(page,cached);}
                var chord=new TriangleChord(mesh.corners(triangle,chordFrom,chordTo));
                cached.entries[slot]=chord;cached.count++;cachedChords++;
                return chord;
            }
            var entries=chords[page];if(entries==null)chords[page]=entries=new TriangleChord[256];
            var chord=entries[slot];if(chord==null)entries[slot]=chord=new TriangleChord(mesh.corners(triangle,chordFrom,chordTo));
            return chord;
        }
    }
    private static final class TriangleChord
    {
        final Vec3[] points;final AABB bounds;
        TriangleChord(Vec3[] points)
        {
            this.points=points;double minX=Double.POSITIVE_INFINITY,minY=minX,minZ=minX,maxX=Double.NEGATIVE_INFINITY,maxY=maxX,maxZ=maxX;
            for(var p:points){minX=Math.min(minX,p.x);minY=Math.min(minY,p.y);minZ=Math.min(minZ,p.z);maxX=Math.max(maxX,p.x);maxY=Math.max(maxY,p.y);maxZ=Math.max(maxZ,p.z);}
            bounds=new AABB(minX,minY,minZ,maxX,maxY,maxZ);
        }
        boolean overlaps(TriangleChord other,Vec3 pad)
        {
            var b=other.bounds;
            // Identical to SAT's three world axes, including touching faces.
            return bounds.maxX+pad.x>b.minX&&bounds.minX-pad.x<b.maxX&&bounds.maxY+pad.y>b.minY&&bounds.minY-pad.y<b.maxY&&bounds.maxZ+pad.z>b.minZ&&bounds.minZ-pad.z<b.maxZ;
        }
    }
    private record Plane(Vec3 axis,double low,double high){}
    /** The convex hull of a leaf's actual triangle endpoints is only a
     * rejection bound. An overlapping hull always reaches the original
     * per-triangle SAT; cavities and disconnected source members stay intact. */
    private static final class LeafHull
    {
        final Vec3[] points;final List<Plane> planes;
        LeafHull(Vec3[] points,List<Vec3> axes)
        {
            this.points=points;var result=new ArrayList<Plane>();
            for(var axis:axes)result.add(project(axis));planes=List.copyOf(result);
        }
        Plane project(Vec3 axis)
        {
            double low=Double.POSITIVE_INFINITY,high=Double.NEGATIVE_INFINITY;
            for(var point:points){double d=point.dot(axis);low=Math.min(low,d);high=Math.max(high,d);}
            return new Plane(axis,low,high);
        }
        boolean separated(LeafHull other,Vec3 pad)
        {
            for(var plane:planes)
            {
                var b=other.project(plane.axis());var axis=plane.axis();
                double error=pad.x*Math.abs(axis.x)+pad.y*Math.abs(axis.y)+pad.z*Math.abs(axis.z);
                // Outward rounding makes this optional early rejection more
                // conservative than the unchanged triangle SAT at large roots.
                double scale=Math.max(Math.max(Math.abs(plane.low()),Math.abs(plane.high())),Math.max(Math.abs(b.low()),Math.abs(b.high())));
                error+=Math.ulp(scale)*16;
                if(plane.high()+error<b.low()||plane.low()-error>b.high())return true;
            }
            return false;
        }
    }
    private static boolean pair(Node a,PairMotion am,Node b,PairMotion bm,double budget,Vec3 extra)
    {
        NervGeometryWorkR53.check();
        if(!am.box(a).intersects(bm.box(b)))return false;
        if(a.left!=null&&(b.left==null||a.end-a.start>=b.end-b.start))return pair(a.left,am,b,bm,budget,extra)||pair(a.right,am,b,bm,budget,extra);
        if(b.left!=null)return pair(a,am,b.left,bm,budget,extra)||pair(a,am,b.right,bm,budget,extra);
        int n=Math.max(divisions(a.radius,am.angle,budget),divisions(b.radius,bm.angle,budget));
        double ae=error(a.radius,am.angle,n),be=error(b.radius,bm.angle,n);
        var pad=new Vec3(ae+be+extra.x,(am.yaw?0:ae)+(bm.yaw?0:be)+extra.y,ae+be+extra.z);
        if(a.end-a.start>1||b.end-b.start>1)
        {
            // All intermediate chord endpoints lie within the whole-interval
            // rotation bound. Add the original subinterval SAT padding too,
            // so this test encloses every existing narrow-phase candidate.
            double aw=n==1?0:error(a.radius,am.angle,1),bw=n==1?0:error(b.radius,bm.angle,1);
            var broad=pad.add(aw+bw,(am.yaw?0:aw)+(bm.yaw?0:bw),aw+bw);
            var ah=am.leafHull(a);var bh=bm.leafHull(b);
            if(bh.separated(ah,broad)||ah.separated(bh,broad))return false;
        }
        for(int s=0;s<n;s++)for(int i=a.start;i<a.end;i++)
        {
            var ap=am.chord(am.mesh.order[i],n,s);
            for(int j=b.start;j<b.end;j++){var bp=bm.chord(bm.mesh.order[j],n,s);if(ap.overlaps(bp,pad)&&TriangleSweepMeshR52.convexSweepPair(ap.points,bp.points,pad))return true;}
        }
        return false;
    }
    private Vec3[] corners(int tri,RigidTransform from,RigidTransform to){var out=new Vec3[6];for(int c=0;c<3;c++){out[c]=from.transformPoint(p(tri,c));out[c+3]=to.transformPoint(p(tri,c));}return out;}
    public boolean intersectsChord(Vec3[] chord,Vec3 error,RigidTransform frame)
    {AABB box=null;for(var p:chord)box=box==null?new AABB(p,p):box.minmax(new AABB(p,p));return chord(root,chord,error,box.inflate(error.x,error.y,error.z),frame);}
    public boolean intersectsChord(Vec3[] chord,Vec3 error,RigidTransform from,RigidTransform to)
    {AABB box=null;for(var p:chord)box=box==null?new AABB(p,p):box.minmax(new AABB(p,p));return movingChord(root,chord,error,box.inflate(error.x,error.y,error.z),from,to,angular(from,to),yawOnly(from,to));}
    private boolean movingChord(Node node,Vec3 chord[],Vec3 pad,AABB box,RigidTransform from,RigidTransform to,double angle,boolean yaw)
    {double e=error(node.radius,angle,1);if(!transformed(node.box,from).minmax(transformed(node.box,to)).inflate(e,yaw?0:e,e).intersects(box))return false;if(node.left!=null)return movingChord(node.left,chord,pad,box,from,to,angle,yaw)||movingChord(node.right,chord,pad,box,from,to,angle,yaw);var certified=new Vec3(pad.x+e,pad.y+(yaw?0:e),pad.z+e);for(int i=node.start;i<node.end;i++)if(TriangleSweepMeshR52.convexSweepPair(chord,corners(order[i],from,to),certified))return true;return false;}
    private boolean chord(Node node,Vec3[] chord,Vec3 error,AABB box,RigidTransform frame)
    {if(!transformed(node.box,frame).intersects(box))return false;if(node.left!=null)return chord(node.left,chord,error,box,frame)||chord(node.right,chord,error,box,frame);for(int i=node.start;i<node.end;i++)if(TriangleSweepMeshR52.convexSweepPair(chord,corners(order[i],frame,frame),error))return true;return false;}
    private boolean visit(Node node,RigidTransform from,RigidTransform to,double angle,boolean yaw,AABB obstacle,double maximumError)
    {
        double r=node.radius;if(!transformed(node.box,from).minmax(transformed(node.box,to)).inflate(error(r,angle,1)).intersects(obstacle))return false;
        if(node.left!=null)return visit(node.left,from,to,angle,yaw,obstacle,maximumError)||visit(node.right,from,to,angle,yaw,obstacle,maximumError);
        int n=divisions(r,angle,maximumError);double e=error(r,angle,n);
        for(int s=0;s<n;s++){var a=from.interpolate(to,(double)s/n);var b=from.interpolate(to,(double)(s+1)/n);for(int i=node.start;i<node.end;i++){var points=new Vec3[6];for(int c=0;c<3;c++){points[c]=a.transformPoint(p(order[i],c));points[c+3]=b.transformPoint(p(order[i],c));}if(TriangleSweepMeshR52.convexSweepBox(points,new Vec3(e,yaw?0:e,e),obstacle))return true;}}
        return false;
    }
}
