package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.supermartijn642.movingelevators.blocks.ControllerBlockEntity;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.*;
import net.minecraftforge.fml.common.Mod;
import java.util.*;

/** Keeps identified passengers inside the native travelling cabin after packet stalls. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class NervLiftPassengerSync
{
    public static final String GATEWAY="regional_gateway";
    public static List<S20PhysicalElevatorDirector.LiftSpec> managedLifts(ServerLevel level)
    {
        var list=new ArrayList<>(S20PhysicalElevatorDirector.s20Lifts(level));
        if(RegionalGatewayDirector.active(level))list.add(new S20PhysicalElevatorDirector.LiftSpec(GATEWAY,List.of(
                new S20PhysicalElevatorDirector.Landing("地下入构站",new net.minecraft.core.BlockPos(-360,-466,750),net.minecraft.core.Direction.NORTH),
                new S20PhysicalElevatorDirector.Landing("NERV 地面入口",new net.minecraft.core.BlockPos(-360,81,750),net.minecraft.core.Direction.NORTH))));
        return list;
    }
    public static boolean carPresent(ServerLevel level,S20PhysicalElevatorDirector.LiftSpec spec,S20PhysicalElevatorDirector.Landing stop)
    {return spec.id().equals(GATEWAY)?RegionalGatewayDirector.carAt(level,stop.walkY()):S20PhysicalElevatorDirector.hasAuthoredCabinAt(level,stop.cabinCentre());}
    private static final Map<ServerLevel,Map<String,Riders>> LEVELS=new WeakHashMap<>();
    private static final class Riders
    {
        final Set<UUID> passengers=new HashSet<>();
        double previousFloor=Double.NaN;
        boolean moving;
        int arrivalGuard;
        AABB lastBounds;
        Vec3 cageAnchor;
        List<AABB> cageBoxes=List.of();
        int observedTick=Integer.MIN_VALUE;
    }
    private static void invalidate(Riders riders)
    {
        riders.passengers.clear();riders.previousFloor=Double.NaN;riders.moving=false;
        riders.arrivalGuard=0;riders.lastBounds=null;riders.cageAnchor=null;
        riders.cageBoxes=List.of();riders.observedTick=Integer.MIN_VALUE;
    }

    @SubscribeEvent(priority=EventPriority.HIGHEST)
    public static void beforePassengerPhysics(TickEvent.PlayerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.START||!(event.player instanceof ServerPlayer p)
                ||p.isSpectator()||p.isPassenger())return;
        var groups=LEVELS.get(p.serverLevel());if(groups==null)return;
        for(var entry:groups.entrySet())
        {
            var riders=entry.getValue();var car=riders.lastBounds;
            if((long)p.getServer().getTickCount()-riders.observedTick>1)continue;
            if(car==null||!riders.passengers.contains(p.getUUID())||!riders.moving&&riders.arrivalGuard<=0)continue;
            if(Math.abs(p.getX()-car.getCenter().x)>12||Math.abs(p.getZ()-car.getCenter().z)>12)continue;
            double margin=1+p.getBbWidth()*.5+.065;
            double x=Mth.clamp(p.getX(),car.minX+margin,car.maxX-margin),z=Mth.clamp(p.getZ(),car.minZ+margin,car.maxZ-margin);
            double floor=car.minY+1,top=car.maxY-1-p.getBbHeight();
            if(riders.cageAnchor!=null)for(var local:riders.cageBoxes)
            {
                var roof=local.move(riders.cageAnchor);
                if(roof.minY>floor+.9&&roof.minX<x+.3&&roof.maxX>x-.3&&roof.minZ<z+.3&&roof.maxZ>z-.3)top=Math.min(top,roof.minY-p.getBbHeight()-.02);
            }
            double y=Mth.clamp(p.getY(),floor,Math.max(floor,top));
            if(Math.abs(x-p.getX())>.001||Math.abs(y-p.getY())>.001||Math.abs(z-p.getZ())>.001)
                reconcile(p,x,y,z,floor,entry.getKey());
        }
    }

    @SubscribeEvent(priority=EventPriority.HIGH)
    public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END||!net.minecraftforge.fml.ModList.get().isLoaded("movingelevators"))return;
        ServerLevel level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);
        if(level==null||!FacilityWorldPolicy.isS20Rebuild(event.getServer()))return;
        Map<String,Riders> groups=LEVELS.computeIfAbsent(level,l->new HashMap<>());
        var specs=managedLifts(level);var activeIds=new HashSet<String>();specs.forEach(spec->activeIds.add(spec.id()));
        groups.keySet().removeIf(id->!activeIds.contains(id));
        for(var spec:specs)
        {
            var base=S20MovingElevatorsAdapter.controllerPosition(spec,spec.lower());
            if(!level.hasChunkAt(base)||!(level.getBlockEntity(base) instanceof ControllerBlockEntity controller))
            {var stale=groups.get(spec.id());if(stale!=null)invalidate(stale);continue;}
            var group=controller.getGroup();if(group==null)
            {var stale=groups.get(spec.id());if(stale!=null)invalidate(stale);continue;}
            Riders riders=groups.computeIfAbsent(spec.id(),s->new Riders());
            double floor;AABB bounds;
            if(group.isMoving())
            {
                var cage=group.getCage();if(cage==null){invalidate(riders);continue;}
                bounds=cage.bounds.move(group.getCageAnchorPos(group.getCurrentY()));
                floor=bounds.minY+1.0D;
            }
            else
            {
                var landing=spec.stops().stream().filter(s->level.hasChunkAt(s.cabinCentre())
                        &&carPresent(level,spec,s)).findFirst();
                if(landing.isEmpty()){invalidate(riders);continue;}
                floor=landing.get().walkY();
                double x=landing.get().cabinCentre().getX()+.5D,z=landing.get().cabinCentre().getZ()+.5D;
                bounds=new AABB(x-group.getCageSizeX()*.5D,floor-1,z-group.getCageSizeZ()*.5D,
                        x+group.getCageSizeX()*.5D,floor-1+group.getCageSizeY(),z+group.getCageSizeZ()*.5D);
            }
            final double currentFloor=floor;
            final AABB car=bounds;
            List<ServerPlayer> players=level.players().stream().filter(p->p.isAlive()&&!p.isSpectator()&&!p.isPassenger()).toList();
            Set<UUID> available=new HashSet<>();players.forEach(p->available.add(p.getUUID()));riders.passengers.retainAll(available);
            // Sample every tick, including the very first movement tick. A
            // caller can enter and press a floor before a five-tick scan runs.
            for(ServerPlayer player:players)
            {
                double oldFloor=Double.isFinite(riders.previousFloor)?riders.previousFloor:floor;
                boolean inside=player.getX()>=car.minX-.01D&&player.getX()<=car.maxX+.01D
                        &&player.getZ()>=car.minZ-.01D&&player.getZ()<=car.maxZ+.01D;
                boolean onFloor=player.getY()>=Math.min(floor,oldFloor)-.3D
                        &&player.getY()<=Math.max(floor,oldFloor)+1.6D;
                if(inside&&onFloor)riders.passengers.add(player.getUUID());
                if(!riders.passengers.contains(player.getUUID()))continue;
                // A deliberate teleport elsewhere releases the association.
                if(Math.abs(player.getX()-car.getCenter().x)>12||Math.abs(player.getZ()-car.getCenter().z)>12)
                {riders.passengers.remove(player.getUUID());continue;}
                if(group.isMoving())
                {
                    double margin=1.0D+player.getBbWidth()*.5D+.06D;
                    double x=Mth.clamp(player.getX(),car.minX+margin,car.maxX-margin);
                    double z=Mth.clamp(player.getZ(),car.minZ+margin,car.maxZ-margin);
                    double y=player.getY();double top=car.maxY-1.0D-player.getBbHeight();
                    var anchor=group.getCageAnchorPos(group.getCurrentY());
                    for(var local:group.getCage().collisionBoxes)
                    {
                        var roof=local.move(anchor);
                        if(roof.minY>currentFloor+.9&&roof.minX<player.getBoundingBox().maxX&&roof.maxX>player.getBoundingBox().minX
                                &&roof.minZ<player.getBoundingBox().maxZ&&roof.maxZ>player.getBoundingBox().minZ)
                            top=Math.min(top,roof.minY-player.getBbHeight()-.02);
                    }
                    if(y<currentFloor-.10D||y>top+.10D)y=Mth.clamp(y,currentFloor,Math.max(currentFloor,top));
                    if(Math.abs(x-player.getX())>.01D||Math.abs(z-player.getZ())>.01D||Math.abs(y-player.getY())>.01D)
                        reconcile(player,x,y,z,currentFloor,spec.id());
                    player.resetFallDistance();
                }
                else if(riders.moving)
                {
                    double margin=1.0D+player.getBbWidth()*.5D+.06D;
                    double x=Mth.clamp(player.getX(),car.minX+margin,car.maxX-margin);
                    double z=Mth.clamp(player.getZ(),car.minZ+margin,car.maxZ-margin);
                    if(inside&&(Math.abs(player.getY()-floor)>.15D||Math.abs(x-player.getX())>.01D||Math.abs(z-player.getZ())>.01D))reconcile(player,x,floor,z,floor,spec.id());
                }
                else if(!inside)riders.passengers.remove(player.getUUID());
            }
            riders.lastBounds=bounds;
            if(group.getCage()!=null){riders.cageBoxes=group.getCage().collisionBoxes;riders.cageAnchor=group.getCageAnchorPos(group.getCurrentY());}
            riders.arrivalGuard=group.isMoving()?2:Math.max(0,riders.arrivalGuard-1);
            riders.previousFloor=floor;riders.moving=group.isMoving();
            riders.observedTick=event.getServer().getTickCount();
        }
    }
    @SubscribeEvent public static void stopping(net.minecraftforge.event.server.ServerStoppingEvent event)
    {LEVELS.keySet().removeIf(level->level.getServer()==event.getServer());}

    private static void reconcile(ServerPlayer player,double x,double y,double z,double floor,String lift)
    {
        // Normal support is predicted by the same native collision solver on
        // both sides. A teleport packet for a one-tick discrepancy repeatedly
        // reset the client's interpolation and made the elevator judder.
        boolean escaped=player.position().distanceToSqr(new Vec3(x,y,z))>4;
        double oldY=player.getY();Vec3 velocity=player.getDeltaMovement();
        if(escaped)player.teleportTo(player.serverLevel(),x,y,z,player.getYRot(),player.getXRot());
        else {player.setPos(x,y,z);player.connection.resetPosition();}
        boolean grounded=y<=floor+.015&&velocity.y<=.05;
        double dy=grounded||y<oldY-.001&&velocity.y>0?0:velocity.y;
        player.setDeltaMovement(velocity.x,dy,velocity.z);player.resetFallDistance();player.setOnGround(grounded);
        ProjectSeele.LOGGER.debug("Lift passenger kept inside native cabin lift={} position={}",lift,player.position());
    }
    private NervLiftPassengerSync(){}
}
