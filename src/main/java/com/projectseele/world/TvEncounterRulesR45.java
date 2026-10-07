package com.projectseele.world;

import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.TrainingPilotEntity;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.phys.Vec3;
import java.util.Map;
import java.util.WeakHashMap;
import java.util.Set;
import java.util.HashSet;

/** Server tactical/loadout contracts. Visual/audio/entity equipment stay with root. */
public final class TvEncounterRulesR45
{
    /** Both real Ramiel AI eligibility and ray length must consume this value. */
    public interface BeamRangeSource
    {double effectiveBeamRangeR45();}
    public interface EquipmentControl
    {
        default boolean issueMissionAtStation(com.projectseele.entity.NervArmamentStationEntity station,EvaUnit01Entity eva,net.minecraft.world.entity.LivingEntity actualPilot){return false;}
        default boolean cannonReady(EvaUnit01Entity eva){return false;}
        default boolean rangesReady(EvaUnit01Entity eva,double metres){return false;}
        default boolean shieldEquipped(EvaUnit01Entity eva){return false;}
        default boolean shieldRayIntersects(EvaUnit01Entity eva,Vec3 beamFrom,Vec3 beamTo){return false;}
        default java.util.Optional<Vec3> shieldBeamContact(EvaUnit01Entity eva,Vec3 beamFrom,Vec3 beamTo)
        {return java.util.Optional.empty();}
        default boolean cannonInput(EvaUnit01Entity eva,TrainingPilotEntity pilot,Vec3 actualAim,boolean hold,boolean release){return false;}
        default boolean shieldInput(EvaUnit01Entity eva,TrainingPilotEntity pilot,boolean brace){return false;}
    }
    private static EquipmentControl equipment=TvEncounterEquipmentControlR45.serverCargoAndCannonR45();
    private static final Map<ServerLevel,Set<java.util.UUID>> REMOTE_OBSERVERS=new WeakHashMap<>();
    private record Seen(java.util.UUID target,long generation,long observedAt){}
    private static final Map<ServerLevel,Map<java.util.UUID,Seen>> SEEN=new WeakHashMap<>();
    private record CannonRefusal(String reason,String phase,boolean frame,String equipment,String cannon,boolean ready,String ray){}
    private record CannonDiagnostic(long checkedAt,java.util.UUID target,long generation,CannonRefusal refusal){}
    private static final Map<ServerLevel,Map<java.util.UUID,CannonDiagnostic>> CANNON_DIAGNOSTICS=new WeakHashMap<>();
    public static void installEquipmentControl(EquipmentControl realControl)
    {equipment=java.util.Objects.requireNonNull(realControl);}
    /** Root's real client capability/observer handshake calls this, not a command. */
    public static void remoteObserver(ServerPlayer player,boolean enabled)
    {
        var set=REMOTE_OBSERVERS.computeIfAbsent(player.serverLevel(),l->new HashSet<>());
        if(enabled)set.add(player.getUUID());else {set.remove(player.getUUID());var seen=SEEN.get(player.serverLevel());if(seen!=null)seen.remove(player.getUUID());}
    }
    /** Client decoder + root renderer confirmation of this exact real frame. */
    public static void remoteTargetObserved(ServerPlayer player,java.util.UUID target,long generation,boolean enabled)
    {
        var map=SEEN.computeIfAbsent(player.serverLevel(),l->new java.util.HashMap<>());
        var d=TvCampaignSavedData.get(player.serverLevel());
        var controlled=EvaPilotResolver.controlTarget(player);
        boolean actualPilot=controlled!=null&&controlled.getPilotEntity()==player
                &&d.sorties.values().stream().anyMatch(s->s.eva!=null&&s.eva.equals(controlled.getUUID()));
        boolean participant=actualPilot||player.getUUID().equals(d.owner)||d.sorties.values().stream().anyMatch(s->player.getUUID().equals(s.commander));
        if(enabled&&participant&&target!=null&&target.equals(d.angel)&&generation==d.generationR43
                &&!d.phase.equals("cancel")&&!d.phase.equals("failure"))map.put(player.getUUID(),new Seen(target,generation,player.serverLevel().getGameTime()));
        else map.remove(player.getUUID());
    }
    public static boolean targetFrameReady(ServerLevel l,TvCampaignSavedData d,ServerPlayer player)
    {
        var site=TvEncounterSitesR45.site(l,d.active).orElse(null);
        if(site==null||player==null||d.angel==null||!visibleToCommander(l,d,player))return false;
        if(site.visibility().equals("native_tracking"))return visibleToCommander(l,d,player);
        var seen=SEEN.getOrDefault(l,Map.of()).get(player.getUUID());
        return seen!=null&&seen.target().equals(d.angel)&&seen.generation()==d.generationR43&&l.getGameTime()-seen.observedAt()<=200;
    }
    public static boolean issueMissionAtStation(com.projectseele.entity.NervArmamentStationEntity station,EvaUnit01Entity eva,net.minecraft.world.entity.LivingEntity actualPilot)
    {return equipment.issueMissionAtStation(station,eva,actualPilot);}
    public static void pauseNpcUnitForRecoveryR47(EvaUnit01Entity eva)
    {
        if(!(eva.getPilotEntity() instanceof TrainingPilotEntity pilot))return;
        equipment.cannonInput(eva,pilot,eva.getEyePosition().add(eva.getForward().scale(16)),false,false);
        equipment.shieldInput(eva,pilot,false);
    }
    public static boolean handles(String id){return id.equals("ramiel")||id.equals("gaghiel");}
    public static String formationSlotBlockerR47(ServerLevel level,String chapter,int unit)
    {
        if(!handles(chapter)||unit>=3)return "";
        var site=TvEncounterSitesR45.site(level,chapter).orElse(null);
        if(site==null)return "当前作战阵地尚未接入。";
        boolean needsSupport=chapter.equals("ramiel")?unit==2:unit!=site.primaryUnit();
        return needsSupport&&!site.supportReady()?"这台机体的支援阵地尚未开放，请先保持现有编成。":"";
    }
    public static String obstruction(ServerLevel l,TvCampaignSavedData d)
    {
        if(!handles(d.active))return CityBattlefieldR29.obstruction(l);
        var site=TvEncounterSitesR45.site(l,d.active).orElse(null);
        if(site==null)return TvEncounterSitesR45.startBlocker(l,d.active);
        if(d.active.equals("ramiel")&&d.sorties.containsKey(2)&&!site.supportReady())return "二号机支援阵地仍在整备中。";
        return site.cityInterlock()?CityBattlefieldR29.obstruction(l):"";
    }
    public static Vec3 unitApproach(ServerLevel l,TvCampaignSavedData d,int unit)
    {
        var site=TvEncounterSitesR45.site(l,d.active).orElse(null);
        if(site==null)return null;
        if(d.active.equals("ramiel"))return switch(unit)
        {case 0->site.cover();case 1->site.hero();case 2->site.supportReady()?site.support():null;default->null;};
        return unit==site.primaryUnit()?site.hero():site.supportReady()?site.support():null;
    }
    public static boolean visibleToCommander(ServerLevel l,TvCampaignSavedData d,ServerPlayer commander)
    {
        var site=TvEncounterSitesR45.site(l,d.active).orElse(null);
        if(site==null||commander==null||commander.level()!=l||d.angel==null)return false;
        if(site.visibility().equals("native_tracking"))
        {
            var target=l.getEntity(d.angel);
            boolean participant=commander.getUUID().equals(d.owner)
                    ||d.sorties.values().stream().anyMatch(s->commander.getUUID().equals(s.commander)
                        ||!s.npc&&commander.getUUID().equals(s.pilotR45));
            return participant&&site.geometryValidated()&&site.modelReady()
                    &&site.id().equals(d.encounterSiteR45)&&site.fingerprint().equals(d.encounterLayoutR45)
                    &&target instanceof net.minecraft.world.entity.Mob mob&&mob.isAlive()
                    &&com.projectseele.event.TvEncounterDirectorR45.owned(mob,d)
                    &&TvEncounterTrackingR50.tracks(l,commander,mob);
        }
        return site.visibility().equals("remote_actual_entity_v1")
                &&REMOTE_OBSERVERS.getOrDefault(l,Set.of()).contains(commander.getUUID());
    }
    public static String equipmentBlocker(ServerLevel l,TvCampaignSavedData d)
    {
        if(!d.active.equals("ramiel"))return "";
        if(d.phase.equals("combat")||d.phase.equals("approach"))
            return com.projectseele.event.TvEncounterDirectorR45.combatEquipmentBlockerR48(l,d);
        if(d.phase.equals("alert"))return "识别与编成确认中；原拉米尔正在钻进。";
        var shooter=TvSortiesR32.assignedUnit(l,d,1);var cover=TvSortiesR32.assignedUnit(l,d,0);
        if(!d.sorties.containsKey(1)||!d.sorties.containsKey(0))return "屋岛编成需要初号机射手与零号机防护，可由玩家或驾驶员加入。";
        if(!TvSortiesR32.readyAssigned(l,d.sorties.get(1))||!TvSortiesR32.readyAssigned(l,d.sorties.get(0)))return "等待初号机与零号机完成整备、发射。";
        var site=TvEncounterSitesR45.site(l,d.active).orElse(null);
        if(site==null||!equipment.rangesReady(shooter,Math.max(site.separation(),site.attackRange())))return "远程火控仍在整备中。";
        if(!TvMissionEquipmentR45.cannonAuthorized(shooter)||!equipment.cannonReady(shooter))return "初号机尚未装配阳离子炮。";
        if(!TvMissionEquipmentR45.shieldAuthorized(cover)||!equipment.shieldEquipped(cover))return "零号机尚未装备防护盾。";
        if(cover.position().distanceTo(site.cover())>12)return "零号机请抵达防护站位，挡在初号机与目标之间。";
        if(shooter.position().distanceTo(site.hero())>12)return "初号机请抵达炮击阵地。";
        var boss=d.angel==null?null:l.getEntity(d.angel);
        Vec3 from=boss==null?site.angel().add(0,7.5,0):boss.getBoundingBox().getCenter();
        Vec3 to=shooter.getEyePosition();
        if(boss!=null&&(!(boss instanceof BeamRangeSource range)||range.effectiveBeamRangeR45()<from.distanceTo(to)))
            return "目标火控仍在校准中，请保持阵地。";
        if(!equipment.shieldRayIntersects(cover,from,to))return "零号机请调整盾面，遮挡目标到初号机的射线。";
        return "";
    }
    /** Pure role intent; uses the same real root equipment API as human inputs. */
    public static boolean npcTactic(ServerLevel l,TvCampaignSavedData d,EvaUnit01Entity eva,TrainingPilotEntity pilot)
    {
        if(d.active.equals("gaghiel"))return TvMarineDirectorR50.npcTacticR50(l,d,eva,pilot);
        if(!d.active.equals("ramiel"))return false;
        var goal=unitApproach(l,d,eva.getUnitVariant());if(goal==null){eva.stopAutonomousR30();return true;}
        var boss=d.angel==null?null:l.getEntity(d.angel);
        var site=TvEncounterSitesR45.site(l,d.active).orElse(null);
        Vec3 aim=boss==null?(site==null?goal:site.angel().add(0,7.5,0)):boss.getBoundingBox().getCenter();
        if(eva.getUnitVariant()==0)
        {
            var side=TvYashimaArrivalR50.shieldSide(l);
            if(side==null||site==null){eva.stopAutonomousR30();d.notice="原盾侧待命通路尚未确认。";return true;}
            boolean counterattack=boss instanceof com.projectseele.entity.RamielEntity ramiel&&ramiel.isCharging();
            Vec3 shieldGoal=counterattack?site.cover():side;
            eva.autonomousWeaponR30(pilot,EvaUnit01Entity.WEAPON_SHIELD_R45);
            // Clearing the gun line is as urgent as entering cover; ordinary
            // walking across this lane consumes almost the entire core window.
            NervPilotCombatR30.tacticalMoveR50(eva,pilot,shieldGoal,aim,true);
            boolean atCover=eva.position().subtract(site.cover()).horizontalDistance()<=1.2&&Math.abs(eva.getY()-site.cover().y)<=1.35;
            equipment.shieldInput(eva,pilot,counterattack&&atCover&&TvMissionEquipmentR45.operational(eva)&&equipment.shieldEquipped(eva));
            return true;
        }
        Vec3 delta=goal.subtract(eva.position()).multiply(1,0,1);
        if(delta.length()>7)return false; // Existing collision-aware travel owns approach.
        eva.autonomousDriveR30(pilot,Vec3.ZERO,aim,false);
        if(d.active.equals("ramiel"))
        {
            if(eva.getUnitVariant()==0)
            {
                eva.autonomousWeaponR30(pilot,EvaUnit01Entity.WEAPON_SHIELD_R45);
                equipment.shieldInput(eva,pilot,TvMissionEquipmentR45.operational(eva)
                    &&TvMissionEquipmentR45.shieldAuthorized(eva)&&equipment.shieldEquipped(eva));
            }
            else if(eva.getUnitVariant()==1)
            {
                if(TvMissionEquipmentR45.cannonAuthorized(eva))eva.autonomousWeaponR30(pilot,EvaUnit01Entity.WEAPON_CANNON);
                var commander=d.owner==null?null:l.getServer().getPlayerList().getPlayer(d.owner);
                diagnoseCannonRefusalR50(l,d,eva,pilot,commander,boss);
                if(!d.phase.equals("combat")||!targetFrameReady(l,d,commander)||!equipmentBlocker(l,d).isEmpty())
                {equipment.cannonInput(eva,pilot,aim,false,false);return true;}
                if(!equipment.cannonReady(eva))return true;
                boolean full=eva.getCannonCharge()>=com.projectseele.config.SeeleConfig.CANNON_CHARGE_TICKS.get();
                boolean exposed=boss instanceof com.projectseele.entity.RamielEntity r&&r.isExposed();
                boolean clear=eva.missionCannonRayClearR50(pilot);
                if(full&&exposed&&!clear)d.notice="阳电子炮真实火线被己方盾面挡住，等待零号机退到侧位。";
                equipment.cannonInput(eva,pilot,aim,boss!=null&&!(full&&exposed&&clear),full&&exposed&&clear);
            }
        }
        return true;
    }
    /** Diagnostics sample the real gates; they never grant fire permission. */
    private static void diagnoseCannonRefusalR50(ServerLevel level,TvCampaignSavedData data,EvaUnit01Entity eva,
            TrainingPilotEntity pilot,ServerPlayer commander,net.minecraft.world.entity.Entity boss)
    {
        var map=CANNON_DIAGNOSTICS.computeIfAbsent(level,ignored->new java.util.HashMap<>());
        var previous=map.get(eva.getUUID());long now=level.getGameTime();
        if(previous!=null&&now>=previous.checkedAt()&&now-previous.checkedAt()<20)return;
        boolean frame=targetFrameReady(level,data,commander);
        String equipmentReason=equipmentBlocker(level,data),cannonReason=TvYashimaDirectorR50.cannonBlocker(eva);
        boolean ready=equipment.cannonReady(eva);
        // Evaluate the same current physical ray even when the frame gate is
        // blocked. An unissued cannon has no meaningful cannon ray to report.
        boolean evaluated=ready&&TvMissionEquipmentR45.cannonAuthorized(eva);
        boolean clear=evaluated&&eva.missionCannonRayClearR50(pilot);
        boolean release=eva.getCannonCharge()>=com.projectseele.config.SeeleConfig.CANNON_CHARGE_TICKS.get()
                &&boss instanceof com.projectseele.entity.RamielEntity ramiel&&ramiel.isExposed();
        String reason=!data.phase.equals("combat")?"phase":!frame?"target_frame":!equipmentReason.isEmpty()?"equipment"
                :!cannonReason.isEmpty()?"cannon_service":!ready?"cannon_not_ready":release&&!clear?"friendly_ray":"";
        var refusal=reason.isEmpty()?null:new CannonRefusal(reason,data.phase,frame,equipmentReason,cannonReason,ready,
                evaluated?Boolean.toString(clear):"not_evaluated");
        map.put(eva.getUUID(),new CannonDiagnostic(now,data.angel,data.generationR43,refusal));
        if(refusal!=null&&(previous==null||previous.generation()!=data.generationR43
                ||!java.util.Objects.equals(previous.target(),data.angel)||!refusal.equals(previous.refusal())))
            com.projectseele.ProjectSeele.LOGGER.info("NERV TV06 NPC cannon held unit={} target={} generation={} reason={} phase={} targetFrameReady={} equipmentBlocker={} cannonBlocker={} cannonReady={} actualFriendlyShieldRayClear={}",
                    eva.getUUID(),data.angel,data.generationR43,reason,data.phase,frame,equipmentReason,cannonReason,ready,refusal.ray());
    }
    /** Root calls this only from the real Ramiel beam-range consumer. */
    public static double missionAttackRange(net.minecraft.world.entity.LivingEntity boss,double configured)
    {
        if(!(boss.level() instanceof ServerLevel l))return configured;
        var d=TvCampaignSavedData.get(l);
        if(!d.active.equals("ramiel")||!boss.getUUID().equals(d.angel)||!(boss instanceof net.minecraft.world.entity.Mob mob)
                ||!com.projectseele.event.TvEncounterDirectorR45.owned(mob,d)
                ||d.phase.equals("cancel")||d.phase.equals("failure"))return configured;
        var site=TvEncounterSitesR45.site(l,d.active).orElse(null);
        return site==null||!site.geometryValidated()||!site.modelReady()
                ||!site.id().equals(d.encounterSiteR45)||!site.fingerprint().equals(d.encounterLayoutR45)?configured:site.attackRange();
    }
    /** Accepted TV06 target stays at its measured battlefield rather than chasing the shooter. */
    public static Vec3 missionRamielAnchor(net.minecraft.world.entity.Mob boss)
    {
        if(!(boss.level() instanceof ServerLevel l))return null;
        var d=TvCampaignSavedData.get(l);
        if(!d.active.equals("ramiel")||!boss.getUUID().equals(d.angel)
                ||!com.projectseele.event.TvEncounterDirectorR45.owned(boss,d))return null;
        var site=TvEncounterSitesR45.site(l,d.active).orElse(null);
        return site!=null&&site.id().equals(d.encounterSiteR45)&&site.fingerprint().equals(d.encounterLayoutR45)?site.angel():null;
    }
    /** The release consumer rechecks the live mission, including actual first-frame visibility. */
    public static boolean missionBeamAllowed(net.minecraft.world.entity.Mob boss)
    {
        if(!(boss.level() instanceof ServerLevel l))return false;
        var d=TvCampaignSavedData.get(l);
        if(!Set.of("alert","approach","combat").contains(d.phase)||d.targetDeathConfirmedR45
                ||missionRamielAnchor(boss)==null||d.owner==null)return false;
        var owner=l.getServer().getPlayerList().getPlayer(d.owner);
        var site=TvEncounterSitesR45.site(l,d.active).orElse(null);
        var shooter=TvSortiesR32.assignedUnit(l,d,1);
        var exposure=TvYashimaSavedDataR50.get(l);
        // Once exposed, putting the cannon down or leaving its crown does not
        // remove the threat. Actual beam range and world LOS still own reach.
        return owner!=null&&owner.level()==l&&site!=null&&site.geometryValidated()&&site.modelReady()
                &&site.id().equals(d.encounterSiteR45)&&site.fingerprint().equals(d.encounterLayoutR45)
                &&exposure.matches(d)&&exposure.fireControlLocked&&shooter!=null&&shooter.isAlive()
                &&shooter.getUUID().equals(exposure.fireTarget)&&boss.getTarget()==shooter;
    }
    public static boolean cannonPermissionR50(EvaUnit01Entity eva)
    {
        if(!eva.getPersistentData().getBoolean("TvMissionCannonAppliedR45")&&!TvMissionEquipmentR45.cannonAuthorized(eva))return true;
        if(!(eva.level() instanceof ServerLevel l))return false;
        var d=TvCampaignSavedData.get(l);var owner=d.owner==null?null:l.getServer().getPlayerList().getPlayer(d.owner);
        return owner!=null&&owner.level()==l&&d.phase.equals("combat")&&targetFrameReady(l,d,owner)
                &&obstruction(l,d).isEmpty()&&equipmentBlocker(l,d).isEmpty()&&TvYashimaDirectorR50.cannonBlocker(eva).isEmpty();
    }
    /** Real incoming ray consumer: only this original mission defender can intercept. */
    public static java.util.Optional<Vec3> missionShieldContactR45(net.minecraft.world.entity.Mob boss,Vec3 from,Vec3 to)
    {
        if(!(boss.level() instanceof ServerLevel l)||missionRamielAnchor(boss)==null)return java.util.Optional.empty();
        var d=TvCampaignSavedData.get(l);var cover=TvSortiesR32.assignedUnit(l,d,0);
        if(!Set.of("alert","approach","combat").contains(d.phase)||cover==null||!TvMissionEquipmentR45.operational(cover))return java.util.Optional.empty();
        return equipment.shieldBeamContact(cover,from,to);
    }
    /** A tactical hold stops firing while the defender keeps its physical shield posture. */
    public static void pauseFire(ServerLevel l,TvCampaignSavedData d)
    {
        for(var sortie:d.sorties.values())
        {
            var eva=TvSortiesR32.assignedUnit(l,sortie);
            if(eva!=null&&eva.getPilotEntity() instanceof TrainingPilotEntity pilot)
            {equipment.cannonInput(eva,pilot,eva.position(),false,false);eva.stopAutonomousR30();}
        }
    }
    public static void stopEquipment(ServerLevel l,TvCampaignSavedData d)
    {
        for(var sortie:d.sorties.values())
        {
            var eva=TvSortiesR32.assignedUnit(l,sortie);
            if(eva!=null&&eva.getPilotEntity() instanceof TrainingPilotEntity pilot)
            {equipment.cannonInput(eva,pilot,eva.position(),false,false);equipment.shieldInput(eva,pilot,false);eva.stopAutonomousR30();}
        }
    }
    public static void clearSession(ServerLevel l){REMOTE_OBSERVERS.remove(l);SEEN.remove(l);CANNON_DIAGNOSTICS.remove(l);}
    public static void forgetTargetFrameR50(ServerPlayer player,java.util.UUID target)
    {for(var map:SEEN.values()){var seen=map.get(player.getUUID());if(seen!=null&&seen.target().equals(target))map.remove(player.getUUID());}}
    public static void logout(ServerPlayer player)
    {for(var set:REMOTE_OBSERVERS.values())set.remove(player.getUUID());for(var map:SEEN.values())map.remove(player.getUUID());}
    private TvEncounterRulesR45(){}
}
