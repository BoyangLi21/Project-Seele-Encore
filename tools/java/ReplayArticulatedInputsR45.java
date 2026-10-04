import com.google.gson.*;
import com.projectseele.physics.ArticulatedBody;
import org.joml.*;
import java.nio.file.*;
import java.util.*;

/** Replays an actual capture; optional omissions are diagnostic counterfactuals, never pass claims. */
public final class ReplayArticulatedInputsR45
{
    static void inspectInitial(ArticulatedBody body,JsonArray output)throws Exception
    {
        var field=ArticulatedBody.class.getDeclaredField("world");field.setAccessible(true);
        var world=(com.bulletphysics.dynamics.DiscreteDynamicsWorld)field.get(body);
        world.updateAabbs();world.performDiscreteCollisionDetection();
        var dispatcher=world.getDispatcher();
        for(int i=0;i<dispatcher.getNumManifolds();i++)
        {
            var contact=dispatcher.getManifoldByIndexInternal(i);
            var a=(com.bulletphysics.collision.dispatch.CollisionObject)contact.getBody0();var b=(com.bulletphysics.collision.dispatch.CollisionObject)contact.getBody1();
            for(int k=0;k<contact.getNumContacts();k++)
            {
                var point=contact.getContactPoint(k);if(point.getDistance()>=0)continue;
                JsonObject row=new JsonObject();row.addProperty("a",String.valueOf(a.getUserPointer()));row.addProperty("b",String.valueOf(b.getUserPointer()));row.addProperty("penetration_blocks",-point.getDistance()/.04F);output.add(row);
            }
        }
    }
    static void suppressSelf(ArticulatedBody body)throws Exception
    {
        var f=ArticulatedBody.class.getDeclaredField("world");f.setAccessible(true);var world=(com.bulletphysics.dynamics.DiscreteDynamicsWorld)f.get(body);
        var b=ArticulatedBody.class.getDeclaredField("bodies");b.setAccessible(true);
        for(Object value:((Map<?,?>)b.get(body)).values())
        {var rigid=(com.bulletphysics.dynamics.RigidBody)value;world.removeRigidBody(rigid);world.addRigidBody(rigid,(short)32,(short)(-1 ^ 32));}
    }
    static void inspectJoints(ArticulatedBody body,JsonArray output,boolean remove)throws Exception
    {
        var f=ArticulatedBody.class.getDeclaredField("world");f.setAccessible(true);var world=(com.bulletphysics.dynamics.DiscreteDynamicsWorld)f.get(body);
        var j=ArticulatedBody.class.getDeclaredField("joints");j.setAccessible(true);
        for(Object value:(List<?>)j.get(body))
        {
            var joint=(com.bulletphysics.dynamics.constraintsolver.TypedConstraint)value;
            if(remove){world.removeConstraint(joint);continue;}
            var row=new JsonObject();row.addProperty("parent",String.valueOf(joint.getRigidBodyA().getUserPointer()));row.addProperty("child",String.valueOf(joint.getRigidBodyB().getUserPointer()));
            joint.buildJacobian();
            if(joint instanceof com.bulletphysics.dynamics.constraintsolver.HingeConstraint hinge)
            {
                row.addProperty("hingeAngle",hinge.getHingeAngle());row.addProperty("lower",hinge.getLowerLimit());row.addProperty("upper",hinge.getUpperLimit());
                var a=joint.getRigidBodyA().getCenterOfMassTransform(new com.bulletphysics.linearmath.Transform());a.mul(hinge.getAFrame(new com.bulletphysics.linearmath.Transform()));
                var b=joint.getRigidBodyB().getCenterOfMassTransform(new com.bulletphysics.linearmath.Transform());b.mul(hinge.getBFrame(new com.bulletphysics.linearmath.Transform()));
                var x=new javax.vecmath.Vector3f();var y=new javax.vecmath.Vector3f();a.basis.getColumn(2,x);b.basis.getColumn(2,y);row.addProperty("hingeAxisDot",x.dot(y));
            }
            else if(joint instanceof com.bulletphysics.dynamics.constraintsolver.ConeTwistConstraint cone)
            {
                row.addProperty("swingLimit",cone.getSolveSwingLimit());row.addProperty("twistLimit",cone.getSolveTwistLimit());
                for(String n:new String[]{"swingCorrection","twistCorrection"}){var field=cone.getClass().getDeclaredField(n);field.setAccessible(true);row.addProperty(n,field.getFloat(cone));}
            }
            output.add(row);
        }
    }
    static void loosenAnkles(ArticulatedBody body)throws Exception
    {
        var f=ArticulatedBody.class.getDeclaredField("joints");f.setAccessible(true);
        for(Object value:(List<?>)f.get(body))if(value instanceof com.bulletphysics.dynamics.constraintsolver.ConeTwistConstraint cone
                &&String.valueOf(cone.getRigidBodyB().getUserPointer()).startsWith("foot_"))cone.setLimit(3.14F,3.14F,3.14F);
    }
    static Vector3f vector(JsonArray a){return new Vector3f(a.get(0).getAsFloat(),a.get(1).getAsFloat(),a.get(2).getAsFloat());}
    static Matrix4f matrix(JsonArray a){float[] f=new float[16];for(int i=0;i<16;i++)f[i]=a.get(i).getAsFloat();return new Matrix4f().set(f);}
    static Map<String,Matrix4f> matrices(JsonObject object)
    {Map<String,Matrix4f> result=new LinkedHashMap<>();object.entrySet().forEach(e->result.put(e.getKey(),matrix(e.getValue().getAsJsonArray())));return result;}
    public static void main(String[] args)throws Exception
    {
        String omit=args.length>2?args[2]:"";ArticulatedBody body=null;Map<String,JsonObject> definitions=new HashMap<>();
        JsonArray frames=new JsonArray(),initialContacts=new JsonArray(),initialJoints=new JsonArray();int steps=0;float error=0;
        try
        {
            for(String line:Files.readAllLines(Path.of(args[0])))
            {
                var row=JsonParser.parseString(line).getAsJsonObject();String op=row.get("op").getAsString();
                switch(op)
                {
                    case "create" -> body=new ArticulatedBody(row.getAsJsonObject("definition"),matrices(row.getAsJsonObject("pose")));
                    case "clearTerrain" -> {if(steps==0||!omit.contains("terrain_refresh"))body.clearTerrain();}
                    case "terrain" -> {if(steps==0||!omit.contains("terrain_refresh")){var q=row.getAsJsonArray("orientation");body.addStaticBox(vector(row.getAsJsonArray("centre")),vector(row.getAsJsonArray("half")),new Quaternionf(q.get(0).getAsFloat(),q.get(1).getAsFloat(),q.get(2).getAsFloat(),q.get(3).getAsFloat()));}}
                    case "velocity" -> body.velocity(vector(row.getAsJsonArray("value")));
                    case "motion" -> {if(!omit.contains("motion"))body.motionFromPose(matrices(row.getAsJsonObject("previous")),row.get("seconds").getAsFloat());}
                    case "controlledPose" -> body.controlledPose(matrices(row.getAsJsonObject("pose")));
                    case "impulse" -> {if(!omit.contains("impulse"))body.impulse(row.get("bone").getAsString(),vector(row.getAsJsonArray("point")),vector(row.getAsJsonArray("impulse")));}
                    case "actorDefinition" -> definitions.put(row.get("id").getAsString(),row.getAsJsonObject("definition"));
                    case "beginActors" -> body.beginActorFrame();
                    case "actor" -> {if(!omit.contains("actors")){String id=row.get("id").getAsString();body.actor(id,definitions.get(id),matrices(row.getAsJsonObject("pose")),matrix(row.getAsJsonArray("frame")));}}
                    case "endActors" -> body.endActorFrame();
                    case "step" -> {if(steps==0){if(omit.contains("self"))suppressSelf(body);if(omit.contains("ankles"))loosenAnkles(body);if(omit.contains("inspect")){inspectInitial(body,initialContacts);inspectJoints(body,initialJoints,false);}if(omit.contains("joints"))inspectJoints(body,initialJoints,true);}body.step(row.get("seconds").getAsFloat());steps++;}
                    case "frame" -> {
                        var frame=body.frame();var entry=new JsonObject();entry.addProperty("step",steps);entry.addProperty("min_y_blocks",frame.min().y/.04F);entry.addProperty("speed",frame.speed());entry.addProperty("contacts",frame.supportContacts());
                        float difference=frame.min().distance(vector(row.getAsJsonArray("min")));error=java.lang.Math.max(error,difference);entry.addProperty("capture_difference",difference);frames.add(entry);
                    }
                    default -> throw new IllegalArgumentException(op);
                }
            }
        }
        finally{if(body!=null)body.close();}
        JsonObject result=new JsonObject();result.addProperty("omitted_inputs",omit);result.addProperty("steps",steps);result.addProperty("max_capture_difference",error);result.add("frames",frames);result.add("diagnostic_initial_contacts",initialContacts);result.add("initial_joints",initialJoints);
        Files.writeString(Path.of(args[1]),new GsonBuilder().setPrettyPrinting().create().toJson(result));
        System.out.println("steps="+steps+" maxDifference="+error+" diagnosticOmissions="+omit);
    }
}
