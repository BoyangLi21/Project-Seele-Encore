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

/** Runtime identity of the local high-detail models: the pack that supplied
 * each resource and a digest naming its bytes, used for capture tags and logs.
 * Any edited asset is accepted; only a missing resource makes it invalid. */
public final class LocalVisualAssetFingerprint
{
    private static final Map<String, Fingerprint> CACHE = new ConcurrentHashMap<>();

    private LocalVisualAssetFingerprint() {}

    public static Fingerprint inspect(String assetName)
    {
        return CACHE.computeIfAbsent(assetName, LocalVisualAssetFingerprint::load);
    }

    public static boolean isStrictMode()
    {
        return Boolean.getBoolean("projectseele.strictHighDetail");
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
        String meshTag = LocalTriangleMeshLayer.captureTag(mesh);
        Fingerprint fingerprint = new Fingerprint(assetName, Map.copyOf(resources), meshTag,
                sourcePack, complete, complete ? "ok" : "missing-resource");
        ProjectSeele.LOGGER.info("Local visual asset fingerprint: {}", fingerprint.description());
        return fingerprint;
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
            byte[] buffer=new byte[65536];
            for(int count;(count=stream.read(buffer))!=-1;)digest.update(buffer,0,count);
            return new ResourceDigest(true, resource.get().sourcePackId(),
                    HexFormat.of().formatHex(digest.digest()));
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
