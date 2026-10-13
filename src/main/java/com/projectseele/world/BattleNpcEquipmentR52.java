package com.projectseele.world;

import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.NervStaffEntity;
import java.util.Comparator;
import java.util.Set;
import net.minecraft.server.level.*;
import net.minecraft.world.level.ChunkPos;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** A regular Unit02 sortie requests the original sword well through the existing staff authorization chain. */
@Mod.EventBusSubscriber(modid="projectseele")
public final class BattleNpcEquipmentR52
{
    private static final TicketType<ChunkPos> TICKET=TicketType.create("battle_sword_operator_r52",Comparator.comparingLong(ChunkPos::toLong),100);
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.START||event.getServer().getTickCount()%20!=0)return;
        var level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);if(level==null)return;
        var data=TvCampaignSavedData.get(level);var sortie=data.sorties.get(2);
        // Marine grappling explicitly requires empty hands; the regular sword request must not reserve that sortie.
        if(sortie==null||!sortie.npc||data.active.isEmpty()||data.active.equals("gaghiel")
                ||Set.of("cancel","failure","combat_victory","episode_archived").contains(data.phase)||data.targetDeathConfirmedR45)return;
        var selected=ArmedSortieSavedDataR48.get(level).selection(2);if(selected!=null)return;
        var commander=level.getServer().getPlayerList().getPlayer(sortie.commander);
        var eva=TvSortiesR32.assignedUnit(level,sortie);if(commander==null||commander.level()!=level||eva==null)return;
        var post=NervStaffDirector.roster(level).stream().filter(p->p.skin().equals("misato")).findFirst().orElse(null);if(post==null)return;
        var chunk=new ChunkPos(post.feet());level.getChunkSource().addRegionTicket(TICKET,chunk,3,chunk);
        var id=NervStaffSavedData.get(level).identity(post.id());
        if(id==null||!(level.getEntity(id) instanceof NervStaffEntity officer)||!officer.isAlive())return;
        var result=StaffOperationsR48.armedSortie(commander,officer,2,true);
        if(result.accepted())
        {
            sortie.rifle=false;data.notice="二号机常规出击已安排原剑井领用；驾驶员完成实际交接后持剑迎击。";data.setDirty();
            com.projectseele.ProjectSeele.LOGGER.info("R52 regular Unit02 original sword requested: eva={} owner={} generation={}",eva.getUUID(),commander.getUUID(),data.generationR43);
        }
    }
    private BattleNpcEquipmentR52(){}
}
