package com.projectseele.client.render;

import com.google.gson.stream.JsonReader;
import com.google.gson.stream.JsonToken;
import com.google.gson.JsonParser;
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

    static void clearCache() { CACHE.clear(); NervFootGuideRigRendererR52.clear(); NervLegacyCarrierRideRendererR52.clear(); }
    static boolean selectedRunningDeckR52(){String key="selected_running_deck";var cached=CACHE.get(key);if(cached!=null)return cached.parts().containsKey("deck");try(var input=Minecraft.getInstance().getResourceManager().open(new ResourceLocation(ProjectSeele.MODID,"eva/full_assembly_geometry_r52_sources.json"));var reader=new InputStreamReader(input,StandardCharsets.UTF_8)){var j=JsonParser.parseReader(reader).getAsJsonObject();boolean selected=j.getAsJsonObject("resources").has(com.projectseele.world.NervLegacyCarrierRideR52.DECK_SOURCE);if(!selected){CACHE.put(key,new Assembly(Map.of(),Map.of()));return false;}try(var deckInput=Minecraft.getInstance().getResourceManager().open(new ResourceLocation(ProjectSeele.MODID,com.projectseele.world.NervLegacyCarrierRideR52.DECK_SOURCE));var deckReader=new InputStreamReader(deckInput,StandardCharsets.UTF_8)){var d=JsonParser.parseReader(deckReader).getAsJsonObject();if(!d.get("schema").getAsString().equals("projectseele.r52.actual-running-deck-housings.v1")||d.get("stride").getAsInt()!=8)throw new IllegalStateException("Selected original housing deck source required");var original=load("carrier");if(original==null)throw new IllegalStateException("Original Tripo material source required");var material=new ResourceLocation("projectseele:textures/entity/tripo_carrier_r48.png");var part=RigidMachineryPartR44.textured(d.getAsJsonObject("parts").getAsJsonArray("deck"),material);CACHE.put(key,new Assembly(Map.of("deck",part),Map.of()));return true;}}catch(Exception unavailable){throw new IllegalStateException("Declared carrier running deck selection unavailable",unavailable);}}
    private static RigidMachineryPartR44 selectedDeckR52(Assembly original){return selectedRunningDeckR52()?CACHE.get("selected_running_deck").parts().get("deck"):original.parts().get("deck");}
    private static Assembly soleBearings(int variant)
    {
        String key="engineered_sole_bearings_"+variant;if(CACHE.containsKey(key))return CACHE.get(key);
        var resource=new ResourceLocation(ProjectSeele.MODID,"mesh/carrier_sole_bearings_r52.json");
        try(var input=Minecraft.getInstance().getResourceManager().open(resource);var reader=new InputStreamReader(input,StandardCharsets.UTF_8))
        {var root=JsonParser.parseReader(reader).getAsJsonObject();if(!root.get("schema").getAsString().equals("projectseele.r52.engineered-carrier-sole-bearings.v1")||root.get("stride").getAsInt()!=8)throw new IllegalStateException("Engineered steel bearing source changed");var material=new ResourceLocation(root.get("texture").getAsString());var parts=new HashMap<String,RigidMachineryPartR44>();for(String side:java.util.List.of("l","r")){String name="sole_bearing_"+variant+"_"+side;parts.put(name,RigidMachineryPartR44.textured(root.getAsJsonObject("parts").getAsJsonArray(name),material));}var result=new Assembly(Map.copyOf(parts),Map.of());CACHE.put(key,result);return result;}
        catch(Exception failure){throw new IllegalStateException("Declared physical carrier requires its exact engineered steel shoes",failure);}
    }
    private static Assembly trimmedCarrierBody()
    {
        String key="engineered_upper_carrier_body";if(CACHE.containsKey(key))return CACHE.get(key);var resource=new ResourceLocation(ProjectSeele.MODID,"mesh/carrier_body_trimmed_r52.json");
        try(var input=Minecraft.getInstance().getResourceManager().open(resource);var reader=new InputStreamReader(input,StandardCharsets.UTF_8))
        {var json=new JsonReader(reader);String schema=null,paint=null,cap=null;var parts=new HashMap<String,RigidMachineryPartR44>();json.beginObject();while(json.hasNext())switch(json.nextName()){case "schema"->schema=json.nextString();case "texture"->paint=json.nextString();case "cap_texture"->cap=json.nextString();case "parts"->{json.beginObject();while(json.hasNext())parts.put(json.nextName(),RigidMachineryPartR44.readTextured(json));json.endObject();}default->json.skipValue();}json.endObject();if(!"projectseele.r52.trimmed-carrier-upper-frame.v1".equals(schema)||!parts.keySet().equals(java.util.Set.of("body_trimmed_r52","upper_frame_cap_r52","interior_cut_caps_r52"))||paint==null||cap==null)throw new IllegalStateException("Actual trimmed carrier source incomplete");var bodyTexture=new ResourceLocation(paint);var capTexture=new ResourceLocation(cap);parts.replaceAll((name,part)->part.withTexture(name.endsWith("cap_r52")||name.endsWith("caps_r52")?capTexture:bodyTexture));var result=new Assembly(Map.copyOf(parts),Map.of());CACHE.put(key,result);return result;}
        catch(Exception failure){throw new IllegalStateException("Declared carrier requires its actual selected trimmed upper body and steel cap",failure);}
    }

    private static Assembly stowedService()
    {
        String key="actual_latched_carrier_service";if(CACHE.containsKey(key))return CACHE.get(key);var resource=new ResourceLocation(ProjectSeele.MODID,"mesh/carrier_service_stow_r52.json");
        try(var input=Minecraft.getInstance().getResourceManager().open(resource);var reader=new InputStreamReader(input,StandardCharsets.UTF_8))
        {var root=JsonParser.parseReader(reader).getAsJsonObject();if(!root.get("schema").getAsString().equals("projectseele.r52.actual-carrier-service-stow.v1")||!root.get("latched_stow").getAsBoolean())throw new IllegalStateException("Physical carrier service stow source required");var parts=new HashMap<String,RigidMachineryPartR44>();var paint=new ResourceLocation(root.get("texture").getAsString());var steel=new ResourceLocation("minecraft:textures/block/iron_block.png");for(var p:root.getAsJsonObject("parts").entrySet())parts.put(p.getKey(),RigidMachineryPartR44.textured(p.getValue().getAsJsonArray(),p.getKey().startsWith("stow_")?steel:paint));var result=new Assembly(Map.copyOf(parts),Map.of());CACHE.put(key,result);return result;}
        catch(Exception failure){throw new IllegalStateException("Declared physical carrier requires its actual folded service parts and hardware",failure);}
    }

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
        if(com.projectseele.entity.EvaMechanicalFrameR52.hasOriginalCarrierControllerR52(unit)){var actor=com.projectseele.entity.EvaMechanicalFrameR52.originalCarrierControllerR52(unit);if(actor==null||!com.projectseele.world.NervOriginalCarrierR52.attachedTo(actor,unit))return null;}
        var assembly=load("carrier");
        if(assembly==null||!assembly.anchors.containsKey("power_reel"))return null;
        var at=assembly.anchors.get("power_reel");
        if(com.projectseele.entity.EvaMechanicalFrameR52.detachedCarrierR52(unit))return com.projectseele.entity.EvaMechanicalFrameR52.carrierFrameR52(unit,partial).transformPoint(at.add(0,-64*(1-unit.carrierRiseProgress(partial)),0));
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
        double deckTravel=com.projectseele.entity.EvaMechanicalFrameR52.carrierDeckTravelR52(unit);if(deckTravel>0)poses.translate(0,-deckTravel*(1-rise),0);
        (deckTravel==64?selectedDeckR52(assembly):assembly.parts.get("deck")).draw(poses, buffers, light);if(deckTravel==64)for(var part:soleBearings(unit.getUnitVariant()).parts.values())part.draw(poses,buffers,light);poses.popPose();
        poses.pushPose();poses.translate(0, -64 * (1 - rise), 0);
        float release = unit.getLaunchPhase() == EvaUnit01Entity.LAUNCH_CLEAR
                ? EvaDorsalMechanism.smooth(1 - (unit.getLaunchTicks() - partial) / 18F) : 0;
        if(deckTravel==64)for(var part:trimmedCarrierBody().parts.values())part.draw(poses,buffers,light);else assembly.parts.get("body").draw(poses, buffers, light);
        poses.pushPose();if(deckTravel!=64)poses.translate(0, 0, 1.5F * release);
        if(deckTravel==64)for(var part:stowedService().parts.values())part.draw(poses,buffers,light);else assembly.parts.get("contact_pads").draw(poses,buffers,light);poses.popPose();
        // Its full-width standing platform belongs outside the narrow shaft.
        // Fold it about the supplied hinge before any carrier travel.
        if(deckTravel==64){poses.popPose();return true;}
        Vec3 hinge = assembly.anchors.get("service_platform");
        poses.pushPose();poses.translate(hinge.x, hinge.y, hinge.z);
        poses.mulPose(Axis.ZP.rotationDegrees(-90));
        poses.translate(-hinge.x, -hinge.y, -hinge.z);
        assembly.parts.get("service_platform").draw(poses, buffers, light);
        poses.popPose();poses.popPose();
        NervFootGuideRigRendererR52.render(poses,light,unit,partial);
        return true;
    }

    private TripoMachineryR48() { }
    static boolean originalCarrier(PoseStack poses,MultiBufferSource buffers,int light,int variant,float rise){var a=load("carrier");if(a==null)return false;poses.pushPose();poses.translate(0,-64D*(1-rise),0);selectedDeckR52(a).draw(poses,buffers,light);for(var p:soleBearings(variant).parts.values())p.draw(poses,buffers,light);for(var p:trimmedCarrierBody().parts.values())p.draw(poses,buffers,light);for(var p:stowedService().parts.values())p.draw(poses,buffers,light);poses.popPose();return true;}
}
