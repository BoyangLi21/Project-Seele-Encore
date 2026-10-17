package com.projectseele.client;

import net.minecraft.client.Minecraft;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import java.util.function.IntSupplier;

/** Optional Oculus binding; the server's real lever remains the source of truth. */
public final class CommandShaderLightR39
{
    private static final BlockPos LEVER=new BlockPos(26,-405,275);
    private static java.lang.ref.WeakReference<Object> previousLevel=new java.lang.ref.WeakReference<>(null);private static long tick=Long.MIN_VALUE;private static int value=1;
    public static int current()
    {
        var level=Minecraft.getInstance().level;
        if(level==null)return 1;
        if(level!=previousLevel.get()||level.getGameTime()!=tick)
        {
            previousLevel=new java.lang.ref.WeakReference<>(level);tick=level.getGameTime();value=1;
            var lever=FacilityFrameClientR52.headquarters(level,LEVER);
            if(level.dimension().location().toString().equals("projectseele:geofront")&&level.hasChunkAt(lever))
            {
                var state=level.getBlockState(lever);
                if(state.hasProperty(BlockStateProperties.POWERED))value=state.getValue(BlockStateProperties.POWERED)?1:0;
            }
        }
        return value;
    }
    @SuppressWarnings({"rawtypes","unchecked"})
    public static void bind(Object uniforms)
    {
        try
        {
            var loader=uniforms.getClass().getClassLoader();
            var holder=Class.forName("net.irisshaders.iris.gl.uniform.UniformHolder",true,loader);
            var frequency=Class.forName("net.irisshaders.iris.gl.uniform.UniformUpdateFrequency",true,loader);
            Object perFrame=Enum.valueOf((Class)frequency,"PER_FRAME");
            holder.getMethod("uniform1i",frequency,String.class,IntSupplier.class).invoke(uniforms,perFrame,"seeleCommandLights",(IntSupplier)CommandShaderLightR39::current);
            for(int axis=0;axis<3;axis++)
            {
                final int component=axis;
                holder.getMethod("uniform1i",frequency,String.class,IntSupplier.class).invoke(uniforms,perFrame,"seeleHeadquarters"+"XYZ".charAt(axis),(IntSupplier)()->headquartersOffset(component));
            }
        }
        catch(ReflectiveOperationException failure){throw new IllegalStateException("Pinned Oculus command-light binding changed",failure);}
    }
    private static int headquartersOffset(int axis)
    {
        var level=Minecraft.getInstance().level;
        var p=level==null?BlockPos.ZERO:FacilityFrameClientR52.headquarters(level,BlockPos.ZERO);
        return axis==0?p.getX():axis==1?p.getY():p.getZ();
    }
    private CommandShaderLightR39(){}
}
