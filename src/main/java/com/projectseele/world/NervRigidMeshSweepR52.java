package com.projectseele.world;

import java.util.*;
import net.minecraft.world.phys.*;

/** Exact selected triangles on one native canonical rigid interpolation.
 * Translation is affine and rotation is shortest-arc SLERP, as rendered by
 * the capsule. This proof cannot certify an arbitrary authored curve. */
public final class NervRigidMeshSweepR52
{
    private final double[] xyz;private final int[] order;private final Node root;
    private static final class Node{AABB box;Node left,right;int start,end;}
    public NervRigidMeshSweepR52(double[] source)
    {if(source.length==0||source.length%9!=0||Arrays.stream(source).anyMatch(x->!Double.isFinite(x)))throw new IllegalArgumentException("Actual finite triangles required");xyz=source.clone();order=new int[xyz.length/9];for(int i=0;i<order.length;i++)order[i]=i;root=build(0,order.length);}
    public AABB bounds(){return root.box;}
    public double[] triangles(){return xyz.clone();}
    public List<AABB> leafEnvelopes(RigidTransform from,RigidTransform to){var boxes=new ArrayList<AABB>();leafEnvelopes(root,from,to,boxes);return List.copyOf(boxes);}
    private static void leafEnvelopes(Node node,RigidTransform from,RigidTransform to,List<AABB> boxes)
    {if(node.left!=null){leafEnvelopes(node.left,from,to,boxes);leafEnvelopes(node.right,from,to,boxes);return;}double e=error(radius(node.box),angular(from,to),1);boxes.add(transformed(node.box,from).minmax(transformed(node.box,to)).inflate(e,yawOnly(from,to)?0:e,e));}
    private Vec3 p(int tri,int c){int n=tri*9+c*3;return new Vec3(xyz[n],xyz[n+1],xyz[n+2]);}
    private AABB box(int tri){var a=p(tri,0);return new AABB(a,a).minmax(new AABB(p(tri,1),p(tri,1))).minmax(new AABB(p(tri,2),p(tri,2)));}
    private double centre(int t,int axis){int n=t*9+axis;return (xyz[n]+xyz[n+3]+xyz[n+6])/3;}
    private void partition(int start,int end,int target,int axis)
    {int low=start,high=end-1;while(low<high){double pivot=centre(order[(low+high)>>>1],axis);int i=low,j=high;while(i<=j){while(centre(order[i],axis)<pivot)i++;while(centre(order[j],axis)>pivot)j--;if(i<=j){int old=order[i];order[i++]=order[j];order[j--]=old;}}if(target<=j)high=j;else if(target>=i)low=i;else break;}}
    private Node build(int start,int end)
    {var n=new Node();n.start=start;n.end=end;for(int i=start;i<end;i++)n.box=n.box==null?box(order[i]):n.box.minmax(box(order[i]));if(end-start>12){int axis=n.box.getXsize()>n.box.getYsize()?0:1;if(n.box.getZsize()>(axis==0?n.box.getXsize():n.box.getYsize()))axis=2;int mid=(start+end)>>>1;partition(start,end,mid,axis);n.left=build(start,mid);n.right=build(mid,end);}return n;}
    public static AABB transformed(AABB b,RigidTransform f)
    {AABB result=null;for(double x:new double[]{b.minX,b.maxX})for(double y:new double[]{b.minY,b.maxY})for(double z:new double[]{b.minZ,b.maxZ}){var p=f.transformPoint(new Vec3(x,y,z));result=result==null?new AABB(p,p):result.minmax(new AABB(p,p));}return result;}
    public static double radius(AABB b)
    {double r=0;for(double x:new double[]{b.minX,b.maxX})for(double y:new double[]{b.minY,b.maxY})for(double z:new double[]{b.minZ,b.maxZ})r=Math.max(r,new Vec3(x,y,z).length());return r;}
    public static double angular(RigidTransform from,RigidTransform to){return Math.toRadians(from.rotationErrorDegrees(to));}
    public static double error(double radius,double angle,int divisions){return angle==0?0:radius*angle*angle/(8D*divisions*divisions)+radius*8e-6;}
    public static int divisions(double radius,double angle,double maximumError)
    {if(!Double.isFinite(maximumError)||maximumError<=radius*8e-6)throw new IllegalArgumentException("Budget must cover real float quaternion error");int n=Math.max(1,(int)Math.ceil(Math.sqrt(radius*angle*angle/(8*(maximumError-radius*8e-6)))));if(n>4096)throw new IllegalArgumentException("Rigid motion subdivision budget exceeded");return n;}
    public static boolean yawOnly(RigidTransform a,RigidTransform b){return a.qx()==0&&a.qz()==0&&b.qx()==0&&b.qz()==0;}
    public AABB envelope(RigidTransform from,RigidTransform to){double e=error(radius(root.box),angular(from,to),1);return transformed(root.box,from).minmax(transformed(root.box,to)).inflate(e,yawOnly(from,to)?0:e,e);}
    public boolean intersects(RigidTransform from,RigidTransform to,AABB obstacle,double maximumError)
    {return visit(root,from,to,obstacle,maximumError);}
    /** Pair BVHs on the same physical time interval. Each narrow test is the
     * two real triangle chord hulls plus certified rotation errors. */
    public boolean intersects(RigidTransform from,RigidTransform to,NervRigidMeshSweepR52 other,RigidTransform otherFrom,RigidTransform otherTo,double maximumError,Vec3 extraError)
    {if(!Double.isFinite(extraError.lengthSqr())||extraError.x<0||extraError.y<0||extraError.z<0)throw new IllegalArgumentException("Finite curve certificate required");return pair(root,from,to,other,other.root,otherFrom,otherTo,maximumError,extraError);}
    private boolean pair(Node a,RigidTransform from,RigidTransform to,NervRigidMeshSweepR52 other,Node b,RigidTransform bf,RigidTransform bt,double budget,Vec3 extra)
    {
        double ar=radius(a.box),br=radius(b.box),aa=angular(from,to),ba=angular(bf,bt);double ae=error(ar,aa,1),be=error(br,ba,1);
        var ab=transformed(a.box,from).minmax(transformed(a.box,to)).inflate(ae+extra.x,(yawOnly(from,to)?0:ae)+extra.y,ae+extra.z);var bb=transformed(b.box,bf).minmax(transformed(b.box,bt)).inflate(be,yawOnly(bf,bt)?0:be,be);if(!ab.intersects(bb))return false;
        if(a.left!=null&&(b.left==null||a.end-a.start>=b.end-b.start))return pair(a.left,from,to,other,b,bf,bt,budget,extra)||pair(a.right,from,to,other,b,bf,bt,budget,extra);
        if(b.left!=null)return pair(a,from,to,other,b.left,bf,bt,budget,extra)||pair(a,from,to,other,b.right,bf,bt,budget,extra);
        int n=Math.max(divisions(ar,aa,budget),divisions(br,ba,budget));ae=error(ar,aa,n);be=error(br,ba,n);var pad=new Vec3(ae+be+extra.x,(yawOnly(from,to)?0:ae)+(yawOnly(bf,bt)?0:be)+extra.y,ae+be+extra.z);
        for(int s=0;s<n;s++){var af=from.interpolate(to,(double)s/n);var at=from.interpolate(to,(double)(s+1)/n);var of=bf.interpolate(bt,(double)s/n);var ot=bf.interpolate(bt,(double)(s+1)/n);for(int i=a.start;i<a.end;i++){var ap=corners(order[i],af,at);for(int j=b.start;j<b.end;j++)if(TriangleSweepMeshR52.convexSweepPair(ap,other.corners(other.order[j],of,ot),pad))return true;}}return false;
    }
    private Vec3[] corners(int tri,RigidTransform from,RigidTransform to){var out=new Vec3[6];for(int c=0;c<3;c++){out[c]=from.transformPoint(p(tri,c));out[c+3]=to.transformPoint(p(tri,c));}return out;}
    public boolean intersectsChord(Vec3[] chord,Vec3 error,RigidTransform frame)
    {AABB box=null;for(var p:chord)box=box==null?new AABB(p,p):box.minmax(new AABB(p,p));return chord(root,chord,error,box.inflate(error.x,error.y,error.z),frame);}
    public boolean intersectsChord(Vec3[] chord,Vec3 error,RigidTransform from,RigidTransform to)
    {AABB box=null;for(var p:chord)box=box==null?new AABB(p,p):box.minmax(new AABB(p,p));return movingChord(root,chord,error,box.inflate(error.x,error.y,error.z),from,to);}
    private boolean movingChord(Node node,Vec3 chord[],Vec3 pad,AABB box,RigidTransform from,RigidTransform to)
    {double e=error(radius(node.box),angular(from,to),1);if(!transformed(node.box,from).minmax(transformed(node.box,to)).inflate(e,yawOnly(from,to)?0:e,e).intersects(box))return false;if(node.left!=null)return movingChord(node.left,chord,pad,box,from,to)||movingChord(node.right,chord,pad,box,from,to);var certified=new Vec3(pad.x+e,pad.y+(yawOnly(from,to)?0:e),pad.z+e);for(int i=node.start;i<node.end;i++)if(TriangleSweepMeshR52.convexSweepPair(chord,corners(order[i],from,to),certified))return true;return false;}
    private boolean chord(Node node,Vec3[] chord,Vec3 error,AABB box,RigidTransform frame)
    {if(!transformed(node.box,frame).intersects(box))return false;if(node.left!=null)return chord(node.left,chord,error,box,frame)||chord(node.right,chord,error,box,frame);for(int i=node.start;i<node.end;i++)if(TriangleSweepMeshR52.convexSweepPair(chord,corners(order[i],frame,frame),error))return true;return false;}
    private boolean visit(Node node,RigidTransform from,RigidTransform to,AABB obstacle,double maximumError)
    {
        double r=radius(node.box),angle=angular(from,to);if(!transformed(node.box,from).minmax(transformed(node.box,to)).inflate(error(r,angle,1)).intersects(obstacle))return false;
        if(node.left!=null)return visit(node.left,from,to,obstacle,maximumError)||visit(node.right,from,to,obstacle,maximumError);
        int n=divisions(r,angle,maximumError);double e=error(r,angle,n);
        for(int s=0;s<n;s++){var a=from.interpolate(to,(double)s/n);var b=from.interpolate(to,(double)(s+1)/n);for(int i=node.start;i<node.end;i++){var points=new Vec3[6];for(int c=0;c<3;c++){points[c]=a.transformPoint(p(order[i],c));points[c+3]=b.transformPoint(p(order[i],c));}if(TriangleSweepMeshR52.convexSweepBox(points,new Vec3(e,yawOnly(from,to)?0:e,e),obstacle))return true;}}
        return false;
    }
}
