package com.projectseele.client.visual;

import com.projectseele.visual.LiftPassengerR20Review;
import net.minecraft.client.Minecraft;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

@Mod.EventBusSubscriber(modid="projectseele",value=Dist.CLIENT)
public final class LiftPassengerR20Client
{
    private static int oldDistance=-1,exitTicks,warmTicks;
    @SubscribeEvent public static void tick(TickEvent.ClientTickEvent e)
    {
        if(!LiftPassengerR20Review.ENABLED||e.phase!=TickEvent.Phase.END)return;var mc=Minecraft.getInstance();
        mc.options.pauseOnLostFocus=false;
        if(mc.screen instanceof net.minecraft.client.gui.screens.PauseScreen)mc.setScreen(null);
        if(!LiftPassengerR20Review.finished&&mc.player!=null&&mc.player.isDeadOrDying()){mc.player.respawn();mc.setScreen(null);return;}
        if(mc.player==null||mc.level==null||mc.screen!=null&&!LiftPassengerR20Review.finished)return;
        if(oldDistance<0){oldDistance=mc.options.renderDistance().get();mc.options.renderDistance().set(8);mc.options.broadcastOptions();mc.options.pauseOnLostFocus=false;}
        if(LiftPassengerR20Review.R22&&warmTicks++<240)return;
        LiftPassengerR20Review.clientReady=true;
        boolean moving=LiftPassengerR20Review.moving;int t=LiftPassengerR20Review.tripAge;
        mc.options.keyUp.setDown(moving&&t%160<45);mc.options.keyRight.setDown(moving&&t%160>=80&&t%160<125);mc.options.keyJump.setDown(moving&&t%140>=60&&t%140<64);
        var target=LiftPassengerR20Review.walkingTargetR43;
        if(LiftPassengerR20Review.R43&&target!=null&&!LiftPassengerR20Review.finished)
        {
            var delta=target.subtract(mc.player.position());
            mc.player.setYRot((float)Math.toDegrees(Math.atan2(-delta.x,delta.z)));mc.player.setXRot(0);
            mc.options.keyRight.setDown(false);mc.options.keyJump.setDown(false);mc.options.keyUp.setDown(delta.horizontalDistanceSqr()>.04);
        }
        if(LiftPassengerR20Review.finished)
        {
            mc.options.keyUp.setDown(false);mc.options.keyRight.setDown(false);mc.options.keyJump.setDown(false);
            if(++exitTicks==1){mc.options.renderDistance().set(oldDistance);mc.options.broadcastOptions();}
            if(exitTicks>30)mc.stop();
        }
    }
}
