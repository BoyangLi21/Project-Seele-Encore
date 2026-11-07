package com.projectseele.mixin;

import com.supermartijn642.movingelevators.elevator.ElevatorCollisionHandler;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.*;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.*;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import java.util.*;

/** Continuous support at native cage contacts; no per-tick player teleport. */
@Mixin(value=ElevatorCollisionHandler.class,remap=false)
public abstract class MovingElevatorPassengerR22Mixin
{
    @Unique private static final ThreadLocal<Set<Player>> projectSeele$standing=ThreadLocal.withInitial(HashSet::new);
    @Unique private static final ThreadLocal<Map<Player,double[]>> projectSeele$airborne=ThreadLocal.withInitial(HashMap::new);
    @Unique private static final ThreadLocal<AABB> projectSeele$localBounds=new ThreadLocal<>();
    @Inject(method="handleEntityCollisions",at=@At("HEAD"),remap=false)
    private static void projectSeele$rememberSupport(Level level,AABB bounds,List<AABB> boxes,Vec3 position,Vec3 motion,CallbackInfo ci)
    {
        var standing=projectSeele$standing.get();standing.clear();var airborne=projectSeele$airborne.get();airborne.clear();
        projectSeele$localBounds.set(bounds);
        AABB car=bounds.move(position);double floor=car.minY+1;
        for(var p:level.getEntitiesOfClass(Player.class,car.inflate(.4),p->!p.isSpectator()&&!p.isPassenger()&&!p.noPhysics))
        {
            // Walking/gravity may put feet a fraction below the old floor.
            // A real jump has positive velocity and stays independent.
            if(p.getDeltaMovement().y<=.05&&Math.abs(p.getY()-floor)<.25
                    &&p.getX()>car.minX+1&&p.getX()<car.maxX-1&&p.getZ()>car.minZ+1&&p.getZ()<car.maxZ-1)standing.add(p);
            else if(level.isClientSide&&p.getY()>=floor-.25&&p.getY()<car.maxY-1
                    &&p.getX()>car.minX+1&&p.getX()<car.maxX-1&&p.getZ()>car.minZ+1&&p.getZ()<car.maxZ-1)airborne.put(p,new double[]{p.getY()+motion.y,p.getDeltaMovement().y});
        }
    }
    @Inject(method="handleEntityCollisions",at=@At("TAIL"),remap=false)
    private static void projectSeele$carryAndCeiling(Level level,AABB bounds,List<AABB> boxes,Vec3 position,Vec3 motion,CallbackInfo ci)
    {
        // The upstream method reassigns its bounds argument to an expanded
        // WORLD-space query box. TAIL receives that reassigned local; moving
        // it again searched a distant box and skipped every real passenger.
        AABB original=projectSeele$localBounds.get();if(original==null)return;
        Vec3 at=position.add(motion);AABB car=original.move(at);double floor=car.minY+1;
        var standing=projectSeele$standing.get();
        var airborne=projectSeele$airborne.get();
        for(var p:level.getEntitiesOfClass(Player.class,car.inflate(1),p->!p.isSpectator()&&!p.isPassenger()&&!p.noPhysics))
        {
            if(!car.contains(p.position())&&!standing.contains(p)&&!airborne.containsKey(p))continue;
            double margin=1+p.getBbWidth()*.5+.065;
            p.setPos(net.minecraft.util.Mth.clamp(p.getX(),car.minX+margin,car.maxX-margin),p.getY(),
                    net.minecraft.util.Mth.clamp(p.getZ(),car.minZ+margin,car.maxZ-margin));
            if(standing.contains(p))
            {
                p.setPos(p.getX(),floor,p.getZ());p.setDeltaMovement(p.getDeltaMovement().multiply(1,0,1));p.setOnGround(true);p.resetFallDistance();
            }
            else if(airborne.containsKey(p))
            {
                var saved=airborne.get(p);boolean landed=saved[0]<=floor;
                p.setPos(p.getX(),Math.max(floor,saved[0]),p.getZ());p.setOnGround(landed);
                p.setDeltaMovement(p.getDeltaMovement().x,landed?0:saved[1],p.getDeltaMovement().z);
            }
            if(p.getY()<floor)
            {p.setPos(p.getX(),floor,p.getZ());p.setDeltaMovement(p.getDeltaMovement().multiply(1,0,1));p.setOnGround(true);p.resetFallDistance();}
            // Capture height includes decoration above the usable ceiling.
            // Use actual collision boxes to prevent a jump entering that roof.
            AABB body=p.getBoundingBox().deflate(.015);double ceiling=Double.POSITIVE_INFINITY;
            for(var local:boxes)
            {
                AABB b=local.move(at);
                if(b.minY>floor+.9&&b.minX<body.maxX&&b.maxX>body.minX&&b.minZ<body.maxZ&&b.maxZ>body.minZ)ceiling=Math.min(ceiling,b.minY);
            }
            if(Double.isFinite(ceiling)&&p.getY()>=floor-.25&&p.getY()<ceiling&&p.getY()+p.getBbHeight()>ceiling)
            {
                p.setPos(p.getX(),Math.max(floor,ceiling-p.getBbHeight()-.01),p.getZ());p.setDeltaMovement(p.getDeltaMovement().multiply(1,0,1));p.resetFallDistance();
            }
            // Vanilla validates the next input against lastGoodY. External
            // platform motion must advance that reference without emitting a
            // teleport. Otherwise normal elevator travel is "moved wrongly".
            if(p instanceof net.minecraft.server.level.ServerPlayer serverPlayer
                    &&car.inflate(.25).contains(p.position()))serverPlayer.connection.resetPosition();
            if(level.isClientSide)com.projectseele.world.LiftPassengerPhaseR22.afterClientCarry.accept(p,motion.y);
        }
        standing.clear();airborne.clear();projectSeele$localBounds.remove();
    }
}
