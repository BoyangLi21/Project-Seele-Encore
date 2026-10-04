package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.item.NervAccessCardR44;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

/** Exact wall-image/portal state only: no lift model, book rendering or actor relocation. */
public final class DeadSeaChamberR45
{
    private DeadSeaChamberR45() {}
    public static boolean handles(NervAccessReaderEntityR44 reader)
    {return DeadSeaChamberSavedDataR45.KEY.equals(reader.chamberId());}
    private static DeadSeaChamberSavedDataR45 bound(ServerLevel level,NervAccessReaderEntityR44 reader)
    {
        var data=DeadSeaChamberSavedDataR45.get(level);data.validate();
        if(!data.configured||!data.world.equals(Tokyo3BuildingWorldIdentityR44.get(level)))
            throw new IllegalStateException("Complete original chamber configuration is not installed in this world");
        boolean valid=data.readers.stream().anyMatch(r->r.pos().equals(reader.getBlockPos())&&r.role().equals(reader.chamberRole())
                &&reader.getBlockState().hasProperty(NervAccessReaderR44.FACING)
                &&reader.getBlockState().getValue(NervAccessReaderR44.FACING)==Direction.byName(r.facing()));
        if(!valid||!reader.exactChamberLayout(data.gate))throw new IllegalStateException("Highest-room reader binding/clearance changed");
        return data;
    }
    public static long observe(ServerLevel level,NervAccessReaderEntityR44 reader)
    {
        try
        {
            var data=bound(level,reader);long now=level.getGameTime();
            if(data.lastTick!=now)
            {
                data.lastTick=now;
                if(data.mode.equals("FAULT"))return 0;
                if(!data.images.stream().allMatch(i->level.hasChunkAt(i.pos())))return 0;
                boolean passageOpen=data.images.stream().filter(i->i.pos().getZ()==340).anyMatch(i->i.matches(level,true));
                boolean held=now>=data.openUntil&&passageOpen&&occupied(level,data);
                if(data.safetyHeld!=held){data.safetyHeld=held;data.setDirty();}
                if(data.mode.equals("OPENING")||data.mode.equals("CLOSING"))transition(level,data,now<data.openUntil||held);
                else if(data.mode.equals("OPEN")&&now>=data.openUntil&&!held)transition(level,data,false);
                else if(data.mode.equals("CLOSED")&&!all(level,data,false))throw new IllegalStateException("Closed wall/artwork ownership changed; no automatic overwrite");
            }
            return data.openUntil;
        }
        catch(Exception failure)
        {hold(level,failure);return 0;}
    }
    public static boolean grant(ServerLevel level,NervAccessReaderEntityR44 reader,Player player,InteractionHand hand)
    {
        try
        {
            var data=bound(level,reader);
            if(data.mode.equals("FAULT")||player==null||!player.isAlive()||player.distanceToSqr(Vec3.atCenterOf(reader.getBlockPos()))>=16
                    ||!(player.getItemInHand(hand).getItem() instanceof NervAccessCardR44 card)||card.clearance()<3)return false;
            if(!data.images.stream().allMatch(i->level.hasChunkAt(i.pos())))return false;
            data.openUntil=level.getGameTime()+200;data.safetyHeld=false;
            transition(level,data,true);return true;
        }
        catch(Exception failure){hold(level,failure);return false;}
    }
    private static AABB aperture(DeadSeaChamberSavedDataR45 data)
    {return new AABB(data.gate.getX(),data.gate.getY(),data.gate.getZ(),data.gate.getX()+data.width,data.gate.getY()+data.height,data.gate.getZ()+1);}
    private static boolean occupied(ServerLevel level,DeadSeaChamberSavedDataR45 data)
    {return !level.getEntities((Entity)null,aperture(data).inflate(.08),actor->actor.isAlive()&&!actor.isSpectator()).isEmpty();}
    private static boolean all(ServerLevel level,DeadSeaChamberSavedDataR45 data,boolean opened)
    {return data.images.stream().allMatch(image->image.matches(level,opened));}
    private static void transition(ServerLevel level,DeadSeaChamberSavedDataR45 data,boolean opened)
    {
        if(!opened&&occupied(level,data)){data.safetyHeld=true;data.setDirty();return;}
        // Both complete images are our durable finite mask. Unknown user edits
        // or full BE metadata fail before the first write, never get cleared.
        for(var image:data.images)if(!image.matches(level,false)&&!image.matches(level,true))
            throw new IllegalStateException("Foreign full state/NBT at chamber image "+image.pos());
        if(all(level,data,opened))
        {data.mode=opened?"OPEN":"CLOSED";data.fault="";data.durable(level);return;}
        data.mode=opened?"OPENING":"CLOSING";data.durable(level);
        for(var image:data.images)image.write(level,opened);
        if(!all(level,data,opened))throw new IllegalStateException("Complete original image readback failed");
        data.mode=opened?"OPEN":"CLOSED";data.fault="";data.durable(level);
    }
    private static void hold(ServerLevel level,Exception failure)
    {
        ProjectSeele.LOGGER.error("Highest-room chamber held; retain original wall/artwork images and all identities",failure);
        try{var data=DeadSeaChamberSavedDataR45.get(level);if(data.configured){data.mode="FAULT";data.fault=failure.toString();data.durable(level);}}
        catch(Exception persistence){failure.addSuppressed(persistence);}
    }
}
