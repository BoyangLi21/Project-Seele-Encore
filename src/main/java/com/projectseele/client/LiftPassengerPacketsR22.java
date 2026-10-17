package com.projectseele.client;
import com.projectseele.world.LiftPassengerPhaseR22;
import net.minecraft.client.Minecraft;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.Level;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.*;
import net.minecraftforge.fml.common.Mod;

/** Publish local walking input after the native platform's END-tick collision step. */
@Mod.EventBusSubscriber(modid="projectseele",value=Dist.CLIENT)
public final class LiftPassengerPacketsR22
{
    private static Level carriedLevel;private static long carriedAt=Long.MIN_VALUE,sentAt=Long.MIN_VALUE;
    private static boolean flushing,deferred;
    public static boolean defer(Player player)
    {
        if(flushing||player!=Minecraft.getInstance().player||player.level()!=carriedLevel)return false;
        boolean recent=player.level().getGameTime()-carriedAt<=2;
        if(recent)deferred=true;return recent;
    }
    private static void flush(Player player)
    {
        if(player!=Minecraft.getInstance().player||player.isPassenger())return;
        long now=player.level().getGameTime();if(sentAt==now&&!deferred)return;
        flushing=true;
        try{((LiftPositionSenderR22)player).projectSeele$sendCarriedPosition();sentAt=now;deferred=false;}
        finally{flushing=false;}
    }
    @SubscribeEvent(priority=EventPriority.LOWEST) public static void tick(TickEvent.ClientTickEvent e)
    {
        var mc=Minecraft.getInstance();
        if(e.phase==TickEvent.Phase.START)
        {
            LiftPassengerPhaseR22.afterClientCarry=(p,dy)->
            {
                if(p!=Minecraft.getInstance().player)return;
                // A horizontal transfer has dy=0 but still needs its walking
                // packet published after the cage carries the passenger.
                carriedLevel=p.level();carriedAt=p.level().getGameTime();flush(p);
            };
        }
        else if(deferred&&mc.player!=null)flush(mc.player);
        if(mc.level==null){carriedLevel=null;carriedAt=Long.MIN_VALUE;sentAt=Long.MIN_VALUE;deferred=false;}
    }
    private LiftPassengerPacketsR22(){}
}
