package com.projectseele.mixin;

import com.projectseele.world.CityExactShapeUnionR45;
import java.util.List;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.AABB;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** Changes only the opt-in marked city's union supplier body; stock provider lifecycle is untouched. */
@Pseudo
@Mixin(targets="com.simibubi.create.content.contraptions.Contraption",remap=false)
public abstract class CityExactUnionCreateMixinR45
{
    @Unique private boolean seele$fullCityFrame;

    @Inject(method="readNBT",at=@At("RETURN"),remap=false,require=1)
    private void seele$readFrame(Level level,CompoundTag tag,boolean spawnData,CallbackInfo callback)
    { seele$fullCityFrame=tag.getBoolean(CityExactShapeUnionR45.MARKER); }

    @Inject(method="writeNBT",at=@At("RETURN"),remap=false,require=1)
    private void seele$saveFrame(boolean spawnData,CallbackInfoReturnable<CompoundTag> callback)
    { if (seele$fullCityFrame)callback.getReturnValue().putBoolean(CityExactShapeUnionR45.MARKER,true); }

    @Inject(method="lambda$gatherBBsOffThread$24",at=@At("HEAD"),cancellable=true,remap=false,require=1)
    private void seele$exactUnion(CallbackInfoReturnable<List<AABB>> callback) throws Exception
    {
        if (!seele$fullCityFrame || !CityExactShapeUnionR45.enabled()) return;
        List<AABB> result=CityExactShapeUnionR45.calculate(this);
        if (result!=null)callback.setReturnValue(result);
    }
}
