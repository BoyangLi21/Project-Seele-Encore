package com.projectseele.world;

import com.google.gson.*;
import java.util.*;
import net.minecraft.world.phys.*;
import org.joml.Quaternionf;

/** Production directory curve/BVH/finite chord proof, including coupled foot
 * rotation that endpoint root boxes miss. Synthetic values are math fixtures. */
public final class DirectoryTriangleSweepR52Test
{
    private static int checks;
    private static void check(boolean ok,String why){checks++;if(!ok)throw new AssertionError(why);}
    private static JsonArray q(Quaternionf q){var a=new JsonArray();for(float v:new float[]{q.x,q.y,q.z,q.w})a.add(v);return a;}
    private static JsonObject named(JsonArray values,String id){for(var v:values)if(v.getAsJsonObject().get("id").getAsString().equals(id))return v.getAsJsonObject();throw new AssertionError(id);}
    private static double[] box(AABB b)
    {
        var p=new Vec3[8];for(int i=0;i<8;i++)p[i]=new Vec3((i&1)==0?b.minX:b.maxX,(i&2)==0?b.minY:b.maxY,(i&4)==0?b.minZ:b.maxZ);
        int[][] faces={{0,1,3,2},{4,6,7,5},{0,4,5,1},{2,3,7,6},{0,2,6,4},{1,5,7,3}};double[] result=new double[108];int n=0;
        for(var f:faces)for(int c:new int[]{f[0],f[1],f[2],f[0],f[2],f[3]}){result[n++]=p[c].x;result[n++]=p[c].y;result[n++]=p[c].z;}return result;
    }
    public static void main(String[] args)
    {
        var json=NervRouteCoreR52Test.rootFixtureForNativeBindingTest();var added=named(json.getAsJsonArray("legs"),"original1").deepCopy();added.addProperty("id","proof_turn");added.addProperty("from","dock1_1");added.addProperty("to","dock1_1");added.addProperty("motion","FOOT_BEARING_TURN");added.add("eva_from_xyzw",q(new Quaternionf()));added.add("eva_to_xyzw",q(new Quaternionf().rotationX((float)Math.PI)));json.getAsJsonArray("legs").add(added);
        var endpoint=named(json.getAsJsonArray("nodes"),"dock1_1").deepCopy();endpoint.addProperty("id","compound_endpoint");endpoint.addProperty("role","PATH");var translation=new JsonArray();for(double v:new double[]{10,3,15})translation.add(v);endpoint.getAsJsonObject("foot_frame").add("translation",translation);endpoint.getAsJsonObject("foot_frame").add("quaternion_xyzw",q(new Quaternionf().rotationY(1.1F)));json.getAsJsonArray("nodes").add(endpoint);
        var compound=added.deepCopy();compound.addProperty("id","compound_incline");compound.addProperty("to","compound_endpoint");compound.addProperty("motion","LAUNCH_INCLINE");compound.add("eva_to_xyzw",q(new Quaternionf().rotationX(1.3F)));json.getAsJsonArray("legs").add(compound);
        var directory=NervRouteDirectoryR52.parse(json);var binding=new FootSupportFrameR52.Binding(new Vec3(-1,-2,1),new Vec3(1,-2,1),RigidTransform.identity());var curve=new DirectoryTrajectoryR52(directory,directory.leg("proof_turn"),binding,0,1);
        var mesh=new TriangleSweepMeshR52(new double[]{0,8,1,.1,8,1,0,8.1,1});var start=curve.sample(0).evaRoot();var end=curve.sample(1).evaRoot();var middle=curve.sample(.5).evaRoot();var sample=new Vec3(0,8,1);var actual=middle.transformPoint(sample);var naive=start.interpolate(end,.5).transformPoint(sample);
        check(actual.distanceTo(naive)>.5,"Fixture did not expose the foot-coupled root arc");var obstacle=new AABB(actual.add(-.05,-.05,-.05),actual.add(.05,.05,.05));check(mesh.intersects(curve,obstacle,.005),"Continuous actual curve missed a midpoint obstacle absent at endpoint roots");
        double radius=sample.distanceTo(binding.contactCentre());int n=curve.divisions(radius,.005);double error=curve.error(radius,n);check(error<=.005,"Certified chord error exceeded caller budget");
        for(int i=0;i<n;i++){var a=curve.sample((double)i/n).evaRoot().transformPoint(sample);var b=curve.sample((double)(i+1)/n).evaRoot().transformPoint(sample);for(int k=0;k<=20;k++){double f=k/20D;var p=curve.sample((i+f)/n).evaRoot().transformPoint(sample);check(p.distanceTo(a.lerp(b,f))<=error,"Actual foot-coupled intermediate point escaped certified chord bound");}}
        var combined=new DirectoryTrajectoryR52(directory,directory.leg("compound_incline"),binding,.13,.88);n=combined.divisions(radius,.005);error=combined.error(radius,n);for(int i=0;i<n;i++){var a=combined.sample((double)i/n).evaRoot().transformPoint(sample);var b=combined.sample((double)(i+1)/n).evaRoot().transformPoint(sample);for(int k=0;k<=20;k++){double f=k/20D;var p=combined.sample((i+f)/n).evaRoot().transformPoint(sample);check(p.distanceTo(a.lerp(b,f))<=error,"Compound real bearing yaw/relative pitch escaped certified curve bound");}}
        boolean rejected=false;try{curve.divisions(radius,curve.roundoffBound(radius)/2);}catch(IllegalArgumentException expected){rejected=true;}check(rejected,"Unachievable float error budget was accepted");
        Vec3[] chord={new Vec3(-2,0,-2),new Vec3(-2,2,-2),new Vec3(-2,0,2),new Vec3(2,0,-2),new Vec3(2,2,-2),new Vec3(2,0,2)};check(TriangleSweepMeshR52.convexSweepBox(chord,0,new AABB(-.1,.5,-.1,.1,.7,.1)),"Translation swept triangle prism missed an interior obstacle");check(!TriangleSweepMeshR52.convexSweepBox(chord,0,new AABB(5,5,5,6,6,6)),"Separated obstacle filled synthetic empty space");
        var straight=new DirectoryTrajectoryR52(directory,directory.leg("original1"),binding,0,1);check(straight.angularTravel()==0&&straight.roundoffBound(60)==0,"Fixed upright transfer invented angular clearance padding");
        check(mesh.intersects(curve,new NervRigidMeshSweepR52(box(obstacle)),RigidTransform.identity(),RigidTransform.identity(),.005),"Actual moving source pair missed the certified foot-coupled midpoint");
        // This triangle's whole arc is inside radius 10.1 around the bearing.
        // A coarse chord's padding reaches the nearby box; the source does not.
        var nearArc=new AABB(10.000009,11.082570271119964,10.609882237993512,10.000011,11.082572271119963,10.60988423799351);
        check(Math.hypot(nearArc.minY-1,nearArc.minZ-10)>10.1,"Near-arc negative fixture entered the true source radius");
        check(!mesh.intersects(curve,nearArc,.005),"Curve enclosure padding was treated as solid machinery");
        check(mesh.intersects(curve,nearArc.inflate(.01),.005),"Refining a near miss waived a real curved-path intrusion");
        var stopped=new DirectoryTrajectoryR52(directory,directory.leg("original1"),binding,0,0);var stoppedFrame=stopped.sample(0).evaRoot();
        var smallBody=new TriangleSweepMeshR52(box(new AABB(-.2,-.2,-.2,.2,.2,.2)));
        var frameBoxes=List.of(new AABB(-2,-2,-.5,-1,2,.5),new AABB(1,-2,-.5,2,2,.5),new AABB(-1,-2,-.5,1,-1,.5),new AABB(-1,1,-.5,1,2,.5));
        double[] frame=frameBoxes.stream().flatMapToDouble(b->Arrays.stream(box(b))).toArray();var hollow=new NervRigidMeshSweepR52(frame);
        check(smallBody.intersects(stopped,hollow.envelope(stoppedFrame,stoppedFrame),.005),"Hollow fixture failed to expose whole-bounding-box false positive");
        check(!smallBody.intersects(stopped,hollow,stoppedFrame,stoppedFrame,.005),"Actual open machinery cavity was filled by its actor box");
        check(smallBody.intersects(stopped,new NervRigidMeshSweepR52(box(new AABB(-.4,-.4,-.05,.4,.4,.05))),stoppedFrame,stoppedFrame,.005),"Real closed leaf crossing the same cavity was missed");
        var reused=smallBody.prepare(stopped,.005);
        for(int i=0;i<120;i++)
        {
            var centre=stoppedFrame.transformPoint(new Vec3(i%2==0?0:4,0,0));
            var movingObstacle=new AABB(centre.add(-.03,-.03,-.03),centre.add(.03,.03,.03));
            check(reused.intersects(movingObstacle)==(i%2==0),"Prepared source reused a previous live obstacle result");
            check(!reused.intersects(hollow,stoppedFrame,stoppedFrame),"Prepared bounds filled a hollow obstacle");
        }
        for(var path:List.of(curve,combined,straight,stopped))for(int i=0;i<=1000;i++)
        {
            double time=i/1000D;var direct=path.directory().sample(path.leg(),path.directory().intervalFraction(path.leg(),path.fromFraction(),path.toFraction(),time),path.binding());
            check(path.sample(time).equals(direct),"Reused source sample changed the actual directory transform");
        }
        System.out.println("R52 actual directory curve/triangle chord proof PASS checks="+checks+"; no native world acceptance");
    }
    private DirectoryTriangleSweepR52Test(){}
}
