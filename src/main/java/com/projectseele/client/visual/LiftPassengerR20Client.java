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
    private static int blockedTicks;
    private static String blockedPhase="";
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
            if(!blockedPhase.equals(LiftPassengerR20Review.phaseR43)){blockedPhase=LiftPassengerR20Review.phaseR43;blockedTicks=0;}
            if(LiftPassengerR20Review.R44 && delta.horizontalDistanceSqr()>.16 && mc.player.horizontalCollision)
            {
                if(++blockedTicks==40)
                    LiftPassengerR20Review.blockedClientR44=LiftPassengerR20Review.collisionWitnessR44(mc.level,mc.player,target,"client");
            }
        }
        // A source-floor teleport is acknowledged only by the real client pose.
        // Repeated floors share X/Z; horizontal proximity can match the old floor.
        if(LiftPassengerR20Review.R44&&LiftPassengerR20Review.clickTargetR44!=null&&!LiftPassengerR20Review.clickedR44&&target!=null&&target.distanceToSqr(mc.player.position())<.09&&mc.player.onGround())
        {
            try
            {
                var pos=LiftPassengerR20Review.clickTargetR44;var state=mc.level.getBlockState(pos);var shape=state.getShape(mc.level,pos);
                if(shape.isEmpty())throw new IllegalStateException("Measured lift input has no actual outline: "+pos);
                var b=shape.bounds();var point=LiftPassengerR20Review.clickPointR44;
                if(point==null)point=new net.minecraft.world.phys.Vec3(pos.getX()+(b.minX+b.maxX)/2,pos.getY()+(b.minY+b.maxY)/2,pos.getZ()+(b.minZ+b.maxZ)/2);
                var eye=mc.player.getEyePosition();var direction=point.subtract(eye);
                if(direction.length()>mc.gameMode.getPickRange()+.05)throw new IllegalStateException("Lift input outside real client reach "+pos+"; actual_client="+mc.player.position()+"; actual_eye="+eye+"; planned_operator="+target+"; planned_hit="+point+"; distance="+direction.length()+"; pick_range="+mc.gameMode.getPickRange()+"; phase="+LiftPassengerR20Review.phaseR43);
                var hit=mc.level.clip(new net.minecraft.world.level.ClipContext(eye,point.add(direction.normalize().scale(.04)),net.minecraft.world.level.ClipContext.Block.OUTLINE,net.minecraft.world.level.ClipContext.Fluid.NONE,mc.player));
                if(hit.getType()!=net.minecraft.world.phys.HitResult.Type.BLOCK||!hit.getBlockPos().equals(pos))throw new IllegalStateException("Actual lift-input sightline hits "+hit.getBlockPos()+" before "+pos);
                mc.player.setYRot((float)Math.toDegrees(Math.atan2(-direction.x,direction.z)));mc.player.setXRot((float)-Math.toDegrees(Math.atan2(direction.y,direction.horizontalDistance())));
                mc.options.keyUp.setDown(false);var action=mc.gameMode.useItemOn(mc.player,net.minecraft.world.InteractionHand.MAIN_HAND,hit);
                var proof=new com.google.gson.JsonObject();proof.addProperty("point","r44_actual_client_use");proof.addProperty("position",pos.toShortString());proof.addProperty("hit",hit.getLocation().toString());proof.addProperty("face",hit.getDirection().getName());proof.addProperty("result",action.name());proof.addProperty("player",mc.player.position().toString());proof.addProperty("planned_target",target.toString());LiftPassengerR20Review.clickReceiptR44=proof;
                com.projectseele.ProjectSeele.LOGGER.info("R44 actual client input {}",proof);
                LiftPassengerR20Review.clickedR44=true;
            }
            catch(Exception failure){LiftPassengerR20Review.clickFailureR44=failure.toString();}
        }
        if(LiftPassengerR20Review.finished)
        {
            mc.options.keyUp.setDown(false);mc.options.keyRight.setDown(false);mc.options.keyJump.setDown(false);
            if(++exitTicks==1)
            {
                // Preserve the user's option without asking the integrated
                // server to load its larger radius for 30 unnecessary exit ticks.
                mc.options.renderDistance().set(oldDistance);mc.options.save();mc.stop();
            }
        }
    }
}
