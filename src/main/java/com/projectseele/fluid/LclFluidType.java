package com.projectseele.fluid;

import java.util.function.Consumer;

import org.joml.Vector3f;

import com.mojang.blaze3d.shaders.FogShape;
import com.mojang.blaze3d.systems.RenderSystem;
import net.minecraft.client.Camera;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.renderer.FogRenderer;
import net.minecraft.resources.ResourceLocation;
import net.minecraftforge.client.extensions.common.IClientFluidTypeExtensions;
import net.minecraftforge.fluids.FluidType;

/** Orange-red LCL with the active resource pack's native water surface. */
public final class LclFluidType extends FluidType
{
    private static final ResourceLocation STILL = new ResourceLocation(
            "minecraft", "block/water_still");
    private static final ResourceLocation FLOW = new ResourceLocation(
            "minecraft", "block/water_flow");
    private static final ResourceLocation OVERLAY = new ResourceLocation(
            "minecraft", "block/water_overlay");
    // R45 inherits water animation, normals and transparency. Only the tint
    // differs; do not force the atlas sprite to opaque or replace water math.
    public static final int TINT = 0xFFDB5420;

    public LclFluidType()
    {
        super(Properties.create()
                .descriptionId("fluid_type.projectseele.lcl")
                .motionScale(0.014D)
                .canPushEntity(true)
                .canSwim(true)
                .canDrown(false)
                .fallDistanceModifier(0.0F)
                .canExtinguish(false)
                .canConvertToSource(false)
                .supportsBoating(false)
                .canHydrate(false)
                .lightLevel(4)
                .density(1050)
                .temperature(310)
                .viscosity(1250));
    }

    @Override
    public void initializeClient(Consumer<IClientFluidTypeExtensions> consumer)
    {
        consumer.accept(new IClientFluidTypeExtensions()
        {
            @Override
            public ResourceLocation getStillTexture()
            {
                return STILL;
            }

            @Override
            public ResourceLocation getFlowingTexture()
            {
                return FLOW;
            }

            @Override
            public ResourceLocation getOverlayTexture()
            {
                return OVERLAY;
            }

            @Override
            public int getTintColor()
            {
                return TINT;
            }

            @Override
            public Vector3f modifyFogColor(Camera camera, float partialTick,
                                           ClientLevel level, int renderDistance,
                                           float darkenWorldAmount,
                                           Vector3f fluidFogColor)
            {
                return new Vector3f(0.86F, 0.33F, 0.125F);
            }

            @Override
            public void modifyFogRender(Camera camera, FogRenderer.FogMode mode,
                                        float renderDistance, float partialTick,
                                        float nearDistance, float farDistance,
                                        FogShape shape)
            {
                RenderSystem.setShaderFogStart(0.0F);
                RenderSystem.setShaderFogEnd(Math.min(renderDistance, 6.0F));
                RenderSystem.setShaderFogShape(FogShape.SPHERE);
            }
        });
    }
}
