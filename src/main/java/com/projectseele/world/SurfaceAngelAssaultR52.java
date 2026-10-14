package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.*;
import com.projectseele.event.TvEncounterDirectorR45;
import com.projectseele.registry.ModEntities;
import java.util.Comparator;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.*;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.MoverType;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

/** One accepted original approaches on the surface, damages only real top-plate contacts, and meets EVA there. */
public final class SurfaceAngelAssaultR52
{
    private static final TicketType<ChunkPos> TICKET=TicketType.create("surface_angel_r52",Comparator.comparingLong(ChunkPos::toLong),100);
    private static void retain(ServerLevel level,Vec3 point)
    {var chunk=new ChunkPos(BlockPos.containing(point));level.getChunkSource().addRegionTicket(TICKET,chunk,3,chunk);}
    public static boolean begun(ServerLevel level,TvCampaignSavedData data)
    {
        if(!SurfaceAngelPlanR52.handles(level,data.active)||data.owner==null)return false;
        var plan=SurfaceAngelPlanR52.plan(level).orElse(null);var site=SurfaceAngelPlanR52.site(level,data.active).orElse(null);
        if(plan==null||site==null||!SurfaceAngelPlanR52.startBlocker(level,data.active).isEmpty())return false;
        data.encounterSiteR45=plan.id();data.encounterLayoutR45=plan.fingerprint();data.setDirty();
        retain(level,site.spawn());tick(level,data);return true;
    }
    private static Mob spawn(ServerLevel level,TvCampaignSavedData data,SurfaceAngelPlanR52.Site site)
    {
        retain(level,site.spawn());if(!level.isPositionEntityTicking(BlockPos.containing(site.spawn())))return null;
        String tag=TvEncounterDirectorR45.tag(data.active);
        if(!level.getEntitiesOfClass(Mob.class,new AABB(site.spawn(),site.spawn()).inflate(180),m->m.isAlive()&&m.getTags().contains(tag)).isEmpty())
        {data.notice="远端仍有未归档的原使徒，不重复生成。";data.setDirty();return null;}
        Mob boss=data.active.equals("sachiel")?ModEntities.SACHIEL.get().create(level):ModEntities.SHAMSHEL.get().create(level);
        if(boss==null)return null;
        boss.moveTo(site.spawn().x,site.spawn().y,site.spawn().z,site.yaw(),0);boss.yBodyRot=boss.yHeadRot=site.yaw();
        boss.setPersistenceRequired();boss.setNoAi(true);boss.addTag(tag);
        boss.getPersistentData().putLong("TvGenerationR45",data.generationR43);boss.getPersistentData().putUUID("TvOwnerR45",data.owner);
        boss.getPersistentData().putString("SurfaceLayoutR52",data.encounterLayoutR45);
        if(boss instanceof SachielEntity){boss.addTag("seele_first_battle_mission");boss.addTag("seele_first_battle_replay");}
        else boss.addTag("seele_tv_shamshel_r24");
        if(!level.noCollision(boss,boss.getBoundingBox())){data.notice="远端原使徒完整躯干净空受阻，未挪到旧近城出生点。";data.setDirty();return null;}
        if(!level.addFreshEntity(boss))return null;
        data.angel=boss.getUUID();data.lastPosition=boss.blockPosition();data.setDirty();
        if(boss instanceof SachielEntity)
        {
            var first=FirstBattleSavedData.get(level);first.missionOwner=data.owner;first.missionAngel=boss.getUUID();
            first.missionLastPos=boss.blockPosition();first.missionCancelRequested=false;first.setDirty();
        }
        ProjectSeele.LOGGER.info("R52 accepted surface Angel deployed: chapter={} uuid={} spawn={} generation={}",data.active,boss.getUUID(),boss.position(),data.generationR43);
        return boss;
    }
    private static void hold(Mob boss)
    {boss.setNoAi(true);boss.setTarget(null);boss.getNavigation().stop();boss.setDeltaMovement(0,boss instanceof ShamshelEntity?0:boss.getDeltaMovement().y,0);if(boss instanceof SachielEntity s)SachielTacticsR34.recordMotion(s,Vec3.ZERO);}
    public static Mob tick(ServerLevel level,TvCampaignSavedData data)
    {
        if(!SurfaceAngelPlanR52.handles(level,data.active))return null;
        var plan=SurfaceAngelPlanR52.plan(level).orElse(null);var site=SurfaceAngelPlanR52.site(level,data.active).orElse(null);
        Mob boss=data.angel!=null&&level.getEntity(data.angel) instanceof Mob m?m:null;
        String blocker=SurfaceAngelPlanR52.startBlocker(level,data.active);
        if(site==null||plan==null||!data.encounterSiteR45.equals(plan.id())||!data.encounterLayoutR45.equals(plan.fingerprint())
                ||!blocker.isEmpty())
        {if(boss!=null&&TvEncounterDirectorR45.owned(boss,data))hold(boss);String notice=blocker.isEmpty()?"原远端路线或地表装甲井安装状态改变，行动暂停。":blocker;if(!data.notice.equals(notice)){data.notice=notice;data.setDirty();}return boss;}
        if(data.angel!=null)
        {
            if(data.lastPosition!=null)retain(level,Vec3.atCenterOf(data.lastPosition));
            if(boss==null)return null; // An unloaded original is never replaced.
            if(!TvEncounterDirectorR45.owned(boss,data)||!boss.getPersistentData().getString("SurfaceLayoutR52").equals(data.encounterLayoutR45))
            {data.notice="原使徒与本次远端路线凭证不符，未接管。";return null;}
        }
        var owner=level.getServer().getPlayerList().getPlayer(data.owner);
        if(owner==null||owner.level()!=level){if(boss!=null)hold(boss);return boss;}
        if(boss==null){boss=spawn(level,data,site);if(boss==null)return null;}
        if(!boss.isAlive()||boss instanceof SachielEntity s&&s.isFirstBattleActive())return boss;
        if(!boss.blockPosition().equals(data.lastPosition)){data.lastPosition=boss.blockPosition();data.setDirty();}
        if(boss instanceof SachielEntity){var first=FirstBattleSavedData.get(level);first.missionLastPos=boss.blockPosition();first.setDirty();}
        retain(level,boss.position());for(double x:new double[]{boss.getBoundingBox().minX,boss.getBoundingBox().maxX})
            for(double z:new double[]{boss.getBoundingBox().minZ,boss.getBoundingBox().maxZ})retain(level,new Vec3(x,boss.getY(),z));
        if(data.phase.equals("alert")&&TvMissionAlertR30.tick(level,data,owner)){data.phase="approach";data.setDirty();}
        final Mob original=boss;
        var defender=data.sorties.values().stream().filter(s->TvSortiesR32.readyAssigned(level,s)).map(s->TvSortiesR32.assignedUnit(level,s))
                .filter(e->e.distanceToSqr(original)<=site.engagementRange()*site.engagementRange()&&original.hasLineOfSight(e))
                .min(Comparator.comparingDouble(original::distanceToSqr)).orElse(null);
        if(defender!=null)
        {
            if(boss.getPersistentData().getBoolean("SurfaceArmorAttackR52"))cancelPlateAttack(boss);
            boss.setNoAi(false);boss.setTarget(defender);
            if(!data.phase.equals("alert")&&!data.phase.equals("combat")&&boss.distanceToSqr(defender)<=48*48)
            {data.phase="combat";data.setDirty();}
            return boss;
        }
        hold(boss);var tag=boss.getPersistentData();
        if(boss instanceof SachielEntity sachiel&&(sachiel.isStrikeActive()||sachiel.isArmorBeamR52())||boss instanceof ShamshelEntity shamshel&&shamshel.isSweeping())
        {contact(level,boss,site);return boss;}
        tag.putBoolean("SurfaceArmorAttackR52",false);
        int cursor=Math.max(0,Math.min(tag.getInt("SurfaceRouteCursorR52"),site.route().size()));
        while(cursor<site.route().size()&&arrived(boss,site.route().get(cursor),site.arrivalRadius()))cursor++;
        tag.putInt("SurfaceRouteCursorR52",cursor);
        if(cursor<site.route().size())
        {
            Vec3 point=site.route().get(cursor);retain(level,point);
            if(!level.isPositionEntityTicking(BlockPos.containing(point)))return boss;
            Vec3 delta=point.subtract(boss.position());Vec3 horizontal=delta.multiply(1,0,1);
            float yaw=(float)Math.toDegrees(Math.atan2(-delta.x,delta.z));boss.setYRot(net.minecraft.util.Mth.approachDegrees(boss.getYRot(),yaw,3));boss.yBodyRot=boss.yHeadRot=boss.getYRot();
            Vec3 step=boss instanceof ShamshelEntity?delta:horizontal;
            if(step.lengthSqr()>1e-8)
            {
                Vec3 before=boss.position();boss.move(MoverType.SELF,step.normalize().scale(Math.min(site.speed(),step.length())));
                if(boss instanceof SachielEntity s)SachielTacticsR34.recordMotion(s,boss.position().subtract(before));
                if(before.distanceToSqr(boss.position())<1e-8&&level.getGameTime()%100==0)
                    ProjectSeele.LOGGER.warn("R52 surface Angel blocked by real world: actor={} route={} cursor={} point={}",boss.getUUID(),data.encounterSiteR45,cursor,point);
            }
            return boss;
        }
        var aim=NervArmorColumnR50.surfaceAimR52(level).orElse(null);if(aim==null)return boss;
        if(boss instanceof ShamshelEntity)
        {
            // Original idle tail skin hangs 0.221m below its root in this selected rig.
            // The real hovering entity rises continuously before pitching; the mesh and shoulder rise with it.
            double clearanceY=site.route().get(site.route().size()-1).y+.35;
            if(boss.getY()<clearanceY-.001){boss.move(MoverType.SELF,new Vec3(0,Math.min(.035,clearanceY-boss.getY()),0));return boss;}
        }
        if(level.getGameTime()<tag.getLong("SurfaceArmorNextAttackR52"))return boss;
        Vec3 toward=aim.subtract(boss.position());float yaw=(float)Math.toDegrees(Math.atan2(-toward.x,toward.z));
        boss.setYRot(net.minecraft.util.Mth.approachDegrees(boss.getYRot(),yaw,3));boss.yBodyRot=boss.yHeadRot=boss.getYRot();
        if(Math.abs(net.minecraft.util.Mth.wrapDegrees(yaw-boss.getYRot()))>8)return boss;
        boolean started=boss instanceof SachielEntity sachiel?sachiel.beginArmorBeamR52(aim):boss instanceof ShamshelEntity shamshel&&shamshel.beginArmorSweepR52(aim);
        if(started){tag.putBoolean("SurfaceArmorAttackR52",true);tag.putBoolean("SurfaceArmorHitR52",false);tag.putBoolean("SurfaceArmorBeamFiredR52",false);tag.putLong("SurfaceArmorNextAttackR52",level.getGameTime()+site.attackPeriod());}
        return boss;
    }
    private static boolean arrived(Mob boss,Vec3 point,double radius)
    {return boss.position().subtract(point).horizontalDistance()<=radius&&Math.abs(boss.getY()-point.y)<=1.6;}
    private static void cancelPlateAttack(Mob boss)
    {if(boss instanceof SachielEntity s){s.cancelStrikeR31();s.cancelArmorBeamR52();}if(boss instanceof ShamshelEntity s)s.cancelSweepR31();boss.getPersistentData().putBoolean("SurfaceArmorAttackR52",false);}
    private static void contact(ServerLevel level,Mob boss,SurfaceAngelPlanR52.Site site)
    {
        var tag=boss.getPersistentData();if(!tag.getBoolean("SurfaceArmorAttackR52")||tag.getBoolean("SurfaceArmorHitR52"))return;
        boolean hit=false;
        if(boss instanceof SachielEntity s)
        {
            if(s.isArmorBeamR52())
            {
                if(s.armorBeamAgeR52(0)<SachielArmorBeamR52.CHARGE||tag.getBoolean("SurfaceArmorBeamFiredR52"))return;
                Vec3 from=SachielArmorBeamR52.origin(s,0),to=s.armorBeamAimR52();
                var ray=level.clip(new net.minecraft.world.level.ClipContext(from,to,net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,s));
                Vec3 visibleEnd=ray.getLocation();
                com.projectseele.network.SeeleNetwork.CHANNEL.send(net.minecraftforge.network.PacketDistributor.TRACKING_ENTITY_AND_SELF.with(()->s),new com.projectseele.network.ClientboundCannonBeamPacket(from.x,from.y,from.z,visibleEnd.x,visibleEnd.y,visibleEnd.z));
                tag.putBoolean("SurfaceArmorBeamFiredR52",true);
                if(NervArmorColumnR50.surfaceImpactR52(level,s,from,to,site.armorDamage()))tag.putBoolean("SurfaceArmorHitR52",true);
                return;
            }
            float age=s.strikeAge(0);if(age<SachielStrike.contactStart(s.strikeMode())||age>SachielStrike.contactEnd(s.strikeMode()))return;
            for(int i=0;i<=4&&!hit;i++)
            {
                float t=age-1+i/4F;var before=SachielStrike.sample(s,t-.25F,0);var now=SachielStrike.sample(s,t,0);
                hit=NervArmorColumnR50.surfaceImpactR52(level,s,before.tip(),now.tip(),site.armorDamage());
            }
        }
        else if(boss instanceof ShamshelEntity s)
        {
            float age=s.sweepAge(0);if(age<ShamshelWhipMotion.contactStart(s.sweepMode())||age>ShamshelWhipMotion.contactEnd(s.sweepMode()))return;
            for(int i=0;i<=4&&!hit;i++)
            {
                var points=ShamshelWhipMotion.points(s,age-1+i/4F,0);var before=ShamshelWhipMotion.points(s,age-1.25F+i/4F,0);
                for(int j=1;j<points.size()&&!hit;j++)hit=NervArmorColumnR50.surfaceImpactR52(level,s,points.get(j-1),points.get(j),site.armorDamage())
                        ||NervArmorColumnR50.surfaceImpactR52(level,s,before.get(j),points.get(j),site.armorDamage());
            }
        }
        if(hit)tag.putBoolean("SurfaceArmorHitR52",true);
    }
    private SurfaceAngelAssaultR52(){}
}
