package com.projectseele.client;

import com.projectseele.network.ClientboundFacilityFrameR52;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.core.BlockPos;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.ClientPlayerNetworkEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** A visual map frame never survives the network connection that declared it. */
@Mod.EventBusSubscriber(modid="projectseele",value=Dist.CLIENT)
public final class FacilityFrameClientR52
{
    private static Object connection;
    private static ClientboundFacilityFrameR52 frame;
    public static void receive(ClientboundFacilityFrameR52 packet)
    {connection=Minecraft.getInstance().getConnection();frame=connection==null?null:packet;}
    public static boolean claimed(ClientLevel level)
    {return frame!=null&&frame.claimed()&&connection==Minecraft.getInstance().getConnection()&&level.dimension().location().equals(frame.dimension());}
    public static boolean headquartersBound(ClientLevel level)
    {return claimed(level)&&frame.headquartersBound();}
    public static String uprightGuideSourceR52(ClientLevel level)
    {return claimed(level)?frame.uprightGuideSourceSHA():"";}
    public static boolean continuousUprightR52(ClientLevel level)
    {return !uprightGuideSourceR52(level).isEmpty();}
    public static BlockPos headquarters(ClientLevel level,BlockPos original)
    {return headquartersBound(level)?original.offset(frame.headquartersTranslation()):original;}
    public static Vec3 headquarters(ClientLevel level,Vec3 original)
    {var p=headquartersBound(level)?frame.headquartersTranslation():BlockPos.ZERO;return original.add(p.getX(),p.getY(),p.getZ());}
    public static boolean insidePyramid(ClientLevel level,Vec3 camera)
    {
        var offset=headquarters(level,BlockPos.ZERO);var local=camera.subtract(offset.getX(),offset.getY(),offset.getZ());
        double y=Math.floor(local.y),radius=Math.floor(120*(1-(y+466)/172)+.5);
        return y>=-466&&y<=-294&&Math.abs(Math.floor(local.x)-30)<=radius&&Math.abs(Math.floor(local.z)-327)<=radius;
    }
    @SubscribeEvent public static void logout(ClientPlayerNetworkEvent.LoggingOut event){connection=null;frame=null;}
    private FacilityFrameClientR52(){}
}
