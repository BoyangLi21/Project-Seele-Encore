package com.projectseele.client.render;
import com.google.gson.JsonParser;
import com.projectseele.entity.*;
import net.minecraft.client.Minecraft;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.phys.*;
import net.minecraft.world.phys.shapes.CollisionContext;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import java.util.*;

/** Small terrain corrections around planted soles, using the actual rendered coordinate frame. */
public final class EvaFootPlacement
{
    private static final Map<Integer,Map<String,Vector3f[]>> GEOMETRY=new HashMap<>();
    public static final Map<Integer,double[]> LAST=new HashMap<>();
    /** Per EVA, last frame: highest ground found under either sole, above the drawn ground (blocks). */
    private static final Map<Integer,Double> LEDGE=new HashMap<>();
    public static double ledgeUnderFoot(EvaUnit01Entity eva){return LEDGE.getOrDefault(eva.getId(),Double.NEGATIVE_INFINITY);}
    /** Per EVA and sole, this frame: world height of the ground found under it. */
    private static final Map<Integer,double[]> UNDER=new HashMap<>();
    /** The ground under a sole this frame (world y), or NaN. */
    public static double groundUnder(EvaUnit01Entity eva,String side)
    {
        var under=UNDER.get(eva.getId()*2+(side.equals("l")?0:1));
        return under!=null&&under[1]==com.projectseele.client.AircraftRenderClockR21.frameNanos()?under[0]:Double.NaN;
    }
    public static void clear(){GEOMETRY.clear();LAST.clear();}
    private static Map<String,Vector3f[]> feet(EvaUnit01Entity eva)
    {
        return GEOMETRY.computeIfAbsent(EvaBodyPose.rigKey(eva),v->{
            Map<String,Vector3f[]> result=new HashMap<>();
            String asset=eva.isExperimentalUnit()?eva.experimentalAssetName():"eva_unit0"+v;
            try(var reader=Minecraft.getInstance().getResourceManager().getResource(new ResourceLocation("projectseele","mesh/"+asset+".mesh.json")).orElseThrow().openAsReader())
            {
                var parts=JsonParser.parseReader(reader).getAsJsonObject().getAsJsonObject("parts");
                for(String side:List.of("l","r"))
                {
                    var part=parts.getAsJsonObject("foot_"+side);var p=part.getAsJsonArray("pivot");var a=part.getAsJsonArray("vertices");List<Vector3f> points=new ArrayList<>();
                    for(int i=0;i<a.size();i+=8)points.add(new Vector3f(-(a.get(i).getAsFloat()+p.get(0).getAsFloat())/16,(a.get(i+1).getAsFloat()+p.get(1).getAsFloat())/16,(a.get(i+2).getAsFloat()+p.get(2).getAsFloat())/16));
                    result.put(side,points.toArray(Vector3f[]::new));
                }
            }
            catch(Exception e){com.projectseele.ProjectSeele.LOGGER.warn("R11 foot support unavailable for variant {}",v,e);}
            return result;
        });
    }
    private static double ground(EvaUnit01Entity eva,Vector3f point)
    {
        // Reach a kerb up to a full step above the sole, or the ground a step below.
        Vec3 from=new Vec3(point.x,point.y+STEP+1,point.z),to=new Vec3(point.x,point.y-STEP-1,point.z);
        for(int i=0;i<5;i++)
        {
            var hit=eva.level().clip(new ClipContext(from,to,ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,eva));if(hit.getType()!=HitResult.Type.BLOCK)return Double.NaN;
            // Starting inside a block: a wall taller than a step stands over the
            // sole, not a kerb to stand on. Read as a 20-block ledge, it lifted
            // a foot pressed against a wall up into it.
            if(i==0&&hit.getLocation().y>point.y+STEP+.5)return Double.NaN;
            var pos=hit.getBlockPos();var s=eva.level().getBlockState(pos);var shape=s.getCollisionShape(eva.level(),pos,CollisionContext.of(eva));
            if(!EvaObstacleCollision.ignores(eva,s,pos,shape))return hit.getLocation().y;
            from=new Vec3(point.x,pos.getY()-.001,point.z);
        }
        return Double.NaN;
    }
    private static final Map<Integer,Long> RAN=new HashMap<>();
    /**
     * Run once this frame if no pose stage already did: every owner's soles
     * meet kerbs and steps, not only the firearm stage's.
     */
    static void ensure(EvaUnit01Entity eva,BakedGeoModel model,float partial,Matrix4f root)
    {
        Long ran=RAN.get(eva.getId());
        if(ran==null||ran!=com.projectseele.client.AircraftRenderClockR21.frameNanos())apply(eva,model,partial,root);
    }
    public static EvaMotionEngineV2.BoneWrites apply(EvaUnit01Entity eva,BakedGeoModel model,float partial,Matrix4f root)
    {
        if(RAN.size()>32)RAN.clear();
        RAN.put(eva.getId(),com.projectseele.client.AircraftRenderClockR21.frameNanos());
        LAST.remove(eva.getId());
        if(eva.hasLegacyStrikeForRender())return EvaMotionEngineV2.BoneWrites.empty();
        if(root==null||!eva.isPoweredOn()||eva.isCrucified()||eva.hasActiveCarrierMotion()||eva.isExperimentalUnit()&&!EvaBodyPose.hasOwnUnRig(eva)||eva.isFirstBattleActive()||eva.isVisuallyAirborneForRender()||eva.isNervLogisticsLocked()||eva.isLaunchSequenceActive()||eva.isBerserk()||eva.getActivationTicks()>0||eva.getVisualPose()!=0||eva.hasLiveActionForRender(partial)||eva.rifleStanceLevel(partial)>1.01F)return EvaMotionEngineV2.BoneWrites.empty();
        var mesh=feet(eva);Set<String> changed=new LinkedHashSet<>();double[] witness=new double[6];int index=0;double ledge=Double.NEGATIVE_INFINITY;
        float yaw=net.minecraft.util.Mth.rotLerp(partial,eva.yBodyRotO,eva.yBodyRot)*net.minecraft.util.Mth.DEG_TO_RAD;
        Vector3f forward=new Vector3f(-net.minecraft.util.Mth.sin(yaw),0,net.minecraft.util.Mth.cos(yaw));
        // A swinging foot crosses the ground at about twice the body's speed:
        // read far enough ahead that it is already up when it reaches the edge.
        float reach=(float)Math.max(REACH,Math.min(20,Math.hypot(eva.getX()-eva.xo,eva.getZ()-eva.zo)*20*.6));
        boolean stepping=com.projectseele.client.EvaStepSmoothingR57.offset(eva,partial)<-3;
        for(String s:List.of("l","r"))
        {
            var foot=model.getBone("foot_"+s).orElse(null);var leg=model.getBone("leg_"+s).orElse(null);var shin=model.getBone("shin_"+s).orElse(null);var ankle=model.getBone("ankle_"+s).orElse(null);
            if(foot==null||leg==null||shin==null||ankle==null||!mesh.containsKey(s))continue;
            Matrix4f matrix=new Matrix4f(root).mul(EvaRigTransforms.model(foot));Vector3f selected=null;float minimum=Float.POSITIVE_INFINITY;
            // Dense sole meshes need one scalar reduction, not tens of thousands
            // of temporary vectors per frame. The minimum remains exact.
            Vector3f toe=null,heel=null;float front=Float.NEGATIVE_INFINITY,rear=Float.POSITIVE_INFINITY;
            for(Vector3f rest:mesh.get(s))
            {
                float y=matrix.m01()*rest.x+matrix.m11()*rest.y+matrix.m21()*rest.z+matrix.m31();if(y<minimum){minimum=y;selected=rest;}
                float ahead=(matrix.m00()*rest.x+matrix.m10()*rest.y+matrix.m20()*rest.z+matrix.m30())*forward.x+(matrix.m02()*rest.x+matrix.m12()*rest.y+matrix.m22()*rest.z+matrix.m32())*forward.z;
                if(ahead>front){front=ahead;toe=rest;}
                if(ahead<rear){rear=ahead;heel=rest;}
            }
            if(selected==null)continue;Vector3f lowest=matrix.transformPosition(new Vector3f(selected));
            int key=eva.getId()*2+(s.equals("l")?0:1);
            Vector3f pivot=EvaRigTransforms.point(foot,EvaRigTransforms.pivot(foot),root);
            // A sole held on a ledge is read where it is held, not where the clip has slid it.
            Vector3f held=hold(key,pivot);lowest.add(held.x,0,held.z);
            // A sole stands on one level, never half on each. Read under its
            // lowest point, toes reaching past a kerb's edge read the kerb's top
            // and the foot was lifted with its heel still before the face, toes
            // in it. Across an edge it goes up when the body is stepping up or
            // the sole is nearer the top, carried on until its heel clears the
            // edge; otherwise it stays below and its toes are drawn back out.
            Vector3f toeAt=matrix.transformPosition(new Vector3f(toe)).add(held.x,0,held.z),heelAt=matrix.transformPosition(new Vector3f(heel)).add(held.x,0,held.z);
            Vector3f middle=new Vector3f(toeAt).add(heelAt).mul(.5F);middle.y=lowest.y;
            double top=ground(eva,new Vector3f(toeAt.x,lowest.y,toeAt.z)),below=ground(eva,new Vector3f(heelAt.x,lowest.y,heelAt.z));
            // Height above the drawn ground: while the body rises onto a kerb it is drawn below the entity.
            double ground,lift=lowest.y-root.m31();
            float onto=0;
            if(Double.isFinite(top)&&Double.isFinite(below)&&top>below+.5)
            {
                ground=below;
                if(stepping||top-lowest.y<lowest.y-below)
                {
                    float length=(float)((toeAt.x-heelAt.x)*forward.x+(toeAt.z-heelAt.z)*forward.z);
                    for(float d=0;d<=length;d+=.5F)
                        if(solid(eva,heelAt.x+forward.x*d,top-.5,heelAt.z+forward.z*d)){onto=d+.5F;ground=top;break;}
                }
            }
            else ground=ground(eva,middle);
            onto=(float)ease(key^0x20000000,onto);
            double plant=1-Math.max(0,Math.min(1,(lift-.35)/1.7));
            // A sole planted on a ledge stays where it landed while the body
            // passes over it and rises, until it lifts. The clips' stance feet
            // slide back faster than the body moves: on a ledge that slid the
            // foot off the edge and the leg folded to keep it up there.
            updateHold(key,pivot,plant,Double.isFinite(ground)&&ground-root.m31()>.5);held=hold(key,pivot);
            if(UNDER.size()>64)UNDER.clear();
            UNDER.put(eva.getId()*2+(s.equals("l")?0:1),new double[]{ground,com.projectseele.client.AircraftRenderClockR21.frameNanos()});
            // Only a planted sole carries the body up onto a ledge.
            if(Double.isFinite(ground)&&plant>.5)ledge=Math.max(ledge,ground-root.m31());
            // Only the terrain's rise or fall under the sole, measured from the
            // drawn ground. Pinning the sole itself pulled every lifting foot
            // down and lagged it behind the clip, so the legs shook each step
            // on flat ground; resting the body on its feet is ground contact's.
            // Flat ground reads a hair below the drawn one; no block edge is that small.
            double rise=Double.isFinite(ground)?Math.max(-STEP,Math.min(STEP,ground-root.m31())):0;
            // A swinging foot rises to the higher of the ground under it and a
            // stride ahead, so it clears a ledge's edge and comes down on top.
            // Swinging feet were left to the clip: the toe went through the
            // ledge's face and then jumped onto its top as it planted.
            double ahead=ground(eva,new Vector3f(lowest).add(forward.x*reach,0,forward.z*reach));
            // A wall taller than a step reads as ground at the ray's start: no clearance for that.
            boolean ledgeAhead=Double.isFinite(ahead)&&ahead<lowest.y+STEP+.5;
            double clear=Math.max(0,Math.max(rise,ledgeAhead?Math.min(STEP,ahead-root.m31()):0));
            rise=rise*plant+clear*(1-plant);
            double flat=Math.max(0,Math.min(1,(Math.abs(rise)-.15)/.3));
            double correction=ease(eva.getId()*2+(s.equals("l")?0:1),rise*flat*flat*(3-2*flat));
            witness[index++]=lowest.y;witness[index++]=ground;witness[index++]=correction;
            float holding=holdWeight(key);
            // A toe that reaches into or through a wall or a kerb's face is
            // drawn back to stand in front of it, along the heading: the long
            // walking stride reached past the body's box into a wall it was
            // pressed against (through an eleven-block wall to its far side),
            // and into a ledge's face before the foot had cleared its edge.
            Vector3f tip=matrix.transformPosition(new Vector3f(toe)).add(held.x,(float)correction,held.z);
            var centre=eva.getPosition(partial);
            // Stopped at once as the toe meets the face, released gently: eased
            // both ways, a swinging foot outran it and its toe went four blocks in.
            float back=(float)easeUnder(key^0x40000000,blocked(eva,tip,lowest.y+(float)correction,centre,forward));
            // Carried onto the ledge only as it rises over the edge, not through the face.
            float up=rise>.5?(float)Math.max(0,Math.min(1,(correction/rise-.6)/.4)):1,shift=onto*up-back;
            if(Math.abs(correction)<.005&&holding<.005&&back<.005&&onto<.005)continue;
            Vector3f target=new Vector3f(pivot).add(held.x+forward.x*shift,(float)correction,held.z+forward.z*shift);
            // The knee bends forward, and up when the foot is lifted high in
            // front. The clip's own knee direction lay along the thigh when a
            // foot was raised onto a ledge, and the solver flipped the knee
            // backwards and flung the foot up behind.
            Vector3f pole=new Vector3f(forward).add(0,.5F,0);
            // Small corrections fade in: a solver switched on at a fixed threshold snapped the walking leg.
            EvaRigTransforms.solveLegFaded(leg,shin,ankle,foot,target,EvaRigTransforms.rotation(matrix),pole,root,Math.max(Math.max(holding,Math.min(1,(back+onto)/.5F)),(float)Math.min(1,Math.abs(correction)/.2)));
            // The solved leg can fall short of its target, a foot lifted onto a
            // kerb lower than asked: the toes are checked again where they are drawn.
            // The solver keeps the foot's turn, so the sole sits where it did under the toe.
            var drawnToe=new Matrix4f(root).mul(EvaRigTransforms.model(foot)).transformPosition(new Vector3f(toe));
            float more=blocked(eva,drawnToe,drawnToe.y+lowest.y-matrix.transformPosition(new Vector3f(toe)).y,centre,forward);
            if(more>0)
            {
                back+=more;EASED.put(key^0x40000000,new Eased(back,com.projectseele.client.AircraftRenderClockR21.frameNanos()));
                target.sub(forward.x*more,0,forward.z*more);
                EvaRigTransforms.solveLegFaded(leg,shin,ankle,foot,target,EvaRigTransforms.rotation(matrix),pole,root,1);
            }
            changed.addAll(List.of("leg_"+s,"shin_"+s,"ankle_"+s,"foot_"+s));
        }
        if(LAST.size()>32)LAST.clear();LAST.put(eva.getId(),witness);
        if(LEDGE.size()>32)LEDGE.clear();LEDGE.put(eva.getId(),ledge);
        return new EvaMotionEngineV2.BoneWrites(Set.copyOf(changed),Set.copyOf(changed),"MOTION_ENGINE_LIVE_ACTION");
    }
    private static final class Hold {float x,z,weight=1;long time;boolean on=true;}
    private static final Map<Integer,Hold> HOLDS=new HashMap<>();
    /** Offset (x, z) from the clip's foot to where a ledge holds it this frame. */
    private static Vector3f hold(int key,Vector3f pivot)
    {
        var hold=HOLDS.get(key);if(hold==null)return new Vector3f();
        // A hold from before an action (no placement while a ledge climb
        // played) pinned the foot where it had stood: 25 blocks behind the
        // body on the wall top, and the leg pulled the body down into it.
        if(com.projectseele.client.AircraftRenderClockR21.frameNanos()-hold.time>250_000_000L||Math.hypot(hold.x-pivot.x,hold.z-pivot.z)>12)
        {HOLDS.remove(key);return new Vector3f();}
        float w=hold.weight*hold.weight*(3-2*hold.weight);
        return new Vector3f((hold.x-pivot.x)*w,0,(hold.z-pivot.z)*w);
    }
    private static float holdWeight(int key){var hold=HOLDS.get(key);return hold==null?0:hold.weight*hold.weight*(3-2*hold.weight);}
    private static void updateHold(int key,Vector3f pivot,double plant,boolean ledge)
    {
        long now=com.projectseele.client.AircraftRenderClockR21.frameNanos();var hold=HOLDS.get(key);
        if(hold!=null&&hold.on&&plant<.4)hold.on=false;
        if((hold==null||!hold.on)&&ledge&&plant>.6)
        {
            // Held from where the foot is drawn now, so a re-plant does not jump.
            var at=new Vector3f(pivot).add(hold(key,pivot));
            hold=new Hold();hold.x=at.x;hold.z=at.z;hold.time=now;
            if(HOLDS.size()>64)HOLDS.clear();
            HOLDS.put(key,hold);return;
        }
        if(hold==null)return;
        float dt=Math.max(0,Math.min(.25F,(now-hold.time)/1e9F));hold.time=now;
        // Released over 0.15 s as the foot lifts.
        if(!hold.on){hold.weight-=dt/.15F;if(hold.weight<=0)HOLDS.remove(key);}
    }
    /**
     * How far back along the heading a toe at tip, sole at sole, must go to
     * stand in front of a wall or a kerb's face. The way from the body to the
     * toe is searched, not the toe alone: a toe through an eleven-block wall
     * stood in the open. Read at the sole as well as the toe cap, which stands
     * higher: a sole lifted onto a kerb's top went over it still below it.
     * A block-high bump is left to the ground correction.
     */
    private static float blocked(EvaUnit01Entity eva,Vector3f tip,float sole,Vec3 centre,Vector3f forward)
    {
        float reachOut=(float)((tip.x-centre.x)*forward.x+(tip.z-centre.z)*forward.z);
        double low=Math.min(tip.y+.6,sole+1.2);
        for(float d=1;d<=reachOut;d+=1)
        {
            double x=tip.x-forward.x*(reachOut-d),z=tip.z-forward.z*(reachOut-d);
            if(solid(eva,x,low,z)||solid(eva,x,tip.y+3,z))return reachOut-d+1;
        }
        return 0;
    }
    /** Follows a rise at once and eases a fall, as ease() does both. */
    private static double easeUnder(int key,double wanted)
    {
        var last=EASED.get(key);
        if(last!=null&&wanted<last.value())return ease(key,wanted);
        if(EASED.size()>64)EASED.clear();
        EASED.put(key,new Eased(wanted,com.projectseele.client.AircraftRenderClockR21.frameNanos()));
        return wanted;
    }
    private static boolean solid(EvaUnit01Entity eva,double x,double y,double z)
    {
        var pos=net.minecraft.core.BlockPos.containing(x,y,z);var state=eva.level().getBlockState(pos);if(state.isAir())return false;
        var shape=state.getCollisionShape(eva.level(),pos,CollisionContext.of(eva));
        if(shape.isEmpty()||EvaObstacleCollision.ignores(eva,state,pos,shape))return false;
        for(var box:shape.toAabbs())if(box.move(pos).contains(x,y,z))return true;
        return false;
    }
    /** The EVA's step height (blocks): a sole is set on ground this far above or below it. */
    private static final double STEP=20;
    /** How far ahead of a swinging sole the ground is read at least (blocks). */
    private static final float REACH=5;
    private record Eased(double value,long time) {}
    private static final Map<Integer,Eased> EASED=new HashMap<>();
    /**
     * The ground under a sole changes block by block, and a ray that found
     * nothing read as no ground: the correction jumped by up to a block
     * between frames and snapped the leg. It now follows over about a tenth of
     * a second.
     */
    private static double ease(int key,double wanted)
    {
        long now=com.projectseele.client.AircraftRenderClockR21.frameNanos();var last=EASED.get(key);double value=wanted;
        if(last!=null)
        {
            double dt=(now-last.time())/1e9;
            if(dt==0)return last.value();
            // A ledge coming under the foot changes it by up to a full step:
            // that eases too, quickly, instead of jumping there.
            if(dt>0&&dt<.25)value=last.value()+(wanted-last.value())*(1-Math.exp(-dt/.05));
        }
        if(EASED.size()>64)EASED.clear();
        EASED.put(key,new Eased(value,now));
        return value;
    }
    private EvaFootPlacement() {}
}
