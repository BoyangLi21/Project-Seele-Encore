package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.visual.RegionalNativeTransitInspection;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.network.chat.Component;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.lang.reflect.Field;
import java.util.*;

/** Uses MTR's own departure restoration without replacing routes or running trains. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class NervTransitRecoveryR53
{
    @SubscribeEvent public static void commands(RegisterCommandsEvent event)
    {
        event.getDispatcher().register(Commands.literal("nerv").then(Commands.literal("transit")
                .requires(s->s.hasPermission(2))
                .then(Commands.literal("status").executes(c->run(c.getSource(),false)))
                .then(Commands.literal("resume").executes(c->run(c.getSource(),true)))));
    }
    private static int run(CommandSourceStack source,boolean resume)
    {
        try
        {
            Object simulator=RegionalNativeTransitInspection.simulator();
            if(simulator==null){message(source,"MTR 尚未加载 GeoFront 交通数据。",true);return 0;}
            simulator.getClass().getMethod("run",Runnable.class).invoke(simulator,(Runnable)()->inspect(source,simulator,resume));
            return 1;
        }
        catch(ReflectiveOperationException e){message(source,"MTR 操作失败："+e.getClass().getSimpleName(),true);return 0;}
    }
    @SuppressWarnings("unchecked") private static void inspect(CommandSourceStack source,Object simulator,boolean resume)
    {
        try
        {
            Class<?> listType=Class.forName("org.mtr.libraries.it.unimi.dsi.fastutil.objects.ObjectArrayList");
            Collection<Object> restart=(Collection<Object>)listType.getConstructor().newInstance();
            List<String> report=new ArrayList<>();int found=0;
            for(Object depot:(Iterable<?>)simulator.getClass().getField("depots").get(simulator))
            {
                String line="";
                for(Object route:(Iterable<?>)depot.getClass().getField("routes").get(depot))
                {
                    String code=(String)route.getClass().getMethod("getRouteNumber").invoke(route);
                    if(Set.of("S1","R1").contains(code)){line=code;break;}
                }
                if(line.isEmpty())continue;found++;int active=0,parked=0;
                for(Object siding:(Iterable<?>)simulator.getClass().getField("sidings").get(simulator))
                {
                    if(siding.getClass().getField("area").get(siding)!=depot)continue;
                    Field field=siding.getClass().getDeclaredField("vehicles");field.setAccessible(true);
                    for(Object vehicle:(Iterable<?>)field.get(siding))
                        if(Boolean.TRUE.equals(vehicle.getClass().getMethod("getIsOnRoute").invoke(vehicle)))active++;else parked++;
                }
                String status=depot.getClass().getMethod("getLastGeneratedStatus").invoke(depot).toString();
                report.add(line+"：线路列车 "+active+"，车库列车 "+parked+"，路径 "+status);
                if(resume&&active==0&&status.equals("SUCCESSFUL"))restart.add(depot);
            }
            if(found==0){message(source,"未找到已登记的 S1/R1 线路；未生成新线路。",true);return;}
            if(!restart.isEmpty())
            {
                simulator.getClass().getMethod("instantDeployDepots",listType).invoke(simulator,restart);
                report.add("已调用 MTR 原生发车恢复，处理 "+restart.size()+" 条空线路。");
            }
            else if(resume)report.add("未重置运行中的列车；现有数量见上。若画面仍无车，需要检查客户端同步/渲染。");
            for(String text:report)message(source,text,false);
        }
        catch(ReflectiveOperationException|RuntimeException e){message(source,"MTR 操作失败："+e.getClass().getSimpleName()+" "+e.getMessage(),true);}
    }
    private static void message(CommandSourceStack source,String text,boolean error)
    {
        ProjectSeele.LOGGER.info("Transit recovery: {}",text);
        source.getServer().execute(()->{if(error)source.sendFailure(Component.literal(text));else source.sendSuccess(()->Component.literal(text),false);});
    }
    private NervTransitRecoveryR53() { }
}
