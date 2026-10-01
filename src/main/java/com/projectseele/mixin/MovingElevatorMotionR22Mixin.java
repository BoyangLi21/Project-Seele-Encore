package com.projectseele.mixin;

import com.supermartijn642.movingelevators.elevator.ElevatorGroup;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.Vec3;
import org.spongepowered.asm.mixin.*;
import org.spongepowered.asm.mixin.injection.*;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Native movement packets correct the prediction gradually, in tick units. */
@Mixin(value=ElevatorGroup.class,remap=false)
public abstract class MovingElevatorMotionR22Mixin
{
    @Shadow public Level level;
    @Shadow private double currentY;
    @Shadow private double speed;
    @Shadow private double lastY;
    @Shadow private double syncCurrentY;
    @Shadow private int targetY;
    @Shadow private boolean isMoving;
    @ModifyConstant(method="update",constant=@Constant(intValue=10),remap=false)
    private int projectSeele$moreFrequentMotionSync(int original){return 2;}
    @Inject(method="stopElevator",at=@At("HEAD"),remap=false)
    private void projectSeele$doNotCarryFinalStepTwice(CallbackInfo ci){lastY=currentY;}
    @Inject(method="stopElevator",at=@At("TAIL"),remap=false)
    private void projectSeele$acknowledgeClientCagePlacement(CallbackInfo ci)
    {
        if(!level.isClientSide || !level.dimension().equals(com.projectseele.world.FacilitySchemaV2.DIMENSION))return;
        var group=(ElevatorGroup)(Object)this;
        com.projectseele.network.SeeleNetwork.CHANNEL.sendToServer(new com.projectseele.network.ServerboundLiftArrivalR44(
                new net.minecraft.core.BlockPos(group.x,targetY,group.z),group.facing));
    }
    @Inject(method="updateCurrentY",at=@At("HEAD"),cancellable=true,remap=false)
    private void projectSeele$boundedCorrection(double received,double receivedSpeed,CallbackInfo ci)
    {
        if(!level.isClientSide||!isMoving)return;
        ci.cancel();
        double direction=Math.signum(targetY-currentY),error=(received-currentY)*direction;
        if(error<=0)return;
        if(error>3)
        {
            // A stalled/loading client must catch up as a rigid car+rider
            // pair. Capping a 40 m cold-start error would leave it behind for
            // the entire trip while the server repeatedly rescued the rider.
            var g=(ElevatorGroup)(Object)this;var cage=g.getCage();double delta=received-currentY;
            if(cage!=null)
            {
                var old=cage.bounds.move(g.getCageAnchorPos(currentY));
                var next=old.move(0,delta,0);
                for(var p:level.players())
                {
                    if(p.isSpectator()||p.isPassenger())continue;
                    boolean inside=old.minX+1<p.getX()&&p.getX()<old.maxX-1&&old.minZ+1<p.getZ()&&p.getZ()<old.maxZ-1;
                    if(!inside||p.getY()<Math.min(old.minY,next.minY)||p.getY()>Math.max(old.maxY,next.maxY))continue;
                    double y=old.inflate(.3).contains(p.position())?p.getY()+delta:p.getY();
                    // A player correction can arrive before the matching cage
                    // packet during chunk loading. Reconcile that same cabin
                    // envelope, then reset both render samples together.
                    y=net.minecraft.util.Mth.clamp(y,next.minY+1,next.maxY-1-p.getBbHeight());
                    p.setPos(p.getX(),y,p.getZ());p.yo=y;p.yOld=y;
                }
            }
            currentY+=delta;lastY+=delta;speed=receivedSpeed;syncCurrentY=Integer.MAX_VALUE;return;
        }
        double nominal=Math.max(speed,receivedSpeed);
        double step=nominal+net.minecraft.util.Mth.clamp(error-nominal,-.06,.06);
        syncCurrentY=currentY+direction*Math.min(Math.abs(targetY-currentY),Math.max(.001,step));
        speed=Math.max(speed,receivedSpeed);
    }
    @ModifyArg(method="moveElevator",at=@At(value="INVOKE",target="Lcom/supermartijn642/movingelevators/elevator/ElevatorCollisionHandler;handleEntityCollisions(Lnet/minecraft/world/level/Level;Lnet/minecraft/world/phys/AABB;Ljava/util/List;Lnet/minecraft/world/phys/Vec3;Lnet/minecraft/world/phys/Vec3;)V"),index=4,remap=false)
    private Vec3 projectSeele$verticalMotion(Vec3 movement)
    {
        // The upstream 1.4.12 jar puts the world X coordinate in the delta.
        return new Vec3(0,movement.y,0);
    }
}
