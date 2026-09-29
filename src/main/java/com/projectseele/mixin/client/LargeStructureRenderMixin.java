package com.projectseele.mixin.client;

import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.IndustrialMemberEntity;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.LevelRenderer;
import net.minecraft.client.renderer.culling.Frustum;
import net.minecraft.client.renderer.entity.EntityRenderDispatcher;
import net.minecraft.core.BlockPos;
import net.minecraft.world.entity.Entity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Large geometry can be visible while the section at its feet is outside the view. */
@Mixin(LevelRenderer.class)
public abstract class LargeStructureRenderMixin
{
    @Unique private Entity seele$renderCandidate;

    @Inject(method="setupRender",at=@At("HEAD"))
    private void seele$reviewTerrainVisibility(CallbackInfo ci)
    {
        // Oculus reapplies its pipeline's smartCull policy at renderLevel HEAD,
        // after client ticks. Apply the diagnostic at the actual terrain pass.
        if("r43-facility-photos".equals(System.getProperty("projectseele.regionalBuild",""))
                &&Boolean.getBoolean("projectseele.reviewNoOcclusion"))Minecraft.getInstance().smartCull=false;
    }

    @Redirect(method="renderLevel",at=@At(value="INVOKE",target="Lnet/minecraft/client/renderer/entity/EntityRenderDispatcher;shouldRender(Lnet/minecraft/world/entity/Entity;Lnet/minecraft/client/renderer/culling/Frustum;DDD)Z"))
    private boolean seele$rememberFrustumCandidate(EntityRenderDispatcher dispatcher,Entity entity,Frustum frustum,double x,double y,double z)
    {
        boolean visible=dispatcher.shouldRender(entity,frustum,x,y,z);
        this.seele$renderCandidate=visible?entity:null;
        return visible;
    }

    @Redirect(method="renderLevel",at=@At(value="INVOKE",target="Lnet/minecraft/client/renderer/LevelRenderer;isChunkCompiled(Lnet/minecraft/core/BlockPos;)Z"))
    private boolean seele$useLoadedGeometryForTallEntities(LevelRenderer renderer,BlockPos position)
    {
        Entity entity=this.seele$renderCandidate;
        if(entity instanceof EvaUnit01Entity eva&&eva.hasActiveCarrierMotion()&&entity.blockPosition().equals(position))return true;
        if((entity instanceof EvaUnit01Entity||entity instanceof IndustrialMemberEntity||entity instanceof com.projectseele.entity.Angel)
                &&entity.blockPosition().equals(position))
        {
            var level=Minecraft.getInstance().level;
            // Frustum and distance checks already passed. This only removes the
            // unrelated requirement that the origin's terrain mesh was compiled.
            return level!=null&&level.getChunkSource().hasChunk(position.getX()>>4,position.getZ()>>4);
        }
        return renderer.isChunkCompiled(position);
    }
}
