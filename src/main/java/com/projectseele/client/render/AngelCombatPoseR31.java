package com.projectseele.client.render;

import com.projectseele.entity.*;
import net.minecraft.world.entity.LivingEntity;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import software.bernie.geckolib.cache.object.GeoBone;
import java.util.*;

/** Full-proportion reaction poses, layered after the shared contact animation. */
public final class AngelCombatPoseR31
{
    private record Pose(float x,float y,float z,float px,float py,float pz,float sx,float sy,float sz)
    {
        static Pose read(GeoBone b){return new Pose(b.getRotX(),b.getRotY(),b.getRotZ(),b.getPosX(),b.getPosY(),b.getPosZ(),b.getScaleX(),b.getScaleY(),b.getScaleZ());}
        void write(GeoBone b){b.setRotX(x);b.setRotY(y);b.setRotZ(z);b.setPosX(px);b.setPosY(py);b.setPosZ(pz);b.setScaleX(sx);b.setScaleY(sy);b.setScaleZ(sz);}
    }
    private static final Map<BakedGeoModel,Map<String,Pose>> BASE=new WeakHashMap<>();
    private static final com.projectseele.util.WeakIdentityMap<LivingEntity,Frame> FRAMES=new com.projectseele.util.WeakIdentityMap<>();
    private static final class Frame {Map<String,Pose> last=Map.of(),held=Map.of();long beat=-1;}
    private static boolean handles(LivingEntity actor){return actor instanceof SachielEntity||actor instanceof ShamshelEntity;}
    static boolean needsGroundSupport(LivingEntity actor)
    {
        if(actor instanceof ShamshelEntity shamshel)return com.projectseele.physics.ShamshelContactPoseR48.groundSupport(shamshel);
        if(com.projectseele.physics.CombatBodyDynamics.active(actor))return false;
        var beat=CombatFeelR31.beat(actor);if(!handles(actor)||beat==null||beat.kind()!=CombatFeelR31.DOWN)return false;
        if(actor.onGround())return true;
        var b=actor.getBoundingBox();return actor.level().getBlockCollisions(actor,new net.minecraft.world.phys.AABB(b.minX+.1,b.minY-.15,b.minZ+.1,b.maxX-.1,b.minY+.01,b.maxZ-.1)).iterator().hasNext();
    }
    private static void visit(GeoBone bone,java.util.function.Consumer<GeoBone> action){action.accept(bone);bone.getChildBones().forEach(b->visit(b,action));}
    private static Map<String,Pose> capture(BakedGeoModel model){Map<String,Pose> result=new HashMap<>();model.topLevelBones().forEach(b->visit(b,v->result.put(v.getName(),Pose.read(v))));return result;}
    private static void write(BakedGeoModel model,Map<String,Pose> poses){poses.forEach((name,p)->model.getBone(name).ifPresent(p::write));}
    static void restoreBeforeGecko(LivingEntity actor,BakedGeoModel model)
    {if(handles(actor)){var old=BASE.remove(model);if(old!=null)write(model,old);}}
    static void rememberGecko(LivingEntity actor,BakedGeoModel model)
    {if(handles(actor))BASE.put(model,capture(model));}
    private static void rotate(BakedGeoModel model,String name,float x,float y,float z)
    {model.getBone(name).ifPresent(b->{b.setRotX(b.getRotX()+x);b.setRotY(b.getRotY()+y);b.setRotZ(b.getRotZ()+z);});}

    public static void apply(LivingEntity actor,BakedGeoModel model,float partial)
    {
        if(!handles(actor)||actor instanceof SachielEntity sachiel&&sachiel.isFirstBattleActive())return;
        Frame frame=FRAMES.computeIfAbsent(actor,e->new Frame());var beat=CombatFeelR31.beat(actor);
        if(beat!=null&&CombatFeelR31.hitPaused(actor))
        {
            if(frame.beat!=beat.start()){frame.beat=beat.start();frame.held=frame.last;}
            if(!frame.held.isEmpty()){write(model,frame.held);return;}
        }
        if(actor instanceof ShamshelEntity shamshel)
        {
            model.topLevelBones().forEach(root->visit(root,b->{
                var r=com.projectseele.physics.ShamshelContactPoseR48.reaction(shamshel,b.getName(),
                        new Vector3f(b.getRotX(),b.getRotY(),b.getRotZ()),partial);
                b.setRotX(r.x);b.setRotY(r.y);b.setRotZ(r.z);
            }));
            frame.last=capture(model);return;
        }
        if(EvaCombatR31.holds(actor))
        {
            float held=AngelGrappleSurfaceR31.heldWeight(actor,partial);
            rotate(model,"torso_upper",-.18F*held,0,0);rotate(model,"head",-.12F*held,0,0);
            if(actor instanceof ShamshelEntity)
            {
                rotate(model,"body",-.18F*held,0,0);
                for(String side:new String[]{"l","r"})for(int segment=0;segment<4;segment++)
                    rotate(model,"whip_"+side+"_"+segment,(segment==0?.4F:.12F)*held,0,(side.equals("l")?.1F:-.1F)*held);
            }
            for(String side:new String[]{"l","r"})
            {rotate(model,"arm_"+side,.65F*held,0,(side.equals("l")?.35F:-.35F)*held);rotate(model,"forearm_"+side,2.5F*held,0,0);rotate(model,"leg_"+side,-.18F*held,0,0);rotate(model,"shin_"+side,.33F*held,0,0);}
        }
        else if(beat!=null&&beat.kind()!=CombatFeelR31.CONTACT)
        {
            float age=CombatFeelR31.age(actor,partial),end=beat.duration();
            Vector3f direction=beat.direction().toVector3f().rotateY((float)-Math.toRadians(180-actor.yBodyRot));
            float length=(float)Math.sqrt(direction.x*direction.x+direction.z*direction.z);
            float dx=length<.001F?0:direction.x/length,dz=length<.001F?1:direction.z/length;
            if(beat.kind()==CombatFeelR31.DOWN||beat.kind()==CombatFeelR31.THROWN)
            {
                float falling=(float)CombatMotionR29.ease(age/(beat.kind()==CombatFeelR31.THROWN?7:12));
                float rise=beat.kind()==CombatFeelR31.THROWN?0:(float)CombatMotionR29.ease((age-(end-20))/20);
                float weight=falling*(1-rise),angle=weight*(beat.kind()==CombatFeelR31.THROWN?1.12F:1.42F);
                rotate(model,"root",angle*dz,0,-angle*dx);
                // RiggedAngelLayer supports the exact deformed mesh against
                // the floor. A guessed root offset let the broad body bury
                // itself when falling forward and float when falling back.
                rotate(model,"torso_lower",-.10F*weight,0,0);rotate(model,"torso_upper",.17F*weight,0,0);
                rotate(model,"head",-.20F*weight,0,0);
                for(String side:new String[]{"l","r"})
                {float s=side.equals("l")?1:-1;rotate(model,"arm_"+side,-.25F*weight,0,s*.34F*weight);rotate(model,"forearm_"+side,-.65F*weight,0,0);rotate(model,"leg_"+side,-.24F*weight,0,0);rotate(model,"shin_"+side,.48F*weight,0,0);}
                if(actor instanceof ShamshelEntity)
                {
                    // Slack whips fold alongside the body before contact.
                    // Leaving the active forward reach rigid made a far-away
                    // tip prop the complete torso twenty blocks above ground.
                    for(String side:new String[]{"l","r"})
                    {
                        float s=side.equals("l")?1:-1;
                        model.getBone("whip_"+side+"_0").ifPresent(b->{b.setRotX(b.getRotX()+(-.48F-b.getRotX())*weight);b.setRotY(b.getRotY()*(1-weight));b.setRotZ(b.getRotZ()+(s*.28F-b.getRotZ())*weight);});
                    }
                }
            }
            else
            {
                float accent=(float)CombatMotionR29.recoil(age)*beat.strength()*(beat.kind()==CombatFeelR31.STAGGER?.28F:.12F);
                rotate(model,"torso_lower",accent*dz*.3F,0,-accent*dx*.3F);
                rotate(model,"torso_upper",accent*dz*.7F,0,-accent*dx*.7F);
                rotate(model,"body",accent*dz,0,-accent*dx);rotate(model,"head",-accent*.45F,0,accent*dx*.25F);
                for(String side:new String[]{"l","r"})rotate(model,"arm_"+side,-accent*.6F,0,side.equals("l")?accent*.4F:-accent*.4F);
            }
        }
        frame.last=capture(model);
    }
    private AngelCombatPoseR31() {}
}
