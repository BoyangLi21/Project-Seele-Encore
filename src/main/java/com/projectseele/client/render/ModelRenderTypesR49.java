package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.DefaultVertexFormat;
import com.mojang.blaze3d.vertex.VertexFormat;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.resources.ResourceLocation;
import java.util.HashMap;
import java.util.Map;

/** Smooth sampling for imported model atlases; block textures stay unchanged. */
final class ModelRenderTypesR49 extends RenderType
{
    private static final Map<ResourceLocation, RenderType> TYPES = new HashMap<>();
    private static final Map<ResourceLocation, RenderType> SOLID = new HashMap<>();

    private ModelRenderTypesR49(String name, com.mojang.blaze3d.vertex.VertexFormat format,
                               VertexFormat.Mode mode, int size, boolean crumbling,
                               boolean sorted, Runnable setup, Runnable clear)
    {
        super(name, format, mode, size, crumbling, sorted, setup, clear);
    }

    static RenderType entity(ResourceLocation texture)
    {
        if (!texture.getNamespace().equals("projectseele")
                || !(texture.getPath().startsWith("textures/entity/")
                || texture.getPath().startsWith("dynamic/unit01_eyes_")))
            return RenderType.entityCutoutNoCull(texture);
        return TYPES.computeIfAbsent(texture, key -> create("entity_cutout_no_cull",
                DefaultVertexFormat.NEW_ENTITY, VertexFormat.Mode.QUADS, 256, true, false,
                CompositeState.builder().setShaderState(RENDERTYPE_ENTITY_CUTOUT_NO_CULL_SHADER)
                        .setTextureState(new TextureStateShard(key, true, false))
                        .setCullState(NO_CULL).setLightmapState(LIGHTMAP).setOverlayState(OVERLAY)
                        .createCompositeState(true)));
    }

    static RenderType solid(ResourceLocation texture)
    {
        if(!texture.getNamespace().equals("projectseele")||!texture.getPath().startsWith("textures/entity/"))
            return RenderType.entitySolid(texture);
        return SOLID.computeIfAbsent(texture,key->create("entity_solid",DefaultVertexFormat.NEW_ENTITY,
                VertexFormat.Mode.QUADS,256,true,false,CompositeState.builder()
                        .setShaderState(RENDERTYPE_ENTITY_SOLID_SHADER)
                        .setTextureState(new TextureStateShard(key,true,false))
                        .setLightmapState(LIGHTMAP).setOverlayState(OVERLAY).createCompositeState(true)));
    }
    static void clear() { TYPES.clear(); SOLID.clear(); }
}
