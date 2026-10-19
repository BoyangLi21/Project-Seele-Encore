package com.projectseele.client;

import com.projectseele.registry.ModBlocks;
import com.projectseele.world.OneWayGlassBlock;
import com.projectseele.world.OneWayGlassBlockEntity;
import java.util.List;
import java.util.Set;
import java.util.HashSet;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.block.model.BakedQuad;
import net.minecraft.client.resources.model.BakedModel;
import net.minecraft.client.resources.model.ModelResourceLocation;
import net.minecraft.client.renderer.block.BlockModelShaper;
import net.minecraft.core.Direction;
import net.minecraft.core.SectionPos;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.ChunkRenderTypeSet;
import net.minecraftforge.client.event.ModelEvent;
import net.minecraftforge.client.model.BakedModelWrapper;
import net.minecraftforge.client.model.data.ModelData;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** The directional facade is static terrain between crossings of the building boundary. */
@Mod.EventBusSubscriber(modid="projectseele",value=Dist.CLIENT)
public final class OneWayGlassVisibilityR53
{
    private static volatile boolean inside;
    private static ClientLevel previousLevel;

    @SubscribeEvent public static void tick(TickEvent.ClientTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END)return;
        var mc=Minecraft.getInstance();var level=mc.level;
        if(level==null){previousLevel=null;inside=false;return;}
        boolean next=FacilityFrameClientR52.insidePyramid(level,mc.gameRenderer.getMainCamera().getPosition());
        if(previousLevel==level&&next==inside)return;
        previousLevel=level;inside=next;
        // Only loaded sections containing these panes need new terrain meshes.
        // New chunks use the current visibility when they are first compiled.
        var camera=mc.gameRenderer.getMainCamera().getPosition();
        int cx=(int)Math.floor(camera.x)>>4,cz=(int)Math.floor(camera.z)>>4;
        int distance=mc.options.getEffectiveRenderDistance()+2;
        Set<SectionPos> sections=new HashSet<>();
        for(int x=cx-distance;x<=cx+distance;x++)for(int z=cz-distance;z<=cz+distance;z++)
        {
            var chunk=level.getChunkSource().getChunk(x,z,net.minecraft.world.level.chunk.ChunkStatus.FULL,false);
            if(chunk==null)continue;
            for(var entity:chunk.getBlockEntities().values())if(entity instanceof OneWayGlassBlockEntity)
                sections.add(SectionPos.of(entity.getBlockPos()));
        }
        for(var section:sections)mc.levelRenderer.setSectionDirty(section.x(),section.y(),section.z());
    }

    @Mod.EventBusSubscriber(modid="projectseele",bus=Mod.EventBusSubscriber.Bus.MOD,value=Dist.CLIENT)
    public static final class Models
    {
        @SubscribeEvent public static void bake(ModelEvent.ModifyBakingResult event)
        {
            for(var state:ModBlocks.ONE_WAY_GLASS.get().getStateDefinition().getPossibleStates())
            {
                if(!state.getValue(OneWayGlassBlock.PYRAMID))continue;
                ModelResourceLocation key=BlockModelShaper.stateToModelLocation(state);
                BakedModel original=event.getModels().get(key);
                if(original!=null)event.getModels().put(key,new BakedModelWrapper<BakedModel>(original)
                {
                    @Override public List<BakedQuad> getQuads(BlockState block,Direction side,RandomSource random)
                    {return inside?List.of():super.getQuads(block,side,random);}
                    @Override public List<BakedQuad> getQuads(BlockState block,Direction side,RandomSource random,ModelData data,RenderType layer)
                    {return inside?List.of():super.getQuads(block,side,random,data,layer);}
                    @Override public ChunkRenderTypeSet getRenderTypes(BlockState block,RandomSource random,ModelData data)
                    {return ChunkRenderTypeSet.of(RenderType.solid());}
                });
            }
        }
    }
    private OneWayGlassVisibilityR53(){}
}
