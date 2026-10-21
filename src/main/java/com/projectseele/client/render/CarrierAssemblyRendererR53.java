package com.projectseele.client.render;

import com.google.gson.JsonArray;
import com.mojang.blaze3d.vertex.PoseStack;
import com.projectseele.world.CarrierAssemblyR53;
import java.util.LinkedHashMap;
import java.util.Map;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.resources.ResourceLocation;

/** Render the same source vertices and actuator frames used by carrier collision. */
final class CarrierAssemblyRendererR53
{
    private static Map<String, RigidMachineryPartR44> parts;

    static void clear() { parts = null; }

    static boolean draw(PoseStack poses, MultiBufferSource buffers, int light,
                        float rise, float release, double deckTravel)
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
            var frame = profile.frame(name, rise, release, deckTravel);
            poses.pushPose();
            var translation = frame.translation();
            poses.translate(translation.x, translation.y, translation.z);
            poses.mulPose(frame.rotation());
            mesh.draw(poses, buffers, light);
            poses.popPose();
        });
        return true;
    }

    private CarrierAssemblyRendererR53() { }
}
