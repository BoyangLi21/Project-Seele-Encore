package com.projectseele.physics;

import com.bulletphysics.collision.broadphase.DbvtBroadphase;
import com.bulletphysics.collision.dispatch.*;
import com.bulletphysics.collision.shapes.*;
import com.bulletphysics.dynamics.*;
import com.bulletphysics.dynamics.constraintsolver.*;
import com.bulletphysics.linearmath.*;
import com.google.gson.*;
import javax.vecmath.*;
import java.util.*;

/** A rebased articulated body. Minecraft supplies static collision geometry and impulses. */
public final class ArticulatedBody implements AutoCloseable
{
    public record Frame(Map<String,org.joml.Matrix4f> deformation,org.joml.Vector3f min,org.joml.Vector3f max,float speed,int supportContacts,float groundImpulse,org.joml.Vector3f impactPoint) {}
    private final CollisionDispatcher dispatcher;
    private final DiscreteDynamicsWorld world;
    private final Map<String,RigidBody> bodies=new LinkedHashMap<>();
    private final Map<String,Transform> binds=new LinkedHashMap<>();
    private final Map<String,List<Vector3f>> surfaceVertices=new HashMap<>();
    private final List<TypedConstraint> joints=new ArrayList<>();
    private final List<RigidBody> scenery=new ArrayList<>();
    private record TerrainSurface(Transform inverse,Vector3f half,Vector3f low,Vector3f high) {}
    private final List<TerrainSurface> surfaces=new ArrayList<>();
    private final Map<String,RigidBody> actors=new HashMap<>();
    private final Set<String> actorFrame=new HashSet<>();
    private boolean closed;
    private final ArticulatedInputTraceR45 trace=new ArticulatedInputTraceR45();
    private final Set<String> tracedActors=new HashSet<>();

    private static Transform transform(JsonArray values)
    {float[] a=new float[16];for(int i=0;i<16;i++)a[i]=values.get(i).getAsFloat();return new Transform(new Matrix4f(a));}
    private static Transform transform(org.joml.Matrix4f m)
    {return new Transform(new Matrix4f(m.m00(),m.m10(),m.m20(),m.m30(),m.m01(),m.m11(),m.m21(),m.m31(),m.m02(),m.m12(),m.m22(),m.m32(),m.m03(),m.m13(),m.m23(),m.m33()));}
    private static org.joml.Matrix4f matrix(Transform transform)
    {Matrix4f m=transform.getMatrix(new Matrix4f());return new org.joml.Matrix4f(m.m00,m.m10,m.m20,m.m30,m.m01,m.m11,m.m21,m.m31,m.m02,m.m12,m.m22,m.m32,m.m03,m.m13,m.m23,m.m33);}
    private static Vector3f vector(JsonArray a){return new Vector3f(a.get(0).getAsFloat(),a.get(1).getAsFloat(),a.get(2).getAsFloat());}
    private RigidBody makeBody(float mass,CollisionShape shape,Transform at)
    {
        shape.setMargin(.004F);Vector3f inertia=new Vector3f();if(mass>0)shape.calculateLocalInertia(mass,inertia);
        var info=new RigidBodyConstructionInfo(mass,new DefaultMotionState(at),shape,inertia);
        info.friction=.85F;info.restitution=0;info.linearDamping=.10F;info.angularDamping=.68F;
        RigidBody body=new RigidBody(info);world.addRigidBody(body);return body;
    }
    public ArticulatedBody(JsonObject definition,Map<String,org.joml.Matrix4f> initialDeformation)
    {
        trace.event("create","definition",definition,"pose",initialDeformation);
        var configuration=new DefaultCollisionConfiguration();dispatcher=new CollisionDispatcher(configuration);
        world=new DiscreteDynamicsWorld(dispatcher,new DbvtBroadphase(),new SequentialImpulseConstraintSolver(),configuration);
        world.setGravity(new Vector3f(0,-9.81F,0));world.getSolverInfo().numIterations=30;
        // Separating an overlap with an animated opponent must not become
        // launch velocity that drives a connected limb through a thin floor.
        world.getSolverInfo().splitImpulse=true;world.getSolverInfo().splitImpulsePenetrationThreshold=-.003F;
        for(var element:definition.getAsJsonArray("bodies"))
        {
            var row=element.getAsJsonObject();String name=row.get("name").getAsString();var dimensions=row.getAsJsonArray("size");
            CollisionShape shape=row.get("shape").getAsString().equals("box")?new BoxShape(vector(dimensions)):new CapsuleShape(dimensions.get(0).getAsFloat(),Math.max(.01F,dimensions.get(1).getAsFloat()));
            if(row.has("hulls")&&!row.getAsJsonArray("hulls").isEmpty())
            {
                List<Vector3f> surface=new ArrayList<>();
                var envelope=new com.bulletphysics.util.ObjectArrayList<Vector3f>();
                for(var hull:row.getAsJsonArray("hulls"))
                {
                    for(var point:hull.getAsJsonArray()){var vertex=vector(point.getAsJsonArray());envelope.add(vertex);surface.add(vertex);}
                }
                // JBullet's CCD path explicitly skips CompoundShape. A rigid
                // anatomical segment uses its convex envelope so fast falls
                // cannot tunnel through thin Minecraft floors. Hit queries
                // still use the original separate armor hull planes.
                shape=new ConvexHullShape(envelope);
                surfaceVertices.put(name,List.copyOf(surface));
            }
            var bind=transform(row.getAsJsonArray("bind"));binds.put(name,bind);
            var body=makeBody(row.get("mass").getAsFloat(),shape,bind);body.setUserPointer(name);body.setActivationState(4);body.setCcdMotionThreshold(.03F);body.setCcdSweptSphereRadius(.025F);bodies.put(name,body);
        }
        for(var element:definition.getAsJsonArray("bodies"))
        {
            var row=element.getAsJsonObject();if(row.get("parent").isJsonNull())continue;
            String name=row.get("name").getAsString(),parent=row.get("parent").getAsString();Transform joint=transform(row.getAsJsonArray("joint"));
            Transform frameA=new Transform(binds.get(parent));frameA.inverse();frameA.mul(joint);Transform frameB=new Transform(binds.get(name));frameB.inverse();frameB.mul(joint);
            TypedConstraint constraint;
            if(row.has("hinge"))
            {
                var hinge=new HingeConstraint(bodies.get(parent),bodies.get(name),frameA,frameB);var limit=row.getAsJsonArray("hinge");
                // JBullet's frame-B convention reverses the authored flexion sign.
                hinge.setLimit(-limit.get(1).getAsFloat(),-limit.get(0).getAsFloat(),.9F,.3F,1);constraint=hinge;
            }
            else
            {
                var cone=new AngularConeConstraintR45(bodies.get(parent),bodies.get(name),frameA,frameB);var limit=row.getAsJsonArray("cone");
                cone.setLimit(limit.get(0).getAsFloat(),limit.get(1).getAsFloat(),limit.get(2).getAsFloat());constraint=cone;
            }
            world.addConstraint(constraint,true);joints.add(constraint);
        }
        for(var entry:bodies.entrySet())
        {
            var deformation=initialDeformation.get(entry.getKey());if(deformation==null)throw new IllegalArgumentException("Missing physical bone "+entry.getKey());
            Transform pose=transform(deformation);pose.mul(binds.get(entry.getKey()));RigidBody body=entry.getValue();
            body.setCenterOfMassTransform(pose);body.setInterpolationWorldTransform(pose);body.getMotionState().setWorldTransform(pose);
        }
    }
    public void addStaticBox(org.joml.Vector3f centre,org.joml.Vector3f halfSize,org.joml.Quaternionf orientation)
    {
        trace.event("terrain","centre",centre,"half",halfSize,"orientation",orientation);
        Transform pose=new Transform();pose.setIdentity();pose.origin.set(centre.x,centre.y,centre.z);pose.setRotation(new Quat4f(orientation.x,orientation.y,orientation.z,orientation.w));
        var body=makeBody(0,new BoxShape(new Vector3f(halfSize.x,halfSize.y,halfSize.z)),pose);body.setUserPointer("terrain");scenery.add(body);
        if(Math.abs(orientation.x)<1e-5F&&Math.abs(orientation.z)<1e-5F){Transform inverse=new Transform(pose);inverse.inverse();Vector3f low=new Vector3f(),high=new Vector3f();body.getAabb(low,high);surfaces.add(new TerrainSurface(inverse,new Vector3f(halfSize.x,halfSize.y,halfSize.z),low,high));}
    }
    public void clearTerrain()
    {trace.event("clearTerrain");for(var body:scenery)world.removeRigidBody(body);scenery.clear();surfaces.clear();}
    public void beginActorFrame(){trace.event("beginActors");actorFrame.clear();}
    public void actor(String id,JsonObject definition,Map<String,org.joml.Matrix4f> deformation,org.joml.Matrix4f frame)
    {
        if(tracedActors.add(id))trace.event("actorDefinition","id",id,"definition",definition);
        trace.event("actor","id",id,"pose",deformation,"frame",frame);
        for(var element:definition.getAsJsonArray("bodies"))
        {
            var row=element.getAsJsonObject();String name=row.get("name").getAsString();
            if(!name.startsWith("torso_")&&!name.startsWith("leg_")&&!name.startsWith("shin_")&&!name.equals("head"))continue;
            String key=id+":"+name;actorFrame.add(key);Transform at=transform(new org.joml.Matrix4f(frame).mul(deformation.get(name)));at.mul(transform(row.getAsJsonArray("bind")));
            var body=actors.get(key);
            if(body==null)
            {
                var shape=new CompoundShape();var identity=new Transform();identity.setIdentity();
                for(var hull:row.getAsJsonArray("hulls"))
                {
                    var points=new com.bulletphysics.util.ObjectArrayList<Vector3f>();for(var vertex:hull.getAsJsonArray())points.add(vector(vertex.getAsJsonArray()));
                    var convex=new ConvexHullShape(points);convex.setMargin(.003F);shape.addChildShape(identity,convex);
                }
                body=makeBody(0,shape,at);world.removeRigidBody(body);
                body.setCollisionFlags((body.getCollisionFlags()&~CollisionFlags.STATIC_OBJECT)|CollisionFlags.KINEMATIC_OBJECT);body.setActivationState(4);body.setUserPointer("other-actor");
                // Re-register after setting the type; a static proxy retained
                // the wrong broadphase mask and kinematic world membership.
                world.addRigidBody(body,com.bulletphysics.collision.broadphase.CollisionFilterGroups.KINEMATIC_FILTER,com.bulletphysics.collision.broadphase.CollisionFilterGroups.DEFAULT_FILTER);actors.put(key,body);
            }
            body.setCenterOfMassTransform(at);body.setInterpolationWorldTransform(at);body.getMotionState().setWorldTransform(at);
        }
    }
    public void endActorFrame()
    {trace.event("endActors");var it=actors.entrySet().iterator();while(it.hasNext()){var e=it.next();if(!actorFrame.contains(e.getKey())){world.removeRigidBody(e.getValue());it.remove();}}world.updateAabbs();}
    public void impulse(String bone,org.joml.Vector3f point,org.joml.Vector3f impulse)
    {
        trace.event("impulse","bone",bone,"point",point,"impulse",impulse);
        var body=bodies.getOrDefault(bone,bodies.get("torso_upper"));var origin=body.getCenterOfMassPosition(new Vector3f());
        body.applyImpulse(new Vector3f(impulse.x,impulse.y,impulse.z),new Vector3f(point.x-origin.x,point.y-origin.y,point.z-origin.z));body.activate(true);
    }
    public void velocity(org.joml.Vector3f velocity)
    {trace.event("velocity","value",velocity);for(var body:bodies.values())body.setLinearVelocity(new Vector3f(velocity.x,velocity.y,velocity.z));}
    public void motionFromPose(Map<String,org.joml.Matrix4f> previous,float seconds)
    {
        trace.event("motion","previous",previous,"seconds",seconds);
        if(seconds<=0)return;
        for(var entry:bodies.entrySet())
        {
            var before=previous.get(entry.getKey());if(before==null)continue;
            Transform old=transform(before);old.mul(binds.get(entry.getKey()));Transform now=entry.getValue().getCenterOfMassTransform(new Transform());
            Vector3f speed=new Vector3f(now.origin);speed.sub(old.origin);speed.scale(1/seconds);if(speed.length()>5)speed.scale(5/speed.length());entry.getValue().setLinearVelocity(speed);
            Quat4f a=old.getRotation(new Quat4f()),b=now.getRotation(new Quat4f());a.conjugate();b.mul(a);if(b.w<0)b.scale(-1);
            float sin=(float)Math.sqrt(b.x*b.x+b.y*b.y+b.z*b.z),angle=2*(float)Math.atan2(sin,b.w);Vector3f angular=new Vector3f(b.x,b.y,b.z);
            if(sin>.00001F)angular.scale(Math.min(9,angle/seconds)/sin);else angular.set(0,0,0);entry.getValue().setAngularVelocity(angular);
        }
    }
    public void step(float seconds)
    {
        trace.event("step","seconds",seconds);
        if(closed)throw new IllegalStateException("Closed body");
        int count=Math.max(1,(int)Math.ceil(Math.min(seconds,.10F)*240));float dt=Math.min(seconds,.10F)/count;
        for(int i=0;i<count;i++)
        {
            Map<String,Transform> previous=new HashMap<>();bodies.forEach((n,b)->previous.put(n,b.getCenterOfMassTransform(new Transform())));
            world.stepSimulation(dt,0,dt);projectSweptTerrain(previous);
        }
    }
    // A matched surface-vertex sweep catches rotational crossings missed by
    // JBullet's centre-sphere CCD. Correct the complete assembly so a contact
    // cannot separate a knee or shoulder. A restitution-free contact impulse
    // removes closing velocity at the actual surface; tangential motion remains.
    // Side walls and ceilings remain owned by Bullet collision detection.
    private void projectSweptTerrain(Map<String,Transform> previous)
    {
        float lift=0;
        Map<RigidBody,Vector3f> contacts=new HashMap<>();Map<RigidBody,Float> depths=new HashMap<>();
        for(var entry:bodies.entrySet())
        {
            var vertices=surfaceVertices.get(entry.getKey());if(vertices==null)continue;
            Transform before=previous.get(entry.getKey()),after=entry.getValue().getCenterOfMassTransform(new Transform());
            Vector3f lo=new Vector3f(),hi=new Vector3f(),oldLo=new Vector3f(),oldHi=new Vector3f();
            entry.getValue().getCollisionShape().getAabb(before,oldLo,oldHi);entry.getValue().getCollisionShape().getAabb(after,lo,hi);
            lo.x=Math.min(lo.x,oldLo.x);lo.y=Math.min(lo.y,oldLo.y);lo.z=Math.min(lo.z,oldLo.z);
            hi.x=Math.max(hi.x,oldHi.x);hi.y=Math.max(hi.y,oldHi.y);hi.z=Math.max(hi.z,oldHi.z);
            List<TerrainSurface> nearby=new ArrayList<>();
            for(var surface:surfaces)if(lo.x<=surface.high.x&&hi.x>=surface.low.x&&lo.z<=surface.high.z&&hi.z>=surface.low.z
                    &&lo.y<=surface.high.y+.004F&&hi.y>=surface.low.y)nearby.add(surface);
            if(nearby.isEmpty())continue;
            for(var vertex:vertices)
            {
                Vector3f from=new Vector3f(vertex),to=new Vector3f(vertex);before.transform(from);after.transform(to);
                for(var surface:nearby)
                {
                    Vector3f a=new Vector3f(from),b=new Vector3f(to);surface.inverse.transform(a);surface.inverse.transform(b);
                    float top=surface.half.y;
                    if(a.y<top-.004F||b.y>=top+.00004F||b.y>a.y+.000001F)continue;
                    float fraction=a.y>b.y?Math.max(0,Math.min(1,(a.y-top)/(a.y-b.y))):1;
                    float x=a.x+(b.x-a.x)*fraction,z=a.z+(b.z-a.z)*fraction;
                    if(Math.abs(x)>surface.half.x||Math.abs(z)>surface.half.z)continue;
                    float depth=top+.00004F-b.y;lift=Math.max(lift,depth);
                    if(depth>depths.getOrDefault(entry.getValue(),0F))
                    {depths.put(entry.getValue(),depth);Vector3f at=new Vector3f(to);at.y+=depth;contacts.put(entry.getValue(),at);}
                }
            }
        }
        if(lift<=0)return;
        Vector3f normal=new Vector3f(0,1,0);
        for(var contact:contacts.entrySet())
        {
            var body=contact.getKey();var at=contact.getValue();Vector3f relative=new Vector3f(at);relative.sub(body.getCenterOfMassPosition(new Vector3f()));
            float closing=body.getVelocityInLocalPoint(relative,new Vector3f()).y;
            float inverse=body.computeImpulseDenominator(at,normal);
            if(closing<0&&inverse>1e-8F)body.applyImpulse(new Vector3f(0,-closing/inverse,0),relative);
        }
        for(var body:bodies.values())
        {
            Transform at=body.getCenterOfMassTransform(new Transform());at.origin.y+=lift;
            body.setCenterOfMassTransform(at);body.setInterpolationWorldTransform(at);body.getMotionState().setWorldTransform(at);
        }
        world.updateAabbs();world.performDiscreteCollisionDetection();
    }
    public void controlledPose(Map<String,org.joml.Matrix4f> deformations)
    {
        trace.event("controlledPose","pose",deformations);
        for(var entry:bodies.entrySet())
        {
            var body=entry.getValue();Transform target=transform(deformations.get(entry.getKey()));target.mul(binds.get(entry.getKey()));
            body.setCollisionFlags(body.getCollisionFlags()|CollisionFlags.KINEMATIC_OBJECT);body.setCenterOfMassTransform(target);body.setInterpolationWorldTransform(target);body.getMotionState().setWorldTransform(target);body.setLinearVelocity(new Vector3f());body.setAngularVelocity(new Vector3f());
        }
        world.updateAabbs();world.performDiscreteCollisionDetection();
    }
    public Frame frame()
    {
        Map<String,org.joml.Matrix4f> result=new LinkedHashMap<>();org.joml.Vector3f min=new org.joml.Vector3f(Float.POSITIVE_INFINITY),max=new org.joml.Vector3f(Float.NEGATIVE_INFINITY);float speed=0;
        for(var entry:bodies.entrySet())
        {
            var body=entry.getValue();Transform transform=body.getCenterOfMassTransform(new Transform());Vector3f low=new Vector3f(),high=new Vector3f();body.getCollisionShape().getAabb(transform,low,high);
            // A rotated compound AABB includes empty corners far below the
            // actual armour. Those corners must never become the recovery floor.
            var vertices=surfaceVertices.get(entry.getKey());
            if(vertices!=null&&!vertices.isEmpty())
            {
                low.set(Float.POSITIVE_INFINITY,Float.POSITIVE_INFINITY,Float.POSITIVE_INFINITY);high.set(Float.NEGATIVE_INFINITY,Float.NEGATIVE_INFINITY,Float.NEGATIVE_INFINITY);
                for(var vertex:vertices){var p=new Vector3f(vertex);transform.transform(p);low.x=Math.min(low.x,p.x);low.y=Math.min(low.y,p.y);low.z=Math.min(low.z,p.z);high.x=Math.max(high.x,p.x);high.y=Math.max(high.y,p.y);high.z=Math.max(high.z,p.z);}
            }
            min.min(new org.joml.Vector3f(low.x,low.y,low.z));max.max(new org.joml.Vector3f(high.x,high.y,high.z));if(entry.getKey().startsWith("torso_"))speed=Math.max(speed,body.getLinearVelocity(new Vector3f()).length());
            Transform inverse=new Transform(binds.get(entry.getKey()));inverse.inverse();transform.mul(inverse);result.put(entry.getKey(),matrix(transform));
        }
        int contacts=0;float impulse=0;org.joml.Vector3f impactPoint=new org.joml.Vector3f();for(int i=0;i<dispatcher.getNumManifolds();i++)
        {
            var contact=dispatcher.getManifoldByIndexInternal(i);var a=(CollisionObject)contact.getBody0();var b=(CollisionObject)contact.getBody1();
            if("terrain".equals(a.getUserPointer())||"terrain".equals(b.getUserPointer()))for(int n=0;n<contact.getNumContacts();n++)
            {
                var point=contact.getContactPoint(n);if(point.getDistance()<.012F)contacts++;
                String bone=String.valueOf("terrain".equals(a.getUserPointer())?b.getUserPointer():a.getUserPointer());
                if((bone.startsWith("torso_")||bone.equals("head"))&&point.appliedImpulse>impulse)
                {impulse=point.appliedImpulse;var p="terrain".equals(a.getUserPointer())?point.positionWorldOnA:point.positionWorldOnB;impactPoint.set(p.x,p.y,p.z);}
            }
        }
        trace.event("frame","min",min,"max",max,"speed",speed,"contacts",contacts,"groundImpulse",impulse);
        return new Frame(Map.copyOf(result),min,max,speed,contacts,impulse,impactPoint);
    }
    @Override public void close()
    {if(closed)return;for(var joint:joints)world.removeConstraint(joint);for(var body:bodies.values())world.removeRigidBody(body);for(var body:scenery)world.removeRigidBody(body);for(var body:actors.values())world.removeRigidBody(body);closed=true;}
}
