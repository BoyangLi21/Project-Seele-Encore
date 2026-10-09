package com.projectseele.client.render;

import com.google.gson.stream.JsonReader;
import com.google.gson.stream.JsonToken;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.math.Axis;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaDorsalMechanism;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.phys.Vec3;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;

/** Supplied textured mechanical surfaces, attached to the existing authoritative machinery. */
final class TripoMachineryR48
{
    private record Assembly(Map<String, RigidMachineryPartR44> parts, Map<String, Vec3> anchors) { }
    private static final Map<String, Assembly> CACHE = new HashMap<>();

    static void clearCache() { CACHE.clear(); }

    private static Assembly load(String name)
    {
        if (CACHE.containsKey(name)) return CACHE.get(name);
        Assembly result = null;
        var resource = new ResourceLocation(ProjectSeele.MODID, "mesh/tripo_" + name + "_r48.json");
        try (var input = Minecraft.getInstance().getResourceManager().open(resource);
             var reader = new InputStreamReader(input, StandardCharsets.UTF_8))
        {
            var json = new JsonReader(reader);json.setLenient(true);
            Map<String, RigidMachineryPartR44> parts = new HashMap<>();
            Map<String, Vec3> anchors = new HashMap<>();
            String textureName = null;boolean hasParts = false,hasAnchors = false;
            json.beginObject();
            while(json.hasNext())
            {
                switch(json.nextName())
                {
                    case "texture" -> textureName = json.nextString();
                    case "parts" ->
                    {
                        hasParts = true;parts.clear();json.beginObject();
                        while(json.hasNext()){String part = json.nextName();parts.put(part,RigidMachineryPartR44.readTextured(json));}
                        json.endObject();
                    }
                    case "anchors" ->
                    {
                        hasAnchors = true;anchors.clear();json.beginObject();
                        while(json.hasNext())
                        {
                            String anchor = json.nextName();json.beginArray();
                            double x = Double.parseDouble(json.nextString()),y = Double.parseDouble(json.nextString()),z = Double.parseDouble(json.nextString());
                            while(json.hasNext())json.skipValue();json.endArray();anchors.put(anchor,new Vec3(x,y,z));
                        }
                        json.endObject();
                    }
                    default -> json.skipValue();
                }
            }
            json.endObject();
            if(json.peek()!=JsonToken.END_DOCUMENT)throw new IllegalArgumentException("Trailing imported machinery document");
            if(!hasParts||!hasAnchors||textureName == null)throw new IllegalArgumentException("Incomplete imported machinery document");
            var texture = new ResourceLocation(textureName);
            if (Minecraft.getInstance().getResourceManager().getResource(texture).isEmpty())
                throw new IllegalStateException("Missing imported texture " + texture);
            parts.replaceAll((part,mesh)->mesh.withTexture(texture));
            if (!parts.containsKey("body")) throw new IllegalArgumentException("No machinery body");
            if (name.equals("gripper") && (!parts.keySet().containsAll(java.util.Set.of("jaw_left", "jaw_right"))
                    || !anchors.keySet().containsAll(java.util.Set.of("mount", "jaw_left", "jaw_right"))))
                throw new IllegalArgumentException("Incomplete clamp joints");
            if (name.equals("carrier") && (!parts.keySet().containsAll(java.util.Set.of("deck", "service_platform", "contact_pads"))
                    || !anchors.containsKey("service_platform"))) throw new IllegalArgumentException("Incomplete carrier assemblies");
            result = new Assembly(Map.copyOf(parts), Map.copyOf(anchors));
            ProjectSeele.LOGGER.info("R48 imported {}: {} moving assemblies", name, parts.size());
        }
        catch (Exception rejected)
        {
            ProjectSeele.LOGGER.warn("R48 {} unavailable; retaining existing complete mechanism", name, rejected);
        }
        CACHE.put(name, result);
        return result;
    }

    static Vec3 clampMount()
    {
        var assembly = load("gripper");
        return assembly == null ? null : assembly.anchors.get("mount");
    }

    /** Cable endpoint on a real imported upright, in the carrier's shared frame. */
    static Vec3 carrierPowerAnchor(EvaUnit01Entity unit,float partial)
    {
        var assembly=load("carrier");
        if(assembly==null||!assembly.anchors.containsKey("power_reel"))return null;
        var at=assembly.anchors.get("power_reel");
        Vec3 rear=Vec3.directionFromRotation(0,EvaUnit01Entity.SILO_BAY_YAW).scale(-1);
        Vec3 right=new Vec3(rear.z,0,-rear.x);
        float rise=unit.carrierRiseProgress(partial);
        return unit.carrierRenderPosition(partial).add(right.scale(at.x)).add(rear.scale(at.z))
                .add(0,at.y-64*(1-rise),0);
    }

    static boolean clamp(PoseStack poses, MultiBufferSource buffers, int light, float open)
    {
        var assembly = load("gripper");
        if (assembly == null) return false;
        assembly.parts.get("body").draw(poses, buffers, light);
        for (String side : new String[] {"left", "right"})
        {
            String key = "jaw_" + side;
            Vec3 pivot = assembly.anchors.get(key);
            poses.pushPose();poses.translate(pivot.x, pivot.y, pivot.z);
            poses.mulPose(Axis.ZP.rotationDegrees((side.equals("left") ? -1 : 1) * 32 * open));
            poses.translate(-pivot.x, -pivot.y, -pivot.z);
            assembly.parts.get(key).draw(poses, buffers, light);poses.popPose();
        }
        return true;
    }

    static boolean carrier(PoseStack poses, MultiBufferSource buffers, int light, EvaUnit01Entity unit, float partial)
    {
        var assembly = load("carrier");
        if (assembly == null) return false;
        float rise = unit.carrierRiseProgress(partial);
        poses.pushPose();
        if (unit.recoveryRackR39()) poses.translate(0, -3 * (1 - rise), 0);
        assembly.parts.get("deck").draw(poses, buffers, light);poses.popPose();
        poses.pushPose();poses.translate(0, -64 * (1 - rise), 0);
        float release = unit.getLaunchPhase() == EvaUnit01Entity.LAUNCH_CLEAR
                ? EvaDorsalMechanism.smooth(1 - (unit.getLaunchTicks() - partial) / 18F) : 0;
        assembly.parts.get("body").draw(poses, buffers, light);
        poses.pushPose();poses.translate(0, 0, 1.5F * release);
        assembly.parts.get("contact_pads").draw(poses,buffers,light);poses.popPose();
        // Its full-width standing platform belongs outside the narrow shaft.
        // Fold it about the supplied hinge before any carrier travel.
        Vec3 hinge = assembly.anchors.get("service_platform");
        poses.pushPose();poses.translate(hinge.x, hinge.y, hinge.z);
        poses.mulPose(Axis.ZP.rotationDegrees(-90));
        poses.translate(-hinge.x, -hinge.y, -hinge.z);
        assembly.parts.get("service_platform").draw(poses, buffers, light);
        poses.popPose();poses.popPose();
        return true;
    }

    private TripoMachineryR48() { }
}
