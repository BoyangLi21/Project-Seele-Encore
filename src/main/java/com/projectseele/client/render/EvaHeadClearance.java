package com.projectseele.client.render;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.resources.ResourceLocation;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.GeoBone;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import java.util.*;

/** Keep the helmet clear of the shouldered rifle without moving the weapon. */
final class EvaHeadClearance
{
    record Triangle(Vector3f a,Vector3f b,Vector3f c,Vector3f min,Vector3f max)
    {
        Triangle(Vector3f a,Vector3f b,Vector3f c)
        {
            this(a,b,c,new Vector3f(a).min(b).min(c),new Vector3f(a).max(b).max(c));
        }
    }

    record Node(Vector3f min,Vector3f max,Node left,Node right,List<Triangle> triangles) {}
    private record Correction(float lift,float roll,int side,double time) {}
    private static final Map<Integer,List<Triangle>> HEADS=new HashMap<>();
    private static final com.projectseele.util.WeakIdentityMap<EvaUnit01Entity,Correction> LAST=new com.projectseele.util.WeakIdentityMap<>();
    private static final List<float[]> CANDIDATES=candidates();
    private static Node rifle;
    private record BodyObstacle(Node shape,Matrix4f inverseBone) {}
    private static final Map<String,Node> BACKS=new HashMap<>();

    static void clear()
    {
        HEADS.clear();LAST.clear();BACKS.clear();rifle=null;
    }

    private static List<float[]> candidates()
    {
        var result=new ArrayList<float[]>();
        for(int lift=0;lift<=5;lift++)for(int roll=-4;roll<=4;roll++)
            result.add(new float[]{lift*.06F,roll*.06F});
        result.sort(Comparator.comparingDouble(v->v[0]*v[0]+v[1]*v[1]));
        return List.copyOf(result);
    }

    static List<Triangle> triangles(ResourceLocation resource,String part)
    {
        float[] points=LocalTriangleMeshLayer.nativeTrianglePositions(resource,part);
        if(points==null)return List.of();
        var result=new ArrayList<Triangle>();
        for(int i=0;i<points.length;i+=9)
            result.add(new Triangle(new Vector3f(points[i],points[i+1],points[i+2]),
                    new Vector3f(points[i+3],points[i+4],points[i+5]),
                    new Vector3f(points[i+6],points[i+7],points[i+8])));
        return List.copyOf(result);
    }

    static Node tree(List<Triangle> source)
    {
        var min=new Vector3f(Float.POSITIVE_INFINITY);var max=new Vector3f(Float.NEGATIVE_INFINITY);
        for(var t:source){min.min(t.min());max.max(t.max());}
        if(source.size()<=8)return new Node(min,max,null,null,List.copyOf(source));
        var span=new Vector3f(max).sub(min);int axis=span.x>=span.y&&span.x>=span.z?0:span.y>=span.z?1:2;
        var sorted=new ArrayList<>(source);
        sorted.sort(Comparator.comparingDouble(t->t.min().get(axis)+t.max().get(axis)));
        int half=sorted.size()/2;
        return new Node(min,max,tree(sorted.subList(0,half)),tree(sorted.subList(half,sorted.size())),List.of());
    }

    private static boolean separates(Vector3f axis,Triangle a,Triangle b)
    {
        if(axis.lengthSquared()<1e-14F)return false;
        float a0=axis.dot(a.a()),a1=axis.dot(a.b()),a2=axis.dot(a.c());
        float b0=axis.dot(b.a()),b1=axis.dot(b.b()),b2=axis.dot(b.c());
        return Math.max(a0,Math.max(a1,a2))<Math.min(b0,Math.min(b1,b2))-1e-6F
                ||Math.max(b0,Math.max(b1,b2))<Math.min(a0,Math.min(a1,a2))-1e-6F;
    }

    private static boolean intersects(Triangle a,Triangle b)
    {
        Vector3f[] ea={new Vector3f(a.b()).sub(a.a()),new Vector3f(a.c()).sub(a.b()),new Vector3f(a.a()).sub(a.c())};
        Vector3f[] eb={new Vector3f(b.b()).sub(b.a()),new Vector3f(b.c()).sub(b.b()),new Vector3f(b.a()).sub(b.c())};
        var na=new Vector3f(ea[0]).cross(ea[1]);var nb=new Vector3f(eb[0]).cross(eb[1]);
        if(na.lengthSquared()<1e-14F||nb.lengthSquared()<1e-14F)return false;
        if(separates(na,a,b)||separates(nb,a,b))return false;
        for(var x:ea)for(var y:eb)if(separates(new Vector3f(x).cross(y),a,b))return false;
        // Coplanar triangles also require separating axes within their plane.
        for(var x:ea)if(separates(new Vector3f(na).cross(x),a,b))return false;
        for(var x:eb)if(separates(new Vector3f(nb).cross(x),a,b))return false;
        return true;
    }

    static boolean hits(Node node,Triangle triangle)
    {
        var a=triangle.min();var b=triangle.max();var c=node.min();var d=node.max();
        if(b.x<c.x||a.x>d.x||b.y<c.y||a.y>d.y||b.z<c.z||a.z>d.z)return false;
        if(node.left()!=null)return hits(node.left(),triangle)||hits(node.right(),triangle);
        for(var other:node.triangles())if(intersects(triangle,other))return true;
        return false;
    }

    private static Quaternionf orientation(Quaternionf base,Vector3f right,Vector3f forward,float lift,float roll)
    {
        return new Quaternionf().fromAxisAngleRad(forward,roll)
                .mul(new Quaternionf().fromAxisAngleRad(right,lift)).mul(base);
    }

    private static boolean applyAndTest(GeoBone head,Matrix4f parent,Matrix4f world,Matrix4f inverseGun,
                                         Quaternionf base,Vector3f right,Vector3f forward,
                                         float lift,float roll,List<Triangle> shape,List<BodyObstacle> blockers)
    {
        EvaRigTransforms.rotate(head,EvaRigTransforms.rotation(parent).invert()
                .mul(orientation(base,right,forward,lift,roll)));
        var transform=new Matrix4f(inverseGun).mul(world).mul(EvaRigTransforms.model(head));
        for(var triangle:shape)
        {
            var posed=new Triangle(transform.transformPosition(new Vector3f(triangle.a())),
                    transform.transformPosition(new Vector3f(triangle.b())),
                    transform.transformPosition(new Vector3f(triangle.c())));
            if(hits(rifle,posed))return true;
        }
        for(var blocker:blockers)
        {
            var local=new Matrix4f(blocker.inverseBone()).mul(EvaRigTransforms.model(head));
            for(var triangle:shape)
                if(hits(blocker.shape(),new Triangle(local.transformPosition(new Vector3f(triangle.a())),
                        local.transformPosition(new Vector3f(triangle.b())),local.transformPosition(new Vector3f(triangle.c())))))return true;
        }
        return false;
    }

    static void apply(EvaUnit01Entity eva,GeoBone head,Matrix4f world,Matrix4f gun,
                       Quaternionf desired,Vector3f right,Vector3f forward,float partial,BakedGeoModel model)
    {
        int key=eva instanceof com.projectseele.entity.EvaPrototypeEntity un?3+un.getUNSerial():eva.getUnitVariant();
        var shape=HEADS.computeIfAbsent(key,v->triangles(new ResourceLocation(
                ProjectSeele.MODID,"mesh/"+(v==3?"eva_prototype":v==4?"eva_un01":"eva_unit0"+v)+".mesh.json"),"head"));
        if(shape.isEmpty())return;
        var blockers=new ArrayList<BodyObstacle>();
        if(eva.rifleStanceLevel(partial)>2.4F)
        {
            String asset=key==3?"eva_prototype":key==4?"eva_un01":"eva_unit0"+key;
            for(String part:List.of("torso_upper","pylon_l","pylon_r","dorsal_cover"))
            {
                var bone=model.getBone(part).orElse(null);if(bone==null)continue;
                String id=asset+"/"+part;Node tree=BACKS.get(id);
                if(tree==null)
                {
                    var triangles=triangles(new ResourceLocation(ProjectSeele.MODID,"mesh/"+asset+".mesh.json"),part);
                    if(triangles.isEmpty())continue;tree=tree(triangles);BACKS.put(id,tree);
                }
                blockers.add(new BodyObstacle(tree,new Matrix4f(EvaRigTransforms.model(bone)).invert()));
            }
        }
        if(rifle==null)
        {
            var triangles=triangles(new ResourceLocation(ProjectSeele.MODID,"mesh/eva_pallet_smg.mesh.json"),"cannon");
            if(triangles.isEmpty())return;
            rifle=tree(triangles);
        }
        Matrix4f parent=EvaRigTransforms.parent(head,world),inverseGun=new Matrix4f(gun).invert();
        double time=(eva.tickCount+partial)/20D;
        var previous=LAST.get(eva);
        if(previous!=null&&(time<previous.time()||time-previous.time()>.5))previous=null;
        float oldLift=previous==null?0:previous.lift(),oldRoll=previous==null?0:previous.roll();
        int rollSide=previous==null?0:previous.side();
        float lift=0,roll=0;boolean found=false;
        double best=Double.POSITIVE_INFINITY;
        // The equally good left/right solutions used to alternate every time
        // the sight passed a triangle edge. Prefer a continuous correction
        // from this actor, not the first discrete candidate in global order.
        if(previous!=null&&!applyAndTest(head,parent,world,inverseGun,desired,right,forward,oldLift,oldRoll,shape,blockers))
        {
            lift=oldLift;roll=oldRoll;found=true;
            best=.08*(lift*lift+2*roll*roll);
        }
        for(var candidate:CANDIDATES)
        {
            // Keep the same shoulder-side solution while the rifle is held.
            // Contact/no-contact changes at a triangle edge must not make the
            // helmet jump across the sight line to the other cheek each frame.
            if(rollSide!=0&&candidate[1]*rollSide<0)continue;
            if(!applyAndTest(head,parent,world,inverseGun,desired,right,forward,candidate[0],candidate[1],shape,blockers))
            {
                double dl=candidate[0]-oldLift,dr=candidate[1]-oldRoll;
                double score=dl*dl+2*dr*dr+.08*(candidate[0]*candidate[0]+2*candidate[1]*candidate[1]);
                if(score<best){best=score;lift=candidate[0];roll=candidate[1];found=true;}
            }
        }
        if(!found&&previous!=null)
        {
            // An unsolved frame does not authorize resetting the head to zero;
            // that reset itself produced the visible side-to-side snap.
            lift=oldLift;roll=oldRoll;
        }
        if(previous!=null)
        {
            float relax=(float)Math.exp(-Math.max(0,time-previous.time())/.18);
            float restLift=oldLift*relax,restRoll=oldRoll*relax;
            if(!applyAndTest(head,parent,world,inverseGun,desired,right,forward,restLift,restRoll,shape,blockers))
            {lift=restLift;roll=restRoll;found=true;}
        }
        if(found&&previous!=null&&time>previous.time()&&time-previous.time()<.5)
        {
            float alpha=(float)(1-Math.exp(-(time-previous.time())/.06));
            float smoothedLift=previous.lift()+(lift-previous.lift())*alpha;
            float smoothedRoll=previous.roll()+(roll-previous.roll())*alpha;
            if(!applyAndTest(head,parent,world,inverseGun,desired,right,forward,smoothedLift,smoothedRoll,shape,blockers))
            {
                lift=smoothedLift;roll=smoothedRoll;
            }
        }
        applyAndTest(head,parent,world,inverseGun,desired,right,forward,lift,roll,shape,blockers);
        if(rollSide==0&&Math.abs(roll)>1e-4F)rollSide=roll>0?1:-1;
        LAST.put(eva,new Correction(lift,roll,rollSide,time));
    }
}
