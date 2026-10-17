package com.projectseele.mixin;

import com.projectseele.world.NervPersonnelTransferR53;
import com.projectseele.world.NervPersonnelTransferR53.PathSpec;
import com.supermartijn642.movingelevators.elevator.*;
import java.util.Comparator;
import java.util.LinkedHashMap;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.*;
import net.minecraft.world.level.*;
import net.minecraft.world.phys.Vec3;
import org.spongepowered.asm.mixin.*;
import org.spongepowered.asm.mixin.injection.*;
import org.spongepowered.asm.mixin.injection.callback.*;

/** Horizontal travel carries the same captured native cage and its riders. */
@Mixin(value=ElevatorGroup.class,remap=false)
public abstract class MovingElevatorTransferR53Mixin implements NervPersonnelTransferR53.NativeState
{
    @Shadow @Final public Level level;
    @Shadow private double currentY;
    @Shadow private double lastY;
    @Shadow private double speed;
    @Shadow private int targetY;
    @Shadow private boolean isMoving;
    @Unique private PathSpec seele$path;
    @Unique private boolean seele$transferring;
    @Unique private boolean seele$descending;
    @Unique private long seele$started=-1;
    @Unique private int seele$duration=1;
    @Unique private double seele$fraction;
    @Unique private static final TicketType<ChunkPos> seele$ticket=TicketType.create("seele_personnel_transfer_r53",Comparator.comparingLong(ChunkPos::toLong),40);

    @Override public PathSpec seele$transferPath(){return seele$path;}
    @Inject(method="getTargetSpeed",at=@At("RETURN"),cancellable=true,remap=false)
    private void seele$deepShaftSpeed(CallbackInfoReturnable<Double> result)
    {
        var path=seele$path();
        if(path!=null&&!seele$transferring&&currentY<path.transferY())
            result.setReturnValue(result.getReturnValue()*4);
    }
    @Unique private ElevatorGroup seele$group(){return (ElevatorGroup)(Object)this;}
    @Unique private PathSpec seele$path()
    {
        if(seele$path==null&&!level.isClientSide)seele$path=NervPersonnelTransferR53.forGroup(seele$group());
        return seele$path;
    }
    @Unique private double seele$fractionAt(double partial)
    {
        if(!seele$transferring||seele$started<0)return seele$fraction;
        double t=Math.max(0,Math.min(1,(level.getGameTime()-seele$started+partial)/seele$duration));
        double eased=t*t*(3-2*t);return seele$descending?eased:1-eased;
    }
    @Unique private Vec3 seele$anchor(double y,double fraction)
    {
        var g=seele$group();var a=g.getCageAnchorBlockPos(0);var base=new Vec3(a.getX(),y+g.getCageHeightOffset(),a.getZ()).subtract(seele$path.offset(0));
        return base.add(seele$path.offset(fraction));
    }
    @Unique private void seele$carry(Vec3 from,Vec3 to)
    {
        var cage=seele$group().getCage();if(cage==null)return;
        var motion=to.subtract(from);
        if(Math.abs(motion.x)+Math.abs(motion.z)<1e-9)
        {
            ElevatorCollisionHandler.handleEntityCollisions(level,cage.bounds,cage.collisionBoxes,from,motion);
            return;
        }
        var car=cage.bounds.move(from);
        var carried=new LinkedHashMap<net.minecraft.world.entity.Entity,double[]>();
        for(var entity:level.getEntities((net.minecraft.world.entity.Entity)null,car.inflate(.25),
                e->!e.isSpectator()&&!e.isPassenger()&&!e.noPhysics))
        {
            if(entity.getX()<=car.minX+1||entity.getX()>=car.maxX-1
                    ||entity.getZ()<=car.minZ+1||entity.getZ()>=car.maxZ-1
                    ||entity.getY()<car.minY+.75||entity.getY()>=car.maxY-1)continue;
            carried.put(entity,new double[]{entity.xo,entity.zo});
            entity.setPos(entity.getX()+motion.x,entity.getY(),entity.getZ()+motion.z);
            // Native collision compares current position with xo/zo. Its
            // reference must move with the cage, or the cage wall pushes a
            // correctly carried passenger back outside. Restore render history
            // afterwards so both camera and cage interpolate the same step.
            entity.xo+=motion.x;entity.zo+=motion.z;
        }
        try
        {
            ElevatorCollisionHandler.handleEntityCollisions(level,cage.bounds,cage.collisionBoxes,
                    from.add(motion.x,0,motion.z),new Vec3(0,motion.y,0));
        }
        finally
        {
            for(var entry:carried.entrySet())
            {
                var entity=entry.getKey();entity.xo=entry.getValue()[0];entity.zo=entry.getValue()[1];
                if(entity instanceof ServerPlayer player)player.connection.resetPosition();
                if(level.isClientSide&&entity instanceof net.minecraft.world.entity.player.Player player)
                    com.projectseele.world.LiftPassengerPhaseR22.afterClientCarry.accept(player,motion.length());
            }
        }
    }
    @Unique private void seele$sync()
    {if(!level.isClientSide)ElevatorGroupCapability.get(level).updateGroup(seele$group());}
    @Unique private boolean seele$retainPath()
    {
        if(!(level instanceof ServerLevel server))return seele$started>=0;
        boolean ready=true;
        for(int x=(Math.min(seele$path.upperX(),seele$path.lowerX())-6)>>4;x<=(Math.max(seele$path.upperX(),seele$path.lowerX())+6)>>4;x++)
            for(int z=(Math.min(seele$path.upperZ(),seele$path.lowerZ())-6)>>4;z<=(Math.max(seele$path.upperZ(),seele$path.lowerZ())+6)>>4;z++)
            {
                var chunk=new ChunkPos(x,z);server.getChunkSource().addRegionTicket(seele$ticket,chunk,2,chunk);
                ready&=server.getChunkSource().getChunkNow(x,z)!=null&&server.areEntitiesLoaded(chunk.toLong());
            }
        return ready;
    }
    @Inject(method="getPos",at=@At("HEAD"),cancellable=true,remap=false)
    private void seele$physicalFloor(int y,CallbackInfoReturnable<BlockPos> result)
    {var path=seele$path();if(path!=null)result.setReturnValue(path.controller(y));}

    @Inject(method="getCageAnchorBlockPos",at=@At("RETURN"),cancellable=true,remap=false)
    private void seele$physicalCabin(int y,CallbackInfoReturnable<BlockPos> result)
    {
        var path=seele$path();if(path==null||y<path.transferY())return;
        result.setReturnValue(result.getReturnValue().offset(path.upperX()-path.lowerX(),0,path.upperZ()-path.lowerZ()));
    }
    @Inject(method="getCageAnchorPos",at=@At("RETURN"),cancellable=true,remap=false)
    private void seele$actualCabin(double y,CallbackInfoReturnable<Vec3> result)
    {
        var path=seele$path();if(path==null)return;
        double partial=level.isClientSide?com.projectseele.client.LiftTransferRenderClockR53.partial():0;
        double fraction=Math.abs(y-path.transferY())<1e-5?(seele$transferring?seele$fractionAt(level.isClientSide?partial-1:0):seele$fraction):y<path.transferY()?1:0;
        result.setReturnValue(result.getReturnValue().subtract(path.offset(0)).add(path.offset(fraction)));
    }
    @Inject(method="moveElevator",at=@At("HEAD"),cancellable=true,remap=false)
    private void seele$enterTransfer(double from,double to,CallbackInfo ci)
    {
        var path=seele$path();if(path==null||!isMoving||seele$transferring)return;
        boolean down=from>path.transferY()&&to<=path.transferY()&&targetY<path.transferY();
        boolean up=from<path.transferY()&&to>=path.transferY()&&targetY>path.transferY();
        if(!down&&!up)return;
        seele$descending=down;seele$fraction=down?0:1;seele$transferring=true;
        seele$duration=path.duration(seele$group().getTargetSpeed());
        seele$started=-1;currentY=path.transferY();lastY=currentY;speed=0;
        seele$carry(seele$anchor(from,seele$fraction),seele$anchor(currentY,seele$fraction));
        if(seele$retainPath())seele$started=level.getGameTime();
        seele$sync();ci.cancel();
    }
    @Inject(method="update",at=@At("HEAD"),cancellable=true,remap=false)
    private void seele$horizontalTravel(CallbackInfo ci)
    {
        if(seele$path()==null||!seele$transferring)return;
        ci.cancel();currentY=lastY=seele$path.transferY();speed=0;
        if(seele$started<0)
        {
            if(!level.isClientSide&&seele$retainPath()){seele$started=level.getGameTime();seele$sync();}
            return;
        }
        if(!level.isClientSide&&level.getGameTime()%20==0)seele$retainPath();
        double next=seele$fractionAt(0);seele$carry(seele$anchor(currentY,seele$fraction),seele$anchor(currentY,next));seele$fraction=next;
        if(level.getGameTime()-seele$started>=seele$duration)
        {seele$transferring=false;seele$fraction=seele$descending?1:0;seele$sync();}
    }
    @Inject(method="write",at=@At("RETURN"),remap=false)
    private void seele$writeTransfer(CallbackInfoReturnable<CompoundTag> result)
    {
        var path=seele$path();if(path==null)return;var tag=path.encode();tag.putBoolean("Active",seele$transferring);tag.putBoolean("Descending",seele$descending);tag.putLong("Started",seele$started);tag.putInt("Duration",seele$duration);tag.putDouble("Fraction",seele$fraction);result.getReturnValue().put(NervPersonnelTransferR53.TAG,tag);
    }
    @Inject(method="read",at=@At("TAIL"),remap=false)
    private void seele$readTransfer(CompoundTag input,CallbackInfo ci)
    {
        var tag=input.getCompound(NervPersonnelTransferR53.TAG);if(tag.isEmpty()){seele$path=null;seele$transferring=false;return;}
        seele$path=PathSpec.decode(tag);seele$transferring=tag.getBoolean("Active");seele$descending=tag.getBoolean("Descending");seele$started=tag.getLong("Started");seele$duration=Math.max(1,tag.getInt("Duration"));seele$fraction=tag.getDouble("Fraction");
    }
}
