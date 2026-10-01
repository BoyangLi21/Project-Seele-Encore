package com.projectseele.client;

import com.google.gson.JsonObject;
import com.projectseele.ProjectSeele;
import net.minecraft.client.Minecraft;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.ViewportEvent;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.ModList;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.event.lifecycle.FMLClientSetupEvent;
import java.lang.invoke.LambdaMetafactory;
import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;
import java.lang.reflect.Proxy;

/** Uses the pinned Embeddium API; horizontal distance and occlusion stay native. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class GeoFrontVerticalVisibilityR44
{
    private static final boolean ENABLED=Boolean.getBoolean("projectseele.r44VerticalCavern");
    private static final float UPWARD_LIMIT=640;
    private static volatile boolean active,installed;
    private static String installation="not requested";
    private static long calls,additionalSections,horizontalRejected;
    private static float highestAdditional;

    @Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT,bus=Mod.EventBusSubscriber.Bus.MOD)
    public static final class Registration
    {
        @SubscribeEvent public static void setup(FMLClientSetupEvent event)
        { if(ENABLED)event.enqueueWork(GeoFrontVerticalVisibilityR44::install); }
    }

    private static void install()
    {
        if(!ModList.get().isLoaded("embeddium")){installation="Embeddium absent";return;}
        try
        {
            Class<?> event=Class.forName("org.embeddedt.embeddium.api.render.chunk.RenderSectionDistanceFilterEvent");
            Class<?> filter=Class.forName("org.embeddedt.embeddium.api.render.chunk.RenderSectionDistanceFilter");
            Class<?> handler=Class.forName("org.embeddedt.embeddium.api.eventbus.EventHandlerRegistrar$Handler");
            Object bus=event.getField("BUS").get(null);
            // Reflection is confined to this one registration event. The hot
            // filter is a primitive SAM, avoiding boxed arguments per section.
            Object listener=Proxy.newProxyInstance(handler.getClassLoader(),new Class<?>[]{handler},(proxy,method,args)->
            {
                if(method.getName().equals("acceptEvent"))
                {
                    try
                    {
                    Object current=event.getMethod("getFilter").invoke(args[0]);
                    if(current!=filter.getField("DEFAULT").get(null))
                    {installation="Another distance filter owns visibility; candidate not installed";return null;}
                    var signature=MethodType.methodType(boolean.class,float.class,float.class,float.class,float.class);
                    var implementation=MethodHandles.lookup().findStatic(GeoFrontVerticalVisibilityR44.class,"allowSection",signature);
                    var factory=LambdaMetafactory.metafactory(MethodHandles.lookup(),"isWithinDistance",MethodType.methodType(filter),signature,implementation,signature);
                    Object candidate=factory.getTarget().invoke();event.getMethod("setFilter",filter).invoke(args[0],candidate);
                    installed=true;installation="Pinned Embeddium distance-filter event; default horizontal rule retained";
                    ProjectSeele.LOGGER.info("R44 GeoFront vertical visibility: {}",installation);return null;
                    }
                    catch(Throwable failure)
                    {installation=failure.toString();ProjectSeele.LOGGER.error("GeoFront visibility filter rejected; native filter retained",failure);return null;}
                }
                if(method.getName().equals("hashCode"))return System.identityHashCode(proxy);
                if(method.getName().equals("equals"))return proxy==args[0];
                if(method.getName().equals("toString"))return "Project SEELE GeoFront visibility registration";
                return null;
            });
            bus.getClass().getMethod("addListener",handler).invoke(bus,listener);
            installation="Distance-filter listener registered; awaiting native renderer";
        }
        catch(Throwable failure)
        {installation=failure.toString();ProjectSeele.LOGGER.error("GeoFront visibility API unavailable; native filter retained",failure);}
    }

    private static void context(double cameraY)
    {
        var level=Minecraft.getInstance().level;
        active=ENABLED&&level!=null&&level.dimension().location().toString().equals("projectseele:geofront")&&cameraY< -128;
    }
    @SubscribeEvent public static void frame(TickEvent.RenderTickEvent event)
    {if(ENABLED&&event.phase==TickEvent.Phase.START)context(Minecraft.getInstance().gameRenderer.getMainCamera().getPosition().y);}
    @SubscribeEvent public static void camera(ViewportEvent.ComputeCameraAngles event)
    {if(ENABLED)context(event.getCamera().getPosition().y);}

    public static boolean allowSection(float x,float y,float z,float distance)
    {
        calls++;
        if(x*x+z*z>=distance*distance){horizontalRejected++;return false;}
        if(Math.abs(y)<distance)return true;
        boolean extra=active&&y>0&&y<UPWARD_LIMIT;
        if(extra){additionalSections++;highestAdditional=Math.max(highestAdditional,y);}
        return extra;
    }
    public static JsonObject snapshot()
    {
        var value=new JsonObject();value.addProperty("enabled",ENABLED);value.addProperty("installed",installed);
        value.addProperty("active",active);value.addProperty("installation",installation);value.addProperty("calls",calls);
        value.addProperty("additional_upward_acceptances",additionalSections);value.addProperty("highest_additional_distance",highestAdditional);
        value.addProperty("horizontal_rejections",horizontalRejected);value.addProperty("upward_limit",UPWARD_LIMIT);
        value.addProperty("requests_additional_chunks",false);return value;
    }
    private GeoFrontVerticalVisibilityR44() { }
}
