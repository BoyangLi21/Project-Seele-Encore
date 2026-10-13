package com.projectseele.world;

import java.util.*;
import net.minecraft.world.phys.*;

/** Full source triangles on the common hoist curve. A speed certificate
 * bounds every intermediate vertex, including changing rope length/roll.
 * Endpoint boxes are only BVH broadphase, never a passage certificate. */
public final class NervCraneSweepR52
{
    private final NervCraneGeometryR52 geometry;
    private final Map<String,Mesh> meshes=new HashMap<>();
    public NervCraneSweepR52(NervCraneGeometryR52 geometry){this.geometry=Objects.requireNonNull(geometry);}
    private static final class Node{AABB box;Node left,right;int start,end;}
    private static final class Mesh
    {
        final double[] xyz;final Integer[] order;final Node root;
        Mesh(double[] xyz){this.xyz=xyz;order=new Integer[xyz.length/9];for(int i=0;i<order.length;i++)order[i]=i;root=build(0,order.length);}
        Vec3 p(int t,int c){int at=t*9+c*3;return new Vec3(xyz[at],xyz[at+1],xyz[at+2]);}
        Node build(int start,int end)
        {var n=new Node();n.start=start;n.end=end;for(int i=start;i<end;i++)for(int c=0;c<3;c++){var p=p(order[i],c);n.box=n.box==null?new AABB(p,p):n.box.minmax(new AABB(p,p));}if(end-start>12){int axis=n.box.getXsize()>n.box.getYsize()?0:1;if(n.box.getZsize()>(axis==0?n.box.getXsize():n.box.getYsize()))axis=2;final int a=axis;Arrays.sort(order,start,end,Comparator.comparingDouble(t->{var p=p(t,0);var q=p(t,1);var r=p(t,2);return a==0?p.x+q.x+r.x:a==1?p.y+q.y+r.y:p.z+q.z+r.z;}));int mid=(start+end)>>>1;n.left=build(start,mid);n.right=build(mid,end);}return n;}
    }
    public final class Curve
    {
        private final NervCranePoseR52.State from,to;
        private final Map<Double,Map<String,NervCraneGeometryR52.Transform>> samples=new HashMap<>();
        private final Map<String,Double> speeds=new HashMap<>();
        private final double numericError;
        private List<Curve> segments;
        private Curve(NervCranePoseR52.State from,NervCranePoseR52.State to,List<Curve> segments){this.from=from;this.to=to;this.segments=List.copyOf(segments);numericError=0;}
        private Curve(NervCranePoseR52.State from,NervCranePoseR52.State to)
        {
            this.from=from;this.to=to;from.interpolate(to,.5);
            if(!NervRigidMeshSweepR52.yawOnly(from.machine(),to.machine()))throw new IllegalArgumentException("Actual horizontal yaw-only runway frame required");
            if(from.referenceRotation()!=null&&!from.referenceRotation().equals(to.referenceRotation()))throw new IllegalArgumentException("Actual held hoist reference changed");
            double machine=from.machine().translation().distanceTo(to.machine().translation()),grip,omega,jaw,mount;
            if(from.coupled())
            {omega=NervRigidMeshSweepR52.angular(from.plug(),to.plug());grip=from.plug().translation().distanceTo(to.plug().translation())+EntryPlugKinematics.CRANE_ATTACHMENT_P.length()*omega;jaw=0;mount=grip+geometry.mount().length()*omega;}
            else
            {
                if(machine>1e-8||from.plug()!=null||from.referenceWorld()==null)throw new IllegalArgumentException("Uncoupled hoist holds its actual trolley and reference");
                double anchor=from.machine().inverse().transformPoint(from.referenceWorld()).y,travel=Math.max(1,-2-anchor),rise=1.875*Math.abs(to.bottom()-from.bottom());
                grip=6*rise;omega=Math.PI*1.875*rise/Math.max(1,travel-2);jaw=Math.toRadians(32)*rise/.65;mount=grip+geometry.mount().length()*omega;
            }
            numericError=8e-6*(1+geometry.mount().length()+Math.max(Math.abs(from.bottom()),Math.abs(to.bottom()))+EntryPlugKinematics.CRANE_ATTACHMENT_P.length());
            if(numericError>=.003)throw new IllegalArgumentException("Real hoist numeric error exceeds native budget");
            var first=sample(0);var last=sample(1);if(!first.keySet().equals(last.keySet())||first.size()!=19)throw new IllegalArgumentException("Complete real hoist inventory changed");
            for(String name:first.keySet())
            {
                var mesh=meshes.computeIfAbsent(name,k->new Mesh(geometry.sourceFor(k)));double r=NervRigidMeshSweepR52.radius(mesh.root.box),v;
                if(name.equals("top"))v=machine;
                else if(name.startsWith("wheel/"))v=machine+2*r*Math.abs(to.machine().translation().z-from.machine().translation().z)/.38;
                else if(name.equals("yoke")||name.startsWith("sheave/"))v=mount;
                else if(name.startsWith("gripper/"))v=grip+omega*r+(name.equals("gripper/body")?0:jaw*(r+2*geometry.jawPivot(name.substring(8)).length()));
                else if(name.startsWith("mount/"))v=mount;
                else
                {
                    double delta=machine+mount;var f=first.get(name);double length=f.scale().y,minimum=length-delta;
                    if(minimum<=.01)throw new IllegalArgumentException("Actual hoist rope lower length cannot be proved");
                    var direction=f.frame().transformVector(new Vec3(0,1,0));var local=from.machine().inverse().transformVector(direction);double turn=2*delta/minimum;double projected=Math.sqrt(Math.max(0,1-local.x*local.x))-turn;
                    if(projected<=1e-6)throw new IllegalArgumentException("Actual hoist rope roll leaves its verified basis");
                    double basis=4*delta/minimum/projected;
                    v=machine+Math.max(Math.abs(mesh.root.box.minY),Math.abs(mesh.root.box.maxY))*delta+Math.sqrt(Math.pow(Math.max(Math.abs(mesh.root.box.minX),Math.abs(mesh.root.box.maxX)),2)+Math.pow(Math.max(Math.abs(mesh.root.box.minZ),Math.abs(mesh.root.box.maxZ)),2))*.065*basis;
                }
                if(!Double.isFinite(v)||v<0)throw new IllegalArgumentException("Actual vertex speed certificate required");speeds.put(name,v);
            }
        }
        Map<String,NervCraneGeometryR52.Transform> sample(double t){return samples.computeIfAbsent(t,k->geometry.transforms(from.interpolate(to,k).pose(geometry.mount())));}
        private Vec3 error(String name,double duration){double pad=speeds.get(name)*duration/2+numericError;return new Vec3(pad,name.equals("top")?0:pad,pad);}
        public Set<String> names(){return segments==null?Set.copyOf(speeds.keySet()):segments.get(0).names();}
        public AABB envelope(String name){if(segments!=null){AABB out=null;for(var segment:segments)out=out==null?segment.envelope(name):out.minmax(segment.envelope(name));return out;}var m=meshes.get(name);return transformed(m.root.box,sample(0).get(name)).minmax(transformed(m.root.box,sample(1).get(name))).inflate(error(name,1).x,error(name,1).y,error(name,1).z);}
        public boolean intersects(String name,AABB obstacle){if(segments!=null)return segments.stream().anyMatch(s->s.intersects(name,obstacle));if(name.startsWith("wheel/")&&obstacle.maxY<=from.machine().translation().y-.00001)return false;return visit(meshes.get(name),meshes.get(name).root,name,0,1,obstacle,0);}
        private boolean visit(Mesh mesh,Node node,String name,double a,double b,AABB obstacle,int depth)
        {
            var first=sample(a).get(name);var last=sample(b).get(name);var e=error(name,b-a);var envelope=transformed(node.box,first).minmax(transformed(node.box,last)).inflate(e.x,e.y,e.z);if(!envelope.intersects(obstacle))return false;
            if(node.left!=null)return visit(mesh,node.left,name,a,b,obstacle,depth)||visit(mesh,node.right,name,a,b,obstacle,depth);
            if(e.x>.003){if(depth>=14)throw new IllegalArgumentException("Actual full hoist sweep budget exceeded");double mid=(a+b)/2;return visit(mesh,node,name,a,mid,obstacle,depth+1)||visit(mesh,node,name,mid,b,obstacle,depth+1);}
            for(int i=node.start;i<node.end;i++){var vertices=new Vec3[6];for(int c=0;c<3;c++){var p=mesh.p(mesh.order[i],c);vertices[c]=first.point(p);vertices[c+3]=last.point(p);}if(TriangleSweepMeshR52.convexSweepBox(vertices,e,obstacle))return true;}return false;
        }
    }
    public Curve between(NervCranePoseR52.State from,NervCranePoseR52.State to){return between(from,to,0);}
    private Curve between(NervCranePoseR52.State from,NervCranePoseR52.State to,int depth)
    {try{return new Curve(from,to);}catch(IllegalArgumentException bound){if(depth>=10||!bound.getMessage().contains("rope"))throw bound;var middle=from.interpolate(to,.5);return new Curve(from,to,List.of(between(from,middle,depth+1),between(middle,to,depth+1)));}}
    private static AABB transformed(AABB box,NervCraneGeometryR52.Transform f)
    {AABB out=null;for(double x:new double[]{box.minX,box.maxX})for(double y:new double[]{box.minY,box.maxY})for(double z:new double[]{box.minZ,box.maxZ}){var p=f.point(new Vec3(x,y,z));out=out==null?new AABB(p,p):out.minmax(new AABB(p,p));}return out;}
}
