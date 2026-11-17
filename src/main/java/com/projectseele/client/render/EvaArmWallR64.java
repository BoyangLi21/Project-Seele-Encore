package com.projectseele.client.render;

import com.projectseele.client.AircraftRenderClockR21;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.world.phys.AABB;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.BakedGeoModel;

import java.util.HashMap;
import java.util.Map;

/**
 * R64 (M3): the arms of a Unit of the planted model keep out of walls.
 * <p>
 * The Unit's box is 17 blocks across and its hands hang and swing 11 to 14 blocks from its axis: a body walking
 * with its box against a building had the arm on that side inside the building, to the elbow at the reach of its
 * swing. Nothing in the pose looked at blocks beside the body (the wall stance looks ahead only).
 * <p>
 * Each frame, after the feet have been set: a hand whose place is taken by a block is drawn toward the body's
 * axis, at its own height, as far as it must go to be clear (never all the way), and the arm is solved to it with
 * the elbow kept where it pointed. The draw is taken up quickly and let go slowly, so an arm swinging past a wall
 * is held in and not flicked. What the Unit walks through (fences, panes) does not move an arm.
 */
final class EvaArmWallR64
{
    /** -Dprojectseele.armWallR64=false: the arms are left as the clips have them (the witness still says how far in they are). */
    private static final boolean ON=!"false".equals(System.getProperty("projectseele.armWallR64"));
    /** Half the side of the box about a hand that must be clear (blocks), and the most of the way to the axis a hand is drawn. */
    private static final float PROBE=1.4F,DRAW_MOST=.8F,CLEAR=.04F;
    /** Seconds over which the draw is taken up and let go. */
    private static final double IN=.045,OUT=.35;

    private static final class State{final float[] draw=new float[2];long frame;}
    private static final Map<Integer,State> STATES=new HashMap<>();

    private EvaArmWallR64(){}

    static void apply(EvaUnit01Entity eva,BakedGeoModel model,Matrix4f root)
    {
        if(STATES.size()>64)STATES.clear();
        State s=STATES.computeIfAbsent(eva.getId(),k->new State());
        long now=AircraftRenderClockR21.frameNanos();
        // The same frame drawn again (the shadow pass): as it was, with no time gone.
        double dt=s.frame==0?0:Math.min(.1,Math.max(0,(now-s.frame)/1e9));
        s.frame=now;
        Vector3f origin=root.transformPosition(new Vector3f());
        double[] witness=EvaPlantedGaitR64.LAST.get(eva.getId());
        for(int i=0;i<2;i++)
        {
            String side=i==0?"l":"r";
            var upper=model.getBone("arm_"+side).orElse(null);var lower=model.getBone("forearm_"+side).orElse(null);
            var wrist=model.getBone("wrist_"+side).orElse(null);var hand=model.getBone("hand_"+side).orElse(null);
            if(upper==null||lower==null||wrist==null||hand==null)continue;
            Vector3f at=EvaRigTransforms.point(hand,EvaRigTransforms.pivot(hand),root);
            Vector3f axis=new Vector3f(origin.x,at.y,origin.z);
            // How much of the way to the axis the hand must go to be clear.
            float need=0;
            if(blocked(eva,at))
            {
                if(blocked(eva,new Vector3f(at).lerp(axis,DRAW_MOST)))need=DRAW_MOST;
                else
                {
                    float low=0,high=DRAW_MOST;
                    for(int k=0;k<6;k++){float mid=(low+high)*.5F;if(blocked(eva,new Vector3f(at).lerp(axis,mid)))low=mid;else high=mid;}
                    // And a little further: a hand held exactly clear was back in the wall with every sway of the arm.
                    need=Math.min(DRAW_MOST,high+CLEAR);
                }
            }
            if(DIAG&&need>0&&dt>0)told(eva,side,at);
            if(dt>0)s.draw[i]+=(need-s.draw[i])*(float)(1-Math.exp(-dt/(need>s.draw[i]?IN:OUT)));
            float span=at.distance(axis);
            if(witness!=null&&witness.length>=36){witness[32+i]=need*span;witness[34+i]=blocked(eva,at)?1:0;}
            if(!ON||s.draw[i]<.004F)continue;
            // Solved in the model's own space, as the arm's other solver is: the way from the model to the world
            // is mirrored, and a hand's turn read through it came out inside out (the hand drawn as a dark slab).
            var model0=new Matrix4f();
            Vector3f target=new Matrix4f(root).invert().transformPosition(new Vector3f(at).lerp(axis,s.draw[i]));
            var centre=EvaRigTransforms.elbow(lower,side);
            Vector3f shoulder=EvaRigTransforms.point(upper,EvaRigTransforms.pivot(upper),model0),elbow=EvaRigTransforms.point(upper,centre,model0);
            var orientation=EvaRigTransforms.rotation(EvaRigTransforms.model(hand));
            // Just inside the arm's reach, so a straight arm has one answer from frame to frame.
            float reach=new Vector3f(centre).sub(EvaRigTransforms.pivot(upper)).length()+EvaRigTransforms.pivot(hand).sub(centre).length();
            float far=target.distance(shoulder);
            if(far>reach-.001F)target.set(new Vector3f(target).sub(shoulder).mul((reach-.001F)/Math.max(far,1e-6F)).add(shoulder));
            EvaRigTransforms.solveArm(upper,lower,wrist,hand,side,target,orientation,elbow.sub(shoulder),model0);
            if(witness!=null&&witness.length>=36)
                witness[34+i]=blocked(eva,EvaRigTransforms.point(hand,EvaRigTransforms.pivot(hand),root))?1:0;
        }
    }

    /** Review only (-Dprojectseele.plantedDiagR64=true): what a hand has met, once a tick. */
    private static final boolean DIAG=Boolean.getBoolean("projectseele.plantedDiagR64");
    private static int toldTick=-1;
    private static void told(EvaUnit01Entity eva,String side,Vector3f p)
    {
        if(eva.tickCount==toldTick)return;
        toldTick=eva.tickCount;
        var box=new AABB(p.x-PROBE,p.y-PROBE,p.z-PROBE,p.x+PROBE,p.y+PROBE,p.z+PROBE);
        String what="nothing";
        for(var pos:net.minecraft.core.BlockPos.betweenClosed(net.minecraft.core.BlockPos.containing(box.minX,box.minY,box.minZ),net.minecraft.core.BlockPos.containing(box.maxX,box.maxY,box.maxZ)))
        {
            var state=eva.level().getBlockState(pos);
            if(!state.isAir()){what=state.getBlock().toString()+" at "+pos.toShortString();break;}
        }
        com.projectseele.ProjectSeele.LOGGER.info("R64ARM tick {} hand {} at {} {} {} (unit at {} {} {}): {}",eva.tickCount,side,
                String.format(java.util.Locale.ROOT,"%.1f",p.x),String.format(java.util.Locale.ROOT,"%.1f",p.y),String.format(java.util.Locale.ROOT,"%.1f",p.z),
                String.format(java.util.Locale.ROOT,"%.1f",eva.getX()),String.format(java.util.Locale.ROOT,"%.1f",eva.getY()),String.format(java.util.Locale.ROOT,"%.1f",eva.getZ()),what);
    }

    /** A block the Unit does not walk through stands in the box about a point. */
    private static boolean blocked(EvaUnit01Entity eva,Vector3f p)
    {
        return eva.level().getBlockCollisions(eva,new AABB(p.x-PROBE,p.y-PROBE,p.z-PROBE,p.x+PROBE,p.y+PROBE,p.z+PROBE)).iterator().hasNext();
    }
}
