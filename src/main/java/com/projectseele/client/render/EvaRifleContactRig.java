package com.projectseele.client.render;

import com.projectseele.entity.EvaBodyPose;
import com.projectseele.entity.EvaRifleKinematics;
import com.projectseele.entity.EvaScale;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix3f;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import software.bernie.geckolib.cache.object.GeoBone;
import java.util.*;

/** Shoulder stock, wrist grips and head-to-sight alignment in the final pose commit. */
public final class EvaRifleContactRig
{
    public record ArmTrace(Vector3f elbow,Vector3f wrist,Vector3f pole) {}
    public record Witness(Vec3 expectedMuzzle,double rightError,double leftError,double footDrift,Vec3 stock,Vec3 shoulder,
                          ArmTrace left,ArmTrace right,boolean measured) {}
    public static final Map<Integer,Witness> LAST=new HashMap<>();
    private static void absolute(GeoBone b,Matrix4f desired,Matrix4f root)
    {
        Matrix4f rel=EvaRigTransforms.parent(b,root).invert().mul(desired);Vector3f p=EvaRigTransforms.pivot(b);
        Vector3f offset=rel.transformPosition(new Vector3f(p)).sub(p);
        b.setPosX(-offset.x*16);b.setPosY(offset.y*16);b.setPosZ(offset.z*16);
        Vector3f scale=rel.getScale(new Vector3f());b.setScaleX(scale.x);b.setScaleY(scale.y);b.setScaleZ(scale.z);
        EvaRigTransforms.rotate(b,EvaRigTransforms.rotation(rel));
    }
    private static boolean bodyBone(String n)
    {
        return n.equals("root")||n.startsWith("torso_")||n.equals("aim_pitch")||n.equals("neck")||n.equals("head")
                ||n.startsWith("leg_")||n.startsWith("shin_")||n.startsWith("ankle_")||n.startsWith("foot_")
                ||n.startsWith("arm_")||n.startsWith("forearm_")||n.startsWith("wrist_")||n.startsWith("hand_")||n.startsWith("finger_");
    }
    public static EvaMotionEngineV2.BoneWrites apply(EvaUnit01Entity eva,BakedGeoModel model,float partial,Matrix4f root)
    {
        if(eva.getWeapon()!=EvaUnit01Entity.WEAPON_RIFLE||!eva.isPoweredOn()||eva.isNervLogisticsLocked()||eva.isBerserk()
                ||eva.isCrucified()||eva.getVisualPose()!=0||eva.getActivationTicks()>0||root==null)return EvaMotionEngineV2.BoneWrites.empty();
        if(model.getBone("wrist_l").isEmpty()||model.getBone("wrist_r").isEmpty()||model.getBone("finger_middle_l").isEmpty())return EvaMotionEngineV2.BoneWrites.empty();
        var body=EvaBodyPose.sample(eva,partial);Set<String> rotations=new LinkedHashSet<>(),positions=new LinkedHashSet<>();
        for(String n:body.rig.keySet())
        {
            GeoBone b=model.getBone(n).orElse(null);if(b==null||!bodyBone(n))continue;
            if(eva.isVisuallyAirborneForRender())
            {
                // Keep the accepted airborne body, while its real shoulder still carries the gun.
                body.rotations.put(n,new Quaternionf().rotationZYX(b.getRotZ(),b.getRotY(),b.getRotX()));
                body.positions.put(n,new Vector3f(-b.getPosX(),b.getPosY(),b.getPosZ()).div(16));
            }
            else
            {
                EvaRigTransforms.rotate(b,body.rotations.get(n));var p=body.positions.get(n);
                b.setPosX(-p.x*16);b.setPosY(p.y*16);b.setPosZ(p.z*16);b.setScaleX(1);b.setScaleY(1);b.setScaleZ(1);
                rotations.add(n);positions.add(n);
            }
        }
        body.dirty();var f=EvaRifleKinematics.sample(eva,partial,eva.getAimDirectionForPoseCapture(partial),body,root);
        Vector3f right=f.right().toVector3f(),forward=f.forward().toVector3f(),up=f.up().toVector3f();
        Matrix3f basis=new Matrix3f().setColumn(0,right).setColumn(1,new Vector3f(forward).negate()).setColumn(2,new Vector3f(up).negate());
        Quaternionf gunRotation=new Quaternionf().setFromNormalized(basis);
        GeoBone cannon=model.getBone("cannon").orElseThrow();Vector3f pc=new Vector3f(24.49137F,88.34269F,.87469F).div(16);
        Matrix4f gun=new Matrix4f().translation(f.grip().toVector3f()).rotate(gunRotation).scale(EvaScale.RENDER_SCALE*EvaRifleKinematics.WEAPON_SCALE).translate(new Vector3f(pc).negate());
        Matrix4f attachment=new Matrix4f().translation(-1.97646F/16,7.68353F/16,.33048F/16).translate(pc)
                .rotateZYX((float)Math.toRadians(31.40634),(float)Math.toRadians(18.77208),(float)Math.toRadians(-45.37424))
                .scale(EvaRifleKinematics.WEAPON_SCALE).translate(new Vector3f(pc).negate());
        Matrix4f rightHand=new Matrix4f().translation(new Vector3f(right).fma(-1.5F,up)).mul(gun).mul(attachment.invert());
        Vector3f rightTarget=rightHand.transformPosition(EvaRigTransforms.pivot(model.getBone("hand_r").orElseThrow()));
        Quaternionf qR=EvaRigTransforms.rotation(rightHand);
        if(model.getBone("r30_hand_frame_r").isPresent())
        {
            var oldWrist=new Vector3f(24.49137F,93.34269F,.87469F).div(16);
            var oldMiddle=new Vector3f(27.3518485F,88.679887F,4.800933F).div(16);
            var oldContact=new Vector3f(oldWrist).lerp(oldMiddle,.65F);
            var contact=rightHand.transformPosition(oldContact);
            qR=retargetHand(model,"r",qR);
            var offset=EvaRigTransforms.pivot(model.getBone("finger_middle_r").orElseThrow()).sub(EvaRigTransforms.pivot(model.getBone("hand_r").orElseThrow())).mul(.65F*EvaScale.RENDER_SCALE);
            rightTarget=contact.sub(qR.transform(offset));
        }
        Quaternionf leftRelative=new Quaternionf().rotationZYX((float)Math.toRadians(-2.51789),(float)Math.toRadians(-33.31161),(float)Math.toRadians(94.97409))
                .rotateZYX((float)Math.toRadians(-.10716),(float)Math.toRadians(10.32404),(float)Math.toRadians(-12.09838));
        Quaternionf refGun=new Quaternionf().rotationZYX((float)Math.toRadians(16.13605),(float)Math.toRadians(8.19676),(float)Math.toRadians(45.25275))
                .rotateZYX((float)Math.toRadians(-15.83803),(float)Math.toRadians(21.17865),(float)Math.toRadians(94.81682))
                .rotateZYX((float)Math.toRadians(31.40634),(float)Math.toRadians(18.77208),(float)Math.toRadians(-45.37424));
        Quaternionf qL=new Quaternionf(gunRotation).mul(refGun.invert().mul(leftRelative));
        if(model.getBone("r30_hand_frame_l").isPresent())qL=retargetHand(model,"l",qL);
        Vector3f palmOffset=EvaRigTransforms.pivot(model.getBone("finger_middle_l").orElseThrow()).sub(EvaRigTransforms.pivot(model.getBone("hand_l").orElseThrow())).mul(.65F*EvaScale.RENDER_SCALE);
        qL.transform(palmOffset);
        Vector3f supportBase=f.grip().subtract(f.up().scale(3.3)).toVector3f().sub(palmOffset);
        var leftUpper=model.getBone("arm_l").orElseThrow();var leftHand=model.getBone("hand_l").orElseThrow();
        var leftShoulder=EvaRigTransforms.point(leftUpper,EvaRigTransforms.pivot(leftUpper),root);
        var leftElbow=EvaRigTransforms.elbow(model.getBone("forearm_l").orElseThrow(),"l");
        float reach=(new Vector3f(leftElbow).sub(EvaRigTransforms.pivot(leftUpper)).length()
                +EvaRigTransforms.pivot(leftHand).sub(leftElbow).length())*root.getScale(new Vector3f()).y-.1F;
        var fromShoulder=new Vector3f(supportBase).sub(leftShoulder);float along=fromShoulder.dot(forward);
        float discriminant=along*along-fromShoulder.lengthSquared()+reach*reach;
        // A supporting hand can slide along the lower foregrip as the barrel
        // rises. Keep that contact on the gun rather than stretching the arm.
        float supportSlide=Math.min(2F,-along+(float)Math.sqrt(Math.max(0,discriminant)));
        Vector3f leftTarget=new Vector3f(supportBase).fma(supportSlide,forward);
        var measured = com.projectseele.entity.EvaRifleGripR45.contacts(eva, body, f.grip(), f.right(), f.forward(), f.up());
        if (measured != null && EvaHandSurfaceR45.applies(eva))
        {
            rightTarget = new Vector3f(measured.right().wrist());
            leftTarget = new Vector3f(measured.left().wrist());
            qR = new Quaternionf(measured.right().rotation());
            qL = new Quaternionf(measured.left().rotation());
        }
        float stance=eva.rifleStanceLevel(partial);
        float support=EvaBodyPose.hasSupportedStances()&&stance>1&&stance<3
                ?(float)Math.pow(Math.sin((stance-1)*Math.PI/2),2):0;
        float prone=EvaBodyPose.hasSupportedStances()?net.minecraft.util.Mth.clamp(stance-2,0,1):eva.rifleProneBlend(partial);
        Vector3f leftPole=new Vector3f(right).negate().add(0,-.7F,0);
        if(EvaBodyPose.hasSupportedStances())
        {
            float kneeling=(1-Math.min(1,Math.abs(stance-1)))*(1-eva.rifleMoveBlend(partial));
            var knee=body.rig.containsKey("r30_knee_socket_l")?new Vector3f(body.rig.get("r30_knee_socket_l").pivot()):new Vector3f(body.rig.get("shin_l").pivot()).add(0,11.4F/16,0);
            var kneeWorld=new Matrix4f(root).mul(body.matrix("leg_l")).transformPosition(knee);
            leftPole.normalize().lerp(kneeWorld.sub(leftShoulder).normalize(),kneeling);
        }
        if(support>0)
        {
            Vector3f ground=new Vector3f(leftShoulder).fma(4,forward);ground.y=(float)eva.getY()+1.8F;
            if(EvaBodyPose.hasOwnUnRig(eva))
            {
                // The shorter UN arm cannot plant while its shoulder is still
                // high in the kneel-to-prone transition. Release the foregrip
                // only as the real floor enters the arm's reach sphere.
                float drop=leftShoulder.y-ground.y;
                support*=net.minecraft.util.Mth.clamp((reach-Math.abs(drop))/3F,0,1);
                float horizontal=(float)Math.sqrt(Math.max(0,reach*reach-drop*drop));
                var flat=new Vector3f(ground).sub(leftShoulder);flat.y=0;
                if(flat.length()>horizontal&&flat.lengthSquared()>1e-6F)flat.normalize().mul(horizontal);
                ground.x=leftShoulder.x+flat.x;ground.z=leftShoulder.z+flat.z;
            }
            boolean fittedHand=com.projectseele.entity.EvaAnatomicalHandsR45.enabled(eva);
            float palmTravel=fittedHand?com.projectseele.entity.EvaAnatomicalHandsR45.supportPalmTravelR45(support):support;
            leftTarget.lerp(ground,palmTravel);
            if(fittedHand)
                leftTarget.fma(-2.5F*(float)Math.sin(Math.PI*palmTravel)
                        -com.projectseele.entity.EvaAnatomicalHandsR45.supportGunClearanceR45(support),up);
            Vector3f handAlong=EvaRigTransforms.pivot(model.getBone("finger_middle_l").orElseThrow()).sub(EvaRigTransforms.pivot(leftHand));
            Vector3f across=EvaRigTransforms.pivot(model.getBone("finger_index_l").orElseThrow()).sub(EvaRigTransforms.pivot(model.getBone("finger_little_l").orElseThrow()));
            Quaternionf palmDown=new Quaternionf().setFromNormalized(handFrame(forward,right).mul(handFrame(handAlong,across).transpose()));
            float palmTurn=fittedHand?com.projectseele.entity.EvaAnatomicalHandsR45.supportPalmTurnR45(support):support;
            qL.slerp(palmDown,palmTurn);
            final float plantedSupport=support;
            for(String n:body.rig.keySet())if(n.startsWith("finger_")&&n.endsWith("_l")&&!n.contains("_axis_"))
                model.getBone(n).ifPresent(b->EvaRigTransforms.rotate(b,new Quaternionf().rotationZYX(b.getRotZ(),b.getRotY(),b.getRotX()).slerp(new Quaternionf(),plantedSupport)));
        }
        float out=1,down=.7F;
        float highAim=net.minecraft.util.Mth.clamp((float)(f.forward().y-.35)/.35F,0,1);
        Vector3f rightPole=new Vector3f(right).mul(out-.35F*highAim).add(0,-down,0);
        rightPole=groundedPole(model,"r",rightTarget,rightPole,root,(float)eva.getY()+3.5F,prone);
        leftPole=groundedPole(model,"l",leftTarget,leftPole,root,(float)eva.getY()+3.5F,Math.max(prone,support));
        double re=solve(model,"r",rightTarget,qR,rightPole,root);
        double le=solve(model,"l",leftTarget,qL,leftPole,root);
        if(com.projectseele.visual.UNR29Review.R30&&le>.5&&eva.tickCount%20==0)
            com.projectseele.ProjectSeele.LOGGER.info("R30 left contact diagnostic stance={} support={} reach={} shoulder={} target={} error={}",stance,support,reach,leftShoulder,leftTarget,le);
        absolute(cannon,gun,root);
        // Lean the gaze toward the existing sight line. This never moves the weapon.
        var head=model.getBone("head").orElseThrow();var headWorld=new Quaternionf(f.headRotation());
        EvaRigTransforms.rotate(head,EvaRigTransforms.rotation(EvaRigTransforms.parent(head,root)).invert().mul(headWorld));
        if(!head.isHidden()&&!(eva instanceof com.projectseele.entity.EvaPrototypeEntity un&&un.isEyeLaserActive()))EvaHeadClearance.apply(eva,head,root,gun,headWorld,right,forward,partial);
        var shoulder=EvaRigTransforms.point(model.getBone("arm_r").orElseThrow(),EvaRigTransforms.pivot(model.getBone("arm_r").orElseThrow()),root);
        if(LAST.size()>32)LAST.clear();LAST.put(eva.getId(),new Witness(f.muzzle(),re,le,-1,f.stock(),new Vec3(shoulder.x,shoulder.y,shoulder.z),
                armTrace(model,"l",leftPole,root),armTrace(model,"r",rightPole,root),measured!=null&&EvaHandSurfaceR45.applies(eva)));
        rotations.addAll(Set.of("neck","head","arm_r","forearm_r","wrist_r","hand_r","arm_l","forearm_l","wrist_l","hand_l","cannon"));
        positions.addAll(Set.of("forearm_r","wrist_r","hand_r","forearm_l","wrist_l","hand_l","cannon"));
        return new EvaMotionEngineV2.BoneWrites(Set.copyOf(rotations),Set.copyOf(positions),"MOTION_ENGINE_LIVE_ACTION");
    }
    private static double solve(BakedGeoModel model,String side,Vector3f target,Quaternionf rotation,Vector3f pole,Matrix4f root)
    {
        return EvaRigTransforms.solveArm(model.getBone("arm_"+side).orElseThrow(),model.getBone("forearm_"+side).orElseThrow(),model.getBone("wrist_"+side).orElseThrow(),model.getBone("hand_"+side).orElseThrow(),side,target,rotation,pole,root);
    }

    private static ArmTrace armTrace(BakedGeoModel model,String side,Vector3f pole,Matrix4f root)
    {
        if(System.getProperty("projectseele.r44HandWitnessPath","").isBlank())return null;
        var lower=model.getBone("forearm_"+side).orElseThrow();var hand=model.getBone("hand_"+side).orElseThrow();
        return new ArmTrace(EvaRigTransforms.point(lower,EvaRigTransforms.elbow(lower,side),root),
                EvaRigTransforms.point(hand,EvaRigTransforms.pivot(hand),root),new Vector3f(pole));
    }


    private static Matrix3f handFrame(Vector3f along,Vector3f across)
    {
        var y=new Vector3f(along).normalize();var x=new Vector3f(across).sub(new Vector3f(y).mul(across.dot(y))).normalize();
        return new Matrix3f().setColumn(0,x).setColumn(1,y).setColumn(2,new Vector3f(x).cross(y));
    }
    private static Quaternionf retargetHand(BakedGeoModel model,String side,Quaternionf rotation)
    {
        float sign=side.equals("r")?1:-1;
        var oldAlong=new Vector3f(sign*(27.3518485F-24.49137F),88.679887F-93.34269F,4.800933F-.87469F);
        var oldAcross=new Vector3f(sign*(28.438445F-22.1963005F),89.0763305F-88.9015215F,.92398F-8.7529835F);
        var along=EvaRigTransforms.pivot(model.getBone("finger_middle_"+side).orElseThrow()).sub(EvaRigTransforms.pivot(model.getBone("hand_"+side).orElseThrow()));
        var across=EvaRigTransforms.pivot(model.getBone("finger_index_"+side).orElseThrow()).sub(EvaRigTransforms.pivot(model.getBone("finger_little_"+side).orElseThrow()));
        return new Quaternionf(rotation).mul(new Quaternionf().setFromNormalized(handFrame(oldAlong,oldAcross).mul(handFrame(along,across).transpose())));
    }

    private static Vector3f groundedPole(BakedGeoModel model,String side,Vector3f target,Vector3f preferred,Matrix4f root,float height,float weight)
    {
        if(weight<.001F)return preferred;
        var upper=model.getBone("arm_"+side).orElseThrow();var hand=model.getBone("hand_"+side).orElseThrow();
        var shoulder=EvaRigTransforms.point(upper,EvaRigTransforms.pivot(upper),root);float scale=root.getScale(new Vector3f()).y;
        var centreLocal=EvaRigTransforms.elbow(model.getBone("forearm_"+side).orElseThrow(),side);
        float a=new Vector3f(centreLocal).sub(EvaRigTransforms.pivot(upper)).length()*scale;
        float b=EvaRigTransforms.pivot(hand).sub(centreLocal).length()*scale;
        var direction=new Vector3f(target).sub(shoulder);float distance=direction.length();if(distance<.001F)return preferred;direction.div(distance);
        distance=Math.max(Math.abs(a-b)+.001F,Math.min(a+b-.001F,distance));
        float along=(a*a-b*b+distance*distance)/(2*distance),radius=(float)Math.sqrt(Math.max(0,a*a-along*along));
        var centre=new Vector3f(shoulder).fma(along,direction);var vertical=new Vector3f(0,1,0).fma(-direction.y,direction);
        if(vertical.lengthSquared()<.001F||radius<.001F)return preferred;vertical.normalize();
        float cosine=net.minecraft.util.Mth.clamp((height-centre.y)/(radius*vertical.y),-.999F,.999F);float sine=(float)Math.sqrt(1-cosine*cosine);
        var sideAxis=new Vector3f(direction).cross(vertical);var first=new Vector3f(vertical).mul(cosine).fma(sine,sideAxis);
        var second=new Vector3f(vertical).mul(cosine).fma(-sine,sideAxis);
        var chosen=first.dot(preferred)>second.dot(preferred)?first:second;
        return new Vector3f(preferred).normalize().lerp(chosen,weight);
    }
}
