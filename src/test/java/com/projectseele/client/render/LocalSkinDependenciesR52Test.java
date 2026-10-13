package com.projectseele.client.render;

import com.google.gson.JsonParser;
import com.projectseele.entity.FirstBattleClip;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.packs.resources.Resource;
import net.minecraft.server.packs.resources.ResourceManager;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import software.bernie.geckolib.cache.object.GeoBone;
import software.bernie.geckolib.loading.json.raw.Model;
import software.bernie.geckolib.loading.object.BakedModelFactory;
import software.bernie.geckolib.loading.object.GeometryTree;
import software.bernie.geckolib.util.JsonUtil;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/** Executes actual selected mesh skinning and native baked rig, without a client/world/GL context. */
public final class LocalSkinDependenciesR52Test
{
    private record Slot(String name,Object mesh,Object part,Object skin,PosedMeshCacheR52 cache) {}
    private static Method oldSkin,newSkin;
    private static double maximumError;
    private static long compared;
    private static Object value(Object record,String name)throws Exception
    {Method method=record.getClass().getDeclaredMethod(name);method.setAccessible(true);return method.invoke(record);}
    @SuppressWarnings("unchecked") private static Map<String,Object> map(Object record,String name)throws Exception
    {return (Map<String,Object>)value(record,name);}
    private static BakedGeoModel bake(Path geo)throws Exception
    {
        try(var reader=Files.newBufferedReader(geo))
        {return BakedModelFactory.DEFAULT_FACTORY.constructGeoModel(GeometryTree.fromModel(JsonUtil.GEO_GSON.fromJson(JsonParser.parseReader(reader),Model.class)));}
    }
    @SuppressWarnings("unchecked") private static List<Slot> slots(Path meshPath)throws Exception
    {
        var resource=new Resource(null,()->Files.newInputStream(meshPath));
        ResourceManager manager=(ResourceManager)Proxy.newProxyInstance(ResourceManager.class.getClassLoader(),new Class<?>[]{ResourceManager.class},
                (proxy,method,args)->switch(method.getName())
                {case "getResource"->Optional.of(resource);case "getResourceOrThrow"->resource;default->throw new UnsupportedOperationException(method.getName());});
        Method load=LocalTriangleMeshLayer.class.getDeclaredMethod("getMesh",ResourceManager.class,ResourceLocation.class);load.setAccessible(true);
        Object mesh=load.invoke(null,manager,new ResourceLocation("projectseele","test/"+meshPath.getFileName()));
        if(mesh==null)throw new AssertionError("Actual selected mesh did not parse: "+meshPath);
        List<Slot> slots=new ArrayList<>();
        for(var entry:map(mesh,"joints").entrySet())
        {
            Object skin=entry.getValue();Map<String,Object> influences=map(skin,"influences");
            Object corrective=value(skin,"corrective");Set<String> drivers=corrective==null?Set.of():map(corrective,"targets").keySet();
            slots.add(new Slot(entry.getKey(),mesh,map(mesh,"parts").get(entry.getKey()),skin,
                    new PosedMeshCacheR52(entry.getKey(),influences.isEmpty()?Set.of((String)value(skin,"other")):influences.keySet(),drivers)));
        }
        return slots;
    }
    private static void evaluate(List<Slot> slots,BakedGeoModel model,Object actor,long frame)throws Exception
    {
        GeoBone root=model.topLevelBones().get(0);
        for(Slot slot:slots)
        {
            slot.cache.prepare(actor,root,frame,.5F);
            GeoBone bone=model.getBone(slot.name).orElseThrow();
            float[] scratch=(float[])value(slot.skin,"scratch");
            float[] cached=slot.cache.sampled(slot.skin)?scratch.clone():null;
            float[] baseline=((float[])oldSkin.invoke(null,slot.mesh,slot.part,bone)).clone();
            float[] actual;
            if(cached==null)actual=(float[])newSkin.invoke(null,slot.mesh,slot.part,bone,slot.cache.commonAncestor());
            else {System.arraycopy(cached,0,scratch,0,cached.length);actual=scratch;}
            for(int i=0;i<actual.length;i++)
            {
                double error=Math.abs(actual[i]-baseline[i]);maximumError=Math.max(maximumError,error);compared++;
                if(error>(i%8<3?.003:.0002))throw new AssertionError("Skin output differs beyond float tolerance: "+slot.name+" index="+i+" error="+error);
            }
            slot.cache.remember(slot.skin);
        }
    }
    private static Map<Slot,Long> revisions(List<Slot> slots)
    {Map<Slot,Long> result=new IdentityHashMap<>();for(Slot slot:slots)result.put(slot,slot.cache.revision());return result;}
    private static Set<String> changed(List<Slot> slots,Map<Slot,Long> before)
    {Set<String> result=new TreeSet<>();for(Slot slot:slots)if(slot.cache.revision()!=before.get(slot))result.add(slot.name);return result;}
    private static void pose(BakedGeoModel model,float seconds)
    {
        var pose=FirstBattleClip.pose(true,seconds);
        for(int i=0;i<pose.names().length;i++)
        {
            var bone=model.getBone(pose.names()[i]).orElse(null);if(bone==null)continue;
            var euler=EvaMotionEngineV2.motionQuaternionToAuthoredEuler(pose.rotations()[i]);var p=pose.positions()[i];
            bone.setRotX(-euler.x);bone.setRotY(-euler.y);bone.setRotZ(euler.z);bone.setPosX(p.x);bone.setPosY(p.y);bone.setPosZ(p.z);
        }
        for(String side:List.of("l","r"))
        {
            var shin=model.getBone("shin_"+side).orElseThrow();EvaRigTransforms.hinge(shin,EvaRigTransforms.knee(shin));
            var forearm=model.getBone("forearm_"+side).orElseThrow();EvaRigTransforms.hinge(forearm,EvaRigTransforms.elbow(forearm,side));
        }
    }
    public static void main(String[] args)throws Exception
    {
        Path assets=Path.of(args[0]),clip=Path.of(args[1]);
        System.setProperty("projectseele.firstBattleReviewClip",clip.toString());
        System.setProperty("projectseele.dorsalPoseReview",clip.getParent().resolve("eva_dorsal_r30.json").toString());
        var model=bake(assets.resolve("geo/eva_unit01.geo.json"));
        List<Slot> body=slots(assets.resolve("mesh/eva_unit01.mesh.json"));
        List<Slot> hands=slots(assets.resolve("mesh/eva_unit01_anatomical_hands_r45.mesh.json"));
        List<Slot> all=new ArrayList<>(body);all.addAll(hands);
        Class<?> meshClass=all.get(0).mesh.getClass(),partClass=all.get(0).part.getClass();
        oldSkin=LocalTriangleMeshLayer.class.getDeclaredMethod("skinVertices",meshClass,partClass,GeoBone.class);oldSkin.setAccessible(true);
        newSkin=LocalTriangleMeshLayer.class.getDeclaredMethod("skinVertices",meshClass,partClass,GeoBone.class,GeoBone.class);newSkin.setAccessible(true);
        Object actor=new Object();long frame=100;
        for(float time:new float[]{0,3,5.1F,8.5F,11,15,17.7F,22}){pose(model,time);evaluate(all,model,actor,frame++);}
        var before=revisions(all);GeoBone root=model.topLevelBones().get(0);
        root.setPosX(root.getPosX()+48);root.setPosY(root.getPosY()+32);root.setRotY(root.getRotY()+.34F);
        root.setScaleX(1.11F);root.setScaleY(.95F);root.setScaleZ(1.05F);root.setPivotZ(root.getPivotZ()+2.5F);
        evaluate(all,model,actor,frame);
        if(!changed(all,before).isEmpty())throw new AssertionError("Common root rigid movement rebuilt geometry: "+changed(all,before));
        before=revisions(hands);var arm=model.getBone("arm_r").orElseThrow();arm.setRotX(arm.getRotX()+.25F);
        evaluate(all,model,actor,frame);
        if(!changed(hands,before).isEmpty())throw new AssertionError("Whole arm movement reskinned rigid hands");
        before=revisions(all);var thumb=model.getBone("r45_hand_r_thumb_2").orElseThrow();thumb.setRotX(thumb.getRotX()+.15F);
        evaluate(all,model,actor,frame);
        if(!changed(all,before).equals(Set.of("hand_r")))throw new AssertionError("Same frame local finger affected wrong skin parts: "+changed(all,before));
        before=revisions(all);var ankle=model.getBone("ankle_r").orElseThrow();ankle.setRotX(ankle.getRotX()+.18F);
        evaluate(all,model,actor,frame);
        if(!changed(all,before).equals(Set.of("shin_r","foot_r")))throw new AssertionError("Local ankle affected wrong skin parts: "+changed(all,before));
        before=revisions(all);var jaw=model.getBone("r37_jaw").orElseThrow();jaw.setRotX(jaw.getRotX()+.12F);
        evaluate(all,model,actor,frame);
        if(!changed(all,before).equals(Set.of("r37_lining")))throw new AssertionError("Local jaw affected wrong skin parts: "+changed(all,before));
        for(Slot slot:hands)
        {
            Object corrective=value(slot.skin,"corrective");
            if(corrective!=null)for(var target:map(corrective,"targets").entrySet())
                EvaRigTransforms.rotate(model.getBone(target.getKey()).orElseThrow(),(org.joml.Quaternionf)target.getValue());
        }
        evaluate(all,model,actor,frame);
        before=revisions(all);evaluate(all,model,new Object(),frame);
        if(!changed(all,before).isEmpty())throw new AssertionError("Identical pose on a second actor rebuilt geometry");
        thumb.setRotX(thumb.getRotX()-.27F);evaluate(all,model,new Object(),frame);
        if(!changed(all,before).equals(Set.of("hand_r")))throw new AssertionError("Second actor pose change was hidden");
        var reloaded=bake(assets.resolve("geo/eva_unit01.geo.json"));evaluate(all,reloaded,new Object(),frame);
        for(Slot slot:hands)if(!slot.cache.commonAncestor().getName().equals(slot.name))throw new AssertionError("Hand LCA differs from real hand bone");
        System.out.println("PASS: actual native baked rig/body+27104tri hands; values compared="+compared+" maxFloatError="+maximumError
                +"; common-root/arm rigid movement retained geometry; finger/ankle/jaw invalidated only their actual dependent parts; contact corrective and second actor/reload retained semantics");
    }
}
