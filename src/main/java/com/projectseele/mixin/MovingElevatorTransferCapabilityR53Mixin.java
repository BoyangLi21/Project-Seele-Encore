package com.projectseele.mixin;

import com.projectseele.world.NervPersonnelTransferR53;
import com.supermartijn642.movingelevators.blocks.ControllerBlockEntity;
import com.supermartijn642.movingelevators.elevator.*;
import net.minecraft.core.*;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.level.Level;
import org.spongepowered.asm.mixin.*;
import org.spongepowered.asm.mixin.injection.*;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** Both physical shaft ends refer to one existing native controller group. */
@Mixin(value=ElevatorGroupCapability.class,remap=false)
public abstract class MovingElevatorTransferCapabilityR53Mixin
{
    @Shadow @Final private Level level;
    @ModifyArg(method={"add","remove"},at=@At(value="INVOKE",target="Lcom/supermartijn642/movingelevators/elevator/ElevatorGroupCapability$ElevatorGroupPosition;<init>(Lnet/minecraft/core/BlockPos;Lnet/minecraft/core/Direction;)V"),index=0,remap=false)
    private BlockPos seele$canonicalGroup(BlockPos actual)
    {return NervPersonnelTransferR53.canonicalController(level,actual);}

    @Inject(method="getGroup",at=@At("HEAD"),cancellable=true,remap=false)
    private void seele$actualController(ControllerBlockEntity controller,CallbackInfoReturnable<ElevatorGroup> result)
    {
        var actual=controller.getBlockPos();var key=NervPersonnelTransferR53.canonicalController(level,actual);
        if(!key.equals(actual))result.setReturnValue(((ElevatorGroupCapability)(Object)this).get(key.getX(),key.getZ(),controller.getFacing()));
    }
    @Redirect(method="readGroup",at=@At(value="INVOKE",target="Lcom/supermartijn642/movingelevators/elevator/ElevatorGroup;read(Lnet/minecraft/nbt/CompoundTag;)V"),remap=false)
    private void seele$replaceClientGroup(ElevatorGroup fresh,CompoundTag data)
    {
        fresh.read(data);
        // Every sync builds a new client group; the one it replaces is still registered here.
        if(!level.isClientSide||!(fresh instanceof NervPersonnelTransferR53.NativeState state))return;
        var previous=((ElevatorGroupCapability)(Object)this).get(fresh.x,fresh.z,fresh.facing);
        if(previous!=null&&previous!=fresh)state.seele$continueFrom(previous);
    }
    @Inject(method="get(IILnet/minecraft/core/Direction;)Lcom/supermartijn642/movingelevators/elevator/ElevatorGroup;",at=@At("HEAD"),cancellable=true,remap=false)
    private void seele$linkedDisplay(int x,int z,Direction facing,CallbackInfoReturnable<ElevatorGroup> result)
    {
        var actual=new BlockPos(x,0,z);var key=NervPersonnelTransferR53.canonicalController(level,actual);
        if(!key.equals(actual))result.setReturnValue(((ElevatorGroupCapability)(Object)this).get(key.getX(),key.getZ(),facing));
    }
}
