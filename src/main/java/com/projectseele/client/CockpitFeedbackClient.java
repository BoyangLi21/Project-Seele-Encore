package com.projectseele.client;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.registry.ModSounds;
import com.projectseele.world.EvaPilotResolver;
import net.minecraft.client.Minecraft;
import net.minecraft.client.resources.sounds.AbstractTickableSoundInstance;
import net.minecraft.client.resources.sounds.SimpleSoundInstance;
import net.minecraft.sounds.SoundSource;
import net.minecraft.util.RandomSource;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.ViewportEvent;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Quiet cockpit drive, restraint servos and sparse real-state alerts; no replacement aim or camera pose. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class CockpitFeedbackClient
{
    private static Drive drive;
    private static int warningCooldown,lastStance=-1;
    private static java.util.UUID linkedPilotActor;
    private static double fovTime=Double.NaN,fovSpeed;
    private static EvaUnit01Entity actor(){var p=Minecraft.getInstance().player;return p==null?null:EvaPilotResolver.controlTarget(p);}
    private static final class Drive extends AbstractTickableSoundInstance
    {
        private final EvaUnit01Entity eva;
        Drive(EvaUnit01Entity eva){super(ModSounds.EVA_DRIVE_LOOP.get(),SoundSource.PLAYERS,RandomSource.create());this.eva=eva;looping=true;delay=0;relative=true;attenuation=Attenuation.NONE;volume=.01F;pitch=.82F;}
        @Override public boolean canStartSilent(){return true;}
        @Override public void tick()
        {
            if(actor()!=eva||!eva.isAlive()||!eva.isPoweredOn()){stop();return;}
            float speed=(float)Math.min(1,eva.getDeltaMovement().horizontalDistance()/1.6);
            float wanted=eva.isFirstBattleActive()?0:.03F*speed;
            volume+=(wanted-volume)*.12F;pitch+=(.82F+speed*.25F-pitch)*.10F;
        }
    }
    /** A new vehicle/link must not inherit another airframe's sound, alerts or FOV filter. */
    public static void resetConnectionR45()
    {
        if(drive!=null)Minecraft.getInstance().getSoundManager().stop(drive);
        drive=null;lastStance=-1;warningCooldown=0;linkedPilotActor=null;fovTime=Double.NaN;fovSpeed=0;
    }
    @SubscribeEvent public static void tick(TickEvent.ClientTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END)return;var eva=actor();var mc=Minecraft.getInstance();
        if(eva==null){resetConnectionR45();return;}
        if(!eva.getUUID().equals(linkedPilotActor))
        {
            resetConnectionR45();
            linkedPilotActor=eva.getUUID();
            mc.gui.setOverlayMessage(net.minecraft.network.chat.Component.translatable("hud.projectseele.pilot_link_ready"),false);
        }
        if(eva.isPoweredOn()&&(drive==null||drive.isStopped())){drive=new Drive(eva);mc.getSoundManager().play(drive);}
        if(eva.isFirstBattleActive())return;
        int stance=eva.isPilotProne()?2:eva.isPilotCrouching()?1:0;
        if(lastStance>=0&&stance!=lastStance)mc.getSoundManager().play(SimpleSoundInstance.forUI(ModSounds.EVA_SERVO.get(),1,.13F));lastStance=stance;
        if(warningCooldown>0)warningCooldown--;
        boolean warning=eva.getHealth()<eva.getMaxHealth()*.3F||(!eva.isUmbilicalConnected()&&eva.getPowerTicks()<1200);
        if(warning&&warningCooldown==0){mc.getSoundManager().play(SimpleSoundInstance.forUI(ModSounds.EVA_COCKPIT_WARNING.get(),1,.20F));warningCooldown=160;}
    }
    @SubscribeEvent public static void fov(ViewportEvent.ComputeFov event)
    {
        var eva=actor();if(eva==null||eva.isFirstBattleActive()||ClientForgeEvents.isRifleSightActive(eva)||eva.getCannonCharge()>0)return;
        double now=eva.level().getGameTime()+event.getPartialTick(),wanted=Math.min(3.2,eva.getDeltaMovement().horizontalDistance()*1.5);
        if(Double.isNaN(fovTime)||now<fovTime||now-fovTime>10)fovSpeed=wanted;
        else fovSpeed+=(wanted-fovSpeed)*(1-Math.pow(.5,(now-fovTime)/20/.12));
        fovTime=now;event.setFOV(event.getFOV()+fovSpeed);
    }
    private CockpitFeedbackClient() {}
}
