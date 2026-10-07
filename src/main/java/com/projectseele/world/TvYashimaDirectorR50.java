package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaShutdownR30;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.RamielEntity;
import com.projectseele.event.TvCampaignDirector;
import com.projectseele.event.TvEncounterDirectorR45;
import com.projectseele.registry.ModEntities;
import java.nio.file.Files;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.WeakHashMap;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerBossEvent;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.level.TicketType;
import net.minecraft.world.entity.MobSpawnType;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.ButtonBlock;
import net.minecraft.world.level.block.LeverBlock;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.level.storage.LevelResource;

/** An accepted real target threatens the roof while the original fleet prepares. */
public final class TvYashimaDirectorR50
{
    private static final TicketType<ChunkPos> TICKET=TicketType.create("tv_yashima_r50",Comparator.comparingLong(ChunkPos::toLong),100);
    private record Controls(List<BlockPos> grid,List<BlockPos> pylons,List<BlockPos> supply,Map<Integer,BlockPos> recovery,BlockPos coolant,BlockPos reload,int drillStepTicks) {}
    private static final Map<ServerLevel,Optional<Controls>> CONTROLS=new WeakHashMap<>();
    private static BlockPos pos(com.google.gson.JsonArray row)
    {if(row.size()!=3)throw new IllegalArgumentException("Control position");return new BlockPos(row.get(0).getAsInt(),row.get(1).getAsInt(),row.get(2).getAsInt());}
    private static Controls controls(ServerLevel level)
    {
        return CONTROLS.computeIfAbsent(level,key->{
            var path=key.getServer().getWorldPath(LevelResource.ROOT).resolve("tv_encounter_sites_r45.json");
            try
            {
                var root=JsonParser.parseString(Files.readString(path)).getAsJsonObject();
                var row=root.getAsJsonObject("sites").getAsJsonObject("ramiel").getAsJsonObject("yashima_controls");
                if(row==null||!row.get("installed").getAsBoolean())return Optional.empty();
                var grid=new java.util.ArrayList<BlockPos>();var pylons=new java.util.ArrayList<BlockPos>();var supply=new java.util.ArrayList<BlockPos>();
                for(var p:row.getAsJsonArray("grid_switches"))grid.add(pos(p.getAsJsonArray()));
                for(var p:row.getAsJsonArray("power_pylons"))pylons.add(pos(p.getAsJsonArray()));
                if(row.has("supply_racks"))for(var raw:row.getAsJsonArray("supply_racks"))supply.add(pos(raw.getAsJsonObject().getAsJsonArray("position")));
                var recovery=new java.util.HashMap<Integer,BlockPos>();
                if(row.has("recovery_storage"))for(var raw:row.getAsJsonArray("recovery_storage"))
                {var storage=raw.getAsJsonObject();int unit=storage.get("unit").getAsInt();if(unit<0||unit>1||recovery.putIfAbsent(unit,pos(storage.getAsJsonArray("position")))!=null)throw new IllegalArgumentException("Recovery stock identity");}
                BlockPos coolant=null,reload=null;
                for(var raw:row.getAsJsonArray("console_buttons"))
                {
                    var button=raw.getAsJsonObject();var role=button.get("role").getAsString();
                    if(role.equals("coolant"))coolant=pos(button.getAsJsonArray("pos"));
                    if(role.equals("reload"))reload=pos(button.getAsJsonArray("pos"));
                }
                int step=row.get("drill_step_ticks").getAsInt();
                if(grid.size()!=3||pylons.isEmpty()||coolant==null||reload==null||step<20||step>1200
                        ||grid.stream().distinct().count()!=3||coolant.equals(reload))throw new IllegalArgumentException("Yashima fixture contract");
                return Optional.of(new Controls(List.copyOf(grid),List.copyOf(pylons),List.copyOf(supply),Map.copyOf(recovery),coolant,reload,step));
            }
            catch(Exception failure){ProjectSeele.LOGGER.error("Installed Yashima controls unavailable",failure);return Optional.empty();}
        }).orElse(null);
    }
    private static void retain(ServerLevel level,BlockPos position)
    {var chunk=new ChunkPos(position);level.getChunkSource().addRegionTicket(TICKET,chunk,2,chunk);}
    public static String startBlocker(ServerLevel level)
    {
        var plan=controls(level);
        if(plan==null||!plan.recovery().containsKey(0)||!plan.recovery().containsKey(1))return "屋岛供电、炮务与机库回收库存尚未完成交接。";
        return NervArmorColumnR50.startBlocker(level);
    }
    public static Optional<BlockPos> recoveryStorage(ServerLevel level,int unit)
    {var plan=controls(level);return plan==null?Optional.empty():Optional.ofNullable(plan.recovery().get(unit));}
    private static void supply(ServerLevel level,Controls plan)
    {
        for(var position:plan.supply())
        {
            retain(level,position);level.getChunk(position.getX()>>4,position.getZ()>>4);
            for(var rack:level.getEntitiesOfClass(com.projectseele.entity.NervArmamentStationEntity.class,new net.minecraft.world.phys.AABB(position).inflate(3)))
            {
                var receipt=rack.getPersistentData().getString(TvMissionEquipmentR45.SUPPLY_RECEIPT);
                for(int unit=0;unit<=1;unit++)rack.commissionTvMissionSupplyR50(unit,receipt);
            }
        }
    }

    /** Only the accepted mission creates this one boss; fleet/equipment are never fabricated. */
    public static boolean begin(ServerLevel level,TvCampaignSavedData data)
    {
        var site=TvEncounterSitesR45.site(level,"ramiel").orElse(null);
        if(site==null||data.owner==null||!data.active.equals("ramiel"))return false;
        var plan=controls(level);if(plan!=null)supply(level,plan);
        var targetPosition=data.lastPosition==null?BlockPos.containing(site.angel()):data.lastPosition;
        retain(level,targetPosition);
        var origin=new ChunkPos(targetPosition);
        // Spawn admission needs the full real body footprint immediately, rather
        // than waiting for a distant EVA to load the target's chunk by arrival.
        for(int x=origin.x-1;x<=origin.x+1;x++)for(int z=origin.z-1;z<=origin.z+1;z++)level.getChunk(x,z);
        if(data.angel!=null)
        {
            if(level.getEntity(data.angel) instanceof RamielEntity original&&original.isAlive()&&TvEncounterDirectorR45.owned(original,data))
            {TvYashimaSavedDataR50.get(level).bind(data);return true;}
            return false;
        }
        var boss=ModEntities.RAMIEL.get().create(level);if(boss==null)return false;
        boss.moveTo(site.angel().x,site.angel().y,site.angel().z,site.yaw()+180,0);
        boss.finalizeSpawn(level,level.getCurrentDifficultyAt(boss.blockPosition()),MobSpawnType.EVENT,null,null);
        if(!level.noCollision(boss,boss.getBoundingBox())){data.notice="拉米尔原目标区被占用，作战暂停；未生成替代目标。";data.setDirty();return false;}
        if(!level.getEntitiesOfClass(RamielEntity.class,boss.getBoundingBox().inflate(128),r->r.isAlive()&&r.getTags().contains(TvEncounterDirectorR45.tag("ramiel"))).isEmpty())
        {data.notice="原战区仍有未交接目标，作战暂停。";data.setDirty();return false;}
        boss.setPersistenceRequired();boss.addTag(TvEncounterDirectorR45.tag("ramiel"));
        boss.getPersistentData().putLong("TvGenerationR45",data.generationR43);
        boss.getPersistentData().putUUID("TvOwnerR45",data.owner);
        boss.setNoAi(false);
        if(!level.addFreshEntity(boss))return false;
        data.angel=boss.getUUID();data.lastPosition=boss.blockPosition();data.setDirty();
        TvYashimaSavedDataR50.get(level).bind(data);
        boss.missionDrillR50(true,(float)Math.max(0,boss.getBoundingBox().getCenter().y-NervArmorColumnR50.frontY(level)));
        ProjectSeele.LOGGER.info("R50 Yashima accepted original target={} owner={} generation={}",data.angel,data.owner,data.generationR43);
        return true;
    }
    private static boolean pressed(ServerLevel level,BlockPos p,boolean lever)
    {
        if(!level.hasChunkAt(p))return false;var state=level.getBlockState(p);
        return (lever?state.getBlock() instanceof LeverBlock:state.getBlock() instanceof ButtonBlock)
                &&state.hasProperty(BlockStateProperties.POWERED)&&state.getValue(BlockStateProperties.POWERED);
    }
    private static void services(ServerLevel level,TvCampaignSavedData data,Controls plan)
    {
        var state=TvYashimaSavedDataR50.get(level);if(!state.matches(data))return;
        boolean coolant=pressed(level,plan.coolant(),false),reload=pressed(level,plan.reload(),false);
        if(coolant&&!state.coolantPressed)state.coolantReady=true;
        if(reload&&!state.reloadPressed)state.reloadReady=true;
        if(coolant!=state.coolantPressed||reload!=state.reloadPressed)
        {state.coolantPressed=coolant;state.reloadPressed=reload;state.setDirty();}
    }
    public static String cannonBlocker(EvaUnit01Entity eva)
    {
        if(!(eva.level() instanceof ServerLevel level))return "";
        var data=TvCampaignSavedData.get(level);
        boolean missionGun=eva.getPersistentData().getBoolean("TvMissionCannonAppliedR45")||TvMissionEquipmentR45.cannonAuthorized(eva);
        if(!missionGun)return "";
        if(!data.active.equals("ramiel")||!data.phase.equals("combat")||data.targetDeathConfirmedR45
                ||!TvMissionEquipmentR45.operational(eva))return "原炮击任务尚未允许开火。";
        var plan=controls(level);var state=TvYashimaSavedDataR50.get(level);
        if(plan==null||!state.matches(data))return "炮务设备与原作战绑定正在恢复。";
        if(plan.grid().stream().anyMatch(p->!pressed(level,p,true)))return "全国电网三路汇流尚未全部接通，请开启阵地实际供电开关。";
        if(plan.pylons().stream().anyMatch(p->!level.hasChunkAt(p)||!(level.getBlockEntity(p) instanceof UmbilicalPylonBlockEntity)))
            return "阵地实际供电插座离线，请检修线路。";
        if(!eva.isUmbilicalConnected()||eva.getUmbilicalAnchor()==null||!plan.pylons().contains(eva.getUmbilicalAnchor()))
            return "初号机尚未连接阵地实际外部电源，内置电池不能给屋岛炮充能。";
        services(level,data,plan);
        if(!state.coolantReady)return "炮管仍需冷却，请操作阵地冷却按钮。";
        if(!state.reloadReady)return "熔断器尚未更换，请操作阵地装填按钮。";
        return "";
    }
    /** The regular reel connects to an actual installed local socket on arrival. */
    public static BlockPos missionPowerAnchor(EvaUnit01Entity eva,BlockPos current,int range)
    {
        if(!(eva.level() instanceof ServerLevel level)||!TvMissionEquipmentR45.operational(eva))return current;
        var data=TvCampaignSavedData.get(level);var site=TvEncounterSitesR45.site(level,"ramiel").orElse(null);var plan=controls(level);
        if(site==null||plan==null||!data.active.equals("ramiel")||data.targetDeathConfirmedR45
                ||!java.util.Set.of("approach","combat").contains(data.phase)||eva.isUmbilicalSevered()
                ||eva.position().distanceTo(site.hero())>90)return current;
        return plan.pylons().stream().filter(p->level.hasChunkAt(p)&&level.getBlockEntity(p) instanceof UmbilicalPylonBlockEntity
                &&eva.position().distanceToSqr(net.minecraft.world.phys.Vec3.atCenterOf(p))<=(double)range*range)
                .min(Comparator.comparingDouble(p->eva.position().distanceToSqr(net.minecraft.world.phys.Vec3.atCenterOf(p)))).orElse(current);
    }
    public static void cannonFired(EvaUnit01Entity eva)
    {
        if(!(eva.level() instanceof ServerLevel level))return;
        var data=TvCampaignSavedData.get(level);var state=TvYashimaSavedDataR50.get(level);var plan=controls(level);
        if(!data.active.equals("ramiel")||!state.matches(data)||plan==null)return;
        state.shots++;state.coolantReady=state.reloadReady=false;
        state.coolantPressed=pressed(level,plan.coolant(),false);state.reloadPressed=pressed(level,plan.reload(),false);state.setDirty();
    }
    /** A compressed playable setup stands in for the TV remote concealed emplacement. */
    private static String firstFireLockBlocker(ServerLevel level,TvCampaignSavedData data,TvEncounterSitesR45.Site site,EvaUnit01Entity shooter)
    {
        if(shooter==null||!TvSortiesR32.readyAssigned(level,data.sorties.get(1))||!TvMissionEquipmentR45.operational(shooter))
            return "等待初号机抵达炮位。";
        var equipment=TvEncounterEquipmentControlR45.serverCargoAndCannonR45();
        if(!TvMissionEquipmentR45.cannonAuthorized(shooter)||!equipment.cannonReady(shooter))return "初号机尚未领取阳电子炮。";
        if(data.sorties.get(1).npc?!TvYashimaArrivalR50.npcCannonEmplacementReadyR50(level,data,shooter)
                :shooter.position().distanceTo(site.hero())>12)
            return "射手尚未在炮位停稳，等待到场交接。";
        var cover=TvSortiesR32.assignedUnit(level,data,0);
        if(cover==null||!TvSortiesR32.readyAssigned(level,data.sorties.get(0))||!TvMissionEquipmentR45.operational(cover)
                ||!equipment.shieldEquipped(cover))return "等待零号机携盾就位。";
        var side=TvYashimaArrivalR50.shieldSide(level);
        boolean center=cover.position().subtract(site.cover()).horizontalDistance()<=1.5&&Math.abs(cover.getY()-site.cover().y)<=1.35;
        boolean standby=side!=null&&cover.position().subtract(side).horizontalDistance()<=1.5&&Math.abs(cover.getY()-side.y)<=1.35;
        if((!center&&!standby)||AirCradleClearanceR31.touchdownContact(cover)==null)return "等待零号机进入防护位置。";
        return "";
    }
    /** Gate only this accepted mission's fire intent, never the actors' damage/collision. */
    public static boolean fireAiAllowedR50(net.minecraft.world.entity.Mob boss)
    {
        if(!(boss.level() instanceof ServerLevel level))return true;
        var data=TvCampaignSavedData.get(level);
        return !data.active.equals("ramiel")||!boss.getUUID().equals(data.angel)||!TvEncounterDirectorR45.owned(boss,data)
                ||TvEncounterRulesR45.missionBeamAllowed(boss);
    }
    public static void fail(ServerLevel level,TvCampaignSavedData data,String reason)
    {
        if(data.phase.equals("failure")||data.targetDeathConfirmedR45)return;
        data.phase="failure";data.notice=reason+" 本行动未计通关；原机体、驾驶员与装备按正常流程回收。";data.setDirty();
        TvMissionEquipmentR45.revokeMission(level);TvEncounterRulesR45.stopEquipment(level,data);
        NervArmorColumnR50.pause(level);
        for(var sortie:data.sorties.values())if(sortie.unit<3)AutoSortieR32.clearAutomatic(level,sortie.unit);
        PilotReturnR39.enqueue(level,List.copyOf(data.sorties.values()));
        if(data.angel!=null&&level.getEntity(data.angel) instanceof RamielEntity boss&&TvEncounterDirectorR45.owned(boss,data))
        {boss.setNoAi(true);boss.setTarget(null);boss.missionDrillR50(false,0);}
        ProjectSeele.LOGGER.info("R50 Yashima failed original={} reason={}",data.angel,reason);
    }
    public static void tick(ServerLevel level,TvCampaignSavedData data,ServerPlayer owner,ServerBossEvent bar)
    {
        var site=TvEncounterSitesR45.site(level,"ramiel").orElse(null);var plan=controls(level);
        if(site==null||plan==null)
        {
            if(data.angel!=null&&level.getEntity(data.angel) instanceof RamielEntity original&&TvEncounterDirectorR45.owned(original,data))
            {original.setNoAi(true);original.setTarget(null);original.missionDrillR50(false,0);}
            NervArmorColumnR50.pause(level);TvEncounterRulesR45.pauseFire(level,data);
            data.notice="原屋岛阵地或炮务配置暂不可用，原目标与钻进暂停。";bar.setName(Component.literal(data.notice));return;
        }
        if(data.phase.equals("failure")||data.targetDeathConfirmedR45)
        {bar.setName(Component.literal(data.notice));TvEncounterRulesR45.stopEquipment(level,data);return;}
        if(data.angel==null)begin(level,data);
        if(data.angel==null){bar.setName(Component.literal(data.notice));return;}
        retain(level,data.lastPosition==null?BlockPos.containing(site.angel()):data.lastPosition);
        if(!(level.getEntity(data.angel) instanceof RamielEntity boss)||!TvEncounterDirectorR45.owned(boss,data))
        {if(level.isPositionEntityTicking(data.lastPosition==null?BlockPos.containing(site.angel()):data.lastPosition)
                &&++data.missingTicksR45>=40)fail(level,data,"原拉米尔信号中断，请确认原目标状态。");return;}
        data.missingTicksR45=0;
        boolean valid=site.geometryValidated()&&site.modelReady()&&site.id().equals(data.encounterSiteR45)&&site.fingerprint().equals(data.encounterLayoutR45);
        if(owner==null||owner.level()!=level||!valid)
        {
            boss.setNoAi(true);boss.setTarget(null);boss.missionDrillR50(false,0);TvEncounterRulesR45.pauseFire(level,data);
            NervArmorColumnR50.pause(level);
            data.notice=!valid?"原阵地配置已变化，目标与钻进暂停。":"司令离线或离开本维度，原目标与钻进暂停。";
            bar.setName(Component.literal(data.notice));return;
        }
        bar.addPlayer(owner);
        for(var sortie:data.sorties.values())
        {var p=level.getServer().getPlayerList().getPlayer(sortie.commander);if(p!=null&&p.level()==level)bar.addPlayer(p);}
        for(var p:plan.grid())retain(level,p);for(var p:plan.pylons())retain(level,p);for(var p:plan.supply())retain(level,p);retain(level,plan.coolant());retain(level,plan.reload());
        // Chunk blocks can be present before their original rack entity attaches.
        // Retry the same one-time receipt after loading; the cargo ledger refuses
        // a second commission even after the original stock has been issued.
        if(TvYashimaSavedDataR50.get(level).onlineTicks%20==0)supply(level,plan);
        int segments=Math.max(1,(int)Math.ceil(site.separation()/16));
        for(int n=0;n<=segments;n++)retain(level,BlockPos.containing(site.hero().lerp(site.angel(),n/(double)segments)));
        services(level,data,plan);
        var service=TvYashimaSavedDataR50.get(level);service.onlineTicks+=10;service.setDirty();
        NervArmorColumnR50.tickRamiel(level,data,boss,plan.drillStepTicks());
        if(NervArmorColumnR50.breachTerminal(level)){fail(level,data,"拉米尔已突破本场登记防护终点。");return;}
        boss.missionDrillR50(true,(float)Math.max(0,boss.getBoundingBox().getCenter().y-NervArmorColumnR50.frontY(level)));
        var shooter=TvSortiesR32.assignedUnit(level,data,1);
        if(shooter!=null&&EvaShutdownR30.wreck(shooter)){fail(level,data,"原初号机已失去炮击能力。");return;}
        String setup=service.fireControlLocked?"":firstFireLockBlocker(level,data,site,shooter);
        if(!service.fireControlLocked&&setup.isEmpty())
        {
            service.fireControlLocked=true;service.fireTarget=shooter.getUUID();service.setDirty();
            ProjectSeele.LOGGER.info("R50 Yashima original cannon emplacement exposed: boss={} shooter={} owner={} generation={}",data.angel,service.fireTarget,data.owner,data.generationR43);
        }
        boss.setNoAi(false);
        boss.setTarget(service.fireControlLocked&&shooter!=null&&shooter.isAlive()&&shooter.getUUID().equals(service.fireTarget)?shooter:null);
        if(!boss.blockPosition().equals(data.lastPosition)){data.lastPosition=boss.blockPosition();data.setDirty();}
        if(data.phase.equals("alert")&&TvMissionAlertR30.tick(level,data,owner)){data.phase="approach";data.setDirty();}
        if(data.phase.equals("approach")&&boss.getTarget()==shooter&&shooter!=null
                &&TvMissionEquipmentR45.cannonAuthorized(shooter)&&TvEncounterEquipmentControlR45.serverCargoAndCannonR45().cannonReady(shooter)
                &&shooter.position().distanceTo(site.hero())<=12&&TvEncounterRulesR45.targetFrameReady(level,data,owner))
        {data.phase="combat";data.setDirty();}
        String blocked=data.phase.equals("alert")?"识别与编成确认中；原拉米尔正在钻进。":TvEncounterRulesR45.equipmentBlocker(level,data);
        if(!service.fireControlLocked&&!setup.isEmpty())blocked=setup;
        if(blocked.isEmpty()&&shooter!=null)blocked=cannonBlocker(shooter);
        String breach=NervArmorColumnR50.geofrontBreached(level)?"GeoFront入口已贯穿；总部与终端尚未失守 · ":"";
        data.notice="屋岛作战 · "+breach+"装甲贯穿 "+NervArmorColumnR50.penetratedLayers(level)+" 层 · "+(blocked.isEmpty()?"炮位就绪，确认核心后炮击。":blocked);
        bar.setName(Component.literal(data.notice));bar.setProgress(Math.max(0,Math.min(1,boss.getHealth()/boss.getMaxHealth())));
    }
    public static void clearSession(ServerLevel level){CONTROLS.remove(level);TvYashimaArrivalR50.clear(level);}
    private TvYashimaDirectorR50(){}
}
