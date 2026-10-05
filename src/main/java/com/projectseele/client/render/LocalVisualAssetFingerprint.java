package com.projectseele.client.render;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

import com.projectseele.ProjectSeele;
import net.minecraft.client.Minecraft;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.packs.resources.Resource;

/** Runtime identity and fail-closed contract for the local high-detail models. */
public final class LocalVisualAssetFingerprint
{
    private static final Map<String, MeshContract> CONTRACTS = Map.of(
            "eva_unit00", new MeshContract(5_510, 43, true),
            "eva_unit01", new MeshContract(6_044, 43, true),
            "eva_unit02", new MeshContract(5_770, 43, true),
            "mass_production_eva", new MeshContract(4_901, 15, false),
            "eva_prototype", new MeshContract(98_722, 46, false),
            "eva_un01", new MeshContract(227_353,62,false));
    private static final Map<String,MeshContract> R11_CONTRACTS=Map.of("eva_unit00",new MeshContract(6994,46,true),"eva_unit01",new MeshContract(7454,46,true),"eva_unit02",new MeshContract(7244,46,true),"eva_prototype",new MeshContract(86855,49,false));
    private static final Map<String,MeshContract> R13_CONTRACTS=Map.of("eva_unit00",new MeshContract(11028,45,true),"eva_unit01",new MeshContract(11666,45,true),"eva_unit02",new MeshContract(11262,45,true),"eva_prototype",new MeshContract(94054,48,false));
    private static final Map<String,MeshContract> R19_CONTRACTS=Map.of("eva_prototype",new MeshContract(139806,48,false));
    private static final Map<String,MeshContract> R21_CONTRACTS=Map.of("eva_prototype",new MeshContract(242686,62,false));
    private static final Map<String,MeshContract> R22_CONTRACTS=Map.of("eva_prototype",new MeshContract(243758,62,false),"eva_un01",new MeshContract(228610,62,false));
    private static final Map<String,MeshContract> R23_CONTRACTS=Map.of("eva_prototype",new MeshContract(239090,64,false),"eva_un01",new MeshContract(222409,64,false));
    private static final Map<String, Fingerprint> CACHE = new ConcurrentHashMap<>();

    private LocalVisualAssetFingerprint() {}

    public static Fingerprint inspect(String assetName)
    {
        return CACHE.computeIfAbsent(assetName, LocalVisualAssetFingerprint::load);
    }

    public static boolean isStrictMode()
    {
        return Boolean.getBoolean("projectseele.visualCapture")
                || Boolean.getBoolean("projectseele.strictHighDetail");
    }

    public static void clearCache()
    {
        CACHE.clear();
    }

    private static Fingerprint load(String assetName)
    {
        Map<String, ResourceDigest> resources = new LinkedHashMap<>();
        ResourceLocation mesh = resource("mesh/" + assetName + ".mesh.json");
        resources.put("mesh", digest(mesh));
        resources.put("geo", digest(resource("geo/" + assetName + ".geo.json")));
        resources.put("animation", digest(resource(
                "animations/" + assetName + ".animation.json")));
        resources.put("texture", digest(resource(
                "textures/entity/" + assetName + ".png")));

        boolean complete = resources.values().stream().allMatch(ResourceDigest::present);
        String sourcePack = complete ? resources.values().iterator().next().sourcePack() : "missing";
        boolean sameSource = complete && resources.values().stream()
                .allMatch(resource -> sourcePack.equals(resource.sourcePack()));
        String meshTag = LocalTriangleMeshLayer.captureTag(mesh);
        MeshContract contract = CONTRACTS.get(assetName);
        boolean meshMatches = contract != null
                && (contract.matches(meshTag, mesh) || R11_CONTRACTS.containsKey(assetName) && R11_CONTRACTS.get(assetName).matches(meshTag,mesh)
                || R13_CONTRACTS.containsKey(assetName) && R13_CONTRACTS.get(assetName).matches(meshTag,mesh)
                || R19_CONTRACTS.containsKey(assetName) && R19_CONTRACTS.get(assetName).matches(meshTag,mesh)
                || R21_CONTRACTS.containsKey(assetName) && R21_CONTRACTS.get(assetName).matches(meshTag,mesh)
                || R22_CONTRACTS.containsKey(assetName) && R22_CONTRACTS.get(assetName).matches(meshTag,mesh)
                || R23_CONTRACTS.containsKey(assetName) && R23_CONTRACTS.get(assetName).matches(meshTag,mesh)
                || matchesR48(assetName,sourcePack,meshTag)
                || matchesR30(assetName,sourcePack,resources,meshTag)
                || matchesR37(assetName,sourcePack,resources,meshTag));
        boolean valid = complete && sameSource && meshMatches;
        String reason = !complete ? "missing-resource"
                : !sameSource ? "mixed-resource-packs"
                : contract == null ? "unknown-mesh-contract"
                : !meshMatches ? "wrong-mesh-contract" : "ok";
        Fingerprint fingerprint = new Fingerprint(assetName, Map.copyOf(resources), meshTag,
                sourcePack, valid, reason);
        ProjectSeele.LOGGER.info("Local visual asset fingerprint: {}", fingerprint.description());
        return fingerprint;
    }
    private static boolean matchesR48(String name,String pack,String tag)
    {
        if(!name.equals("eva_prototype")&&!name.equals("eva_un01"))return false;
        var manager=Minecraft.getInstance().getResourceManager();
        var manifest=manager.getResource(resource("eva/un_models_r48.json"));
        if(manifest.isEmpty()||!manifest.get().sourcePackId().equals(pack))return false;
        try(var reader=manifest.get().openAsReader())
        {
            var document=com.google.gson.JsonParser.parseReader(reader).getAsJsonObject();
            if(!document.get("schema").getAsString().equals("projectseele.owner-tripo-r48.v1"))return false;
            var model=document.getAsJsonObject("models").getAsJsonObject(name);
            if(model==null)return false;
            int count=model.get("triangles").getAsInt(),parts=model.get("parts").getAsInt();
            if(count<100000||count>250000||parts<40||!tag.startsWith("triangle-mesh-"+count+"-p"+parts+"-"))return false;
            var geo=manager.getResource(resource("geo/"+name+".geo.json"));
            if(geo.isEmpty()||!geo.get().sourcePackId().equals(pack))return false;
            var bones=new java.util.HashMap<String,String>();
            try(var g=geo.get().openAsReader())
            {
                var rows=com.google.gson.JsonParser.parseReader(g).getAsJsonObject().getAsJsonArray("minecraft:geometry")
                        .get(0).getAsJsonObject().getAsJsonArray("bones");
                for(var row:rows)
                {
                    var b=row.getAsJsonObject();String key=b.get("name").getAsString();
                    if(bones.containsKey(key))return false;
                    bones.put(key,b.has("parent")?b.get("parent").getAsString():"");
                }
            }
            if(!bones.containsKey("tripo_hand_adapter_r48"))return false;
            for(String key:bones.keySet())
            {
                var visited=new java.util.HashSet<String>();String cursor=key;
                while(!cursor.isEmpty())
                {if(!visited.add(cursor)||!bones.containsKey(cursor))return false;cursor=bones.get(cursor);}
            }
            for(var key:model.getAsJsonArray("visible_parts"))
                if(!bones.containsKey(key.getAsString())||!LocalTriangleMeshLayer.hasPart(resource("mesh/"+name+".mesh.json"),key.getAsString()))return false;
            for(String side:new String[]{"l","r"})for(String digit:new String[]{"index","middle","ring","little","thumb"})
                for(String joint:new String[]{"","_tip","_distal"})
                    if(!bones.containsKey("finger_"+digit+joint+"_"+side))return false;
            for(String path:new String[]{"textures/entity/"+name+"_n.png","textures/entity/"+name+"_s.png",
                    "textures/entity/"+name+"_eyes.png","motion/un_finger_poses_r48.json"})
            {var value=manager.getResource(resource(path));if(value.isEmpty()||!value.get().sourcePackId().equals(pack))return false;}
            return true;
        }
        catch(Exception error){ProjectSeele.LOGGER.warn("R48 owner supplied UN model contract rejected for {}",name,error);return false;}
    }
    private static boolean matchesR30(String name,String pack,Map<String,ResourceDigest> resources,String tag)
    {
        if(!name.equals("eva_prototype")&&!name.equals("eva_un01"))return false;
        var manifest=Minecraft.getInstance().getResourceManager().getResource(resource("eva/un_models_r30.json"));if(manifest.isEmpty()||!pack.equals(manifest.get().sourcePackId()))return false;
        try(var reader=manifest.get().openAsReader())
        {
            var all=com.google.gson.JsonParser.parseReader(reader).getAsJsonObject();if(!all.get("schema").getAsString().equals("projectseele.un-models-r30.v1"))return false;
            var model=all.getAsJsonObject("models").getAsJsonObject(name);if(model==null||model.get("triangles").getAsInt()<200000)return false;
            if(!tag.startsWith("triangle-mesh-"+model.get("triangles").getAsInt()+"-p"+model.get("parts").getAsInt()+"-"))return false;
            for(var entry:resources.entrySet())if(!model.getAsJsonObject("sha256").get(entry.getKey()).getAsString().equals(entry.getValue().sha256()))return false;
            for(var entry:model.getAsJsonObject("pbr").entrySet())
            {var actual=digest(resource(entry.getKey()));if(!actual.present()||!actual.sourcePack().equals(pack)||!actual.sha256().equals(entry.getValue().getAsString()))return false;}
            return true;
        }
        catch(Exception error){ProjectSeele.LOGGER.warn("R30 model manifest rejected for {}",name,error);return false;}
    }

    private static boolean matchesR37(String name,String pack,Map<String,ResourceDigest> resources,String tag)
    {
        if(!name.equals("eva_unit01"))return false;
        var manifest=Minecraft.getInstance().getResourceManager().getResource(resource("eva/unit01_tv_jaw_r37.json"));
        if(manifest.isEmpty()||!pack.equals(manifest.get().sourcePackId()))return false;
        try(var reader=manifest.get().openAsReader())
        {
            var model=com.google.gson.JsonParser.parseReader(reader).getAsJsonObject();
            if(!model.get("schema").getAsString().equals("projectseele.tv-jaw-r37.v1")||model.get("triangles").getAsInt()<11666||model.get("parts").getAsInt()!=49)return false;
            if(!tag.startsWith("triangle-mesh-"+model.get("triangles").getAsInt()+"-p49-"))return false;
            for(var entry:resources.entrySet())if(!model.getAsJsonObject("sha256").get(entry.getKey()).getAsString().equals(entry.getValue().sha256()))return false;
            return true;
        }
        catch(Exception error){ProjectSeele.LOGGER.warn("R37 jaw manifest rejected",error);return false;}
    }

    private static ResourceLocation resource(String path)
    {
        return new ResourceLocation(ProjectSeele.MODID, path);
    }

    private static ResourceDigest digest(ResourceLocation location)
    {
        Optional<Resource> resource = Minecraft.getInstance().getResourceManager()
                .getResource(location);
        if (resource.isEmpty())
        {
            return new ResourceDigest(false, "missing", "missing");
        }
        try (var stream = resource.get().open())
        {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return new ResourceDigest(true, resource.get().sourcePackId(),
                    HexFormat.of().formatHex(digest.digest(stream.readAllBytes())));
        }
        catch (Exception exception)
        {
            ProjectSeele.LOGGER.error("Failed to fingerprint local visual resource " + location,
                    exception);
            return new ResourceDigest(false, "unreadable", "unreadable");
        }
    }

    private static String shortHash(String value)
    {
        if (value.length() >= 8 && value.chars().allMatch(character ->
                Character.digit(character, 16) >= 0))
        {
            return value.substring(0, 8);
        }
        try
        {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return HexFormat.of().formatHex(digest.digest(
                    value.getBytes(StandardCharsets.UTF_8))).substring(0, 8);
        }
        catch (Exception exception)
        {
            return "00000000";
        }
    }

    private record MeshContract(int triangles, int parts,
                                boolean nativeThumbs)
    {
        private boolean matches(String meshTag, ResourceLocation mesh)
        {
            if (!meshTag.startsWith("triangle-mesh-" + triangles
                    + "-p" + parts + "-"))
            {
                return false;
            }
            if (!nativeThumbs)
            {
                return true;
            }
            for (String side : new String[] {"l", "r"})
            {
                // SmOd already supplies the visible thumb as one authored
                // mesh.  The other four digits use the generated articulated
                // three-segment chains.  Requiring this exact split prevents
                // both the former doubled/overlong thumb and a silently
                // missing finger chain from passing strict mode.
                if (!LocalTriangleMeshLayer.hasPart(
                        mesh, "finger_thumb_" + side)
                        || LocalTriangleMeshLayer.hasPart(
                        mesh, "finger_thumb_distal_" + side)
                        || LocalTriangleMeshLayer.hasPart(
                        mesh, "finger_thumb_tip_" + side))
                {
                    return false;
                }
                for (String digit : new String[] {
                        "index", "middle", "ring", "little"})
                {
                    if (!LocalTriangleMeshLayer.hasPart(
                            mesh, "finger_" + digit + "_" + side)
                            || !LocalTriangleMeshLayer.hasPart(mesh,
                            "finger_" + digit + "_distal_" + side)
                            || !LocalTriangleMeshLayer.hasPart(mesh,
                            "finger_" + digit + "_tip_" + side))
                    {
                        return false;
                    }
                }
            }
            return true;
        }
    }

    public record ResourceDigest(boolean present, String sourcePack, String sha256) {}

    public record Fingerprint(String assetName, Map<String, ResourceDigest> resources,
                              String meshTag, String sourcePack, boolean valid, String reason)
    {
        public String compactTag()
        {
            return assetName + "-" + meshTag
                    + "-g" + shortHash(resources.get("geo").sha256())
                    + "-a" + shortHash(resources.get("animation").sha256())
                    + "-t" + shortHash(resources.get("texture").sha256())
                    + "-s" + shortHash(sourcePack);
        }

        public String description()
        {
            return compactTag() + " valid=" + valid + " reason=" + reason
                    + " source=" + sourcePack
                    + " meshSha256=" + resources.get("mesh").sha256()
                    + " geoSha256=" + resources.get("geo").sha256()
                    + " animationSha256=" + resources.get("animation").sha256()
                    + " textureSha256=" + resources.get("texture").sha256();
        }
    }
}
