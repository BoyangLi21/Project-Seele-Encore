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
        Vec3 from=new Vec3(point.x,point.y+3.5,point.z),to=new Vec3(point.x,point.y-4,point.z);
        for(int i=0;i<5;i++)
        {
            var hit=eva.level().clip(new ClipContext(from,to,ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,eva));if(hit.getType()!=HitResult.Type.BLOCK)return Double.NaN;
            var pos=hit.getBlockPos();var s=eva.level().getBlockState(pos);var shape=s.getCollisionShape(eva.level(),pos,CollisionContext.of(eva));
            if(!EvaObstacleCollision.ignores(eva,s,pos,shape))return hit.getLocation().y;
            from=new Vec3(point.x,pos.getY()-.001,point.z);
        }
        return Double.NaN;
    }
    public static EvaMotionEngineV2.BoneWrites apply(EvaUnit01Entity eva,BakedGeoModel model,float partial,Matrix4f root)
    {
        LAST.remove(eva.getId());
        if(eva.hasLegacyStrikeForRender())return EvaMotionEngineV2.BoneWrites.empty();
        if(root==null||!eva.isPoweredOn()||eva.isCrucified()||eva.hasActiveCarrierMotion()||eva.isExperimentalUnit()&&!EvaBodyPose.hasOwnUnRig(eva)||eva.isFirstBattleActive()||eva.isVisuallyAirborneForRender()||eva.isNervLogisticsLocked()||eva.isLaunchSequenceActive()||eva.isBerserk()||eva.getActivationTicks()>0||eva.getVisualPose()!=0||eva.hasLiveActionForRender(partial)||eva.rifleStanceLevel(partial)>1.01F)return EvaMotionEngineV2.BoneWrites.empty();
        var mesh=feet(eva);Set<String> changed=new LinkedHashSet<>();double[] witness=new double[6];int index=0;
        for(String s:List.of("l","r"))
        {
            var foot=model.getBone("foot_"+s).orElse(null);var leg=model.getBone("leg_"+s).orElse(null);var shin=model.getBone("shin_"+s).orElse(null);var ankle=model.getBone("ankle_"+s).orElse(null);
            if(foot==null||leg==null||shin==null||ankle==null||!mesh.containsKey(s))continue;
            Matrix4f matrix=new Matrix4f(root).mul(EvaRigTransforms.model(foot));Vector3f selected=null;float minimum=Float.POSITIVE_INFINITY;
            // Dense sole meshes need one scalar reduction, not tens of thousands
            // of temporary vectors per frame. The minimum remains exact.
            for(Vector3f rest:mesh.get(s)){float y=matrix.m01()*rest.x+matrix.m11()*rest.y+matrix.m21()*rest.z+matrix.m31();if(y<minimum){minimum=y;selected=rest;}}
            if(selected==null)continue;Vector3f lowest=matrix.transformPosition(new Vector3f(selected));
            double ground=ground(eva,lowest),lift=lowest.y-eva.getY();
            double plant=1-Math.max(0,Math.min(1,(lift-.35)/1.7));
            double correction=Double.isFinite(ground)?Math.max(-2.6,Math.min(2.6,ground+.05-lowest.y))*plant:0;
            witness[index++]=lowest.y;witness[index++]=ground;witness[index++]=correction;
            if(Math.abs(correction)<.025)continue;
            Vector3f target=EvaRigTransforms.point(foot,EvaRigTransforms.pivot(foot),root).add(0,(float)correction,0);
            Vector3f hip=EvaRigTransforms.point(leg,EvaRigTransforms.pivot(leg),root);Vector3f knee=EvaRigTransforms.point(leg,EvaRigTransforms.knee(shin),root);
            EvaRigTransforms.solveLeg(leg,shin,ankle,foot,target,EvaRigTransforms.rotation(matrix),knee.sub(hip),root);
            changed.addAll(List.of("leg_"+s,"shin_"+s,"ankle_"+s,"foot_"+s));
        }
        if(LAST.size()>32)LAST.clear();LAST.put(eva.getId(),witness);
        return new EvaMotionEngineV2.BoneWrites(Set.copyOf(changed),Set.copyOf(changed),"MOTION_ENGINE_LIVE_ACTION");
    }
    private EvaFootPlacement() {}
}
