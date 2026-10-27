package com.projectseele.entity;

import com.google.gson.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

/** Complete fixed-keypose review admission. This is not production rig4 admission. */
public final class Unit03ReviewContractR53
{
    public static final String PROPERTY="projectseele.unit03ReviewDirectoryR53";
    public static final String MARKER="unit03_source_review_r53";
    public record Contract(Path directory,Path world,UUID actor,String fingerprint,JsonObject poses) {}
    private static Contract loaded;
    public static boolean requested(){return !System.getProperty(PROPERTY,"").isBlank();}
    public static synchronized Contract current()
    {
        if(!requested())return null;
        if(loaded==null)
        {
            try{loaded=validate(Path.of(System.getProperty(PROPERTY)),System.getProperties());}
            catch(Exception failure){throw new IllegalStateException("Unit03 isolated review contract rejected",failure);}
        }
        return loaded;
    }
    public static boolean actor(UUID id)
    {var contract=current();return contract!=null&&contract.actor().equals(id);}
    public static Contract validate(Path directory,Properties properties)throws Exception
    {
        Path root=directory.toAbsolutePath().normalize();Path manifest=root.resolve("unit03_review_contract.json");
        JsonObject c=json(manifest);
        require("projectseele.unit03-review-contract.r53.v1".equals(c.get("schema").getAsString()),"schema");
        require("fixed_keyposes_only".equals(c.get("scope").getAsString())&&!c.get("combat_gameplay_admitted").getAsBoolean(),"scope");
        require(c.get("rig").getAsInt()==4&&MARKER.equals(c.get("marker").getAsString()),"rig identity");
        Path world=Path.of(c.get("world").getAsString()).toAbsolutePath().normalize();
        require(world.startsWith(root.resolve("isolated-client/saves"))
                &&world.getFileName().toString().equals("SEELE_R53_UNIT03_SOURCE_REVIEW"),"isolated world");
        var requiredProperties=Map.of(PROPERTY,root,"projectseele.combatBundleDirectory",root.resolve("runtime"),
                "projectseele.bodyPoseReviewDirectory",root.resolve("runtime"),"projectseele.gameplayReviewDirectory",root.resolve("runtime"),
                "projectseele.bodyPhysicsProfiles",root.resolve("runtime/articulated_bodies_r35.json"),
                "projectseele.handRigDirectoryR45",root.resolve("hands"),"projectseele.capturedLocomotionDirectory",root.resolve("captured"));
        require(c.getAsJsonObject("properties").keySet().equals(requiredProperties.keySet()),"property set");
        require(properties.getProperty("projectseele.bodyPoseReview","").isBlank(),"conflicting single body override");
        for(var e:requiredProperties.entrySet())
        {
            require(Path.of(c.getAsJsonObject("properties").get(e.getKey()).getAsString()).toAbsolutePath().normalize().equals(e.getValue()),"declared property "+e.getKey());
            require(Path.of(properties.getProperty(e.getKey(),"")).toAbsolutePath().normalize().equals(e.getValue()),"effective property "+e.getKey());
        }
        var files=c.getAsJsonObject("files");
        for(String name:List.of("runtime/combat_bundle_r44.json","keyposes.json","hands/unit04/hand_rig_contract.json",
                "resources/pack.mcmeta","resources/assets/projectseele/mesh/eva_un01.mesh.json",
                "resources/assets/projectseele/mesh/eva_un01_anatomical_hands_r53.mesh.json",
                "resources/assets/projectseele/geo/eva_un01.geo.json","resources/assets/projectseele/animations/eva_un01.animation.json",
                "resources/assets/projectseele/textures/entity/eva_un01.png","resources/assets/projectseele/textures/entity/eva_un01_eyes.png",
                "resources/assets/projectseele/hand_rigs/unit04/hand_rig_contract.json","resources/assets/projectseele/eva/source_surface_r53.json",
                "unit03-review-resources.zip"))require(files.has(name),"required fingerprint "+name);
        for(var e:files.entrySet())
        {
            Path p=root.resolve(e.getKey()).normalize();require(p.startsWith(root)&&Files.isRegularFile(p),"file "+e.getKey());
            require(digest(Files.readAllBytes(p)).equals(e.getValue().getAsString()),"hash "+e.getKey());
        }
        var runtime=json(root.resolve("runtime/combat_bundle_r44.json"));
        require(runtime.get("revision").getAsInt()==44&&runtime.getAsJsonObject("files").size()>=28,"complete runtime");
        Set<String> names=new HashSet<>();for(var e:c.getAsJsonArray("runtime_names"))names.add(e.getAsString());
        require(names.equals(runtime.getAsJsonObject("files").keySet()),"runtime membership");
        for(var e:runtime.getAsJsonObject("files").entrySet())
            require(files.has("runtime/"+e.getKey())&&files.get("runtime/"+e.getKey()).equals(e.getValue()),"runtime identity");
        for(var e:c.getAsJsonObject("unchanged_runtime").entrySet())
            require(e.getValue().equals(runtime.getAsJsonObject("files").get(e.getKey())),"unchanged runtime "+e.getKey());
        var body=json(root.resolve("runtime/eva_body_r44.json"));var rig=body.getAsJsonObject("rigs").getAsJsonArray("4");
        var geo=json(root.resolve("resources/assets/projectseele/geo/eva_un01.geo.json"));
        var gameplay=json(root.resolve("runtime/eva_gameplay_r44_4.json"));
        var physics=json(root.resolve("runtime/articulated_bodies_r35.json")).getAsJsonObject("models").getAsJsonObject("4");
        require(rig.equals(geo.getAsJsonArray("minecraft:geometry").get(0).getAsJsonObject().get("bones"))
                &&rig.equals(gameplay.get("rig_contract_r44"))&&rig.equals(physics.get("render_rig")),"cross-domain rig");
        require(gameplay.get("rig_key").getAsInt()==4&&physics.getAsJsonArray("bodies").size()==15
                &&physics.get("recovery_review_pending").getAsBoolean(),"physics review boundary");
        Set<String> boneNames=new HashSet<>();for(var e:rig)require(boneNames.add(e.getAsJsonObject().get("name").getAsString()),"duplicate bone");
        require(boneNames.size()==108&&boneNames.contains(MARKER)&&boneNames.contains("unit03_shared_unit01_r53"),"review marker");
        var hand=json(root.resolve("hands/unit04/hand_rig_contract.json"));
        require(hand.get("rig").getAsInt()==4&&hand.getAsJsonArray("new_bones").size()==30,"hand identity");
        require(hand.equals(json(root.resolve("resources/assets/projectseele/hand_rigs/unit04/hand_rig_contract.json"))),"hand resource equality");
        for(var b:hand.getAsJsonArray("new_bones"))require(rig.contains(b),"measured hand bone");
        require(!Files.exists(root.resolve("captured/eva_locomotion_capture_r44_4.json")),"unadmitted locomotion");
        for(int k=0;k<3;k++)require(files.has("hands/unit0"+k+"/hand_rig_contract.json"),"normal hand preservation");
        var mesh=json(root.resolve("resources/assets/projectseele/mesh/eva_un01.mesh.json"));
        require(mesh.get("triangleCount").getAsInt()==3909,"complete source surface");
        var poses=json(root.resolve("keyposes.json")).getAsJsonObject("poses");
        require(poses.keySet().equals(Set.of("source_rest","hand_fist","hand_open","idle","rifle_stance","r32_jab")),"finite pose scope");
        for(var entry:poses.entrySet())
        {
            require(entry.getValue().getAsJsonObject().keySet().equals(boneNames),"complete pose "+entry.getKey());
            for(var b:entry.getValue().getAsJsonObject().entrySet())
            {
                var p=b.getValue().getAsJsonObject();var q=p.getAsJsonArray("rotation_xyzw");var v=p.getAsJsonArray("position");
                require(q.size()==4&&v.size()==3,"pose channels");double norm=0;
                for(var x:q){double n=x.getAsDouble();require(Double.isFinite(n),"finite quaternion");norm+=n*n;}
                require(Math.abs(norm-1)<1e-5,"unit quaternion");
                for(var x:v)require(Double.isFinite(x.getAsDouble())&&Math.abs(x.getAsDouble())<=256,"finite position");
            }
        }
        return new Contract(root,world,UUID.fromString(c.get("actor_uuid").getAsString()),digest(Files.readAllBytes(manifest)),poses);
    }
    private static JsonObject json(Path p)throws Exception{return JsonParser.parseString(Files.readString(p)).getAsJsonObject();}
    private static String digest(byte[] b)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(b));}
    private static void require(boolean value,String reason){if(!value)throw new IllegalArgumentException("Unit03 review: "+reason);}
    private Unit03ReviewContractR53(){}
}
