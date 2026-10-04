package com.projectseele.world;

import com.projectseele.entity.*;
import com.projectseele.event.TvCampaignDirector;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.*;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.chunk.ChunkStatus;
import net.minecraft.world.phys.*;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.util.*;

/** Tactical intent only: native travel, the real capsule and the same contact/ballistics code as a human pilot. */
@Mod.EventBusSubscriber(modid="projectseele")
public final class NervPilotCombatR30
{
    private static final TicketType<ChunkPos> TICKET=TicketType.create("nerv_pilot_combat_r30",Comparator.comparingLong(ChunkPos::toLong),100);
    private static final Map<EvaUnit01Entity,Brain> BRAINS=new WeakHashMap<>();
    private static final class Brain
    {
        int age,retreat,gunTicks;long nextOrder,nextSteer,nextRadio;float health=-1;
        Vec3 steer=Vec3.ZERO;String tactic="",spokenTopic="";UUID station;
    }
    public static boolean controls(EvaUnit01Entity e)
    {
        if(PilotReturnR39.controls(e))return true;
        if(!(e.level() instanceof ServerLevel l)||e.isExperimentalUnit())return false;var d=TvCampaignSavedData.get(l);
        var sortie=d.sorties.get(e.getUnitVariant());
        return sortie!=null&&sortie.npc&&!AutoSortieR32.missionToken(l).isEmpty()
                &&e==TvSortiesR32.assignedUnit(l,sortie)&&e.getPilotEntity() instanceof TrainingPilotEntity pilot
                &&sortie.pilotR45!=null&&sortie.pilotR45.equals(pilot.getUUID())&&pilot.getAssignedVariant()==sortie.unit;
    }
    private static void retain(ServerLevel l,BlockPos p)
    {var c=new ChunkPos(p);l.getChunkSource().addRegionTicket(TICKET,c,3,c);l.getChunkSource().getChunkFuture(c.x,c.z,ChunkStatus.FULL,true);}
    private static NervStaffEntity officer(ServerLevel l,String skin)
    {
        var post=NervStaffDirector.roster(l).stream().filter(p->p.skin().equals(skin)).findFirst().orElse(null);if(post==null)return null;
        retain(l,post.feet());var id=NervStaffSavedData.get(l).identity(post.id());return id!=null&&l.getEntity(id) instanceof NervStaffEntity npc?npc:null;
    }
    private static void say(ServerPlayer commander,TrainingPilotEntity pilot,Brain b,String topic)
    {
        b.tactic=topic;
        var d=TvCampaignSavedData.get((ServerLevel)pilot.level());String status=pilot.getName().getString()+"："+switch(topic){case "weapon_approach"->"前往武器井";case "weapon_acquired"->"武器接收完成";case "enroute"->"正在前往迎击区";case "evade"->"规避使徒攻击";case "ranged"->"保持距离射击";case "close_in"->"正在接近目标";case "melee"->"近距离交战";case "finale_spacing"->"稳住机体，保持目标在正面";default->"保持通信";};
        if(!status.equals(d.notice)){d.notice=status;d.setDirty();}
        if(commander==null||commander.level().getGameTime()<b.nextRadio||b.spokenTopic.equals(topic))return;
        b.nextRadio=commander.level().getGameTime()+160;b.spokenTopic=topic;
        NervStaffDialogue.say(commander,pilot.getName().getString()+" · 驾驶员通信",StaffDialogueCatalogR24.next(commander,PilotRadioR28.profile(pilot.getAssignedVariant()),"technician",topic));
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.START)return;var l=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);if(l==null)return;
        var d=TvCampaignSavedData.get(l);
        for(var entry:new ArrayList<>(BRAINS.entrySet()))if(entry.getKey().isRemoved()||AutoSortieR32.missionToken(l).isEmpty()||!d.sorties.containsKey(entry.getKey().getUnitVariant())||!d.sorties.get(entry.getKey().getUnitVariant()).npc)
        {entry.getKey().stopAutonomousR30();BRAINS.remove(entry.getKey());}
        if(d.active.isEmpty()||Set.of("cancel","failure","alert","combat_victory","episode_archived").contains(d.phase)||d.targetDeathConfirmedR45)return;
        for(var sortie:List.copyOf(d.sorties.values()))if(sortie.npc)tickUnit(l,d,sortie);
    }
    private static void tickUnit(ServerLevel l,TvCampaignSavedData d,TvCampaignSavedData.Sortie sortie)
    {
        var owner=l.getServer().getPlayerList().getPlayer(sortie.commander);
        var eva=TvSortiesR32.assignedUnit(l,sortie);
        if(eva==null){EvaLogisticsDirector.loadControlTarget(l,sortie.unit);return;}
        if(owner==null||owner.level()!=l){eva.stopAutonomousR30();return;}
        if(d.phase.equals("failure")){TvEncounterRulesR45.stopEquipment(l,d);eva.stopAutonomousR30();return;}
        retain(l,eva.blockPosition());var b=BRAINS.computeIfAbsent(eva,key->new Brain());b.age++;
        if(EvaShutdownR30.disabled(eva)){eva.stopAutonomousR30();d.notice="机体已关机。司令，可以通过运输部门请求回收。";return;}
        String phase=EvaLogisticsDirector.status(l,sortie.unit).phase();
        if(!phase.equals("DEPLOYED"))
        {
            eva.stopAutonomousR30();if(l.getGameTime()<b.nextOrder)return;b.nextOrder=l.getGameTime()+100;
            if(phase.equals("PARKED"))
            {
                var pilots=TrainingPilotDirector.pilots(l).stream().filter(p->p.getAssignedVariant()==sortie.unit).toList();
                if(pilots.size()!=1){d.notice="原驾驶员尚未接通，机体保持待命。";return;}
                var pilot=pilots.get(0);
                if(sortie.pilotR45==null){sortie.pilotR45=pilot.getUUID();d.setDirty();}
                if(!sortie.pilotR45.equals(pilot.getUUID())){d.notice="驾驶员身份与本次编成不符，未重新派遣。";return;}
                AutoSortieR32.assignCommander(eva,owner);
                if(!sortie.dispatchRequested)
                {var result=TrainingPilotDirector.start(l,sortie.unit);sortie.dispatchRequested=result.accepted();d.notice=result.message();d.setDirty();}
            }
            return;
        }
        if(!(eva.getPilotEntity() instanceof TrainingPilotEntity pilot)||sortie.pilotR45==null||!sortie.pilotR45.equals(pilot.getUUID()))
        {eva.stopAutonomousR30();return;}
        if(eva.isFirstBattleActive()||eva.isLaunchSequenceActive()||eva.isNervLogisticsLocked()){eva.stopAutonomousR30();return;}
        eva.autonomousGuardR30(pilot);
        String city=TvEncounterRulesR45.obstruction(l,d);
        if(!city.isEmpty())
        {
            eva.stopAutonomousR30();d.notice=city;
            if(l.getGameTime()>=b.nextOrder&&!CityBattlefieldR29.loweringRequested(l)
                    &&(!TvEncounterRulesR45.handles(d.active)||TvEncounterSitesR45.site(l,d.active).map(TvEncounterSitesR45.Site::cityInterlock).orElse(false)))
            {
                var winter=officer(l,"fuyutsuki");
                // Retry while the async entity section is still retained; a ten-second
                // retry after a five-second ticket kept unloading the operator forever.
                b.nextOrder=l.getGameTime()+(winter==null?10:winter.busy()?20:200);
                if(winter!=null&&!winter.busy())NervStaffDialogue.converse(owner,winter,"城市降下");
            }
            return;
        }
        LivingEntity angel=d.angel!=null&&l.getEntity(d.angel) instanceof LivingEntity target?target:null;
        Vec3 goal=TvEncounterRulesR45.handles(d.active)?TvEncounterRulesR45.unitApproach(l,d,sortie.unit):TvCampaignDirector.approachPointR30(l);
        if(goal==null){eva.stopAutonomousR30();return;}
        if(d.active.equals("ramiel"))
        {
            boolean held=sortie.unit==0?TvMissionEquipmentR45.shieldAuthorized(eva):sortie.unit==1?TvMissionEquipmentR45.cannonAuthorized(eva):true;
            if(!held)
            {
                var depot=TvMissionEquipmentR45.nearestPhysicalCargo(l,eva);
                if(depot==null){eva.stopAutonomousR30();d.notice=sortie.unit==0?"等待运输部门送达防护盾。":"等待运输部门送达阳离子炮。";return;}
                retain(l,depot.blockPosition());if(!depot.isReadyAndStocked())depot.deploy();
                if(eva.position().subtract(depot.position()).horizontalDistance()>21)
                {move(l,eva,pilot,b,depot.position(),null,false);say(owner,pilot,b,"weapon_approach");return;}
                eva.autonomousDriveR30(pilot,Vec3.ZERO,depot.position().add(0,35,0),false);
                if(TvEncounterRulesR45.issueMissionAtStation(depot,eva,pilot))say(owner,pilot,b,"weapon_acquired");
                return;
            }
            // Preserve collision-aware travel; never chase the distant boss or
            // fall through to the old rifle/melee AI.
            if(!TvEncounterRulesR45.npcTactic(l,d,eva,pilot))
            {move(l,eva,pilot,b,goal,angel,false);say(owner,pilot,b,"enroute");}
            else {b.tactic=sortie.unit==0?"shield_station":"cannon_station";}
            return;
        }
        if(sortie.rifle&&(eva.getArmamentMask()&(1<<EvaUnit01Entity.WEAPON_RIFLE))==0&&angel==null)
        {
            var station=b.station!=null&&l.getEntity(b.station) instanceof NervArmamentStationEntity n?n:NervArmamentStationEntity.commandStation(l);
            if(station!=null)
            {
                b.station=station.getUUID();retain(l,station.blockPosition());if(!station.isReadyAndStocked())station.deploy();
                double distance=eva.position().subtract(station.position()).horizontalDistance();
                if(distance>21){move(l,eva,pilot,b,station.position(),null,true);say(owner,pilot,b,"weapon_approach");return;}
                eva.autonomousDriveR30(pilot,Vec3.ZERO,station.position().add(0,35,0),false);
                if(station.issueToAssignedPilotR30(pilot,eva)){say(owner,pilot,b,"weapon_acquired");sortie.rifle=false;d.setDirty();}return;
            }
        }
        if(angel==null||!angel.isAlive())
        {move(l,eva,pilot,b,goal,null,true);say(owner,pilot,b,"enroute");return;}
        if(angel instanceof FirstBattleSignals.Actor actor&&actor.firstBattleSignals().active(angel))
        {eva.stopAutonomousR30();return;}
        retain(l,angel.blockPosition());double range=eva.position().subtract(angel.position()).horizontalDistance();
        if(b.health>=0&&eva.getHealth()<b.health-.01)b.retreat=26;b.health=eva.getHealth();
        boolean telegraph=angel instanceof SachielEntity sachiel&&sachiel.isStrikeActive()&&sachiel.strikeAge(1)<13||angel instanceof ShamshelEntity shamshel&&shamshel.isSweeping()&&shamshel.sweepAge(1)<12;
        Vec3 toward=angel.position().subtract(eva.position()).multiply(1,0,1).normalize();Vec3 aim=angel.position().add(0,angel.getBbHeight()*.57,0);
        if(angel instanceof SachielEntity sachiel&&sortie.unit==1&&sachiel.getHealth()<=sachiel.getMaxHealth()*.32F&&!sachiel.hasUsedFirstBattle())
        {
            // Finish the current swing, then make room with ordinary movement.
            // Never pull either actor into the scripted pose or bypass collision checks.
            eva.settleAutonomousAttackR30(pilot);
            if(com.projectseele.event.FirstBattleDirector.tryStart(sachiel,eva,false))return;
            Vec3 spacing=range<24?toward.scale(-.7):range>37?toward.scale(.65):Vec3.ZERO;
            if(spacing.lengthSqr()<.001&&eva.position().subtract(goal).horizontalDistance()>14)spacing=goal.subtract(eva.position()).multiply(1,0,1).normalize().scale(.5);
            eva.autonomousDriveR30(pilot,steer(l,eva,b,spacing),aim,false);say(owner,pilot,b,"finale_spacing");return;
        }
        if(b.retreat>0||telegraph&&range<55)
        {
            if(b.retreat>0)b.retreat--;Vec3 dodge=toward.yRot((b.age/120%2==0?1:-1)*(float)Math.PI*.5F).add(toward.scale(-.65)).normalize();
            eva.autonomousDriveR30(pilot,steer(l,eva,b,dodge),aim,true);say(owner,pilot,b,"evade");return;
        }
        boolean rifle=(eva.getArmamentMask()&(1<<EvaUnit01Entity.WEAPON_RIFLE))!=0;
        boolean shield=angel instanceof Angel a&&a.getAtField()>0;
        if(rifle&&range>48&&(!shield||b.gunTicks<90))
        {
            eva.autonomousWeaponR30(pilot,EvaUnit01Entity.WEAPON_RIFLE);b.gunTicks++;
            Vec3 direction=range>145?toward:toward.yRot((b.age/100%2==0?1:-1)*(float)Math.PI*.5F).scale(.38);
            eva.autonomousDriveR30(pilot,steer(l,eva,b,direction),aim,false);eva.autonomousAttackR30(pilot,3);say(owner,pilot,b,"ranged");return;
        }
        int cycle=(b.age/180)%3;int weapon=shield||cycle==0?EvaUnit01Entity.WEAPON_KNIFE:EvaUnit01Entity.WEAPON_FISTS;
        eva.autonomousWeaponR30(pilot,weapon);
        if(range>30){Vec3 flank=angel.position();
            var lead=angel instanceof net.minecraft.world.entity.Mob mob?mob.getTarget():null;if(lead!=eva&&lead!=null){Vec3 radial=eva.position().subtract(flank).multiply(1,0,1).normalize().yRot((sortie.unit%2==0?1:-1)*.6F);flank=flank.add(radial.scale(25));}
            move(l,eva,pilot,b,flank,angel,true);say(owner,pilot,b,"close_in");return;}
        Vec3 circle=range<18?toward.scale(-.6):Vec3.ZERO;
        eva.autonomousDriveR30(pilot,steer(l,eva,b,circle),aim,false);
        if(b.age%12==0)eva.autonomousAttackR30(pilot,weapon==EvaUnit01Entity.WEAPON_KNIFE?(b.age/48)%2:cycle==1?0:(b.age/48)%2==0?1:2);
        say(owner,pilot,b,"melee");
    }
    private static void move(ServerLevel l,EvaUnit01Entity eva,TrainingPilotEntity pilot,Brain b,Vec3 goal,LivingEntity enemy,boolean run)
    {
        Vec3 delta=goal.subtract(eva.position()).multiply(1,0,1);Vec3 direction=delta.length()>7?delta.normalize():Vec3.ZERO;
        Vec3 aim=enemy==null?eva.position().add(direction.scale(30)).add(0,45,0):enemy.position().add(0,enemy.getBbHeight()*.57,0);
        eva.autonomousDriveR30(pilot,steer(l,eva,b,direction),aim,run&&delta.length()>45);
    }
    private static Vec3 steer(ServerLevel l,EvaUnit01Entity eva,Brain b,Vec3 desired)
    {
        if(desired.lengthSqr()<.001)return Vec3.ZERO;
        if(l.getGameTime()<b.nextSteer)return b.steer;b.nextSteer=l.getGameTime()+5;
        for(int angle:new int[]{0,25,-25,50,-50,85,-85,115,-115})
        {
            Vec3 direction=desired.yRot((float)Math.toRadians(angle));Vec3 step=direction.normalize().scale(3);
            if(CombatSpacingR32.clip(eva,step).horizontalDistanceSqr()<step.horizontalDistanceSqr()*.9)continue;
            AABB hull=eva.getBoundingBox().deflate(.12).move(step);
            if(!l.noCollision(eva,hull)&&!l.noCollision(eva,hull.move(0,1,0)))continue;
            Vec3 next=eva.position().add(step);boolean ground=l.getBlockCollisions(eva,new AABB(next.x-3,next.y-2,next.z-3,next.x+3,next.y+.05,next.z+3)).iterator().hasNext();
            if(!ground)continue;b.steer=direction;return direction;
        }
        b.steer=Vec3.ZERO;return Vec3.ZERO;
    }
    private NervPilotCombatR30(){}
}
