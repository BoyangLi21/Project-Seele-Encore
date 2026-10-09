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
    private static final Map<ResourceLocation, RenderType> OPTICS = new HashMap<>();
    private static final Map<ResourceLocation, RenderType> LIT_OPTICS = new HashMap<>();
    private record TriangleTexture(ResourceLocation texture, boolean smooth) { }
    private static final Map<TriangleTexture, RenderType> TRIANGLES = new HashMap<>();
    private static final Map<ResourceLocation, RenderType> TRIANGLE_OPTICS = new HashMap<>();
    private static final Map<ResourceLocation, RenderType> TRIANGLE_LIT_OPTICS = new HashMap<>();
    private static final Map<ResourceLocation, RenderType> TRIANGLE_SOLID = new HashMap<>();

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

    static RenderType entityTriangles(ResourceLocation texture)
    {
        boolean smooth=texture.getNamespace().equals("projectseele")
                && (texture.getPath().startsWith("textures/entity/")
                || texture.getPath().startsWith("dynamic/unit01_eyes_"));
        return entityTriangles(texture,smooth);
    }

    static RenderType solidTriangles(ResourceLocation texture)
    {
        return TRIANGLE_SOLID.computeIfAbsent(texture,key->create("entity_solid",DefaultVertexFormat.NEW_ENTITY,
                VertexFormat.Mode.TRIANGLES,256,true,false,CompositeState.builder()
                        .setShaderState(RENDERTYPE_ENTITY_SOLID_SHADER)
                        .setTextureState(new TextureStateShard(key,key.getNamespace().equals("projectseele")
                                &&key.getPath().startsWith("textures/entity/"),false))
                        .setLightmapState(LIGHTMAP).setOverlayState(OVERLAY).createCompositeState(true)));
    }

    static RenderType entityTriangles(ResourceLocation texture,boolean smooth)
    {
        // Iris's QUADS extension replaces smooth normals with a face normal.
        // A separate type keeps three-point meshes out of ordinary quad buffers.
        return TRIANGLES.computeIfAbsent(new TriangleTexture(texture,smooth),key->create("entity_cutout_no_cull",
                DefaultVertexFormat.NEW_ENTITY,VertexFormat.Mode.TRIANGLES,256,true,false,
                CompositeState.builder().setShaderState(RENDERTYPE_ENTITY_CUTOUT_NO_CULL_SHADER)
                        .setTextureState(new TextureStateShard(key.texture(),key.smooth(),false))
                        .setCullState(NO_CULL).setLightmapState(LIGHTMAP).setOverlayState(OVERLAY)
                        .createCompositeState(true)));
    }

    static boolean opticTexture(ResourceLocation texture)
    {
        return texture.getNamespace().equals("projectseele")
                && (texture.getPath().endsWith("_eyes.png")
                || texture.getPath().startsWith("dynamic/unit01_eyes_"));
    }
    static RenderType optics(ResourceLocation texture,boolean emissive)
    {
        return (emissive?LIT_OPTICS:OPTICS).computeIfAbsent(texture,
                key->createOptics(key,emissive,VertexFormat.Mode.QUADS));
    }

    static RenderType opticsTriangles(ResourceLocation texture,boolean emissive)
    {
        return (emissive?TRIANGLE_LIT_OPTICS:TRIANGLE_OPTICS).computeIfAbsent(texture,
                key->createOptics(key,emissive,VertexFormat.Mode.TRIANGLES));
    }

    private static RenderType createOptics(ResourceLocation texture,boolean emissive,VertexFormat.Mode mode)
    {
        // The eyes shader carries emission through Oculus; entity lightmap
        // brightness alone still leaves an optic in the shaded body pass.
        if(emissive)
            return create("eyes",
                    DefaultVertexFormat.NEW_ENTITY,mode,256,false,true,
                    CompositeState.builder().setShaderState(RENDERTYPE_EYES_SHADER)
                            .setTextureState(new TextureStateShard(texture,true,false))
                            .setTransparencyState(ADDITIVE_TRANSPARENCY).setWriteMaskState(COLOR_WRITE)
                            .setLayeringState(VIEW_OFFSET_Z_LAYERING).setCullState(NO_CULL)
                            .createCompositeState(false));
        // Both optic states reuse the exact skinned head surface. Give that
        // coplanar decal a depth bias so the base head cannot overwrite it
        // when buffered entity batches are flushed in a different order.
        return create("entity_cutout_no_cull",
                DefaultVertexFormat.NEW_ENTITY,mode,256,true,false,
                CompositeState.builder().setShaderState(RENDERTYPE_ENTITY_CUTOUT_NO_CULL_SHADER)
                        .setTextureState(new TextureStateShard(texture,true,false))
                        .setLayeringState(VIEW_OFFSET_Z_LAYERING).setCullState(NO_CULL)
                        .setLightmapState(LIGHTMAP).setOverlayState(OVERLAY)
                        .createCompositeState(true));
    }
    static void clear()
    {
        TYPES.clear();SOLID.clear();OPTICS.clear();LIT_OPTICS.clear();
        TRIANGLES.clear();TRIANGLE_OPTICS.clear();TRIANGLE_LIT_OPTICS.clear();
        TRIANGLE_SOLID.clear();
    }
}
