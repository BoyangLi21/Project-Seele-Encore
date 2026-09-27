package com.projectseele.client.visual;

import com.projectseele.ProjectSeele;
import com.projectseele.visual.AirLiftR30Review;
import com.projectseele.world.FacilitySchemaV2;
import net.minecraft.client.Minecraft;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Isolated real observer receives the same positional landing sound as a player. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class AirLiftR40Client
{
    private static final boolean ENABLED="r40-airlift".equals(System.getProperty("projectseele.regionalBuild",""));
    private static int ticks;
    private static String photoPhase="";private static int stablePhase;
    private static final java.util.Set<String> photos=new java.util.HashSet<>();
    @SubscribeEvent public static void tick(TickEvent.ClientTickEvent event)
    {
        if(!ENABLED||event.phase!=TickEvent.Phase.END)return;
        var mc=Minecraft.getInstance();
        if(AirLiftR30Review.finished()){mc.stop();return;}
        var server=mc.getSingleplayerServer();
        if(server==null||mc.player==null||++ticks%10!=0||AirLiftR30Review.observer==null)return;
        if(!server.getWorldPath(LevelResource.ROOT).normalize().getFileName().toString().equals("SEELE_R32_AIR_REVIEW"))throw new IllegalStateException("Airlift review boundary");
        mc.options.pauseOnLostFocus=false;
        mc.options.renderDistance().set(8);
        var at=AirLiftR30Review.observer.add(75,35,-65);
        server.execute(()->{
            var player=server.getPlayerList().getPlayers().get(0);
            player.setGameMode(GameType.SPECTATOR);
            player.teleportTo(server.getLevel(FacilitySchemaV2.DIMENSION),at.x,at.y,at.z,49,8);
        });
        String key=AirLiftR30Review.reviewStage+"_"+AirLiftR30Review.reviewPhase;
        if(!key.equals(photoPhase)){photoPhase=key;stablePhase=0;}
        if(++stablePhase==5&&photos.add(key)&&java.util.Set.of("CRUISE","RELEASE","GROUND_APPROACH","ROLL_IN").contains(AirLiftR30Review.reviewPhase))
        {
            var folder=java.nio.file.Path.of("../artifacts/world_combat_r40/airlift/native_photos_"+Integer.getInteger("projectseele.airReviewUnSerial",0));
            try
            {
                java.nio.file.Files.createDirectories(folder);
                try(var capture=net.minecraft.client.Screenshot.takeScreenshot(mc.getMainRenderTarget()))
                {capture.writeToFile(folder.resolve(key+".png"));}
            }
            catch(java.io.IOException error){throw new IllegalStateException("Airlift photo could not be written",error);}
        }
    }
    private AirLiftR40Client(){}
}
