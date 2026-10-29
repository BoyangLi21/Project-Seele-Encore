package com.projectseele.world;

import com.google.gson.JsonObject;
import com.projectseele.entity.YashimaCannonGeometryR52.Geometry;
import java.util.*;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.phys.*;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Two measured original gun contacts, one gun lift/AIM clock, one draw/proof geometry. */
public final class FixedCannonCradleR52
{
    public record Spec(double floorTop,double closedRootY,double raisedRootY)
    {
        public Spec{if(!Double.isFinite(floorTop+closedRootY+raisedRootY)||raisedRootY<=closedRootY||raisedRootY-closedRootY>16.5+.00001)throw new IllegalArgumentException("Explicit cradle floor and admitted six-stage stroke required");}
        public CompoundTag encode(){var t=new CompoundTag();t.putDouble("floor_top",floorTop);t.putDouble("closed_root_y",closedRootY);t.putDouble("raised_root_y",raisedRootY);return t;}
        public static Spec decode(CompoundTag t){if(!t.contains("floor_top")||!t.contains("closed_root_y")||!t.contains("raised_root_y"))throw new IllegalArgumentException("Synced installed cannon cradle required");return new Spec(t.getDouble("floor_top"),t.getDouble("closed_root_y"),t.getDouble("raised_root_y"));}
        public static Spec parse(JsonObject t){return new Spec(t.get("floor_top").getAsDouble(),t.get("closed_root_y").getAsDouble(),t.get("raised_root_y").getAsDouble());}
    }
    private record Source(NervAirframeGeometryR52.Part part,NervRigidMeshSweepR52 mesh){}
    public record Piece(NervAirframeGeometryR52.Part part,NervRigidMeshSweepR52 mesh,RigidTransform frame){}
    private record Contact(Vec3 local,Vec3 normal,Vec3 rest,Vec3 restNormal,double member,Source saddle,Source tube,Source rod){}
    private static final Map<Geometry,Map<Spec,Model>> MODELS=new WeakHashMap<>();
    private static synchronized Model model(Geometry g,Spec spec){return MODELS.computeIfAbsent(g,k->new HashMap<>()).computeIfAbsent(spec,k->new Model(g,spec));}
    private static final class Model
    {
        final Geometry gun;final Spec spec;final List<Contact> contacts;final Source plate,cylinder,crosshead,ball,rail,hanger;final List<Source> sleeves;final Vec3 cross;final double curveCoefficient;
        Model(Geometry g,Spec s)
        {
            gun=g;spec=s;var points=new ArrayList<Contact>();double coefficient=1;
            var pivot=g.point(Vec3.ZERO,new Quaternionf(),g.pivot());
            for(int index:new int[]{9023,986})
            {
                var tri=YashimaCannonMeshR52.sourceTriangleR52(index);var normal=YashimaCannonMeshR52.sourceNormalR52(index);var local=tri[0].add(tri[1]).add(tri[2]).scale(1D/3);var rest=g.point(Vec3.ZERO,new Quaternionf(),local);
                var restNormal=new Vec3(g.rotation().transform(normal.toVector3f())).normalize();var top=new Vec3[3];for(int i=0;i<3;i++)top[i]=local.add(tri[i].subtract(local).scale(.65)).scale(g.scale());
                double length=rest.add(restNormal.scale(.37)).add(0,s.closedRootY(),0).distanceTo(new Vec3(rest.x,s.floorTop()+3.75,rest.z)),member=length*.8;if(length<=.5)throw new IllegalArgumentException("Source contact cannot support the installed platform");
                points.add(new Contact(local,normal,rest,restNormal,member,prism("saddle_"+points.size(),top,normal,.12),beam("aim_outer_tube_"+points.size(),member,.28,12,.23),beam("aim_inner_rod_"+points.size(),member,.2,12,0)));
                // Endpoint rotates about the real gun pivot. Normalized strut
                // direction has bounded first/second derivatives while its
                // admitted span >= member+.15; this covers its true analytic
                // path beyond the canonical rigid chord's own rotation bound.
                double r=rest.subtract(pivot).length()+.37,min=member+.15;coefficient=Math.max(coefficient,r+member*(2*r/min+4*r*r/(min*min)));
            }
            contacts=List.copyOf(points);curveCoefficient=coefficient*4+1;
            plate=box("floor_plate",new Vec3(-1.5,0,-1.5),new Vec3(1.5,.3,1.5));cylinder=beam("outer_cylinder",2.9,1.25,16,1.19);crosshead=box("crosshead",new Vec3(-2,0,-2),new Vec3(2,.3,2));ball=sphere("ball_joint",.25);
            var sections=new ArrayList<Source>();for(int k=1;k<=6;k++){double r=1.25-k*.1;sections.add(beam("sleeve_"+k,2.9,r,16,r-.055));}sleeves=List.copyOf(sections);
            var d=contacts.get(1).rest.subtract(contacts.get(0).rest).multiply(1,0,1);cross=new Vec3(-d.z,0,d.x).normalize();rail=beam("platform_rail",d.length(),.2,8,0);hanger=beam("rail_hanger",2.2,.12,8,0);
        }
        List<Piece> pieces(Vec3 origin,Quaternionf aim)
        {return pieces(origin,aim,false);}
        List<Piece> pieces(Vec3 origin,Quaternionf aim,boolean strict)
        {
            double rise=origin.y-spec.closedRootY();if(strict&&(rise<-.01||rise>spec.raisedRootY()-spec.closedRootY()+.01))throw new IllegalArgumentException("Cannon cradle outside its actual lift stroke");
            var result=new ArrayList<Piece>();var m=gun.matrix(origin,aim);var gunFrame=RigidTransform.of(new Vec3(m.getTranslation(new Vector3f())),m.getUnnormalizedRotation(new Quaternionf()).normalize());
            for(int i=0;i<contacts.size();i++)
            {
                var c=contacts.get(i);var xz=new Vec3(origin.x+c.rest.x,0,origin.z+c.rest.z);add(result,c.saddle,gunFrame);
                add(result,plate,translation(xz.add(0,spec.floorTop(),0)));add(result,cylinder,translation(xz.add(0,spec.floorTop()+.3,0)));
                for(int k=1;k<=6;k++)add(result,sleeves.get(k-1),translation(xz.add(0,spec.floorTop()+.3+rise*k/6,0)));
                add(result,crosshead,translation(xz.add(0,spec.floorTop()+3.2+rise,0)));
                var base=xz.add(0,spec.floorTop()+3.75+rise,0);var normal=new Vec3(aim.transform(c.restNormal.toVector3f())).normalize();var end=gun.point(origin,aim,c.local).add(normal.scale(.37));var axis=end.subtract(base);double length=axis.length();
                // Normal aiming may overlap/extend the visual struts. Their
                // diagnostic stroke limit must never abort a server tick or draw.
                if(strict&&(2*c.member-length<.15||length<c.member+.15))throw new IllegalArgumentException("Real fixed cannon aim strut overlap/stroke exhausted");
                axis=length>1e-9?axis.scale(1/length):new Vec3(0,1,0);var rotation=new Quaternionf().rotationTo(new Vector3f(0,1,0),axis.toVector3f());
                add(result,c.tube,RigidTransform.of(base,rotation));add(result,c.rod,RigidTransform.of(end.subtract(axis.scale(c.member)),rotation));add(result,ball,translation(end));add(result,ball,translation(base));
            }
            for(int side:new int[]{-1,1})
            {
                var a=contacts.get(0).rest.multiply(1,0,1).add(cross.scale(1.7*side)).add(origin.x,spec.floorTop()+1+rise,origin.z);var b=contacts.get(1).rest.multiply(1,0,1).add(cross.scale(1.7*side)).add(origin.x,spec.floorTop()+1+rise,origin.z);
                add(result,rail,RigidTransform.of(a,new Quaternionf().rotationTo(new Vector3f(0,1,0),b.subtract(a).normalize().toVector3f())));add(result,hanger,translation(a));add(result,hanger,translation(b));
            }
            return List.copyOf(result);
        }
    }
    public static List<Piece> pieces(Geometry gun,Spec spec,Vec3 position,Quaternionf aim){return model(gun,spec).pieces(position,aim);}
    public static AABB bounds(Geometry gun,Spec spec,Vec3 position,Quaternionf aim){AABB all=null;for(var p:pieces(gun,spec,position,aim)){var b=NervRigidMeshSweepR52.transformed(p.mesh.bounds(),p.frame);all=all==null?b:all.minmax(b);}return all;}
    private record Interval(NervRigidMeshSweepR52 mesh,RigidTransform from,RigidTransform to,Vec3 curve,AABB box){}
    public static final class Sweep
    {
        private final List<Interval> intervals;private final AABB bounds;
        private Sweep(Geometry gun,Spec spec,Vec3 from,Vec3 to,Quaternionf a,Quaternionf b)
        {
            var model=model(gun,spec);double angle=2*Math.acos(Math.min(1,Math.abs(a.dot(b))));int divisions=Math.max(1,(int)Math.ceil(angle*Math.sqrt(model.curveCoefficient/(8*.0005))));if(divisions>4096)throw new IllegalStateException("Actual aim curve subdivision exceeded");
            var out=new ArrayList<Interval>();AABB all=null;double error=model.curveCoefficient*angle*angle/(8D*divisions*divisions)+.000002;var curve=new Vec3(error,error,error);
            for(int i=0;i<divisions;i++)
            {
                float x=i/(float)divisions,y=(i+1)/(float)divisions;var A=model.pieces(from.lerp(to,x),new Quaternionf(a).slerp(b,x),true);var B=model.pieces(from.lerp(to,y),new Quaternionf(a).slerp(b,y),true);
                for(int j=0;j<A.size();j++){var p=A.get(j);var q=B.get(j);var box=p.mesh.envelope(p.frame,q.frame).inflate(error);out.add(new Interval(p.mesh,p.frame,q.frame,curve,box));all=all==null?box:all.minmax(box);}
            }
            intervals=List.copyOf(out);bounds=all;
        }
        public AABB bounds(){return bounds;}
        public List<AABB> envelopes(){return intervals.stream().map(Interval::box).toList();}
        public boolean intersects(AABB obstacle){for(var p:intervals)if(p.box.intersects(obstacle)&&p.mesh.intersects(p.from,p.to,obstacle.inflate(p.curve.x,p.curve.y,p.curve.z),.001))return true;return false;}
        public boolean intersects(NervRigidMeshSweepR52 other,RigidTransform frame){for(var p:intervals)if(p.mesh.intersects(p.from,p.to,other,frame,frame,.001,p.curve))return true;return false;}
    }
    public static Sweep sweep(Geometry gun,Spec spec,Vec3 from,Vec3 to,Quaternionf a,Quaternionf b){return new Sweep(gun,spec,from,to,a,b);}
    private static RigidTransform translation(Vec3 p){return RigidTransform.of(p,new Quaternionf());}
    private static void add(List<Piece> out,Source s,RigidTransform f){out.add(new Piece(s.part,s.mesh,f));}
    private static Source source(String name,List<Vec3> triangles,boolean contact)
    {var v=new double[triangles.size()*6];for(int i=0;i<triangles.size();i++){var p=triangles.get(i);int n=i*6;v[n]=p.x;v[n+1]=p.y;v[n+2]=p.z;v[n+3]=contact?166:71;v[n+4]=contact?97:117;v[n+5]=contact?31:125;}var part=new NervAirframeGeometryR52.Part(name,v);return new Source(part,new NervRigidMeshSweepR52(part.xyz()));}
    private static void triangle(List<Vec3> v,Vec3 a,Vec3 b,Vec3 c){if(b.subtract(a).cross(c.subtract(a)).lengthSqr()>1e-20){v.add(a);v.add(b);v.add(c);}}
    private static void reverse(List<Vec3> v){for(int i=0;i<v.size();i+=3){var b=v.get(i+1);v.set(i+1,v.get(i+2));v.set(i+2,b);}}
    private static Source box(String name,Vec3 lo,Vec3 hi)
    {var p=new Vec3[]{lo,new Vec3(hi.x,lo.y,lo.z),new Vec3(hi.x,hi.y,lo.z),new Vec3(lo.x,hi.y,lo.z),new Vec3(lo.x,lo.y,hi.z),new Vec3(hi.x,lo.y,hi.z),hi,new Vec3(lo.x,hi.y,hi.z)};var v=new ArrayList<Vec3>();for(int i:new int[]{0,1,2,0,2,3,4,6,5,4,7,6,0,4,5,0,5,1,1,5,6,1,6,2,2,6,7,2,7,3,3,7,4,3,4,0})v.add(p[i]);reverse(v);return source(name,v,false);}
    private static Source prism(String name,Vec3[] p,Vec3 normal,double depth)
    {var b=new Vec3[3];for(int i=0;i<3;i++)b[i]=p[i].add(normal.scale(depth));var v=new ArrayList<Vec3>();triangle(v,p[0],p[1],p[2]);triangle(v,b[2],b[1],b[0]);for(int i=0;i<3;i++){int j=(i+1)%3;triangle(v,p[i],b[i],p[j]);triangle(v,p[j],b[i],b[j]);}if(p[1].subtract(p[0]).cross(p[2].subtract(p[0])).dot(normal)>0)reverse(v);return source(name,v,true);}
    private static Source beam(String name,double length,double radius,int sides,double inner)
    {
        var v=new ArrayList<Vec3>();for(int i=0;i<sides;i++){double a=i*Math.PI*2/sides,b=(i+1)*Math.PI*2/sides;var p=new Vec3(Math.cos(a)*radius,0,Math.sin(a)*radius);var q=new Vec3(Math.cos(b)*radius,0,Math.sin(b)*radius);var r=p.add(0,length,0);var s=q.add(0,length,0);triangle(v,p,q,r);triangle(v,q,s,r);
            if(inner>0){var P=p.scale(inner/radius);var Q=q.scale(inner/radius);var R=P.add(0,length,0);var S=Q.add(0,length,0);triangle(v,P,R,Q);triangle(v,Q,R,S);triangle(v,p,P,q);triangle(v,q,P,Q);triangle(v,r,s,R);triangle(v,s,S,R);}else{triangle(v,Vec3.ZERO,q,p);triangle(v,new Vec3(0,length,0),r,s);}}
        reverse(v);return source(name,v,false);
    }
    private static Source sphere(String name,double radius)
    {var v=new ArrayList<Vec3>();for(int i=0;i<8;i++)for(int j=0;j<16;j++){var a=spherePoint(i,j,radius);var b=spherePoint(i+1,j,radius);var c=spherePoint(i,j+1,radius);var d=spherePoint(i+1,j+1,radius);triangle(v,a,b,c);triangle(v,c,b,d);}reverse(v);return source(name,v,false);}
    private static Vec3 spherePoint(int i,int j,double radius){double a=Math.PI*i/8,b=Math.PI*j/8;return new Vec3(Math.sin(a)*Math.cos(b)*radius,Math.cos(a)*radius,Math.sin(a)*Math.sin(b)*radius);}
    private FixedCannonCradleR52(){}
}
