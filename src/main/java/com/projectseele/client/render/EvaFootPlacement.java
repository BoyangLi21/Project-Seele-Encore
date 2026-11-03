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
        float reach=(float)Math.max(REACH,Math.min(20,Math.hypot(eva.getX()-eva.xo,eva.getZ()-eva.zo)*20*.3));
        for(String s:List.of("l","r"))
        {
            var foot=model.getBone("foot_"+s).orElse(null);var leg=model.getBone("leg_"+s).orElse(null);var shin=model.getBone("shin_"+s).orElse(null);var ankle=model.getBone("ankle_"+s).orElse(null);
            if(foot==null||leg==null||shin==null||ankle==null||!mesh.containsKey(s))continue;
            Matrix4f matrix=new Matrix4f(root).mul(EvaRigTransforms.model(foot));Vector3f selected=null;float minimum=Float.POSITIVE_INFINITY;
            // Dense sole meshes need one scalar reduction, not tens of thousands
            // of temporary vectors per frame. The minimum remains exact.
            for(Vector3f rest:mesh.get(s)){float y=matrix.m01()*rest.x+matrix.m11()*rest.y+matrix.m21()*rest.z+matrix.m31();if(y<minimum){minimum=y;selected=rest;}}
            if(selected==null)continue;Vector3f lowest=matrix.transformPosition(new Vector3f(selected));
            int key=eva.getId()*2+(s.equals("l")?0:1);
            Vector3f pivot=EvaRigTransforms.point(foot,EvaRigTransforms.pivot(foot),root);
            // A sole held on a ledge is read where it is held, not where the clip has slid it.
            Vector3f held=hold(key,pivot);lowest.add(held.x,0,held.z);
            // Height above the drawn ground: while the body rises onto a kerb it is drawn below the entity.
            double ground=ground(eva,lowest),lift=lowest.y-root.m31();
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
            if(Math.abs(correction)<.005&&holding<.005)continue;
            Vector3f target=new Vector3f(pivot).add(held.x,(float)correction,held.z);
            // The knee bends forward, and up when the foot is lifted high in
            // front. The clip's own knee direction lay along the thigh when a
            // foot was raised onto a ledge, and the solver flipped the knee
            // backwards and flung the foot up behind.
            Vector3f pole=new Vector3f(forward).add(0,.5F,0);
            // Small corrections fade in: a solver switched on at a fixed threshold snapped the walking leg.
            EvaRigTransforms.solveLegFaded(leg,shin,ankle,foot,target,EvaRigTransforms.rotation(matrix),pole,root,Math.max(holding,(float)Math.min(1,Math.abs(correction)/.2)));
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
