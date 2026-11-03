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
    public static final double CAP_FORWARD=EvaRifleClearance.muzzle().y;
    public static final double CAP_DOWN=-EvaRifleClearance.muzzle().z;
    private static final double STOCK_BACK=-EvaRifleClearance.stock().y;
    private static final double STOCK_UP=EvaRifleClearance.stock().z;
    /**
     * Stock pocket relative to the right shoulder joint (blocks; lateral + is
     * the EVA's right): on the right pectoral plate below the joint, so the
     * stock rests against the right side of the chest instead of under the
     * chin. Lying down, it moves ahead of the shoulder along the ground.
     */
    private static final double POCKET_LATERAL=property("projectseele.rifleStockLateral",-2.4),
            POCKET_FORWARD=property("projectseele.rifleStockForward",4.4),
            POCKET_DOWN=property("projectseele.rifleStockDown",-1.2),
            POCKET_FORWARD_PRONE=property("projectseele.rifleStockForwardProne",1.0),
            POCKET_DOWN_PRONE=property("projectseele.rifleStockDownProne",-2.4),
            /** Rise of the stock from low ready to aimed fire. */
            SIGHT_LIFT=property("projectseele.rifleSightLift",0.8);
    /** The chest turns at most this far from the hips toward the sight line; beyond it the barrel pivots on the stock. */
    private static final float TWIST_LIMIT=50;
    /**
     * With the rifle up the chest also turns this far right of the sight
     * line (degrees), bringing the left shoulder forward: square to the
     * target, the support hand had to reach across the belly with a locked arm.
     */
    private static final float BLADE=(float)property("projectseele.rifleBladeR57",18);
    /**
     * Share of that turn the hips take while the EVA stands its ground. The
     * stance already puts the right foot back; square hips under a bladed
     * chest twisted the narrow waist by forty degrees.
     */
    private static final float HIP_SHARE=(float)property("projectseele.rifleHipShareR57",.45);
    /** The drawn barrel converges on the sight line no nearer than this, so a wall or the floor close ahead cannot swing it. */
    private static final double MIN_CONVERGENCE=96;
    // Server and client threads share this JVM in single player.
    private static final java.util.Map<EvaUnit01Entity,double[]> CONVERGENCE=java.util.Collections.synchronizedMap(new java.util.WeakHashMap<>());
    public record Frame(Vec3 grip,Vec3 muzzle,Vec3 stock,Vec3 forward,Vec3 up,Vec3 right,
                        float ready,float recoil,Vec3 eye,Quaternionf headRotation) {}

    public static Matrix4f world(EvaUnit01Entity entity,float partial)
    {
        boolean posed=EvaAirTransportR31.active(entity)||EvaShutdownR30.displayed(entity);
        Vec3 position=posed?EvaAirTransportR31.framePosition(entity,partial):entity.level().isClientSide?entity.getPosition(partial):entity.position();
        if(!posed&&entity.hasActiveCarrierMotion())position=entity.carrierRenderPosition(partial);
        float yaw=posed?EvaAirTransportR31.frameYaw(entity,partial):entity.level().isClientSide?Mth.rotLerp(partial,entity.yBodyRotO,entity.yBodyRot):entity.yBodyRot;
        // The actual locked heading also owns stopped/fallen CPU sockets;
        // the renderer applies this same heading before the captured joints.
        if(!entity.isExperimentalUnit()&&entity.isNervLogisticsLocked())yaw=entity.mechanicalYawR52();
        return frameWorldR52(position,yaw);
    }
    /** Shared outer frame for independently checked pre-lock body sockets. */
    public static Matrix4f frameWorldR52(Vec3 position,float yaw)
    {return new Matrix4f().translation(position.toVector3f()).rotateY((180-yaw)*Mth.DEG_TO_RAD).scale(EvaScale.RENDER_SCALE);}

    public static Frame sample(EvaUnit01Entity entity,float partial,Vec3 direction)
    {
        var body=EvaBodyPose.sample(entity,partial);
        twist(body,twistDegrees(entity,partial,direction));
        return sample(entity,partial,direction,body,world(entity,partial));
    }

    private static double property(String key,double fallback)
    {
        return Double.parseDouble(System.getProperty(key,String.valueOf(fallback)));
    }

    /**
     * Yaw (degrees, Minecraft sense) the chest turns from the hips toward the
     * sight line. The hull follows the pilot's view slowly; the chest takes up
     * the difference so the stock stays on the chest instead of orbiting it.
     */
    public static float twistDegrees(EvaUnit01Entity entity,float partial,Vec3 direction)
    {
        if(EvaRifleClearance.usesLegacyGripFit()||direction.x*direction.x+direction.z*direction.z<1e-6)return 0;
        float body=entity.level().isClientSide?Mth.rotLerp(partial,entity.yBodyRotO,entity.yBodyRot):entity.yBodyRot;
        float aim=(float)Math.toDegrees(Math.atan2(-direction.x,direction.z));
        float ready=entity.rifleReadyBlend(partial),upright=1-entity.rifleProneBlend(partial);
        float weight=(.35F+.65F*ready)*upright;
        return Mth.clamp(Mth.wrapDegrees(aim-body),-TWIST_LIMIT,TWIST_LIMIT)*weight+BLADE*ready*upright;
    }

    /**
     * Yaw (degrees, Minecraft sense) the hips take of the sampled chest's whole
     * turn from them, the stance's own and the sight line's: none while
     * walking, where they face the way the legs go, or lying.
     */
    public static float hipDegrees(EvaUnit01Entity entity,float partial,EvaBodyPose.Sample body)
    {
        if(!body.rig.containsKey("torso_upper")||!body.rig.containsKey("torso_lower"))return 0;
        Vector3f chest=body.matrix("torso_upper").transformDirection(new Vector3f(0,0,-1)),hips=body.matrix("torso_lower").transformDirection(new Vector3f(0,0,-1));
        float turn=Mth.wrapDegrees((float)Math.toDegrees(Math.atan2(chest.x,-chest.z)-Math.atan2(hips.x,-hips.z)));
        return turn*HIP_SHARE*(1-Mth.clamp(entity.rifleMoveBlend(partial),0,1))*(1-entity.rifleProneBlend(partial));
    }

    /**
     * Turns the hips of a sampled body about the vertical through the chest
     * joint, leaving the chest exactly where it was, so the stock, arms and
     * sight line do not move. The legs swing with the hips; the renderer
     * plants the feet again.
     */
    public static void turnHips(EvaBodyPose.Sample body,float degrees)
    {
        if(Math.abs(degrees)<.01F||!body.rig.containsKey("torso_upper")||!body.rig.containsKey("torso_lower"))return;
        Matrix4f chest=body.matrix("torso_upper");
        Vector3f centre=chest.transformPosition(new Vector3f(body.rig.get("torso_upper").pivot()));
        // Minecraft yaw grows clockwise from above; model space turns the other way.
        Matrix4f turn=new Matrix4f().translation(centre).rotateY(-degrees*Mth.DEG_TO_RAD).translate(-centre.x,-centre.y,-centre.z);
        String parent=body.rig.get("torso_lower").parent();
        Matrix4f above=parent==null?new Matrix4f():body.matrix(parent);
        Matrix4f hips=new Matrix4f(above).invert().mul(turn).mul(body.matrix("torso_lower"));
        setLocal(body,"torso_lower",hips);
        body.dirty();
        String chestParent=body.rig.get("torso_upper").parent();
        setLocal(body,"torso_upper",(chestParent==null?new Matrix4f():body.matrix(chestParent)).invert().mul(chest));
        body.dirty();
    }

    /** Stores a rigid local transform as the bone's rotation about its pivot plus offset. */
    private static void setLocal(EvaBodyPose.Sample body,String name,Matrix4f local)
    {
        Vector3f pivot=body.rig.get(name).pivot();
        body.rotations.put(name,local.getNormalizedRotation(new Quaternionf()));
        body.positions.put(name,local.transformPosition(new Vector3f(pivot)).sub(pivot));
    }

    /** Turns the chest of a sampled body about the vertical through its waist joint. */
    public static void twist(EvaBodyPose.Sample body,float degrees)
    {
        if(Math.abs(degrees)<.01F||!body.rig.containsKey("torso_upper")||!body.rig.containsKey("torso_lower"))return;
        var parent=body.matrix("torso_lower").getNormalizedRotation(new Quaternionf());
        // Minecraft yaw grows clockwise from above; model space turns the other way.
        var yaw=new Quaternionf().rotationY(-degrees*Mth.DEG_TO_RAD);
        body.rotations.put("torso_upper",new Quaternionf(parent).invert().mul(yaw).mul(parent).mul(body.rotations.get("torso_upper")));
        body.dirty();
    }

    /**
     * Distance along the sight line the barrel converges on: the sighted
     * surface, never nearer than {@link #MIN_CONVERGENCE}, eased over about a
     * quarter second so sweeping across near and far surfaces does not twitch
     * the weapon.
     */
    private static double convergence(EvaUnit01Entity entity,double sighted)
    {
        // Ballistics keep the exact sighted point; only the drawn weapon eases.
        if(!entity.level().isClientSide)return sighted;
        double wanted=Math.max(MIN_CONVERGENCE,sighted);
        long now=System.nanoTime();
        double[] state=CONVERGENCE.get(entity);
        if(state==null){CONVERGENCE.put(entity,new double[]{wanted,now});return wanted;}
        double dt=Math.min(.5,Math.max(0,(now-state[1])/1e9));
        state[0]+=(wanted-state[0])*(1-Math.exp(-dt/.25));
        state[1]=now;
        return state[0];
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
        float twist=twistDegrees(entity,partial,optical);
        // The caller turned the chest by the same yaw; carry the pocket with it.
        if(twist!=0)f.rotateY(-twist*Mth.DEG_TO_RAD);
        Vec3 bodyForward=new Vec3(f.x,0,f.z).normalize();
        float ready=entity.rifleReadyBlend(partial),recoil=entity.rifleRecoilBlend(partial);
        boolean supported=EvaBodyPose.hasSupportedStances();
        double lateralOffset=supported?-2.3:switch(entity.getUnitVariant()){case 0->2.8;case 2->1.9;default->1.4;};
        double forwardOffset=EvaBodyPose.hasOwnUnRig(entity)?3.8:supported?5:2;
        var handRig=EvaAnatomicalHandsR45.forEntityR53(entity);
        boolean measuredGrip=EvaTripoHandsR48.enabled(entity,body)||handRig!=null&&!handRig.grips().isEmpty();
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
        boolean chestPocket=!EvaRifleClearance.usesLegacyGripFit();
        Vec3 pocket=shoulder.add(bodyRight.scale(lateralOffset)).add(bodyForward.scale(forwardOffset)).add(0,pocketY,0);
        if(chestPocket)
        {
            // The stock rests against the right side of the chest and only
            // rises a little to aim. (The earlier carry moved it six blocks
            // inboard and five up, under the chin, with the barrel across the
            // face.) Standing or crouched it rides the chest plate as the
            // chest leans; lying down it stays level ahead of the shoulder.
            float prone=entity.rifleProneBlend(partial);
            Vector3f chestForward=chest.transformDirection(new Vector3f(0,0,-1)).normalize(),chestUp=chest.transformDirection(new Vector3f(0,1,0)).normalize();
            Vec3 riding=shoulder.add(bodyRight.scale(POCKET_LATERAL)).add(new Vec3(chestForward).scale(POCKET_FORWARD)).add(new Vec3(chestUp).scale(POCKET_DOWN));
            Vec3 lying=shoulder.add(bodyRight.scale(POCKET_LATERAL)).add(bodyForward.scale(POCKET_FORWARD_PRONE)).add(0,POCKET_DOWN_PRONE,0);
            pocket=riding.lerp(lying,prone);
            stockLift=SIGHT_LIFT*sight;
        }
        Vector3f headPoint=new Matrix4f(world).mul(body.matrix("head")).transformPosition(new Vector3f(body.rig.get("head").pivot()));
        Vec3 joint=new Vec3(headPoint.x,headPoint.y,headPoint.z);
        // Keep the carry offset in the aim frame while the chassis catches up
        // with a turn. Otherwise the fixed chest offset crosses the pilot's
        // sight line and the same rifle drifts from the right to screen centre.
        Vec3 horizontalAim=new Vec3(optical.x,0,optical.z);
        if(!chestPocket&&horizontalAim.lengthSqr()>1e-6&&bodyForward.lengthSqr()>1e-6)
        {
            var turn=new Quaternionf().rotationTo(bodyForward.toVector3f(),horizontalAim.normalize().toVector3f());
            pocket=joint.add(new Vec3(turn.transform(pocket.subtract(joint).toVector3f())));
        }
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
            Vec3 target=eye.add(optical.scale(convergence(entity,hit.getType()==HitResult.Type.MISS?end.distanceTo(eye):hit.getLocation().distanceTo(eye))));
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
            Vec3 muzzle=grip.add(aim.scale(CAP_FORWARD)).subtract(up.scale(CAP_DOWN)).add(right.scale(EvaRifleClearance.muzzle().x));
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
