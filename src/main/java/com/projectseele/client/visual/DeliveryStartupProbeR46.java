package com.projectseele.client.visual;

import com.google.gson.JsonObject;
import com.projectseele.ProjectSeele;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.screens.TitleScreen;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.loading.FMLPaths;
import java.nio.file.*;

/** Explicit isolated startup check. Never selects or opens a world. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class DeliveryStartupProbeR46
{
    private static final String OUTPUT=System.getProperty("projectseele.r46DeliveryStartupProbe", "");
    private static int readyTicks;
    private static boolean finished;
    @SubscribeEvent public static void tick(TickEvent.ClientTickEvent event)
    {
        if(OUTPUT.isBlank()||finished||event.phase!=TickEvent.Phase.END)return;
        var mc=Minecraft.getInstance();
        if(!(mc.screen instanceof TitleScreen)||mc.getOverlay()!=null)return;
        if(++readyTicks<20)return;
        finished=true;
        var row=new JsonObject();row.addProperty("world_opened",mc.level!=null);
        try
        {
            Path output=Path.of(OUTPUT).toAbsolutePath().normalize();
            if(Files.exists(output))throw new IllegalStateException("Existing probe evidence retained");
            var iris=Class.forName("net.irisshaders.iris.Iris");Object config=iris.getMethod("getIrisConfig").invoke(null);
            var name=(java.util.Optional<?>)config.getClass().getMethod("getShaderPackName").invoke(config);
            String selected=name.isPresent()?name.get().toString():"";
            Path game=FMLPaths.GAMEDIR.get();
            row.addProperty("shader_selected",selected);
            row.addProperty("personal_archive_exists",Files.isRegularFile(game.resolve("shaderpacks").resolve(selected)));
            row.addProperty("install_receipt_exists",Files.isRegularFile(game.resolve("config/projectseele-private-visuals-r46.json")));
            row.addProperty("tv_cage",com.projectseele.config.PortableRuntimeOwnersR45.tvCage());
            row.addProperty("personnel_platforms",com.projectseele.config.PortableRuntimeOwnersR45.personnelPlatforms());
            row.addProperty("passed",selected.startsWith("SEELE_Local_Cavern_R46_")&&row.get("personal_archive_exists").getAsBoolean()
                    &&row.get("install_receipt_exists").getAsBoolean()&&row.get("tv_cage").getAsBoolean()&&row.get("personnel_platforms").getAsBoolean()&&mc.level==null);
            row.addProperty("not_validated","In-world shader appearance, GPU material rendering and user acceptance");
            Files.createDirectories(output.getParent());Files.writeString(output,row.toString(),StandardOpenOption.CREATE_NEW);
        }
        catch(Exception error){ProjectSeele.LOGGER.error("R46 isolated delivery startup probe failed",error);}
        mc.stop();
    }
    private DeliveryStartupProbeR46(){}
}
