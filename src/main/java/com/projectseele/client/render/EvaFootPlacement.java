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
        for(String s:List.of("l","r"))
        {
            var foot=model.getBone("foot_"+s).orElse(null);var leg=model.getBone("leg_"+s).orElse(null);var shin=model.getBone("shin_"+s).orElse(null);var ankle=model.getBone("ankle_"+s).orElse(null);
            if(foot==null||leg==null||shin==null||ankle==null||!mesh.containsKey(s))continue;
            Matrix4f matrix=new Matrix4f(root).mul(EvaRigTransforms.model(foot));Vector3f selected=null;float minimum=Float.POSITIVE_INFINITY;
            // Dense sole meshes need one scalar reduction, not tens of thousands
            // of temporary vectors per frame. The minimum remains exact.
            for(Vector3f rest:mesh.get(s)){float y=matrix.m01()*rest.x+matrix.m11()*rest.y+matrix.m21()*rest.z+matrix.m31();if(y<minimum){minimum=y;selected=rest;}}
            if(selected==null)continue;Vector3f lowest=matrix.transformPosition(new Vector3f(selected));
            // Height above the drawn ground: while the body rises onto a kerb it is drawn below the entity.
            double ground=ground(eva,lowest),lift=lowest.y-root.m31();
            if(Double.isFinite(ground))ledge=Math.max(ledge,ground-root.m31());
            double plant=1-Math.max(0,Math.min(1,(lift-.35)/1.7));
            // Only the terrain's rise or fall under the sole, measured from the
            // drawn ground. Pinning the sole itself pulled every lifting foot
            // down and lagged it behind the clip, so the legs shook each step
            // on flat ground; resting the body on its feet is ground contact's.
            // Flat ground reads a hair below the drawn one; no block edge is that small.
            double rise=Double.isFinite(ground)?Math.max(-STEP,Math.min(STEP,ground-root.m31())):0,flat=Math.max(0,Math.min(1,(Math.abs(rise)-.15)/.3));
            double correction=ease(eva.getId()*2+(s.equals("l")?0:1),rise*flat*flat*(3-2*flat)*plant);
            witness[index++]=lowest.y;witness[index++]=ground;witness[index++]=correction;
            if(Math.abs(correction)<.005)continue;
            Vector3f target=EvaRigTransforms.point(foot,EvaRigTransforms.pivot(foot),root).add(0,(float)correction,0);
            Vector3f hip=EvaRigTransforms.point(leg,EvaRigTransforms.pivot(leg),root);Vector3f knee=EvaRigTransforms.point(leg,EvaRigTransforms.knee(shin),root);
            // Small corrections fade in: a solver switched on at a fixed threshold snapped the walking leg.
            EvaRigTransforms.solveLegFaded(leg,shin,ankle,foot,target,EvaRigTransforms.rotation(matrix),knee.sub(hip),root,(float)Math.min(1,Math.abs(correction)/.2));
            changed.addAll(List.of("leg_"+s,"shin_"+s,"ankle_"+s,"foot_"+s));
        }
        if(LAST.size()>32)LAST.clear();LAST.put(eva.getId(),witness);
        if(LEDGE.size()>32)LEDGE.clear();LEDGE.put(eva.getId(),ledge);
        return new EvaMotionEngineV2.BoneWrites(Set.copyOf(changed),Set.copyOf(changed),"MOTION_ENGINE_LIVE_ACTION");
    }
    /** The EVA's step height (blocks): a sole is set on ground this far above or below it. */
    private static final double STEP=20;
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
            if(dt>0&&dt<.25&&Math.abs(wanted-last.value())<3)value=last.value()+(wanted-last.value())*(1-Math.exp(-dt/.06));
        }
        if(EASED.size()>64)EASED.clear();
        EASED.put(key,new Eased(value,now));
        return value;
    }
    private EvaFootPlacement() {}
}
