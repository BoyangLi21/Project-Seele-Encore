package com.projectseele.client.render;

import com.google.gson.JsonArray;
import com.mojang.blaze3d.vertex.PoseStack;
import com.projectseele.world.CarrierAssemblyR53;
import com.projectseele.world.CarrierMountProfileR53;
import com.projectseele.world.CarrierFootBearingR53;
import java.util.LinkedHashMap;
import java.util.Map;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.resources.ResourceLocation;

/** Render the same source vertices and actuator frames used by carrier collision. */
final class CarrierAssemblyRendererR53
{
    private static Map<String, RigidMachineryPartR44> parts;
    private static final Map<String, RigidMachineryPartR44> soles = new LinkedHashMap<>();

    static void clear() { parts = null;soles.clear(); }

    static boolean draw(PoseStack poses, MultiBufferSource buffers, int light,
                        float rise, float release, double deckTravel)
    { return draw(poses, buffers, light, rise, release, deckTravel, -1, CarrierMountProfileR53.LEGACY); }

    static boolean draw(PoseStack poses, MultiBufferSource buffers, int light,
                        float rise, float release, double deckTravel, int variant, CarrierMountProfileR53.State mounting)
    {
        var profile = CarrierAssemblyR53.selected();
        if (profile == null) return false;
        if (parts == null)
        {
            var loaded = new LinkedHashMap<String, RigidMachineryPartR44>();
            profile.parts().forEach((name, source) ->
            {
                var encoded = new JsonArray();
                for (float value : source.encoded()) encoded.add(value);
                loaded.put(name, RigidMachineryPartR44.textured(encoded, new ResourceLocation(source.texture())));
            });
            parts = Map.copyOf(loaded);
        }
        parts.forEach((name, mesh) ->
        {
            if (mounting.supportOnly() && !name.equals("deck") && !name.startsWith("toe_")) return;
            var frame = profile.frame(name, rise, release, deckTravel, mounting);
            poses.pushPose();
            var translation = frame.translation();
            poses.translate(translation.x, translation.y, translation.z);
            poses.mulPose(frame.rotation());
            mesh.draw(poses, buffers, light);
            poses.popPose();
        });
        if (mounting.aboveFloor() || mounting.shallowBay() || mounting.supportOnly())
        {
            var source = java.util.Objects.requireNonNull(CarrierFootBearingR53.selected(), "Selected finite sole supports required");
            for (var pad : source.variant(variant))
            {
                var mesh = soles.computeIfAbsent(source.fingerprint() + "/" + pad.name(), key -> { var encoded = new JsonArray();for (double value : pad.rgb()) encoded.add(value);return RigidMachineryPartR44.triangles(encoded); });
                poses.pushPose();poses.translate(0, mounting.elevation(), 0);mesh.draw(poses, buffers, light);poses.popPose();
            }
        }
        return true;
    }

    private CarrierAssemblyRendererR53() { }
}
