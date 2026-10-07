package com.projectseele.entity;

import com.projectseele.config.SeeleConfig;
import net.minecraft.util.Mth;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix3f;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Shoulder carries the weapon; the dominant eye finds its existing sight line. */
public final class EvaRifleKinematics
{
    public static final float WEAPON_SCALE=.72F;
    public static final double CAP_FORWARD=20.3010625D*WEAPON_SCALE;
    public static final double CAP_DOWN=.1561192D*WEAPON_SCALE;
    private static final double STOCK_BACK=49.700046D/16*EvaScale.RENDER_SCALE*WEAPON_SCALE;
    private static final double STOCK_UP=7.656318D/16*EvaScale.RENDER_SCALE*WEAPON_SCALE;
    public record Frame(Vec3 grip,Vec3 muzzle,Vec3 stock,Vec3 forward,Vec3 up,Vec3 right,
                        float ready,float recoil,Vec3 eye,Quaternionf headRotation) {}

    public static Matrix4f world(EvaUnit01Entity entity,float partial)
    {
        boolean posed=EvaAirTransportR31.active(entity)||EvaShutdownR30.displayed(entity);
        Vec3 position=posed?EvaAirTransportR31.framePosition(entity,partial):entity.level().isClientSide?entity.getPosition(partial):entity.position();
        if(!posed&&entity.hasActiveCarrierMotion())position=entity.carrierRenderPosition(partial);
        float yaw=posed?EvaAirTransportR31.frameYaw(entity,partial):entity.level().isClientSide?Mth.rotLerp(partial,entity.yBodyRotO,entity.yBodyRot):entity.yBodyRot;
        if(!posed&&!entity.isExperimentalUnit()&&entity.isNervLogisticsLocked())yaw=EvaUnit01Entity.SILO_BAY_YAW;
        return new Matrix4f().translation(position.toVector3f()).rotateY((180-yaw)*Mth.DEG_TO_RAD).scale(EvaScale.RENDER_SCALE);
    }

    public static Frame sample(EvaUnit01Entity entity,float partial,Vec3 direction)
    {
        return sample(entity,partial,direction,EvaBodyPose.sample(entity,partial),world(entity,partial));
    }

    private static Quaternionf facing(Vec3 forward)
    {
        Vec3 right=forward.cross(new Vec3(0,1,0));
        if(right.lengthSqr()<1e-8)right=new Vec3(1,0,0);else right=right.normalize();
        Vec3 up=right.cross(forward).normalize();
        return new Quaternionf().setFromNormalized(new Matrix3f().setColumn(0,right.toVector3f())
                .setColumn(1,up.toVector3f()).setColumn(2,forward.scale(-1).toVector3f()));
    }

    public static Frame sample(EvaUnit01Entity entity,float partial,Vec3 direction,EvaBodyPose.Sample body,Matrix4f world)
    {
        Vec3 optical=direction.normalize();
        Vector3f shoulderPoint=new Matrix4f(world).mul(body.matrix("arm_r"))
                .transformPosition(new Vector3f(body.rig.get("arm_r").pivot()));
        Vec3 shoulder=new Vec3(shoulderPoint.x,shoulderPoint.y,shoulderPoint.z);
        var chest=new Matrix4f(world).mul(body.matrix("torso_upper"));
        Vector3f lateral=chest.transformDirection(new Vector3f(1,0,0)).normalize();
        Vec3 bodyRight=new Vec3(lateral.x,lateral.y,lateral.z);
        Vector3f f=world.transformDirection(new Vector3f(0,0,-1)).normalize();
        Vec3 bodyForward=new Vec3(f.x,0,f.z).normalize();
        float ready=entity.rifleReadyBlend(partial),recoil=entity.rifleRecoilBlend(partial);
        boolean supported=EvaBodyPose.hasSupportedStances();
        double lateralOffset=supported?-2.3:switch(entity.getUnitVariant()){case 0->2.8;case 2->1.9;default->1.4;};
        double forwardOffset=EvaBodyPose.hasOwnUnRig(entity)?3.8:supported?5:2;
        boolean measuredGrip=EvaTripoHandsR48.enabled(entity,body)||EvaAnatomicalHandsR45.enabled(entity)
                &&!EvaBodyPose.hasOwnUnRig(entity)
                &&!EvaAnatomicalHandsR45.rig(entity.getUnitVariant()).grips().isEmpty();
        if(measuredGrip)
        {
            forwardOffset=1.2;
            // At the exact server threshold where firing is allowed, the
            // barrel and fingers must already be in their held pose. Using
            // raw .96 left a 4.7m optical miss while fireRifle accepted shots.
            ready=entity.rifleHeldPoseReadinessR45(partial);
        }
        // Low ready and shoulder aim are distinct poses. A client-only scope
        // used to leave everyone else seeing the same carry height. The shared
        // server aim signal now raises the existing stock into the shoulder
        // pocket; measured grips, arm reach and optics consume that same frame.
        float sight=entity.rifleSightBlendR45(partial);sight=sight*sight*(3-2*sight);
        double stockLift=measuredGrip?5*sight:5;
        double pocketY=supported?-3.1:Mth.lerp(entity.rifleProneBlend(partial),-1.5D,.2D);
        Vec3 pocket=shoulder.add(bodyRight.scale(lateralOffset)).add(bodyForward.scale(forwardOffset)).add(0,pocketY,0);
        Vector3f headPoint=new Matrix4f(world).mul(body.matrix("head")).transformPosition(new Vector3f(body.rig.get("head").pivot()));
        Vec3 joint=new Vec3(headPoint.x,headPoint.y,headPoint.z);
        Vector3f eyeLocal=EvaBodyPose.eyePoint(entity).sub(body.rig.get("head").pivot()).mul(EvaScale.RENDER_SCALE);
        Quaternionf baseHead=facing(optical),head=new Quaternionf(baseHead);
        Vector3f initialEye=baseHead.transform(new Vector3f(eyeLocal));
        Vec3 eye=joint.add(initialEye.x,initialEye.y,initialEye.z);
        Frame result=null;
        double carryLift=0;
        // Camera, target ray and weapon share this deterministic optical point.
        for(int iteration=0;iteration<(measuredGrip?6:3);iteration++)
        {
            Vec3 carriedPocket=pocket.add(0,carryLift,0);
            Vec3 end=eye.add(optical.scale(SeeleConfig.EVA_RIFLE_RANGE.get()));
            var hit=entity.level().clip(new ClipContext(eye,end,ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,entity));
            Vec3 target=hit.getType()==HitResult.Type.MISS?end:hit.getLocation();
            Vec3 aim=target.subtract(carriedPocket.add(0,stockLift,0)).normalize();
            if(aim.lengthSqr()<1e-8)aim=optical;
            for(int pass=0;pass<2;pass++)
            {
                Vec3 right=aim.cross(new Vec3(0,1,0));right=right.lengthSqr()<1e-8?bodyRight:right.normalize();
                Vec3 up=right.cross(aim).normalize();
                aim=target.subtract(carriedPocket.add(up.scale(stockLift))).add(up.scale(STOCK_UP+CAP_DOWN)).normalize();
            }
            aim=aim.add(0,-(1-ready)*.6+recoil*.008,0).normalize();
            double height=Math.max(.5,carriedPocket.y+stockLift-entity.getY()-1.1);
            double maxDown=Math.min(.98,height/(STOCK_BACK+CAP_FORWARD));
            if(aim.y < -maxDown)
            {
                Vec3 flat=new Vec3(aim.x,0,aim.z).normalize();aim=flat.scale(Math.sqrt(1-maxDown*maxDown)).add(0,-maxDown,0);
            }
            Vec3 right=aim.cross(new Vec3(0,1,0));right=right.lengthSqr()<1e-8?bodyRight:right.normalize();
            Vec3 up=right.cross(aim).normalize();
            Vec3 stock=carriedPocket.add(up.scale(stockLift)).subtract(aim.scale(recoil*.22));
            Vec3 grip=stock.add(aim.scale(STOCK_BACK)).subtract(up.scale(STOCK_UP));
            // During kneel/prone handoffs the magazine or receiver can reach
            // the floor before the muzzle. Lift the complete held weapon by
            // its measured support hull; both hands and the optical solution
            // consume this same corrected frame.
            var contacts=EvaRifleGripR45.contacts(entity,body,grip,right,aim,up);
            double clearance=Math.max(EvaRifleClearance.lift(grip,right,aim,up,entity.getY()),
                    EvaRifleGripR45.reachLift(contacts,body,world));
            if(clearance>0)
            {
                grip=grip.add(0,clearance,0);stock=stock.add(0,clearance,0);
                // Re-solve from the ACTUAL carry origin on the next pass.
                // Otherwise the prone gun ray misses the optical target by
                // its floor/reach lift, even with zero recoil and full aim.
                if(measuredGrip)carryLift+=clearance;
            }
            Vec3 muzzle=grip.add(aim.scale(CAP_FORWARD)).subtract(up.scale(CAP_DOWN)).add(right.scale(-.0014665D*WEAPON_SCALE));
            if(supported)
            {
                // The raised rear receiver reaches 4.35 blocks above the bore.
                Vec3 line=grip.add(up.scale(4.5));Vec3 offset=line.subtract(joint);
                Vec3 across=offset.subtract(aim.scale(offset.dot(aim)));double radius=eyeLocal.length();
                if(across.lengthSqr()<radius*radius)
                {
                    Vec3 desiredEye=across.add(aim.scale(Math.sqrt(radius*radius-across.lengthSqr())));
                    Quaternionf align=new Quaternionf().rotationTo(initialEye,desiredEye.toVector3f());
                    float angle=2*(float)Math.acos(Mth.clamp(Math.abs(align.w),0,1));
                    if(angle>.35F)align=new Quaternionf().slerp(align,.35F/angle);
                    float headWeight=Mth.clamp((ready-.35F)/.65F,0,1);
                    headWeight=headWeight*headWeight*(3-2*headWeight);
                    if(measuredGrip)
                    {
                        float reachable=(float)Mth.clamp((radius*radius-across.lengthSqr())/(radius*radius*.3),0,1);
                        reachable=reachable*reachable*(3-2*reachable);
                        headWeight*=sight*reachable;
                    }
                    align=new Quaternionf().slerp(align,headWeight);
                    head=new Quaternionf(align).mul(baseHead);
                }
            }
            Vector3f offset=head.transform(new Vector3f(eyeLocal));eye=joint.add(offset.x,offset.y,offset.z);
            result=new Frame(grip,muzzle,stock,aim,up,right,ready,recoil,eye,new Quaternionf(head));
        }
        return result;
    }
}
