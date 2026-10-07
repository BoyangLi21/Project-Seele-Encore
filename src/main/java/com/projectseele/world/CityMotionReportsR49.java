package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.NervStaffEntity;
import java.util.HashMap;
import java.util.Map;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** A city order's caller receives observation only; this service owns no machine or ticket. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class CityMotionReportsR49
{
    private CityMotionReportsR49() {}

    public static void watch(ServerPlayer caller, NervStaffEntity operator, BlockPos origin)
    {
        if (caller.serverLevel() != operator.level() || !NervStaffDialogue.authorized(caller)
                || !caller.serverLevel().dimension().equals(FacilitySchemaV2.DIMENSION)
                || !StaffAuthorityR25.allows(operator, "city_rise")) return;
        var status = Tokyo3RetractionDirector.status(caller.serverLevel(), origin);
        var state=CityMotionReportSavedDataR49.get(caller.serverLevel());
        if(settled(status)){state.remove(caller.getUUID());return;}
        if(!state.bind(caller.getUUID(),operator.getUUID(),origin,status.motionReport(),caller.serverLevel().getGameTime()))
            NervStaffDialogue.reply(caller,operator,"城市进度联络名额已满，请稍后再查询。");
    }

    private static boolean settled(Tokyo3RetractionDirector.Status status)
    {
        return status.phase().equals("RIGID_IDLE") || status.phase().equals("DEPLOYED") || status.phase().equals("RETRACTED");
    }

    @SubscribeEvent
    public static void tick(TickEvent.ServerTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END || event.getServer().getTickCount()%20!=0) return;
        ServerLevel level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);if(level==null)return;
        var state=CityMotionReportSavedDataR49.get(level);if(state.watches.isEmpty())return;
        Map<BlockPos,Tokyo3RetractionDirector.Status> statuses=new HashMap<>();
        var entries=state.watches.entrySet().iterator();
        while(entries.hasNext())
        {
            var watch=entries.next().getValue();
            var status=statuses.computeIfAbsent(watch.origin,p->Tokyo3RetractionDirector.status(level,p));
            boolean ended=settled(status);
            ServerPlayer caller=event.getServer().getPlayerList().getPlayer(watch.caller);
            boolean present=caller!=null&&caller.serverLevel()==level;
            if(!present)
            {
                watch.suspended=true;
                if(ended){entries.remove();state.setDirty();}
                continue;
            }
            if(!NervStaffDialogue.authorized(caller)){entries.remove();state.setDirty();continue;}
            if(level.getGameTime()<watch.next&&!ended)continue;
            var actor=level.getEntity(watch.operator);
            if(actor==null)
            {
                watch.suspended=true;
                if(ended){entries.remove();state.setDirty();}
                continue; // No chunk loading or replacement operator.
            }
            if(!(actor instanceof NervStaffEntity operator)||!operator.isAlive()||!StaffAuthorityR25.allows(operator,"city_rise"))
            {entries.remove();state.setDirty();continue;}
            String report = status.motionReport();
            if(watch.suspended||!report.equals(watch.previous))
            {
                NervStaffDialogue.reply(caller,operator,"碇，"+(watch.suspended?"通信已恢复。":"")+report);
                watch.previous=report;state.setDirty();
            }
            watch.suspended=false;watch.next=level.getGameTime()+200;
            if(ended){entries.remove();state.setDirty();}
        }
    }
}
