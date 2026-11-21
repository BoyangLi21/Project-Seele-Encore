package com.projectseele.mixin;

import net.minecraft.server.level.ChunkHolder;
import net.minecraft.server.level.ChunkMap;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.gen.Invoker;

@Mixin(ChunkMap.class)
public interface CityChunkMapAccessor
{
    @Invoker("getChunks")
    Iterable<ChunkHolder> seele$chunksR65();
}
