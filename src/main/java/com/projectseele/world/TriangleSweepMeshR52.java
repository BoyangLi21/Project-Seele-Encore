package com.projectseele.world;

import java.util.*;
import net.minecraft.world.phys.*;

/** Immutable original triangle topology with a local BVH. Broadphase boxes
 * never fill an imported frame's empty mouth or concave cavity. */
public final class TriangleSweepMeshR52
{
    private final double[] xyz;
    private final int[] order;
    private final Node root;
    private final boolean closed;
    private record Vertex(double x,double y,double z){}
    private static final class Node{AABB box;Node left,right;int start,end;}
    public TriangleSweepMeshR52(double[] triangles)
    {
        if(triangles.length==0||triangles.length%9!=0||Arrays.stream(triangles).anyMatch(v->!Double.isFinite(v)))throw new IllegalArgumentException("Complete finite original triangles required");
        xyz=triangles.clone();order=new int[xyz.length/9];var vertices=new HashMap<Vertex,Integer>();var edges=new HashMap<Long,Integer>();
        for(int i=0;i<order.length;i++){order[i]=i;int[] ids=new int[3];for(int c=0;c<3;c++){var p=point(i,c);ids[c]=vertices.computeIfAbsent(new Vertex(p.x,p.y,p.z),key->vertices.size());}for(int c=0;c<3;c++){int a=ids[c],b=ids[(c+1)%3];if(a!=b)edges.merge(((long)Math.min(a,b)<<32)|(Math.max(a,b)&0xffffffffL),1,Integer::sum);}}
        closed=!edges.isEmpty()&&edges.values().stream().allMatch(n->n==2);root=build(0,order.length);
    }
    public int triangles(){return order.length;}
    public double[] vertices(){return xyz.clone();}
    public AABB bounds(){return root.box;}
    public boolean closed(){return closed;}
    private Vec3 point(int triangle,int corner){int n=triangle*9+corner*3;return new Vec3(xyz[n],xyz[n+1],xyz[n+2]);}
    private AABB triangleBox(int t){var a=point(t,0);var b=point(t,1);var c=point(t,2);return new AABB(a,a).minmax(new AABB(b,b)).minmax(new AABB(c,c));}
    private double centre(int t,int axis){int n=t*9+axis;return (xyz[n]+xyz[n+3]+xyz[n+6])/3;}
    private void select(int start,int end,int target,int axis)
    {
        int low=start,high=end-1;while(low<high){double pivot=centre(order[(low+high)>>>1],axis);int i=low,j=high;while(i<=j){while(centre(order[i],axis)<pivot)i++;while(centre(order[j],axis)>pivot)j--;if(i<=j){int old=order[i];order[i++]=order[j];order[j--]=old;}}if(target<=j)high=j;else if(target>=i)low=i;else break;}
    }
    private Node build(int start,int end)
    {
        var node=new Node();node.start=start;node.end=end;for(int i=start;i<end;i++){var b=triangleBox(order[i]);node.box=node.box==null?b:node.box.minmax(b);}if(end-start>12){int axis=node.box.getXsize()>node.box.getYsize()?0:1;if(node.box.getZsize()>(axis==0?node.box.getXsize():node.box.getYsize()))axis=2;int mid=(start+end)>>>1;select(start,end,mid,axis);node.left=build(start,mid);node.right=build(mid,end);}return node;
    }
    private static double radius(AABB box,Vec3 bearing)
    {double squared=0;for(double x:new double[]{box.minX,box.maxX})for(double y:new double[]{box.minY,box.maxY})for(double z:new double[]{box.minZ,box.maxZ})squared=Math.max(squared,new Vec3(x,y,z).distanceToSqr(bearing));return Math.sqrt(squared);}
    private static AABB transformed(AABB box,RigidTransform frame)
    {AABB result=null;for(double x:new double[]{box.minX,box.maxX})for(double y:new double[]{box.minY,box.maxY})for(double z:new double[]{box.minZ,box.maxZ}){var p=frame.transformPoint(new Vec3(x,y,z));var b=new AABB(p,p);result=result==null?b:result.minmax(b);}return result;}
    public AABB envelope(DirectoryTrajectoryR52 path)
    {double r=radius(root.box,path.footCentreLocal());return transformed(root.box,path.sample(0).evaRoot()).minmax(transformed(root.box,path.sample(1).evaRoot())).inflate(path.error(r,1));}
    public PreparedSweep prepare(DirectoryTrajectoryR52 path,double maximumError){return new PreparedSweep(path,maximumError);}
    public final class PreparedSweep
    {
        private final DirectoryTrajectoryR52 path;private final double maximumError;private final AABB wholeEnvelope;
        private final Map<Node,AABB> envelopes=new IdentityHashMap<>();
        private final Map<Node,Double> radii=new IdentityHashMap<>();
        private final Map<Node,List<CurveSegment>> segments=new IdentityHashMap<>();
        private PreparedSweep(DirectoryTrajectoryR52 path,double maximumError){this.path=Objects.requireNonNull(path);if(!Double.isFinite(maximumError)||maximumError<=0)throw new IllegalArgumentException("Positive finite error required");this.maximumError=maximumError;wholeEnvelope=envelope(root);}
        private double radius(Node node){return radii.computeIfAbsent(node,n->TriangleSweepMeshR52.radius(n.box,path.footCentreLocal()));}
        private AABB envelope(Node node){return envelopes.computeIfAbsent(node,n->transformed(n.box,path.sample(0).evaRoot()).minmax(transformed(n.box,path.sample(1).evaRoot())).inflate(path.error(radius(n),1)));}
        private List<CurveSegment> segments(Node node)
        {
            return segments.computeIfAbsent(node,n->{double r=radius(n);int count=path.divisions(r,maximumError);double error=path.error(r,count);var result=new ArrayList<CurveSegment>(count);
                for(int i=0;i<count;i++){double a=(double)i/count,b=(double)(i+1)/count;var from=path.sample(a).evaRoot();var to=path.sample(b).evaRoot();result.add(new CurveSegment(a,b,from,to,error,count,transformed(n.box,from).minmax(transformed(n.box,to)).inflate(error)));}return List.copyOf(result);});
        }
        public boolean intersects(AABB obstacle){return wholeEnvelope.intersects(obstacle)&&(TriangleSweepMeshR52.this.intersects(root,this,obstacle)||closed&&inside(path.sample(0).evaRoot().inverse().transformPoint(obstacle.getCenter())));}
        public boolean intersects(NervRigidMeshSweepR52 obstacle,RigidTransform from,RigidTransform to){return paired(root,this,obstacle,from,to,obstacle.envelope(from,to));}
    }
    private record CurveSegment(double start,double end,RigidTransform from,RigidTransform to,double error,int divisions,AABB bounds){}
    public boolean intersects(DirectoryTrajectoryR52 path,AABB obstacle,double maximumError)
    {return prepare(path,maximumError).intersects(obstacle);}
    /** The same certified directory curve against actual moving machinery,
     * including its empty centre. Neither actor's broadphase fills that hole. */
    public boolean intersects(DirectoryTrajectoryR52 path,NervRigidMeshSweepR52 obstacle,
            RigidTransform obstacleFrom,RigidTransform obstacleTo,double maximumError)
    {
        return prepare(path,maximumError).intersects(obstacle,obstacleFrom,obstacleTo);
    }
    private boolean paired(Node node,PreparedSweep query,NervRigidMeshSweepR52 obstacle,
            RigidTransform obstacleFrom,RigidTransform obstacleTo,AABB obstacleBounds)
    {
        if(!query.envelope(node).intersects(obstacleBounds))return false;
        if(node.left!=null)return paired(node.left,query,obstacle,obstacleFrom,obstacleTo,obstacleBounds)
                ||paired(node.right,query,obstacle,obstacleFrom,obstacleTo,obstacleBounds);
        for(var segment:query.segments(node))
        {
            if(!segment.bounds.intersects(obstacleBounds))continue;
            var from=segment.from;var to=segment.to;var pad=new Vec3(segment.error,segment.error,segment.error);
            var otherFrom=obstacleFrom.interpolate(obstacleTo,segment.start);var otherTo=obstacleFrom.interpolate(obstacleTo,segment.end);
            for(int i=node.start;i<node.end;i++)
            {
                var chord=new Vec3[6];for(int c=0;c<3;c++){var point=point(order[i],c);chord[c]=from.transformPoint(point);chord[c+3]=to.transformPoint(point);}
                if(obstacle.intersectsChord(chord,pad,otherFrom,otherTo))return true;
            }
        }
        return false;
    }
    private boolean inside(Vec3 point)
    {
        if(!root.box.contains(point))return false;var direction=new Vec3(1,.000037,.000071);var hits=new TreeSet<Double>();ray(root,point,direction,hits);return hits.size()%2==1;
    }
    private void ray(Node node,Vec3 point,Vec3 direction,Set<Double> hits)
    {
        var end=point.add(direction.scale(root.box.getSize()*8+1));if(!node.box.contains(point)&&node.box.clip(point,end).isEmpty())return;
        if(node.left!=null){ray(node.left,point,direction,hits);ray(node.right,point,direction,hits);return;}
        for(int i=node.start;i<node.end;i++){int t=order[i];var a=point(t,0);var ab=point(t,1).subtract(a);var ac=point(t,2).subtract(a);var cross=direction.cross(ac);double determinant=ab.dot(cross);if(Math.abs(determinant)<1e-14)continue;var offset=point.subtract(a);double u=offset.dot(cross)/determinant;if(u<0||u>1)continue;var q=offset.cross(ab);double v=direction.dot(q)/determinant;if(v<0||u+v>1)continue;double distance=ac.dot(q)/determinant;if(distance>0)hits.add(Math.rint(distance*1e10)/1e10);}
    }
    private boolean intersects(Node node,PreparedSweep query,AABB obstacle)
    {
        if(!query.envelope(node).intersects(obstacle))return false;
        if(node.left!=null)return intersects(node.left,query,obstacle)||intersects(node.right,query,obstacle);
        for(var segment:query.segments(node))
        {
            if(!segment.bounds.intersects(obstacle))continue;
            for(int i=node.start;i<node.end;i++)
                if(refinedTriangleBox(query.path,order[i],query.radius(node),segment.start,segment.end,segment.from,segment.to,segment.divisions,0,obstacle))return true;
        }
        return false;
    }
    private boolean refinedTriangleBox(DirectoryTrajectoryR52 path,int triangle,double radius,double a,double b,
            RigidTransform from,RigidTransform to,int divisions,int depth,AABB obstacle)
    {
        double error=path.error(radius,divisions);var points=new Vec3[6];
        for(int corner=0;corner<3;corner++){var p=point(triangle,corner);points[corner]=from.transformPoint(p);points[corner+3]=to.transformPoint(p);}
        if(!convexSweepBox(points,error,obstacle))return false;
        // The error is an enclosure, not solid machinery. Refine only a
        // suspected hit; unresolved or roundoff-limited cases still block.
        if(depth==4||divisions>2048||path.error(radius,divisions*2)>=error)return true;
        double mid=(a+b)*.5;var middle=path.sample(mid).evaRoot();
        return refinedTriangleBox(path,triangle,radius,a,mid,from,middle,divisions*2,depth+1,obstacle)
                ||refinedTriangleBox(path,triangle,radius,mid,b,middle,to,divisions*2,depth+1,obstacle);
    }
    /** SAT for the six-corner chord hull Minkowski-summed with the certified
     * L-infinity error box. All hull face/edge axes are included; extra axes
     * can only prove a true separation. Boundary-only contact is not overlap. */
    public static boolean convexSweepBox(Vec3[] corners,double error,AABB box)
    {
        return convexSweepBox(corners,new Vec3(error,error,error),box);
    }
    public static boolean convexSweepBox(Vec3[] corners,Vec3 error,AABB box)
    {
        if(corners.length!=6||!Double.isFinite(error.lengthSqr())||error.x<0||error.y<0||error.z<0)throw new IllegalArgumentException("Finite chord/error required");
        Vec3[] world={new Vec3(1,0,0),new Vec3(0,1,0),new Vec3(0,0,1)};
        for(var axis:world)if(separated(corners,error,box,axis))return false;
        for(int i=0;i<6;i++)for(int j=i+1;j<6;j++)
        {
            var edge=corners[j].subtract(corners[i]);for(var axis:world)if(separated(corners,error,box,edge.cross(axis)))return false;
            for(int k=j+1;k<6;k++)if(separated(corners,error,box,edge.cross(corners[k].subtract(corners[i]))))return false;
        }
        return true;
    }
    private static boolean separated(Vec3[] points,Vec3 error,AABB box,Vec3 axis)
    {
        if(axis.lengthSqr()<1e-28)return false;double low=Double.POSITIVE_INFINITY,high=Double.NEGATIVE_INFINITY;for(var p:points){double value=p.dot(axis);low=Math.min(low,value);high=Math.max(high,value);}double pad=error.x*Math.abs(axis.x)+error.y*Math.abs(axis.y)+error.z*Math.abs(axis.z);low-=pad;high+=pad;
        var centre=box.getCenter();double b=centre.dot(axis),half=Math.abs(axis.x)*box.getXsize()/2+Math.abs(axis.y)*box.getYsize()/2+Math.abs(axis.z)*box.getZsize()/2;return high<=b-half||low>=b+half;
    }
    public static boolean convexSweepPair(Vec3[] a,Vec3[] b,Vec3 error)
    {
        if(a.length!=6||b.length!=6||!Double.isFinite(error.lengthSqr())||error.x<0||error.y<0||error.z<0)throw new IllegalArgumentException("Actual paired triangle hulls required");
        for(var axis:new Vec3[]{new Vec3(1,0,0),new Vec3(0,1,0),new Vec3(0,0,1)})if(separated(a,b,error,axis))return false;
        int an=distinctEndpointCount(a),bn=distinctEndpointCount(b);
        for(var hull:new Vec3[][]{a,b})
        {
            int n=hull==a?an:bn;
            for(int i=0;i<n;i++)for(int j=i+1;j<n;j++)for(int k=j+1;k<n;k++)if(separated(a,b,error,hull[j].subtract(hull[i]).cross(hull[k].subtract(hull[i]))))return false;
        }
        for(int i=0;i<an;i++)for(int j=i+1;j<an;j++)for(int k=0;k<bn;k++)for(int m=k+1;m<bn;m++)if(separated(a,b,error,a[j].subtract(a[i]).cross(b[m].subtract(b[k]))))return false;
        return true;
    }
    private static int distinctEndpointCount(Vec3[] points)
    {
        // An exactly stationary triangle repeats its three vertices. Removing
        // only those duplicates preserves every hull face and edge axis.
        return points[0].equals(points[3])&&points[1].equals(points[4])&&points[2].equals(points[5])?3:6;
    }
    private static boolean separated(Vec3[] a,Vec3[] b,Vec3 error,Vec3 axis)
    {
        if(axis.lengthSqr()<1e-28)return false;double al=Double.POSITIVE_INFINITY,ah=Double.NEGATIVE_INFINITY,bl=al,bh=ah;for(var p:a){double v=p.dot(axis);al=Math.min(al,v);ah=Math.max(ah,v);}for(var p:b){double v=p.dot(axis);bl=Math.min(bl,v);bh=Math.max(bh,v);}double pad=error.x*Math.abs(axis.x)+error.y*Math.abs(axis.y)+error.z*Math.abs(axis.z);return ah+pad<=bl||al-pad>=bh;
    }
}
