package com.projectseele.client;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.NervSlidingDoorEntity;
import net.minecraft.client.Minecraft;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.phys.AABB;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RenderHighlightEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Keep the invisible collision cells from drawing voxel wireframes over a real door leaf. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class NervDoorHighlightR45
{
    @SubscribeEvent public static void block(RenderHighlightEvent.Block event)
    {
        var level=Minecraft.getInstance().level;if(level==null)return;
        BlockPos at=event.getTarget().getBlockPos();if(!level.getBlockState(at).is(Blocks.BARRIER))return;
        for(var door:level.getEntitiesOfClass(NervSlidingDoorEntity.class,new AABB(at).inflate(3)))
        {
            BlockPos centre=door.blockPosition();int across=door.isAxisX()?at.getX()-centre.getX():at.getZ()-centre.getZ();
            int normal=door.isAxisX()?at.getZ()-centre.getZ():at.getX()-centre.getX();
            if(door.getDoorId()>=0&&normal==0&&Math.abs(across)<=1&&at.getY()>=centre.getY()&&at.getY()<centre.getY()+2)
            {event.setCanceled(true);return;}
        }
    }
    private NervDoorHighlightR45() {}
}
