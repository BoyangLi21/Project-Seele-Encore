package com.projectseele.mixin.client;

import com.mojang.blaze3d.vertex.BufferBuilder;
import com.mojang.blaze3d.vertex.DefaultedVertexConsumer;
import com.mojang.blaze3d.vertex.VertexFormat;
import com.projectseele.client.render.DirectVertexTarget;
import java.nio.ByteBuffer;
import org.lwjgl.system.MemoryUtil;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;

/** Lets {@link com.projectseele.client.render.DirectMeshWriter} write whole quads between vertices. */
@Mixin(BufferBuilder.class)
public abstract class BufferBuilderDirectMixin extends DefaultedVertexConsumer implements DirectVertexTarget
{
    @Shadow private ByteBuffer buffer;
    @Shadow private int nextElementByte;
    @Shadow private int vertices;
    @Shadow private int elementIndex;
    @Shadow private VertexFormat format;
    @Shadow private VertexFormat.Mode mode;
    @Shadow private boolean building;
    @Shadow protected abstract void ensureCapacity(int bytes);

    @Override public VertexFormat projectseele$quadFormat()
    {
        return building&&mode==VertexFormat.Mode.QUADS&&elementIndex==0&&!defaultColorSet?format:null;
    }

    @Override public long projectseele$end()
    {
        return MemoryUtil.memAddress(buffer,nextElementByte);
    }

    @Override public long projectseele$reserve(int count)
    {
        int stride=format.getVertexSize(),bytes=count*stride;
        // endVertex always leaves room for one more vertex.
        ensureCapacity(bytes+stride);
        long address=MemoryUtil.memAddress(buffer,nextElementByte);
        nextElementByte+=bytes;vertices+=count;
        return address;
    }
}
