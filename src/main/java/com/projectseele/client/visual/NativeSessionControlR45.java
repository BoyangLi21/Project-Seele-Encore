package com.projectseele.client.visual;

import com.projectseele.ProjectSeele;
import java.nio.file.Files;
import java.nio.file.Path;
import net.minecraft.client.Minecraft;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Explicit QA lifecycle only; does not move a camera/player or edit a world. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID, value=Dist.CLIENT)
public final class NativeSessionControlR45
{
    private static final String STOP=System.getProperty("projectseele.nativeSessionStopFileR45","");
    private static boolean closing;

    @SubscribeEvent
    public static void tick(TickEvent.ClientTickEvent event)
    {
        if(STOP.isBlank()||closing||event.phase!=TickEvent.Phase.END)return;
        var mc=Minecraft.getInstance();
        Path game=mc.gameDirectory.toPath().toAbsolutePath().normalize();
        if(!game.getFileName().toString().equals("gameDir")
                ||!java.util.Set.of("native_candidate_session_v1","native_candidate_session_v2")
                    .contains(game.getParent().getFileName().toString()))
            throw new IllegalStateException("Native session lifecycle requires the named isolated QA gameDir");
        Path stop=Path.of(STOP).toAbsolutePath().normalize();
        if(!Path.of(STOP).isAbsolute()||stop.startsWith(game.resolve("saves")))
            throw new IllegalStateException("QA stop signal must be an absolute external artifact path");
        // A software-only city test must not run an unrelated photo itinerary
        // just to prevent Minecraft pausing when the desktop loses focus.
        mc.options.pauseOnLostFocus=false;
        if(Files.isRegularFile(stop))
        {
            closing=true;
            ProjectSeele.LOGGER.info("Root requested normal isolated native session shutdown");
            mc.stop();
        }
    }

    private NativeSessionControlR45() {}
}
