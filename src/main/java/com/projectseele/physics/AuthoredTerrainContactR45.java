package com.projectseele.physics;

import com.projectseele.entity.*;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.phys.*;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import java.util.*;

/** Final terrain inequalities after animation blending and target warping. */
public final class AuthoredTerrainContactR45
{
    private record Point(String bone,Vector3f position) {}
    private static final Map<CombatBodyProfiles.Profile,List<Point>> POINTS=new IdentityHashMap<>();
    private static synchronized List<Point> points(CombatBodyProfiles.Profile profile)
    {
        return POINTS.computeIfAbsent(profile,p->{
            List<Point> result=new ArrayList<>();
            for(var value:p.definition().getAsJsonArray("bodies"))
            {
                var row=value.getAsJsonObject();String name=row.get("name").getAsString();
                if(!row.has("hulls"))continue;
                float[] matrix=new float[16];for(int i=0;i<16;i++)matrix[i]=row.getAsJsonArray("bind").get(i).getAsFloat();
                var bind=new Matrix4f().set(matrix).transpose();
                for(var hull:row.getAsJsonArray("hulls"))for(var vertex:hull.getAsJsonArray())
                    result.add(new Point(name,bind.transformPosition(CombatBodyProfiles.vector(vertex.getAsJsonArray())).div(CombatBodyProfiles.MODEL_TO_PHYSICS)));
            }
            return List.copyOf(result);
        });
    }
    public static void apply(SachielEntity actor,EvaBodyPose.Sample pose,float partial)
    {
        if(actor.isFirstBattleActive()||EvaCombatR31.holds(actor))return;
        if(!actor.onGround())
        {
            // The remote interpolation flag may lag the visible landing.
            // Require the actual supporting collision shape in that case.
            var box=actor.getBoundingBox();
            var bearing=new AABB(box.minX+.1,box.minY-.15,box.minZ+.1,box.maxX-.1,box.minY+.01,box.maxZ-.1);
            if(!actor.level().getBlockCollisions(actor,bearing).iterator().hasNext())return;
        }
        var profile=CombatBodyProfiles.get(actor);if(profile==null)return;
        var surface=points(profile);
        var origin=actor.level().isClientSide?actor.getPosition(partial):actor.position();
        float yaw=(180-actor.getYRot())*(float)Math.PI/180;
        for(String side:List.of("l","r"))for(boolean arm:new boolean[]{false,true})
        {
            String end=(arm?"hand_":"foot_")+side;
            for(int iteration=0;iteration<3;iteration++)
            {
                Vector3f lowest=null;
                for(var point:surface)
                {
                    if(!point.bone().equals(end)&&!(arm&&(point.bone().equals("arm_"+side)||point.bone().equals("forearm_"+side))))continue;
                    var v=pose.matrix(point.bone()).transformPosition(new Vector3f(point.position()));
                    if(lowest==null||v.y<lowest.y)lowest=v;
                }
                if(lowest==null)break;
                var local=new Vector3f(lowest).mul(EvaScale.RENDER_SCALE).rotateY(yaw);
                Vec3 world=origin.add(local.x,local.y,local.z);
                // Start above the actor's bearing plane even when a downstroke
                // has already crossed a thin floor; never raycast from inside it.
                double start=Math.max(world.y,origin.y)+2;
                var hit=actor.level().clip(new ClipContext(new Vec3(world.x,start,world.z),world.add(0,-2,0),ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,actor));
                if(hit.getType()!=HitResult.Type.BLOCK||world.y>=hit.getLocation().y+.02)break;
                var matrix=pose.matrix(end);var orientation=matrix.getUnnormalizedRotation(new Quaternionf()).normalize();
                var goal=matrix.transformPosition(new Vector3f(pose.rig.get(end).pivot()));
                goal.y+=(float)((hit.getLocation().y+.02-world.y)/EvaScale.RENDER_SCALE);
                if(arm)swingArmClear(pose,side,lowest,(float)((hit.getLocation().y+.02-world.y)/EvaScale.RENDER_SCALE));
                else AnatomicalLimbConstraints.reachFoot(pose,profile,side,goal,orientation);
            }
        }
    }
    private static void swingArmClear(EvaBodyPose.Sample pose,String side,Vector3f contact,float lift)
    {
        String bone="arm_"+side;var matrix=pose.matrix(bone);
        var shoulder=matrix.transformPosition(new Vector3f(pose.rig.get(bone).pivot()));
        var from=new Vector3f(contact).sub(shoulder);float length=from.length();if(length<1e-6F)return;
        float y=Math.min(length-.0001F,from.y+lift),horizontal=(float)Math.hypot(from.x,from.z);
        if(horizontal<1e-6F)return;
        float radius=(float)Math.sqrt(Math.max(0,length*length-y*y));
        var to=new Vector3f(from.x*radius/horizontal,y,from.z*radius/horizontal);
        // Contact may be on the upper-arm armour, not at the hand marker.
        // Raising only the hand with two-bone IK can lower that armour again
        // during a sub-tick blend. Swing the connected arm from its shoulder,
        // preserving the authored elbow, wrist, finger angles and all lengths.
        var rotation=new Quaternionf().rotationTo(from,to).mul(matrix.getUnnormalizedRotation(new Quaternionf()).normalize());
        String parent=pose.rig.get(bone).parent();
        if(parent!=null)rotation=pose.matrix(parent).getUnnormalizedRotation(new Quaternionf()).normalize().invert().mul(rotation);
        pose.rotations.put(bone,rotation);pose.dirty();
    }
    private AuthoredTerrainContactR45(){}
}
