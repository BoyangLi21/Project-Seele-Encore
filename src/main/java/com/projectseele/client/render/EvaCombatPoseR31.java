package com.projectseele.client.render;

import com.projectseele.entity.*;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix3f;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.*;
import java.util.*;

/** Final contact pose: real wrist chains meet the shared combat hand targets. */
public final class EvaCombatPoseR31
{
    private record BonePose(Quaternionf rotation,Vector3f position) {}
    private static final com.projectseele.util.WeakIdentityMap<EvaUnit01Entity,Map<String,BonePose>> FROZEN=new com.projectseele.util.WeakIdentityMap<>();
    private static final com.projectseele.util.WeakIdentityMap<EvaUnit01Entity,Long> STAMP=new com.projectseele.util.WeakIdentityMap<>();
    private static final com.projectseele.util.WeakIdentityMap<EvaUnit01Entity,Vec3[]> RELEASE=new com.projectseele.util.WeakIdentityMap<>();
    public static void resetEntityR31(EvaUnit01Entity e){FROZEN.remove(e);STAMP.remove(e);RELEASE.remove(e);}
    private static void rotate(BakedGeoModel m,String name,float x,float y,float z,float w,Set<String> changed)
    {m.getBone(name).ifPresent(b->{b.setRotX(b.getRotX()+x*w);b.setRotY(b.getRotY()+y*w);b.setRotZ(b.getRotZ()+z*w);changed.add(name);});}
    public static EvaMotionEngineV2.BoneWrites apply(EvaUnit01Entity e,BakedGeoModel m,float partial,Matrix4f root)
    {
        if(e.isNervLogisticsLocked()||e.isFirstBattleActive()||EvaShutdownR30.disabled(e))return EvaMotionEngineV2.BoneWrites.empty();
        Set<String> changed=new HashSet<>(),position=new HashSet<>();int action=EvaCombatR31.action(e);float age=EvaCombatR31.age(e,partial);
        if(EvaGameplayMotionR32.sharedBody(e,partial))
        {
            var body=EvaBodyPose.sample(e,partial);
            PhysicalBodyRenderer.pivots(body,m);
            boolean completeHands=EvaGameplayMotionR32.sharedHands(e,partial);
            for(String name:body.rig.keySet())if(completeHands||!name.startsWith("finger_"))m.getBone(name).ifPresent(b->{EvaRigTransforms.rotate(b,body.rotations.get(name));var p=body.positions.get(name);b.setPosX(-p.x*16);b.setPosY(p.y*16);b.setPosZ(p.z*16);changed.add(name);position.add(name);});
            if(!e.isBerserk()&&e.getWeapon()!=EvaUnit01Entity.WEAPON_RIFLE&&!(e instanceof EvaPrototypeEntity un&&un.isEyeLaserActive()))
                m.getBone("head").ifPresent(b->EvaRigTransforms.rotate(b,new Quaternionf(body.rotations.get("head")).rotateY(-e.pilotHeadYawForRender(partial)*Mth.DEG_TO_RAD).rotateX(-e.pilotHeadPitchForRender(partial)*Mth.DEG_TO_RAD)));
            if(com.projectseele.visual.CombatR31Review.ENABLED&&EvaCombatSupportR33.ready(e)&&EvaCombatSupportR33.strike(e))
                for(String side:new String[]{"l","r"})m.getBone("foot_"+side).ifPresent(b->{
                    var expected=EvaCombatSupportR33.anchor(e,side,partial);
                    if(expected!=null)com.projectseele.client.visual.CombatR31Client.toeSupport(e,side,new Vec3(EvaRigTransforms.point(b,EvaRigTransforms.pivot(b).add(EvaCombatSupportR33.toe(e,side)),root)),expected);
                });
            // Weapon and eye optics solve against the final airborne skeleton.
            // A full-body attack layer must not leave the gun on the prior arm pose.
            var rifle=EvaRifleContactRig.apply(e,m,partial,root);changed.addAll(rifle.rotationBones());position.addAll(rifle.positionBones());
            var optics=EvaUNLaserPose.apply(e,m,root);changed.addAll(optics.rotationBones());
            return new EvaMotionEngineV2.BoneWrites(Set.copyOf(changed),Set.copyOf(position),"MOTION_ENGINE_LIVE_ACTION");
        }
        String capture=switch(action){case EvaCombatR31.REACH,EvaCombatR31.HOLD->"r31_grapple_start";case EvaCombatR31.THROW->"r31_shoulder_throw";case EvaCombatR31.AIR_STRIKE,EvaCombatR31.AIR_SLAM,EvaCombatR31.LAND->"r31_air_downstrike";default->"";};
        boolean captured=!capture.isEmpty()&&EvaBodyPose.combatCaptureReadyR31(e,capture);
        if(captured)
        {
            var body=EvaBodyPose.sample(e,partial);
            for(String name:body.rig.keySet())if(!name.startsWith("finger_"))m.getBone(name).ifPresent(b->{EvaRigTransforms.rotate(b,body.rotations.get(name));var p=body.positions.get(name);b.setPosX(-p.x*16);b.setPosY(p.y*16);b.setPosZ(p.z*16);changed.add(name);position.add(name);});
        }
        if(action!=EvaCombatR31.NONE)
        {
            float w=(float)CombatMotionR29.ease(age/6);
            if(action==EvaCombatR31.AIR_STRIKE)
            {
                w*=1-(float)CombatMotionR29.ease((age-20)/7);
                float drive=(float)CombatMotionR29.ease((age-4)/7);rotate(m,"torso_upper",-.12F,-.30F*drive,0,w,changed);
                if(!captured){rotate(m,"leg_l",.55F,0,-.08F,w,changed);rotate(m,"shin_l",-.8F,0,0,w,changed);
                rotate(m,"leg_r",-.18F,0,.07F,w,changed);rotate(m,"forearm_l",1.2F,0,.15F,w,changed);}
                hand(e,m,"r",EvaCombatR31.aerialHand(e,partial),e.getForward().multiply(1,0,1).normalize().toVector3f(),w,root,changed,position);
            }
            else if(action==EvaCombatR31.AIR_SLAM)
            {
                if(!captured){
                rotate(m,"torso_upper",.16F,0,0,w,changed);rotate(m,"leg_l",.55F,0,-.1F,w,changed);rotate(m,"leg_r",.55F,0,.1F,w,changed);
                for(String side:List.of("l","r"))
                {rotate(m,"shin_"+side,-.9F,0,0,w,changed);rotate(m,"arm_"+side,2.5F,0,side.equals("l")?.20F:-.20F,w,changed);rotate(m,"forearm_"+side,.9F,0,0,w,changed);}
                }
            }
            else if(action==EvaCombatR31.LAND)
            {
                float weight=(float)Math.sin(Math.PI*Mth.clamp(age/12,0,1));rotate(m,"torso_upper",.22F,0,0,weight,changed);
                for(String side:List.of("l","r")){rotate(m,"leg_"+side,.3F,0,0,weight,changed);rotate(m,"shin_"+side,-.55F,0,0,weight,changed);}
            }
            else
            {
                var victim=EvaCombatR31.target(e);
                if(victim!=null)
                {
                    float reach=action==EvaCombatR31.REACH?(float)CombatMotionR29.ease(age/18):1;
                    if(action==EvaCombatR31.THROW)reach*=1-(float)CombatMotionR29.ease((age-20)/6);
                    float throwing=action==EvaCombatR31.THROW?(float)CombatMotionR29.ease(age/13):0;
                    rotate(m,"torso_lower",-.08F,.12F*throwing,0,w,changed);rotate(m,"torso_upper",.08F-.32F*throwing,-.25F*throwing,0,w,changed);
                    Vec3 f=e.getForward().multiply(1,0,1).normalize(),r=f.cross(new Vec3(0,1,0));
                    if(action==EvaCombatR31.HOLD||action==EvaCombatR31.THROW&&age<=16)
                        RELEASE.put(e,new Vec3[]{EvaCombatR31.grip(e,victim,true,partial),EvaCombatR31.grip(e,victim,false,partial)});
                    for(String side:List.of("l","r"))
                    {
                        boolean left=side.equals("l");Vec3 target=EvaCombatR31.grip(e,victim,left,partial);
                        if(action==EvaCombatR31.THROW&&age>16)
                        {
                            var release=RELEASE.get(e);Vec3 from=release==null?target:release[left?0:1];
                            var follow=e.getPosition(partial).add(0,48-9*throwing,0).add(f.scale(18+6*throwing)).add(r.scale(left?-5:5));
                            target=from.lerp(follow,CombatMotionR29.ease((age-16)/8));
                        }
                        var surface=AngelGrappleSurfaceR31.contact(victim,left,partial);
                        Vec3 normal=surface==null?r.scale(left?1:-1):surface.outwardNormal().multiply(-1,0,-1).normalize();
                        hand(e,m,side,target,normal.toVector3f(),reach,root,changed,position);
                    }
                }
            }
        }
        var beat=CombatFeelR31.beat(e);
        if(beat!=null&&beat.kind()==CombatFeelR31.STAGGER&&!e.isPilotProne()&&!e.isPilotCrouching()&&e.onGround())
        {
            var body=EvaBodyPose.sample(e,partial);
            for(String side:List.of("l","r"))for(String prefix:List.of("leg_","shin_","ankle_","foot_"))
            {
                String name=prefix+side;m.getBone(name).ifPresent(b->{EvaRigTransforms.rotate(b,body.rotations.get(name));var p=body.positions.get(name);b.setPosX(-p.x*16);b.setPosY(p.y*16);b.setPosZ(p.z*16);changed.add(name);position.add(name);});
            }
        }
        if(beat!=null&&(beat.kind()==CombatFeelR31.DOWN||beat.kind()==CombatFeelR31.THROWN))
        {
            float weight=1;
            var body=EvaBodyPose.sample(e,partial);
            for(var n:body.rig.keySet())m.getBone(n).ifPresent(b->{
                var q=new Quaternionf().rotationZYX(b.getRotZ(),b.getRotY(),b.getRotX()).slerp(body.rotations.get(n),weight);EvaRigTransforms.rotate(b,q);
                var p=body.positions.get(n);b.setPosX(Mth.lerp(weight,b.getPosX(),-p.x*16));b.setPosY(Mth.lerp(weight,b.getPosY(),p.y*16));b.setPosZ(Mth.lerp(weight,b.getPosZ(),p.z*16));changed.add(n);position.add(n);
            });
        }
        if(action!=EvaCombatR31.NONE)
        {
            for(String side:List.of("l","r"))
            {
                m.getBone("shin_"+side).ifPresent(b->{EvaRigTransforms.hinge(b,EvaRigTransforms.knee(b));position.add(b.getName());});
                m.getBone("forearm_"+side).ifPresent(b->{EvaRigTransforms.hinge(b,EvaRigTransforms.elbow(b,side));position.add(b.getName());});
            }
        }
        if(beat!=null&&CombatFeelR31.hitPaused(e))
        {
            var all=new ArrayList<GeoBone>();m.getBone("root").ifPresent(b->collect(b,all));
            if(STAMP.getOrDefault(e,Long.MIN_VALUE)!=beat.start())
            {
                Map<String,BonePose> pose=new HashMap<>();for(var b:all)pose.put(b.getName(),new BonePose(new Quaternionf().rotationZYX(b.getRotZ(),b.getRotY(),b.getRotX()),new Vector3f(b.getPosX(),b.getPosY(),b.getPosZ())));
                FROZEN.put(e,pose);STAMP.put(e,beat.start());
            }
            for(var b:all){var held=FROZEN.get(e).get(b.getName());if(held==null)continue;EvaRigTransforms.rotate(b,held.rotation);b.setPosX(held.position.x);b.setPosY(held.position.y);b.setPosZ(held.position.z);changed.add(b.getName());position.add(b.getName());}
        }
        return new EvaMotionEngineV2.BoneWrites(Set.copyOf(changed),Set.copyOf(position),"MOTION_ENGINE_LIVE_ACTION");
    }
    private static void collect(GeoBone b,List<GeoBone> all){all.add(b);for(var child:b.getChildBones())collect(child,all);}
    private static Matrix3f frame(Vector3f y,Vector3f x)
    {y=new Vector3f(y).normalize();x=new Vector3f(x).sub(new Vector3f(y).mul(x.dot(y))).normalize();return new Matrix3f().setColumn(0,x).setColumn(1,y).setColumn(2,new Vector3f(x).cross(y));}
    private static void hand(EvaUnit01Entity e,BakedGeoModel m,String side,Vec3 contact,Vector3f palmNormal,float weight,Matrix4f root,Set<String> changed,Set<String> position)
    {
        var upper=m.getBone("arm_"+side).orElse(null);var lower=m.getBone("forearm_"+side).orElse(null);var wrist=m.getBone("wrist_"+side).orElse(null);var hand=m.getBone("hand_"+side).orElse(null);
        if(upper==null||lower==null||wrist==null||hand==null||root==null)return;
        var middle=m.getBone("finger_middle_"+side).orElse(hand);var index=m.getBone("finger_index_"+side).orElse(hand);var little=m.getBone("finger_little_"+side).orElse(hand);
        var along=EvaRigTransforms.pivot(middle).sub(EvaRigTransforms.pivot(hand));if(along.lengthSquared()<1e-8)along.set(0,-1,0);
        var across=EvaRigTransforms.pivot(index).sub(EvaRigTransforms.pivot(little));if(across.lengthSquared()<1e-8)across.set(1,0,0);
        Vector3f desiredY=new Vector3f(0,1,0),desiredZ=new Vector3f(palmNormal);if(Math.abs(desiredY.dot(desiredZ))>.9F)desiredZ.set(0,0,1);
        var desiredX=new Vector3f(desiredY).cross(desiredZ).normalize();var q=new Quaternionf().setFromNormalized(frame(desiredY,desiredX).mul(frame(along,across).transpose()));
        var target=contact.toVector3f().sub(q.transform(new Vector3f(along).mul(.62F*EvaScale.RENDER_SCALE)));
        var bones=new GeoBone[]{upper,lower,wrist,hand};Map<GeoBone,BonePose> before=new HashMap<>();for(var b:bones)before.put(b,new BonePose(new Quaternionf().rotationZYX(b.getRotZ(),b.getRotY(),b.getRotX()),new Vector3f(b.getPosX(),b.getPosY(),b.getPosZ())));
        EvaRigTransforms.solveArm(upper,lower,wrist,hand,side,target,q,new Vector3f(side.equals("l")?1:-1,-1,0),root);
        for(var b:bones){var old=before.get(b);EvaRigTransforms.rotate(b,new Quaternionf(old.rotation).slerp(new Quaternionf().rotationZYX(b.getRotZ(),b.getRotY(),b.getRotX()),weight));b.setPosX(Mth.lerp(weight,old.position.x,b.getPosX()));b.setPosY(Mth.lerp(weight,old.position.y,b.getPosY()));b.setPosZ(Mth.lerp(weight,old.position.z,b.getPosZ()));changed.add(b.getName());position.add(b.getName());}
        var palm=EvaRigTransforms.pivot(hand).fma(.62F,along);var actual=EvaRigTransforms.point(hand,palm,root);
        com.projectseele.client.visual.CombatR31Client.handWitness(e,side,new Vec3(actual),contact,weight);
    }
    private EvaCombatPoseR31() {}
}
