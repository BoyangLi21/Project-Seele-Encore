package com.projectseele.client.visual;

import com.projectseele.visual.LiftPassengerR20Review;
import com.supermartijn642.movingelevators.blocks.ControllerBlockEntity;
import net.minecraft.client.Minecraft;
import net.minecraft.util.Mth;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.*;

/** Sample the rendered passenger and rendered car in the same frame. */
@Mod.EventBusSubscriber(modid="projectseele",value=Dist.CLIENT)
public final class LiftFrameR22Audit
{
    private static final List<String> ROWS=new ArrayList<>();
    private static boolean written;
    @SubscribeEvent public static void frame(TickEvent.RenderTickEvent e)
    {
        if(!LiftPassengerR20Review.R22||e.phase!=TickEvent.Phase.END||written)return;
        var mc=Minecraft.getInstance();
        if(LiftPassengerR20Review.finished)
        {
            try {var p=Path.of(System.getProperty("projectseele.liftFrameFile","../artifacts/access_r22/lift_frames.csv"));Files.createDirectories(p.getParent());Files.write(p,ROWS);written=true;}
            catch(Exception x){throw new IllegalStateException(x);}return;
        }
        var pos=LiftPassengerR20Review.controllerPosition;
        if(mc.player==null||mc.level==null||pos==null||!LiftPassengerR20Review.moving)return;
        if(!(mc.level.getBlockEntity(pos) instanceof ControllerBlockEntity c)||c.getGroup()==null||!c.getGroup().isMoving())return;
        var g=c.getGroup();if(g.getCage()==null)return;
        double floor=g.getCage().bounds.minY+g.getCageAnchorPos(Mth.lerp(e.renderTickTime,g.getLastY(),g.getCurrentY())).y+1;
        double y=Mth.lerp(e.renderTickTime,mc.player.yo,mc.player.getY());
        if(ROWS.isEmpty())ROWS.add("nanos,controller_x,controller_z,trip_tick,partial,player_y,cage_floor,relative_y,vertical_velocity");
        ROWS.add(String.format(Locale.ROOT,"%d,%d,%d,%d,%.5f,%.6f,%.6f,%.6f,%.6f",System.nanoTime(),pos.getX(),pos.getZ(),LiftPassengerR20Review.tripAge,e.renderTickTime,y,floor,y-floor,mc.player.getDeltaMovement().y));
    }
}
