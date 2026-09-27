package com.projectseele.entity;

import com.projectseele.registry.ModSounds;
import com.projectseele.util.WeakIdentityMap;
import net.minecraft.util.Mth;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;
import org.joml.Vector3f;

/** Stance mechanisms sound while stationary; impacts require knee-pad bearing. */
public final class EvaStanceFoleyR41
{
    private static final class State
    {
        float velocity;
        int knees;
        long loadAt=-100;
    }
    private static final WeakIdentityMap<EvaUnit01Entity,State> STATES=new WeakIdentityMap<>();
    public static void tick(EvaUnit01Entity eva,float before,float stance)
    {
        if(eva.level().isClientSide)return;
        if(!eva.isPoweredOn()||eva.isNervLogisticsLocked()||eva.isFirstBattleActive()||EvaShutdownR30.disabled(eva))
        {STATES.remove(eva);return;}
        State state=STATES.get(eva);
        if(state==null){STATES.put(eva,new State());return;}
        float velocity=stance-before;
        long now=eva.level().getGameTime();
        if(Math.abs(velocity)>.002F&&(Math.abs(state.velocity)<=.002F||state.velocity*velocity<0)&&now-state.loadAt>=8)
        {
            CombatFoleyR36.load(eva);state.loadAt=now;
            com.projectseele.visual.StanceContactR41Review.sound(eva,"joint_load",eva.position());
        }
        state.velocity=velocity;
        if(stance<.35F){state.knees=0;return;}
        if(Math.abs(velocity)<.001F||now%2!=0)return;
        var pose=EvaBodyPose.sample(eva,0);int bearing=0;
        for(int i=0;i<2;i++)
        {
            String side=i==0?"l":"r",marker="r30_knee_socket_"+side;
            Vector3f joint=pose.rig.containsKey(marker)?new Vector3f(pose.rig.get(marker).pivot())
                    :new Vector3f(pose.rig.get("shin_"+side).pivot()).add(0,11.4F/16,0);
            Vector3f point=pose.matrix("leg_"+side).transformPosition(joint).mul(EvaScale.RENDER_SCALE).rotateY((180-eva.getYRot())*Mth.DEG_TO_RAD);
            Vec3 centre=eva.position().add(point.x,point.y,point.z);
            var floor=eva.level().clip(new ClipContext(centre,centre.add(0,-8,0),ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,eva));
            if(floor.getType()==HitResult.Type.MISS||centre.y-floor.getLocation().y>(eva.isExperimentalUnit()?3:2.5))continue;
            bearing|=1<<i;
            if((state.knees&(1<<i))==0&&velocity>0)
            {
                EvaMovementSounds.play(eva,floor.getLocation(),ModSounds.EVA_LAND.get(),1.9F,.95F);
                com.projectseele.visual.StanceContactR41Review.sound(eva,"knee_bearing_"+side,floor.getLocation());
            }
        }
        state.knees=bearing;
    }
    private EvaStanceFoleyR41(){}
}
