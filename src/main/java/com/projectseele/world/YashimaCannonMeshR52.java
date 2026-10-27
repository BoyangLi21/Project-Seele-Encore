package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.entity.*;
import java.util.*;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.phys.*;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Complete original gun and current selected EVA skin. Empty space in a long barrel's broadphase is not a solid. */
public final class YashimaCannonMeshR52
{
    private record Source(String sha,double[] triangles,List<Vec3> normals,AABB bounds){}
    private record Body(long tick,String source,List<NervRigidMeshSweepR52> parts,List<NervRigidMeshSweepR52> complete){}
    private static volatile Source source;
    private static final Map<Float,NervRigidMeshSweepR52> GUNS=new HashMap<>();
    private static final Map<Vec3,Vec3> NORMALS=new java.util.concurrent.ConcurrentHashMap<>();
    private static final com.projectseele.util.WeakIdentityMap<EvaUnit01Entity,Body> BODIES=new com.projectseele.util.WeakIdentityMap<>();
    private static synchronized Source source()
    {
        if(source!=null)return source;
        try
        {
            byte[] bytes=EvaOriginalMeshGeometryR52.classpathBytes("mesh/positron_cannon_payload_r50.mesh.json");
            String sha=HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(bytes));
            var root=JsonParser.parseString(new String(bytes,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();int stride=root.get("stride").getAsInt();
            var points=new ArrayList<Vec3>();var normals=new ArrayList<Vec3>();AABB raw=null;
            for(var entry:root.getAsJsonObject("parts").entrySet())
            {
                var part=entry.getValue().getAsJsonObject();var pivot=YashimaCannonGeometryR52.vector(part.getAsJsonArray("pivot"));var vertices=part.getAsJsonArray("vertices");
                if(stride<3||vertices.size()%stride!=0||vertices.size()/stride%3!=0)throw new IllegalArgumentException("Complete original cannon triangles required");
                for(int i=0;i<vertices.size();i+=stride)
                {var p=new Vec3(vertices.get(i).getAsDouble(),vertices.get(i+1).getAsDouble(),vertices.get(i+2).getAsDouble()).add(pivot);points.add(p);raw=raw==null?new AABB(p,p):raw.minmax(new AABB(p,p));}
                if(stride<8)throw new IllegalArgumentException("Original cannon surface normals required");
                for(int i=0;i<vertices.size();i+=stride*3)normals.add(new Vec3(-vertices.get(i+5).getAsDouble(),vertices.get(i+6).getAsDouble(),vertices.get(i+7).getAsDouble()).normalize());
            }
            var centre=raw.getCenter();double[] triangles=new double[points.size()*3];AABB bounds=null;int n=0;
            for(var p:points)
            {p=new Vec3(-(p.x-centre.x)/16,(p.y-raw.minY)/16,(p.z-centre.z)/16);triangles[n++]=p.x;triangles[n++]=p.y;triangles[n++]=p.z;bounds=bounds==null?new AABB(p,p):bounds.minmax(new AABB(p,p));}
            source=new Source(sha,triangles,List.copyOf(normals),bounds);return source;
        }
        catch(Exception error){throw new IllegalStateException("Original fixed cannon source unavailable",error);}
    }
    public static void requireOriginal(JsonObject manifest,YashimaCannonGeometryR52.Geometry geometry)
    {
        var original=source();String declared=manifest.get("source_mesh_sha256").getAsString();var b=geometry.bounds();var a=original.bounds();
        if(!original.sha().equals(declared)||new Vec3(a.minX,a.minY,a.minZ).distanceTo(new Vec3(b.minX,b.minY,b.minZ))>.00001
                ||new Vec3(a.maxX,a.maxY,a.maxZ).distanceTo(new Vec3(b.maxX,b.maxY,b.maxZ))>.00001
                ||geometry.bore().distanceTo(new Vec3(0,-1,0))>.00001)throw new IllegalArgumentException("Fixed gun must use complete unchanged original source and barrel axis");
        // Muzzle is the area centroid of the twelve coplanar original barrel
        // end faces; an open barrel's centroid can lie inside the aperture.
        if(geometry.muzzle().distanceTo(new Vec3(-.08035911122,.0764567931,-.20946485753))>.0001)
            throw new IllegalArgumentException("Actual original barrel aperture required");
        for(var marker:List.of(geometry.pivot(),geometry.left(),geometry.right()))
            if(surfaceDistanceSquared(marker,original.triangles())>1e-8)throw new IllegalArgumentException("Fixed cannon marker is not on its actual original triangles");
    }
    private static double surfaceDistanceSquared(Vec3 p,double[] triangles)
    {return surface(p,triangles)[0];}
    public static Vec3 normalR52(Vec3 marker)
    {return NORMALS.computeIfAbsent(marker,p->{var s=source();var found=surface(p,s.triangles());if(found[0]>1e-8)throw new IllegalArgumentException("Original grip surface normal unavailable");return s.normals().get((int)found[1]);});}
    /** Pilot interaction picks the actual original surface, beyond a human hand's vanilla reach. */
    public static Vec3 rayHitR52(YashimaCannonEntityR52 actor,Vec3 start,Vec3 end)
    {
        var geometry=actor.geometryR52();if(geometry==null)return null;var matrix=geometry.matrix(actor.position(),actor.aimR52(1));var inverse=new org.joml.Matrix4f(matrix).invert();
        var a=new Vec3(inverse.transformPosition(start.toVector3f()));var d=new Vec3(inverse.transformPosition(end.toVector3f())).subtract(a);double nearest=Double.POSITIVE_INFINITY;var points=source().triangles();
        for(int i=0;i<points.length;i+=9)
        {
            var p=new Vec3(points[i],points[i+1],points[i+2]);var ab=new Vec3(points[i+3],points[i+4],points[i+5]).subtract(p);var ac=new Vec3(points[i+6],points[i+7],points[i+8]).subtract(p);var cross=d.cross(ac);double determinant=ab.dot(cross);
            if(Math.abs(determinant)<1e-12)continue;var offset=a.subtract(p);double u=offset.dot(cross)/determinant;if(u<0||u>1)continue;var q=offset.cross(ab);double v=d.dot(q)/determinant;if(v<0||u+v>1)continue;
            double t=ac.dot(q)/determinant;if(t>=0&&t<=1)nearest=Math.min(nearest,t);
        }
        return Double.isFinite(nearest)?new Vec3(matrix.transformPosition(a.add(d.scale(nearest)).toVector3f())):null;
    }
    private static double[] surface(Vec3 p,double[] triangles)
    {
        double best=Double.POSITIVE_INFINITY;int index=-1;
        for(int i=0;i<triangles.length;i+=9)
        {
            var a=new Vec3(triangles[i],triangles[i+1],triangles[i+2]);var b=new Vec3(triangles[i+3],triangles[i+4],triangles[i+5]);var c=new Vec3(triangles[i+6],triangles[i+7],triangles[i+8]);
            var ab=b.subtract(a);var ac=c.subtract(a);var normal=ab.cross(ac);if(normal.lengthSqr()<1e-20)continue;
            var projected=p.subtract(normal.scale(p.subtract(a).dot(normal)/normal.lengthSqr()));var ap=projected.subtract(a);
            double aa=ab.lengthSqr(),bb=ab.dot(ac),cc=ac.lengthSqr(),dd=ap.dot(ab),ee=ap.dot(ac),det=aa*cc-bb*bb;
            double v=(dd*cc-ee*bb)/det,w=(ee*aa-dd*bb)/det;
            double distance=v>=0&&w>=0&&v+w<=1?p.distanceToSqr(projected):Double.POSITIVE_INFINITY;
            for(var pair:List.of(new Vec3[]{a,b},new Vec3[]{b,c},new Vec3[]{c,a}))
            {var d=pair[1].subtract(pair[0]);double t=Math.max(0,Math.min(1,p.subtract(pair[0]).dot(d)/d.lengthSqr()));distance=Math.min(distance,p.distanceToSqr(pair[0].add(d.scale(t))));}
            if(distance<best){best=distance;index=i/9;}
        }
        return new double[]{best,index};
    }
    private static synchronized NervRigidMeshSweepR52 gun(float scale)
    {return GUNS.computeIfAbsent(scale,s->{var vertices=source().triangles().clone();for(int i=0;i<vertices.length;i++)vertices[i]*=s;return new NervRigidMeshSweepR52(vertices);});}
    public static Vec3[] sourceTriangleR52(int index)
    {var xyz=source().triangles();if(index<0||index*9+8>=xyz.length)throw new IllegalArgumentException("Actual original cannon face required");int n=index*9;return new Vec3[]{new Vec3(xyz[n],xyz[n+1],xyz[n+2]),new Vec3(xyz[n+3],xyz[n+4],xyz[n+5]),new Vec3(xyz[n+6],xyz[n+7],xyz[n+8])};}
    public static Vec3 sourceNormalR52(int index){return source().normals().get(index);}
    /** Exactly the visible original gun and its source cradle for native doors/carriers. */
    public static List<NervFlightProofR52.ObstacleMesh> actualObstacleMeshesR52(YashimaCannonEntityR52 actor)
    {
        try
        {
        var geometry=actor.geometryR52();var spec=actor.cradleR52();if(geometry==null||spec==null)return null;var result=new ArrayList<NervFlightProofR52.ObstacleMesh>();
        if(actor.loadedR52())result.add(new NervFlightProofR52.ObstacleMesh(gun(geometry.scale()),frame(geometry,actor.position(),actor.aimR52(1))));
        for(var part:FixedCannonCradleR52.pieces(geometry,spec,actor.position(),actor.aimR52(1)))result.add(new NervFlightProofR52.ObstacleMesh(part.mesh(),part.frame()));return List.copyOf(result);
        }
        catch(RuntimeException unavailable){return null;}
    }
    private static RigidTransform frame(YashimaCannonGeometryR52.Geometry geometry,Vec3 position,Quaternionf aim)
    {var m=geometry.matrix(position,aim);return RigidTransform.of(new Vec3(m.getTranslation(new Vector3f())),m.getUnnormalizedRotation(new Quaternionf()).normalize());}
    private static Body body(EvaUnit01Entity eva)
    {
        if(!eva.isPoweredOn()||eva.isBerserk()||eva.isFirstBattleActive()||EvaAirTransportR31.active(eva)||EvaDorsalMechanism.open(eva)>.0001F
                ||EvaDorsalMechanism.bow(eva)>.0001F||EvaBerserkMotionR34.mouth(eva,1)!=0)throw new IllegalStateException("Original closed powered fixed-gun operator required");
        var provider=EvaOriginalMeshGeometryR52.readOnlySelectedProviderR52();
        if(!provider.handContractFingerprint(eva.getUnitVariant()).equals(EvaAnatomicalHandsR45.contractFingerprintR45(eva.getUnitVariant())))throw new IllegalStateException("Fixed gun actual hand source differs from rendered source");
        var cached=BODIES.get(eva);long tick=eva.level().getGameTime();if(cached!=null&&cached.tick()==tick&&cached.source().equals(provider.sourceFingerprint()))return cached;
        var pose=EvaBodyPose.sample(eva,0);var actual=provider.evaluate(eva.getUnitVariant(),pose,EvaAnatomicalHandsR45.sample(eva,0));var meshes=new ArrayList<NervRigidMeshSweepR52>();var complete=new ArrayList<NervRigidMeshSweepR52>();
        for(var part:actual.parts()){var mesh=new NervRigidMeshSweepR52(part.triangles());complete.add(mesh);if(!Set.of("hand_l","hand_r","wrist_l","wrist_r").contains(part.bone()))meshes.add(mesh);}
        cached=new Body(tick,provider.sourceFingerprint(),List.copyOf(meshes),List.copyOf(complete));BODIES.put(eva,cached);return cached;
    }
    static boolean clearHatchR54(YashimaCannonEntityR52 actor,NervSiloDoorEntity hatch,float from,float to)
    {
        var geometry=actor.geometryR52();var spec=actor.cradleR52();if(geometry==null||spec==null)return false;
        var aim=actor.aimR52(1);var gunFrame=frame(geometry,actor.position(),aim);
        var source=hatch.declaredGeometryR52();var frame=hatch.actualFrameR52();
        if(source.intersects(frame,from,to,gun(geometry.scale()),gunFrame,gunFrame))return false;
        for(var piece:FixedCannonCradleR52.pieces(geometry,spec,actor.position(),aim))
            if(source.intersects(frame,from,to,piece.mesh(),piece.frame(),piece.frame()))return false;
        return true;
    }
    public static boolean clear(ServerLevel level,YashimaCannonEntityR52 actor,Vec3 proposed,Quaternionf aim)
    {
        try
        {
            var geometry=actor.geometryR52();var spec=actor.cradleR52();if(geometry==null||spec==null)return false;var mesh=gun(geometry.scale());
            var from=frame(geometry,actor.position(),actor.aimR52(1));var to=frame(geometry,proposed,aim);var cradle=FixedCannonCradleR52.sweep(geometry,spec,actor.position(),proposed,actor.aimR52(1),aim);var broad=mesh.envelope(from,to).minmax(cradle.bounds());
            for(var shape:level.getBlockCollisions(actor,broad))for(var obstacle:shape.toAabbs())if(mesh.intersects(from,to,obstacle.deflate(.001),.001)||cradle.intersects(obstacle.deflate(.001)))return false;
            var holder=TvYashimaStationR52.boundEva(level,actor);
            if(holder!=null)
            {
                var world=RigidTransform.of(holder.position(),new Quaternionf().rotationY((180-holder.getYRot())*(float)Math.PI/180));
                for(var part:body(holder).parts())if(mesh.intersects(from,to,part,world,world,.001,Vec3.ZERO))return false;
                for(var part:body(holder).complete())if(cradle.intersects(part,world))return false;
            }
            for(var entity:level.getEntities(actor,broad,e->e.isAlive()&&e instanceof LivingEntity&&e!=holder
                    &&(holder==null||!e.isPassengerOfSameVehicle(holder))))if(mesh.intersects(from,to,entity.getBoundingBox().deflate(.001),.001)||cradle.intersects(entity.getBoundingBox().deflate(.001)))return false;
            // The actual hatch shell and its stacked panels are entity source
            // geometry; an open controlled block mask does not remove them.
            for(var hatch:level.getEntitiesOfClass(NervSiloDoorEntity.class,broad))
            {var actual=NervFlightProofR52.actualObstacleMeshes(hatch);if(actual==null||actual.isEmpty())return false;for(var p:actual)if(mesh.intersects(from,to,p.mesh(),p.frame(),p.endFrame(),.001,Vec3.ZERO)||cradle.intersects(p.mesh(),p.frame()))return false;}
            actor.getPersistentData().remove("FixedCannonCollisionHoldR52");return true;
        }
        catch(RuntimeException error)
        {actor.getPersistentData().putString("FixedCannonCollisionHoldR52",error.getMessage()==null?error.getClass().getSimpleName():error.getMessage());return false;}
    }
    private YashimaCannonMeshR52(){}
}
