package com.projectseele.world;
import com.google.gson.*;
import com.projectseele.entity.SiloHatchMechanism;
import java.nio.file.*;
import java.util.*;
import net.minecraft.world.phys.*;
import org.joml.Quaternionf;

/** Actual triangles for the ten measured fixed intersections; never an exemption. */
public final class MeasureFixedLowerContactsR53
{
    private record Tri(int id,Vec3 a,Vec3 b,Vec3 c,AABB box){Vec3 normal(){return b.subtract(a).cross(c.subtract(a));}Vec3[] chord(){return new Vec3[]{a,b,c,a,b,c};}}
    private static List<Tri> tris(NervRigidMeshSweepR52 mesh,RigidTransform frame,AABB broad)
    {
        var out=new ArrayList<Tri>();var xyz=mesh.triangles();
        for(int i=0;i<xyz.length;i+=9){var a=frame.transformPoint(new Vec3(xyz[i],xyz[i+1],xyz[i+2]));var b=frame.transformPoint(new Vec3(xyz[i+3],xyz[i+4],xyz[i+5]));var c=frame.transformPoint(new Vec3(xyz[i+6],xyz[i+7],xyz[i+8]));var box=new AABB(a,a).minmax(new AABB(b,b)).minmax(new AABB(c,c));if(box.inflate(2e-7).intersects(broad))out.add(new Tri(i/9,a,b,c,box));}return out;
    }
    private static double[] ary(Vec3 p){return new double[]{p.x,p.y,p.z};}
    private static boolean inside(Vec3 p,Tri t,double margin)
    {
        var u=t.b().subtract(t.a());var v=t.c().subtract(t.a());var w=p.subtract(t.a());double uu=u.dot(u),uv=u.dot(v),vv=v.dot(v),wu=w.dot(u),wv=w.dot(v),d=uu*vv-uv*uv;
        if(Math.abs(d)<1e-25)return false;double a=(vv*wu-uv*wv)/d,b=(uu*wv-uv*wu)/d;return a>=margin&&b>=margin&&1-a-b>=margin;
    }
    private static void points(Tri a,Tri b,List<Vec3> out)
    {
        var n=b.normal().normalize();var q=new Vec3[]{a.a(),a.b(),a.c()};
        for(int i=0;i<3;i++){var p=q[i];var end=q[(i+1)%3];double x=p.subtract(b.a()).dot(n),y=end.subtract(b.a()).dot(n);
            if(Math.abs(x)<1e-8&&inside(p,b,-1e-7))out.add(p);
            if(x*y<0){var at=p.add(end.subtract(p).scale(x/(x-y)));if(inside(at,b,-1e-7))out.add(at);}}
    }
    public static void main(String[] args)throws Exception
    {
        var lowerRoot=RigidTransform.of(new Vec3(.5,-1062.96,328.5),new Quaternionf(0,1,0,0));var hatchRoot=RigidTransform.of(new Vec3(.5,-1062.99,328.5),new Quaternionf());
        var hatch=NervSiloHatchGeometryR52.loadClasspath(new SiloHatchMechanism.Spec(33,33,120,180,-1,-2.01,true));var result=new ArrayList<Object>();
        for(var lower:NervLowerFrameR52.pieces(0))if(lower.kind().equals("fixed"))for(var part:hatch.pieces(0))if(!part.moving())
        {
            var hm=new NervRigidMeshSweepR52(part.part().xyz());var lf=lowerRoot.compose(lower.local());var hf=hatchRoot.compose(part.local());
            if(!lower.mesh().intersects(lf,lf,hm,hf,hf,.003,Vec3.ZERO))continue;
            var lb=NervRigidMeshSweepR52.transformed(lower.mesh().bounds(),lf);var hb=NervRigidMeshSweepR52.transformed(hm.bounds(),hf);var aa=tris(lower.mesh(),lf,hb.inflate(2e-7));var bb=tris(hm,hf,lb.inflate(2e-7));var pairs=new ArrayList<Object>();var intersections=new ArrayList<Vec3>();int proper=0,coplanar=0;
            for(var a:aa)for(var b:bb)
            {
                if(!a.box().inflate(2e-7).intersects(b.box().inflate(2e-7))||!TriangleSweepMeshR52.convexSweepPair(a.chord(),b.chord(),Vec3.ZERO))continue;
                var points=new ArrayList<Vec3>();boolean flat=Math.abs(a.normal().normalize().dot(b.normal().normalize()))>1-1e-9;
                if(flat)coplanar++;else{points(a,b,points);points(b,a,points);}boolean crossing=false;
                for(var p:points)for(var q:points){var mid=p.add(q).scale(.5);if(p.distanceToSqr(q)>1e-14&&inside(mid,a,1e-7)&&inside(mid,b,1e-7))crossing=true;}
                if(crossing)proper++;intersections.addAll(points);
                pairs.add(Map.of("lower_triangle",a.id(),"hatch_triangle",b.id(),"lower_world_triangle",new double[][]{ary(a.a()),ary(a.b()),ary(a.c())},"hatch_world_triangle",new double[][]{ary(b.a()),ary(b.b()),ary(b.c())},"parallel_or_coplanar",flat,"proper_transverse_surface_crossing",crossing,"actual_intersection_points",points.stream().map(MeasureFixedLowerContactsR53::ary).toList()));
            }
            AABB ib=null;for(var p:intersections)ib=ib==null?new AABB(p,p):ib.minmax(new AABB(p,p));var row=new LinkedHashMap<String,Object>();row.put("lower_member",lower.name());row.put("hatch_member",part.part().name());row.put("declared_lower_joint",lower.declaration().has("joint")?lower.declaration().get("joint").getAsString():null);row.put("proper_transverse_triangle_pairs",proper);row.put("parallel_triangle_pairs",coplanar);row.put("triangle_pairs",pairs);row.put("canonical_intersection_point_bounds",ib==null?null:new double[]{ib.minX,ib.minY,ib.minZ,ib.maxX,ib.maxY,ib.maxZ});row.put("authorization","No automatic fixed-contact exemption. Proper transverse crossings prove interpenetrating mesh surfaces; Root must choose real joint/detail or relief.");result.add(row);
            System.out.println(lower.name()+" vs "+part.part().name()+" pairs="+pairs.size()+" proper="+proper+" parallel="+coplanar);
        }
        var output=new LinkedHashMap<String,Object>();output.put("world_written",false);output.put("game_started",false);output.put("lower_source_sha",NervLowerFrameR52.SOURCE_SHA);output.put("hatch_source_sha",NervSiloHatchGeometryR52.SOURCE_SHA);output.put("canonical_root_x",.5);output.put("world_variant_integer_x_offsets",new int[]{72,30,-12});output.put("fixed_pairs",result);
        Files.writeString(Path.of(args[0]),new GsonBuilder().setPrettyPrinting().create().toJson(output));
    }
}
