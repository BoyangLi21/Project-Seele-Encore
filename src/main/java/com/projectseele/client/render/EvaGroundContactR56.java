package com.projectseele.client.render;

import com.projectseele.entity.EvaAirTransportR31;
import com.projectseele.entity.EvaBodyPose;
import com.projectseele.entity.EvaScale;
import com.projectseele.entity.EvaShutdownR30;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.client.Minecraft;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * The drawn body rests on the ground, whichever pose owner drew it.
 * <p>
 * A planted foot lies flat on its sole instead of balancing on a heel or
 * toe edge. Then the lowest part of the body, sole, knee, elbow, hand or
 * chest, is brought onto the ground: blending from standing to lying left
 * the folded body hanging up to five blocks in the air before it dropped.
 */
final class EvaGroundContactR56
{
    static final String[] PARTS=EvaMeshPointsR63.PARTS;
    /** Rest-pose hull samples per part (model units): the extremes along 26 directions. */
    private record Ankle(float x,float z,long time,float planted,float rate) {}
    /** Last ankle position per EVA and side (world), its frame time and planted weight. */
    private static final Map<String,Ankle> ANKLES=new HashMap<>();
    /** Stiffness (1/s) of the critically damped spring that settles a foot onto, or lifts it off, the ground. */
    private static final float PLANT_RATE=18F;
    /** The other foot this high (blocks) means double support; this high, mid-swing. */
    private static final float STANCE_LOW=1.5F,STANCE_HIGH=5F;
    /** A sole this far above the ground still counts as planted (blocks), fading out by the second. */
    private static final float PLANT_NEAR=.3F,PLANT_FAR=1.8F;
    /**
     * An ankle moving faster than this (blocks per second) is swinging, not
     * planted. Kept well above a stance foot that skates with the clip: a
     * lower bar switched planted feet on and off between frames.
     */
    private static final float PLANT_SLOW=30F,PLANT_FAST=60F;
    /** Shin tilt from vertical (degrees) up to which the sole lies level, and from which the foot stands on its toes. */
    private static final float LEVEL_SHIN=40,INSTEP_SHIN=70;
    /**
     * Ankle extension (foot rotX from the shin, degrees) of a foot behind a lying
     * shin: down on its toes. Pointed flat onto its instep, the ankle cuff stood
     * out under the leg like broken armour and the toes hung off the ground.
     */
    private static final float INSTEP_POINT=Float.parseFloat(System.getProperty("projectseele.proneFootR56","-42"));
    /** The body is lowered at most this far onto the ground, and raised at most the second (blocks). */
    private static final float MAX_DROP=8F,MAX_LIFT=3F;

    static void apply(EvaUnit01Entity eva,BakedGeoModel model,float partial,Matrix4f root)
    {
        if(root==null||!applies(eva))return;
        var hulls=hulls(eva);
        if(hulls.isEmpty())return;
        float ground=root.m31();
        long now=com.projectseele.client.AircraftRenderClockR21.frameNanos();
        // Feet are judged against the floor the body is about to be set on:
        // a folding body hanging in the air still stands on its feet.
        float floor=lowest(model,root,hulls);
        if(!Float.isFinite(floor))return;
        float floorL=footFloor(eva,"l",ground,floor),floorR=footFloor(eva,"r",ground,floor);
        float left=soleHeight(eva,model,root,hulls,"l")-floorL,right=soleHeight(eva,model,root,hulls,"r")-floorR;
        float walking=eva.isPilotProne()?0:Mth.clamp(eva.rifleMoveBlend(partial),0,1);
        settleFoot(eva,model,root,hulls,"l",floorL,right,now,walking);
        settleFoot(eva,model,root,hulls,"r",floorR,left,now,walking);
        float support=clearanceAboveFeet(eva,model,root,hulls,ground),sinkWanted=0;
        for(String side:new String[]{"l","r"})
        {
            double under=EvaFootPlacement.groundUnder(eva,side);
            float sole=soleHeight(eva,model,root,hulls,side);
            if(!Double.isFinite(under)||Math.abs(under-ground)<=.5){support=Math.min(support,sole-ground);continue;}
            // A sole on ground of its own only holds the body up. Measured against the drawn ground,
            // one on a ledge pulled the body down onto it, and one on lower ground lifted the whole
            // body three blocks off the leg that was already reaching for its footing.
            support=Math.min(support,Math.max(0,sole-(float)under));
            var last=ANKLES.get(eva.getId()+side);
            // A planted leg that still cannot reach the lower ground takes the pelvis down with it.
            if(under<ground-.5&&last!=null)sinkWanted=Math.max(sinkWanted,(sole-(float)under)*step((last.planted()-.1F)/.3F));
        }
        // A run stands on its stance feet alone, by the clip's support mask: its body leaves the ground.
        float flight=EvaBodyPose.gaitFlight(eva,partial);
        float gap=Mth.clamp(support,-MAX_LIFT,MAX_DROP)*(1-flight);
        var base=model.getBone("root").orElse(null);
        if(base==null)return;
        // Root offsets are model pixels; the world frame only turns and scales.
        float grounded=base.getPosY()-gap*16/EvaScale.RENDER_SCALE;
        float sink=easeSink(eva,sinkWanted,now);
        // How far the ground under either sole lies from the drawn plane, 0 on level ground to 1.
        float uneven=0;
        for(String side:new String[]{"l","r"})
        {
            double under=EvaFootPlacement.groundUnder(eva,side);
            if(Double.isFinite(under))uneven=Math.max(uneven,Mth.clamp(((float)Math.abs(under-ground)-.5F)/1.5F,0,1));
        }
        float drawn=base.getPosY()+easeGrounding(eva,-gap*16/EvaScale.RENDER_SCALE,walking,now,uneven)+EvaBodyWeightR59.pelvis(eva,partial,now,walking)-sink*16/EvaScale.RENDER_SCALE;
        base.setPosY(drawn);
        if(com.projectseele.client.visual.EvaConnectedActionReview.ENABLED)
        {
            // Review witness: drawn plane, floor, per sole height over its floor and ground under it, support,
            // gap, sink wanted and eased, flight, walking, planted shares, root offset over the grounded one.
            var l=ANKLES.get(eva.getId()+"l");var r=ANKLES.get(eva.getId()+"r");
            if(EvaFootPlacement.GROUNDING.size()>32)EvaFootPlacement.GROUNDING.clear();
            EvaFootPlacement.GROUNDING.put(eva.getId(),new double[]{ground,floor,left,right,EvaFootPlacement.groundUnder(eva,"l"),EvaFootPlacement.groundUnder(eva,"r"),support,gap,sinkWanted,sink,flight,walking,
                    l==null?-1:l.planted(),r==null?-1:r.planted(),(drawn-grounded)*EvaScale.RENDER_SCALE/16});
        }
        // The eased pelvis sits this far above (+) or below (-) the grounded
        // one: planted legs take up the difference so their soles stay down.
        float lift=(drawn-grounded)*EvaScale.RENDER_SCALE/16;
        for(String side:new String[]{"l","r"})
        {
            var last=ANKLES.get(eva.getId()+side);
            if(last==null||last.planted()<=.1F)continue;
            // On ground of its own a planted sole is set on that ground wherever the pelvis went.
            double under=EvaFootPlacement.groundUnder(eva,side);
            float drop=Double.isFinite(under)&&Math.abs(under-ground)>.5?soleHeight(eva,model,root,hulls,side)-(float)under:lift;
            // A stance foot takes the whole difference; a partial share
            // left the sole floating while the foot eased onto the ground.
            if(Math.abs(drop)>.01F)reachGround(model,root,side,drop*step((last.planted()-.1F)/.3F));
        }
        if(flight>.01F)for(String side:new String[]{"l","r"})
        {
            float contact=EvaBodyWeightR59.contact(eva,side);
            if(contact<=.01F)continue;
            double under=EvaFootPlacement.groundUnder(eva,side);
            float floorHere=Double.isFinite(under)&&under>ground+.5?(float)under:ground;
            float gapHere=soleHeight(eva,model,root,hulls,side)-floorHere;
            // It lets go as the clip lifts the foot: held down to the end of the window,
            // the leg straightened and the knee snapped back in the frame it was released.
            reachGround(model,root,side,gapHere*contact*(1-step((Math.abs(gapHere)-PIN_NEAR)/(PIN_FAR-PIN_NEAR))));
        }
    }

    /**
     * The last word on the floor, after every layer that may turn a leg: a sole
     * under the ground is raised by bending its own leg. Blends, follow-through
     * and joint limits each moved a foot after it had been set down, and a
     * kneeling foot sat two blocks under the road for half a second.
     */
    static void keepSolesUp(EvaUnit01Entity eva,BakedGeoModel model,Matrix4f root)
    {
        if(root==null||!applies(eva))return;
        var hulls=hulls(eva);
        if(hulls.isEmpty())return;
        float ground=root.m31();
        for(String side:new String[]{"l","r"})
        {
            double under=EvaFootPlacement.groundUnder(eva,side);
            float floor=Double.isFinite(under)?(float)under:ground;
            float depth=soleHeight(eva,model,root,hulls,side)-floor;
            if(depth<0)reachGround(model,root,side,depth);
        }
    }

    /** A running sole this far off the ground (blocks) is held to it, fading out by the second. */
    private static final float PIN_NEAR=.5F,PIN_FAR=2.2F;
    private record Grounding(float offset,float speed,long time,float uneven) {}
    private static final Map<Integer,Grounding> PELVIS=new HashMap<>();
    /** Stiffness (1/s) of the walking grounding spring, and its largest lag behind the grounding offset (model pixels). */
    private static final float PELVIS_RATE=18F,PELVIS_LAG=1.1F;
    /**
     * On uneven ground the offset may lag this much further (model pixels), let go of over the
     * given time (seconds) once the ground is level again. Which sole holds the body up changes
     * with every terrace there, by up to three blocks at once; held within the walking lag, the
     * whole body jumped that far in a frame.
     */
    private static final float PELVIS_LAG_UNEVEN=14F,UNEVEN_RELEASE=.6F;

    /**
     * Walking, the grounding offset (not the pelvis height) follows through a
     * critically damped spring: a jump in which sole is lowest eases, while
     * the clip's own rise and fall reaches the screen unfiltered. Easing the
     * height lagged that bob by a third of a block, and the stance legs were
     * bent every frame to take it up.
     */
    private static float easeGrounding(EvaUnit01Entity eva,float offset,float walking,long now,float unevenNow)
    {
        var last=PELVIS.get(eva.getId());
        if(last!=null&&last.time()==now)
        {
            float held=PELVIS_LAG+PELVIS_LAG_UNEVEN*last.uneven();
            return Mth.lerp(walking,offset,Mth.clamp(last.offset(),offset-held,offset+held));
        }
        float dt=last==null?0:(now-last.time())/1e9F;
        float uneven=unevenNow;
        if(last!=null&&dt>0&&dt<.25F)uneven=Math.max(unevenNow,last.uneven()*(float)Math.exp(-dt/UNEVEN_RELEASE));
        float lag=PELVIS_LAG+PELVIS_LAG_UNEVEN*uneven;
        float eased=offset,speed=0;
        if(last!=null&&dt>0&&dt<.25F)
        {
            float error=last.offset()-offset,step=(last.speed()+PELVIS_RATE*error)*dt,decay=(float)Math.exp(-PELVIS_RATE*dt);
            eased=offset+(error+step)*decay;
            speed=(last.speed()-PELVIS_RATE*step)*decay;
        }
        eased=Mth.clamp(eased,offset-lag,offset+lag);
        if(PELVIS.size()>32)PELVIS.clear();
        PELVIS.put(eva.getId(),new Grounding(eased,speed,now,uneven));
        return Mth.lerp(walking,offset,eased);
    }

    private record Sink(float value,long time) {}
    private static final Map<Integer,Sink> SINKS=new HashMap<>();
    /** How far the pelvis goes down for a leg on lower ground (blocks), and how fast it goes down and comes back (1/s). */
    private static final float MAX_SINK=8F,SINK_DOWN=14F,SINK_UP=5F;

    /** Goes down quickly, for the foot that needs the ground, and comes back slowly, so it does not bob with each stride. */
    private static float easeSink(EvaUnit01Entity eva,float wanted,long now)
    {
        wanted=Mth.clamp(wanted,0,MAX_SINK);
        var last=SINKS.get(eva.getId());
        if(last!=null&&last.time()==now)return last.value();
        float value=wanted;
        if(last!=null)
        {
            float dt=(now-last.time())/1e9F;
            if(dt<.25F)value=last.value()+(wanted-last.value())*(1-(float)Math.exp(-dt*(wanted>last.value()?SINK_DOWN:SINK_UP)));
        }
        if(SINKS.size()>32)SINKS.clear();
        SINKS.put(eva.getId(),new Sink(value,now));
        return value;
    }

    /** The ground a foot is judged against: its own where that differs from the drawn plane, else the floor below the body. */
    private static float footFloor(EvaUnit01Entity eva,String side,float ground,float floor)
    {
        double under=EvaFootPlacement.groundUnder(eva,side);
        return Double.isFinite(under)&&Math.abs(under-ground)>.5?(float)under:floor;
    }

    /** Bend or reach a planted leg so its sole moves down by {@code drop} blocks (up when negative). */
    static void reachGround(BakedGeoModel model,Matrix4f root,String side,float drop)
    {
        var leg=model.getBone("leg_"+side).orElse(null);var shin=model.getBone("shin_"+side).orElse(null);
        var ankle=model.getBone("ankle_"+side).orElse(null);var foot=model.getBone("foot_"+side).orElse(null);
        if(leg==null||shin==null||ankle==null||foot==null)return;
        var footWorld=new Matrix4f(root).mul(EvaRigTransforms.model(foot));
        var target=EvaRigTransforms.point(foot,EvaRigTransforms.pivot(foot),root).add(0,-drop,0);
        var hip=EvaRigTransforms.point(leg,EvaRigTransforms.pivot(leg),root);
        var knee=EvaRigTransforms.point(leg,EvaRigTransforms.knee(shin),root);
        // A drop of a hair fades in rather than switching the solver on.
        EvaRigTransforms.solveLegFaded(leg,shin,ankle,foot,target,EvaRigTransforms.rotation(footWorld),knee.sub(hip),root,Math.min(1,Math.abs(drop)/.15F));
    }

    static boolean applies(EvaUnit01Entity eva)
    {
        // A ledge climb hangs on its hands and the foot set on the top, not on
        // the ground below: lowered onto its dangling foot, the body sank five
        // blocks and the foot on the top went into it.
        return eva.isPoweredOn()&&!eva.isCrucified()&&!eva.hasActiveCarrierMotion()&&!eva.isFirstBattleActive()
                &&!com.projectseele.entity.EvaFieldActionsR45.CLIMB.equals(com.projectseele.entity.EvaFieldActionsR45.clip(eva))
                &&!eva.isVisuallyAirborneForRender()&&!eva.isNervLogisticsLocked()&&!eva.isLaunchSequenceActive()
                &&eva.getActivationTicks()<=0&&eva.getVisualPose()==0&&!EvaShutdownR30.displayed(eva)
                &&!EvaAirTransportR31.active(eva)&&!com.projectseele.physics.CombatBodyDynamics.active(eva)
                &&(!eva.isExperimentalUnit()||EvaBodyPose.hasOwnUnRig(eva));
    }

    /**
     * Rest a foot that is on the ground the way its shin allows. Over a steep
     * shin (standing, squatting, the front foot of a kneel) the sole lies
     * level; under a shin lying along the ground (the rear leg of a kneel,
     * prone) it stands on its toes, pointing back and down.
     * Blending prone by its progress instead pointed the feet of a body still
     * squatting, which stood on its toe tips.
     */
    private static float soleHeight(BakedGeoModel model,Matrix4f root,Map<String,Vector3f[]> hulls,String side)
    {
        var foot=model.getBone("foot_"+side).orElse(null);var points=hulls.get("foot_"+side);
        return foot==null||points==null?Float.POSITIVE_INFINITY:lowest(new Matrix4f(root).mul(EvaRigTransforms.model(foot)),points);
    }

    /**
     * The height of a sole for comparing with the ground under it. On a slope that ground is a
     * line: each point of the sole is read against the line's height under it, so a sole lying
     * along the slope is on the ground and not a block and a half into it at its low end.
     */
    private static float soleHeight(EvaUnit01Entity eva,BakedGeoModel model,Matrix4f root,Map<String,Vector3f[]> hulls,String side)
    {
        double[] line=EvaFootPlacement.slopeUnder(eva,side);
        if(line==null)return soleHeight(model,root,hulls,side);
        var foot=model.getBone("foot_"+side).orElse(null);var points=hulls.get("foot_"+side);
        if(foot==null||points==null)return Float.POSITIVE_INFINITY;
        var matrix=new Matrix4f(root).mul(EvaRigTransforms.model(foot));var at=new Vector3f();
        float minimum=Float.POSITIVE_INFINITY;
        for(var p:points)
        {
            matrix.transformPosition(p,at);
            minimum=Math.min(minimum,at.y-(float)(line[2]*((at.x-line[3])*line[5]+(at.z-line[4])*line[6])));
        }
        return minimum;
    }

    private static void settleFoot(EvaUnit01Entity eva,BakedGeoModel model,Matrix4f root,Map<String,Vector3f[]> hulls,
                                   String side,float ground,float other,long now,float walking)
    {
        var foot=model.getBone("foot_"+side).orElse(null);var shin=model.getBone("shin_"+side).orElse(null);
        var points=hulls.get("foot_"+side);
        if(foot==null||shin==null||foot.getParent()==null||points==null)return;
        var matrix=new Matrix4f(root).mul(EvaRigTransforms.model(foot));
        float height=lowest(matrix,points)-ground;
        var ankle=matrix.transformPosition(EvaRigTransforms.pivot(foot));
        String key=eva.getId()+side;
        var last=ANKLES.get(key);
        float planted;
        if(last!=null&&last.time()==now)planted=last.planted();
        else
        {
            float dt=last==null?0:(now-last.time())/1e9F,speed=0;
            if(dt>0&&dt<.25F)speed=(float)Math.hypot(ankle.x-last.x(),ankle.z-last.z())/dt;
            float wanted=(1-step((height-PLANT_NEAR)/(PLANT_FAR-PLANT_NEAR)))*(1-step((speed-PLANT_SLOW)/(PLANT_FAST-PLANT_SLOW)));
            // A walking foot lies flat at mid-stance, while the other swings
            // high; at heel strike and push-off it keeps its roll. Lying, the
            // instep rests whatever the other foot does.
            float swing=step((other-STANCE_LOW)/(STANCE_HIGH-STANCE_LOW));
            wanted*=Mth.lerp(lying(model,side),swing,1);
            // Settle in and out through a spring that starts and stops
            // gently. A weight flickering with the frame-to-frame speed
            // snapped the foot between its poses; a plain exponential ease
            // still turned the foot ten to fifteen degrees in its first frame.
            float rate=0;
            if(dt>0&&dt<.25F)
            {
                float error=last.planted()-wanted,step=(last.rate()+PLANT_RATE*error)*dt,decay=(float)Math.exp(-PLANT_RATE*dt);
                planted=Mth.clamp(wanted+(error+step)*decay,0,1);
                rate=(last.rate()-PLANT_RATE*step)*decay;
            }
            else planted=wanted;
            if(ANKLES.size()>64)ANKLES.clear();
            ANKLES.put(key,new Ankle(ankle.x,ankle.z,now,planted,rate));
        }
        // A walking foot keeps the clip's heel strike and toe-off. Laid flat
        // each stance, its rolled edge rose up to a block and a half and the
        // grounded pelvis sank and sprang back at every footfall.
        float level=planted*(1-walking);
        if(level<=.01F)return;
        var modelRotation=EvaRigTransforms.rotation(EvaRigTransforms.model(foot));
        var parent=EvaRigTransforms.rotation(EvaRigTransforms.model(foot.getParent()));
        var up=modelRotation.transform(new Vector3f(0,1,0));
        // Flat on the ground it stands on: on a slope that is the slope's own plane, as far as the sole follows it.
        var normal=new Vector3f(0,1,0);
        double[] line=EvaFootPlacement.slopeUnder(eva,side);
        if(line!=null)
        {
            float rise=(float)Math.atan(line[2]);
            normal.set(-(float)line[5]*Mth.sin(rise),Mth.cos(rise),-(float)line[6]*Mth.sin(rise));
            root.invert(new Matrix4f()).transformDirection(normal).normalize();
        }
        var flat=new Quaternionf().rotationTo(up,normal).mul(modelRotation);
        float lying=lying(model,side);
        var instep=new Quaternionf(parent).mul(new Quaternionf().rotationX(INSTEP_POINT*Mth.DEG_TO_RAD));
        var wanted=new Quaternionf(modelRotation).slerp(new Quaternionf(flat).slerp(instep,lying),level);
        EvaRigTransforms.rotate(foot,parent.invert().mul(wanted));
    }

    /** How far the shin lies along the ground: 0 steep (sole level), 1 lying (on the toes). */
    private static float lying(BakedGeoModel model,String side)
    {
        var shin=model.getBone("shin_"+side).orElse(null);
        if(shin==null)return 0;
        // The shin runs from the knee down to the ankle along its local -Y.
        var along=EvaRigTransforms.rotation(EvaRigTransforms.model(shin)).transform(new Vector3f(0,-1,0));
        float tilt=(float)Math.toDegrees(Math.acos(Mth.clamp(-along.y,-1,1)));
        return step((tilt-LEVEL_SHIN)/(INSTEP_SHIN-LEVEL_SHIN));
    }

    /**
     * Review witness: the world height of the lowest point of the body as this frame draws it, and the index in
     * PARTS of the part it belongs to. On the unit's own hull points, whatever owns the pose: the offline scan has
     * no mesh for UN-00 and put a UN unit's bones on Unit-01's.
     */
    static void witnessLowestR63(EvaUnit01Entity eva,BakedGeoModel model,Matrix4f root)
    {
        if(root==null||!com.projectseele.client.visual.EvaConnectedActionReview.ENABLED)return;
        var hulls=hulls(eva);
        if(hulls.isEmpty())return;
        float lowest=Float.POSITIVE_INFINITY;int part=-1;
        for(int i=0;i<PARTS.length;i++)
        {
            var bone=model.getBone(PARTS[i]).orElse(null);var points=hulls.get(PARTS[i]);
            if(bone==null||points==null||bone.isHidden())continue;
            float y=lowest(new Matrix4f(root).mul(EvaRigTransforms.model(bone)),points);
            if(y<lowest){lowest=y;part=i;}
        }
        if(part<0)return;
        if(EvaFootPlacement.LOWEST_R63.size()>32)EvaFootPlacement.LOWEST_R63.clear();
        EvaFootPlacement.LOWEST_R63.put(eva.getId(),new double[]{lowest,part});
    }

    private static float lowest(BakedGeoModel model,Matrix4f root,Map<String,Vector3f[]> hulls)
    {
        float lowest=Float.POSITIVE_INFINITY;
        for(String name:PARTS)
        {
            var bone=model.getBone(name).orElse(null);var points=hulls.get(name);
            if(bone==null||points==null||bone.isHidden())continue;
            lowest=Math.min(lowest,lowest(new Matrix4f(root).mul(EvaRigTransforms.model(bone)),points));
        }
        return lowest;
    }

    /**
     * How far the lowest part of the body other than its soles is over the ground (+infinity if none
     * is known). A leg whose foot stands on lower ground of its own is over that ground, not the
     * drawn plane. Read against the plane, the shins of a unit standing on a hillside with both
     * feet below it counted as underground, and the whole body was raised off its feet: 1.2 blocks
     * on the review hill, the soles left that far over the ground they had just been set on.
     */
    private static float clearanceAboveFeet(EvaUnit01Entity eva,BakedGeoModel model,Matrix4f root,Map<String,Vector3f[]> hulls,float ground)
    {
        float least=Float.POSITIVE_INFINITY;
        for(String name:PARTS)
        {
            if(name.startsWith("foot_"))continue;
            var bone=model.getBone(name).orElse(null);var points=hulls.get(name);
            if(bone==null||points==null||bone.isHidden())continue;
            float floor=ground;
            if(name.startsWith("shin_")||name.startsWith("leg_"))
            {
                double under=EvaFootPlacement.groundUnder(eva,name.endsWith("_l")?"l":"r");
                if(Double.isFinite(under)&&under<ground-.5)floor=(float)under;
            }
            least=Math.min(least,lowest(new Matrix4f(root).mul(EvaRigTransforms.model(bone)),points)-floor);
        }
        return least;
    }

    private static float lowest(Matrix4f matrix,Vector3f[] points)
    {
        float minimum=Float.POSITIVE_INFINITY;
        for(var p:points)minimum=Math.min(minimum,matrix.m01()*p.x+matrix.m11()*p.y+matrix.m21()*p.z+matrix.m31());
        return minimum;
    }

    private static float step(float t)
    {
        t=Mth.clamp(t,0,1);
        return t*t*(3-2*t);
    }

    /** Reads the unit's hull samples now if no frame has needed them yet (taken from the mesh held for drawing). */
    static void warm(EvaUnit01Entity eva){hulls(eva);}
    private static Map<String,Vector3f[]> hulls(EvaUnit01Entity eva)
    {
        // Empty when the unit has no mesh to draw: it then stands as posed.
        return EvaMeshPointsR63.of(eva,PARTS).hulls();
    }

    private EvaGroundContactR56() {}
}
