package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaGameplayMotionR32;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.GaghielEntity;
import com.projectseele.event.TvCampaignDirector;
import com.projectseele.event.TvEncounterDirectorR45;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerBossEvent;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.level.TicketType;
import net.minecraft.tags.FluidTags;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.MobSpawnType;
import net.minecraft.world.entity.projectile.Projectile;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.phys.EntityHitResult;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.entity.EntityJoinLevelEvent;
import net.minecraftforge.event.entity.ProjectileImpactEvent;
import net.minecraftforge.event.entity.living.LivingDeathEvent;
import net.minecraftforge.event.entity.player.PlayerInteractEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.lang.reflect.Method;
import java.util.Comparator;
import java.util.UUID;

/** Port relocation exercise: real original artillery, an active aquatic target and recoverable sortie. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class TvMarineDirectorR50
{
    public static final UUID[] ORIGINAL_CANNONS={UUID.fromString("a2f5ffe8-278c-4fd2-8edd-2a4f378fca5f"),UUID.fromString("4e33b3e4-051f-46de-8935-673c7afabe49")};
    private static final Vec3[] CANNON_POS={new Vec3(1420.5,65,350.5),new Vec3(1471.5,65,392.5)};
    private static final TicketType<ChunkPos> TICKET=TicketType.create("tv_marine_r50",Comparator.comparingLong(ChunkPos::toLong),200);
    private static final int CHARGE_TICKS=80,RELOAD_TICKS=200,DOUBLE_WINDOW=120;
    private static final String SHOT="TvMarineCannonR50",GEN="TvMarineShotGenerationR50";
    private static void retain(ServerLevel level,BlockPos pos)
    {var chunk=new ChunkPos(pos);level.getChunkSource().addRegionTicket(TICKET,chunk,2,chunk);}
    private static void retainSite(ServerLevel level,TvMarineSiteR50.Site site)
    {
        retain(level,BlockPos.containing(site.spawn()));retain(level,site.powerBlock());retain(level,site.powerControl());
        for(var pos:CANNON_POS)retain(level,BlockPos.containing(pos));
        for(var pos:site.cannonControls())retain(level,pos);
        for(var pos:site.pylons())retain(level,pos);
        var boss=TvMarineSavedDataR50.get(level).boss;
        Entity actual=boss==null?null:level.getEntity(boss);
        Vec3 end=actual==null?site.spawn():actual.position();
        if(actual!=null)
        {
            retain(level,actual.blockPosition());var box=actual.getBoundingBox();
            for(double x:new double[]{box.minX,box.maxX})for(double z:new double[]{box.minZ,box.maxZ})retain(level,BlockPos.containing(x,end.y,z));
        }
        // Only this local encounter's two physical shot paths are retained.
        for(Vec3 cannon:CANNON_POS)
        {
            int segments=Math.max(1,(int)Math.ceil(cannon.distanceTo(end)/16));
            for(int n=0;n<=segments;n++)retain(level,BlockPos.containing(cannon.lerp(end,n/(double)segments)));
        }
    }
    public static String startBlocker(ServerLevel level)
    {
        var site=TvMarineSiteR50.site(level).orElse(null);
        if(site==null)return "海战的实测水域尚未安装。";
        if(!site.geometryValidated()||!site.modelReady())return "海战水域与目标仍在验收中。";
        if(!BuiltInRegistries.ENTITY_TYPE.containsKey(new ResourceLocation("projectseele:gaghiel")))return "海战目标尚未接入。";
        if(TvMarineSavedDataR50.get(level).cannonCleanupPending)return "原舰炮的上次操纵交接仍待确认，请等待原炮加载。";
        return "";
    }
    public static void begin(ServerLevel level,TvCampaignSavedData campaign)
    {
        if(!campaign.active.equals("gaghiel")||campaign.owner==null)return;
        var site=TvMarineSiteR50.site(level).orElse(null);if(site==null)return;
        var state=TvMarineSavedDataR50.get(level);state.begin(campaign,site);retainSite(level,site);
        spawn(level,campaign,state,site);
    }
    private static void spawn(ServerLevel level,TvCampaignSavedData campaign,TvMarineSavedDataR50 state,TvMarineSiteR50.Site site)
    {
        if(state.boss!=null||campaign.angel!=null)return;
        if(!level.isPositionEntityTicking(BlockPos.containing(site.spawn())))return;
        var type=BuiltInRegistries.ENTITY_TYPE.get(new ResourceLocation("projectseele:gaghiel"));var created=type.create(level);
        if(!(created instanceof GaghielEntity boss))return;
        boss.configureMarineR50(site.center(),site.radiusX(),site.radiusZ(),site.seabed(),site.water(),site.scale());
        boss.moveTo(site.spawn().x,site.spawn().y,site.spawn().z,site.yaw(),0);
        boss.finalizeSpawn(level,level.getCurrentDifficultyAt(boss.blockPosition()),MobSpawnType.EVENT,null,null);
        if(!level.getFluidState(boss.blockPosition()).is(FluidTags.WATER)||!level.noCollision(boss,boss.getBoundingBox()))
        {state.notice="海战出生水体或完整躯干净空不符合实测配置。";state.setDirty();return;}
        boss.addTag(TvEncounterDirectorR45.tag("gaghiel"));boss.getPersistentData().putLong("TvGenerationR45",campaign.generationR43);boss.getPersistentData().putUUID("TvOwnerR45",campaign.owner);
        boss.setNoAi(false);if(!level.addFreshEntity(boss))return;
        campaign.angel=state.boss=boss.getUUID();campaign.lastPosition=boss.blockPosition();campaign.setDirty();state.phase="active";state.setDirty();
    }
    public static void tick(ServerLevel level,TvCampaignSavedData campaign,ServerPlayer commander,ServerBossEvent bar)
    {
        var site=TvMarineSiteR50.site(level).orElse(null);var state=TvMarineSavedDataR50.get(level);
        if(site==null||!site.geometryValidated()||!site.modelReady()){campaign.notice="海战原水域配置待恢复，行动暂停。";freeze(level,campaign);return;}
        if(!state.bound(campaign)){begin(level,campaign);if(!state.bound(campaign))return;}
        if(!state.site.equals(site.id()))
        {freeze(level,campaign);campaign.notice="原海战水域身份已改变，请恢复本次登记水域后继续。";return;}
        if(campaign.phase.equals("combat_victory")||campaign.phase.equals("episode_archived"))
        {state.phase="return";state.powerEnabled=false;restoreOriginalCannons(level,state);state.setDirty();bar.removeAllPlayers();return;}
        retainSite(level,site);spawn(level,campaign,state,site);
        if(commander!=null)bar.addPlayer(commander);
        for(var sortie:campaign.sorties.values()){var p=level.getServer().getPlayerList().getPlayer(sortie.commander);if(p!=null&&p.level()==level)bar.addPlayer(p);}
        var entity=state.boss==null?null:level.getEntity(state.boss);
        if(campaign.phase.equals("failure")||state.phase.equals("failure"))
        {freeze(level,campaign);bar.setName(Component.literal(campaign.notice+" · 机体回收后可重试"));return;}
        if(commander==null||commander.level()!=level)
        {freeze(level,campaign);state.notice=campaign.notice="指挥员离线或离开本战区维度，海战与倒计时暂停。";return;}
        if(campaign.phase.equals("alert")&&TvMissionAlertR30.tick(level,campaign,commander))
        {campaign.phase="approach";campaign.setDirty();}
        if(entity==null)
        {
            if(state.boss==null)
            {state.spawnWait+=10;if(state.spawnWait>=200)fail(level,campaign,state,"海战目标出生水体或净空未通过，未计通关。");}
            else if(level.isPositionEntityTicking(campaign.lastPosition==null?BlockPos.containing(site.spawn()):campaign.lastPosition)&&++state.missingTicks>=20)
                fail(level,campaign,state,"原海战目标通信中断，未生成替身；请确认战区或取消行动。");
            state.setDirty();return;
        }
        if(!(entity instanceof GaghielEntity boss)||!TvEncounterDirectorR45.owned(boss,campaign))
        {fail(level,campaign,state,"原海战目标身份不一致，行动暂停。");return;}
        state.missingTicks=0;boss.setNoAi(false);state.elapsed+=10;
        for(int i=0;i<2;i++)
        {
            if(originalCannon(level,i)==null)
            {
                state.spawnWait+=10;
                if(state.spawnWait>=200)fail(level,campaign,state,"第"+(i+1)+"座原舰炮失联、受损或离开原炮座，行动暂停；不会补造炮台。");
                else campaign.notice="原舰炮通信正在恢复；近海目标已活动。";
                state.setDirty();return;
            }
            if(!takeCannon(level,state,i))
            {fail(level,campaign,state,"原舰炮正在由其他人员操作，或真实接口未确认，海战未接管库存。");return;}
        }
        state.spawnWait=0;
        if(!boss.blockPosition().equals(campaign.lastPosition)){campaign.lastPosition=boss.blockPosition();campaign.setDirty();}
        for(int i=0;i<2;i++)state.cannonCooldown[i]=Math.max(0,state.cannonCooldown[i]-10);
        boolean supply=physicalPowerSwitchR50(level,site,state)&&MilitaryR07Director.state(level).power&&level.hasChunkAt(site.powerBlock())&&level.getBlockState(site.powerBlock()).is(Blocks.IRON_BLOCK);
        state.powerCharge=supply?Math.min(100,state.powerCharge+10):Math.max(0,state.powerCharge-20);
        for(int i=0;i<2;i++)state.cannonCharge[i]=state.powerCharge>=100&&originalCannon(level,i)!=null?Math.min(CHARGE_TICKS,state.cannonCharge[i]+10):Math.max(0,state.cannonCharge[i]-20);
        EvaUnit01Entity lead=TvSortiesR32.assignedUnit(level,campaign,2);
        boolean leadAtSea=lead!=null&&lead.isAlive()&&lead.getPilotEntity()!=null&&!lead.isPowerDepleted()
                &&TvSortiesR32.readyAssigned(level,campaign.sorties.get(2))&&lead.position().distanceTo(site.center())<=180;
        if(leadAtSea)
        {
            boss.setTarget(lead);if(!campaign.phase.equals("combat")){campaign.phase="combat";campaign.setDirty();}
            // Two actual posed hands must occupy the mouth opening while the pilot braces.
            Vec3 left=EvaGameplayMotionR32.hand(lead,"l",1),right=EvaGameplayMotionR32.hand(lead,"r",1);
            double mouthRadius=10*boss.modelScaleR50()+2;
            boolean contact=left.distanceTo(boss.mouthWorldPos(1))<=mouthRadius&&right.distanceTo(boss.mouthWorldPos(1))<=mouthRadius
                    &&lead.getWeapon()==EvaUnit01Entity.WEAPON_FISTS&&lead.isPilotCrouching()&&lead.getDeltaMovement().horizontalDistance()<.55
                    &&lead.isUmbilicalConnected()&&(boss.getAtField()<=0||lead.isAtFieldOn()&&lead.getAtFieldEnergy()>0)&&boss.mouthOpen(1)>.6;
            state.holdTicks=contact?Math.min(200,state.holdTicks+10):0;
            boss.holdMouthR50(state.holdTicks>=20?lead.getUUID():null);
        }
        else
        {
            var crew=level.getEntitiesOfClass(ServerPlayer.class,boss.getBoundingBox().inflate(180),p->!p.isSpectator()&&!p.isCreative()).stream()
                    .min(Comparator.comparingDouble(p->p.distanceToSqr(boss))).orElse(null);
            boss.setTarget(crew);boss.holdMouthR50(null);state.holdTicks=0;
        }
        if(state.elapsed>=site.deadline()){fail(level,campaign,state,"海战拦截时限已过，未及时完成二号机水中牵制与击破；本场可回收后重试。");return;}
        if(lead!=null&&campaign.phase.equals("combat")&&(!lead.isAlive()||com.projectseele.entity.EvaShutdownR30.wreck(lead)))
        {fail(level,campaign,state,"原二号机失去战斗能力，请先回收整备。");return;}
        state.notice="美里：二号机，把它引到舰炮正前方，再撑住嘴。 · 舰桥电源"+(supply?"接通":"断开")+" · 一炮"+cannonStatusR50(state,0)+" / 二炮"+cannonStatusR50(state,1)+" · 拦截余"+Math.max(0,(site.deadline()-state.elapsed)/20)+"秒";
        if(boss.mouthHeldR50())state.notice+=" · 真实口部接触稳定，请在6秒内完成双炮";
        campaign.notice=state.notice;bar.setName(Component.literal(state.notice));bar.setProgress(Math.max(0,Math.min(1,boss.getHealth()/boss.getMaxHealth())));state.setDirty();
    }
    private static void freeze(ServerLevel level,TvCampaignSavedData campaign)
    {if(campaign.angel!=null&&level.getEntity(campaign.angel) instanceof GaghielEntity boss&&TvEncounterDirectorR45.owned(boss,campaign)){boss.setNoAi(true);boss.holdMouthR50(null);}}
    private static void fail(ServerLevel level,TvCampaignSavedData campaign,TvMarineSavedDataR50 state,String notice)
    {
        campaign.phase=state.phase="failure";campaign.notice=state.notice=notice;campaign.setDirty();state.powerEnabled=false;state.setDirty();freeze(level,campaign);
        restoreOriginalCannons(level,state);
        TvMissionEquipmentR45.revokeMission(level);TvEncounterRulesR45.stopEquipment(level,campaign);
        for(var sortie:campaign.sorties.values())if(sortie.unit<3)AutoSortieR32.clearAutomatic(level,sortie.unit);
        PilotReturnR39.enqueue(level,java.util.List.copyOf(campaign.sorties.values()));
    }
    /** Retry retains the original live Boss UUID, health and AT damage. */
    public static void retry(ServerLevel level,TvCampaignSavedData campaign)
    {
        var state=TvMarineSavedDataR50.get(level);var site=TvMarineSiteR50.site(level).orElse(null);
        if(site==null||!state.bound(campaign)||state.boss==null)return;
        retainSite(level,site);
        if(campaign.lastPosition!=null)retain(level,campaign.lastPosition);
        var entity=level.getEntity(state.boss);
        if(entity!=null&&(!(entity instanceof GaghielEntity boss)||!boss.isAlive()||!TvEncounterDirectorR45.owned(boss,campaign)))return;
        state.phase="active";state.elapsed=0;state.cargoHealth=site.cargoHealth();state.powerCharge=state.holdTicks=0;state.powerEnabled=false;state.missingTicks=0;
        for(int i=0;i<2;i++){state.cannonCharge[i]=state.cannonCooldown[i]=state.coreHits[i]=state.shotTagBudget[i]=0;state.cannonFired[i]=-10000;state.cannonOperator[i]=null;}
        for(var sortie:campaign.sorties.values())if(sortie.eva!=null&&level.getEntity(sortie.eva) instanceof EvaUnit01Entity original)
        {
            var data=original.getPersistentData();data.remove("R50MarineArrivalGeneration");data.remove("R50MarineArrivalLayout");data.remove("R50MarineDeliveryNextRequest");data.putInt("MarineWalkIndexR50",0);
        }
        if(entity instanceof GaghielEntity boss){boss.holdMouthR50(null);boss.setNoAi(false);}state.setDirty();
    }
    /** Only an explicit cancellation may remove this mission's owned target. */
    public static void cancel(ServerLevel level,TvCampaignSavedData campaign)
    {
        var state=TvMarineSavedDataR50.get(level);if(!state.bound(campaign))return;
        if(state.boss!=null&&level.getEntity(state.boss) instanceof GaghielEntity boss&&TvEncounterDirectorR45.owned(boss,campaign))
        {boss.discard();campaign.angel=null;campaign.lastPosition=null;campaign.setDirty();}
        state.phase="idle";state.powerEnabled=false;state.setDirty();
        restoreOriginalCannons(level,state);
        TvEncounterRulesR45.stopEquipment(level,campaign);
        for(var sortie:campaign.sorties.values())if(sortie.unit<3)AutoSortieR32.clearAutomatic(level,sortie.unit);
        PilotReturnR39.enqueue(level,java.util.List.copyOf(campaign.sorties.values()));
    }
    public static boolean damageAllowed(ServerLevel level,GaghielEntity boss)
    {
        var campaign=TvCampaignSavedData.get(level);
        if(!boss.getTags().contains(TvEncounterDirectorR45.tag("gaghiel")))return true;
        var state=TvMarineSavedDataR50.get(level);var owner=campaign.owner==null?null:level.getServer().getPlayerList().getPlayer(campaign.owner);
        return state.bound(campaign)&&boss.getUUID().equals(state.boss)&&TvEncounterDirectorR45.owned(boss,campaign)
                &&!campaign.phase.equals("cancel")&&!campaign.phase.equals("failure")&&owner!=null&&owner.level()==level;
    }
    private static String cannonStatusR50(TvMarineSavedDataR50 state,int index)
    {return state.cannonCooldown[index]>0?"装填"+((state.cannonCooldown[index]+19)/20)+"秒":state.cannonCharge[index]<CHARGE_TICKS?"校准"+((CHARGE_TICKS-state.cannonCharge[index]+19)/20)+"秒":"就绪";}
    /** This only relaxes the underwater eligibility; EVA still requires an actual pylon and cable range. */
    public static boolean marinePowerAllowed(EvaUnit01Entity eva)
    {
        if(!(eva.level() instanceof ServerLevel level)||eva.isExperimentalUnit()||eva.getUnitVariant()!=2)return false;
        var campaign=TvCampaignSavedData.get(level);var state=TvMarineSavedDataR50.get(level);var site=TvMarineSiteR50.site(level).orElse(null);
        var sortie=campaign.sorties.get(2);
        return site!=null&&state.bound(campaign)&&state.phase.equals("active")&&physicalPowerSwitchR50(level,site,state)&&state.powerCharge>=100
                &&sortie!=null&&eva.getUUID().equals(sortie.eva)&&eva.getPilotEntity()!=null
                &&eva.position().distanceTo(site.center())<=256&&MilitaryR07Director.state(level).power&&level.getBlockState(site.powerBlock()).is(Blocks.IRON_BLOCK);
    }
    /** Transfer the same unsevered lead between actual commissioned marine reels before it is overextended. */
    public static BlockPos missionPowerAnchor(EvaUnit01Entity eva,BlockPos current,int range)
    {
        if(!(eva.level() instanceof ServerLevel level)||eva.isUmbilicalSevered()||!marinePowerAllowed(eva)||range<=0)return current;
        var site=TvMarineSiteR50.site(level).orElse(null);if(site==null)return current;
        if(current==null)return null; // The ordinary real-pylon connection code owns first attachment.
        double currentDistance=eva.position().distanceTo(Vec3.atCenterOf(current));
        if(!level.hasChunkAt(current)||!(level.getBlockEntity(current) instanceof UmbilicalPylonBlockEntity)||currentDistance>range)return current;
        BlockPos nearest=null;double best=currentDistance;
        for(BlockPos p:site.pylons())
        {
            if(!level.hasChunkAt(p)||!(level.getBlockEntity(p) instanceof UmbilicalPylonBlockEntity))continue;
            double distance=eva.position().distanceTo(Vec3.atCenterOf(p));
            if(distance<best&&distance<=range){best=distance;nearest=p;}
        }
        double margin=Math.max(8,Math.min(20,range*.12));
        return nearest!=null&&currentDistance>=range-margin&&currentDistance-best>=6?nearest:current;
    }
    /** Same original NPC, physical travel and posed hands as the human route; no stand-in EVA is spawned. */
    public static boolean npcTacticR50(ServerLevel level,TvCampaignSavedData campaign,EvaUnit01Entity eva,com.projectseele.entity.TrainingPilotEntity pilot)
    {
        if(!campaign.active.equals("gaghiel")||eva.getUnitVariant()!=2||campaign.angel==null
                ||!(level.getEntity(campaign.angel) instanceof GaghielEntity boss)||!damageAllowed(level,boss))return false;
        var site=TvMarineSiteR50.site(level).orElse(null);if(site==null||eva.position().distanceTo(site.center())>180)return false;
        var sortie=campaign.sorties.get(2);if(sortie==null||!eva.getUUID().equals(sortie.eva)||!pilot.getUUID().equals(sortie.pilotR45))return false;
        Vec3 mouth=boss.mouthWorldPos(1),gunAxis=CANNON_POS[0].add(CANNON_POS[1]).scale(.5).subtract(boss.position()).multiply(1,0,1).normalize();
        Vec3 intercept=boss.position().add(gunAxis.scale(49));
        Vec3 destination=TvMarineWalkR50.approachGoal(level,campaign,eva,intercept);
        if(destination==null)
        {eva.stopAutonomousR30();eva.autonomousMarineBraceR50(pilot,false);campaign.notice="水下接应坡尚未确认，二号机保持接应位置。";return true;}
        Vec3 delta=destination.subtract(eva.position()).multiply(1,0,1);
        Vec3 left=EvaGameplayMotionR32.hand(eva,"l",1),right=EvaGameplayMotionR32.hand(eva,"r",1);
        double hands=Math.max(left.distanceTo(mouth),right.distanceTo(mouth));
        boolean atIntercept=destination==intercept;
        boolean braceZone=atIntercept&&delta.length()<18&&mouth.distanceTo(eva.position().add(0,25,0))<25;
        if(braceZone)
        {
            // Finish the committed strike and clear queues before asking the
            // actual crouch/arm solver to enter support. Guard hands are not
            // themselves a prerequisite for reaching the visible upper jaw.
            eva.settleAutonomousAttackR30(pilot);
            if(eva.hasLiveActionForRender(0))
            {eva.autonomousDriveR30(pilot,Vec3.ZERO,mouth,false);eva.autonomousMarineBraceR50(pilot,false);return true;}
        }
        boolean brace=braceZone&&(boss.mouthHeldR50()||boss.mouthOpen(1)>.45);
        Vec3 movement=brace||delta.length()<6?Vec3.ZERO:delta.normalize().scale(.58);
        eva.autonomousWeaponR30(pilot,EvaUnit01Entity.WEAPON_FISTS);eva.autonomousGuardR30(pilot);
        eva.autonomousDriveR30(pilot,movement,mouth,false);eva.autonomousMarineBraceR50(pilot,brace);
        if(!braceZone&&!brace&&hands<18*boss.modelScaleR50()+4&&eva.tickCount%30==0)eva.autonomousAttackR30(pilot,0);
        return true;
    }
    private static Entity originalCannon(ServerLevel level,int index)
    {
        var cannon=level.getEntity(ORIGINAL_CANNONS[index]);
        if(cannon!=null)
        {
            try {if((Boolean)cannon.getClass().getMethod("isWreck").invoke(cannon)||((Number)cannon.getClass().getMethod("getHealth").invoke(cannon)).floatValue()<=0)return null;}
            catch(ReflectiveOperationException failure){return null;}
        }
        return cannon!=null&&cannon.isAlive()&&cannon.getTags().contains("seele_r07_owned")&&cannon.position().distanceTo(CANNON_POS[index])<4
                &&BuiltInRegistries.ENTITY_TYPE.getKey(cannon.getType()).toString().equals(index==0?"superbwarfare:mk_42":"superbwarfare:hpj_11")?cannon:null;
    }
    private static boolean takeCannon(ServerLevel level,TvMarineSavedDataR50 state,int index)
    {
        Entity cannon=originalCannon(level,index);if(cannon==null||cannon.isVehicle())return false;
        try
        {
            if(state.cannonBefore[index].isEmpty())
            {
                var before=state.cannonBefore[index];before.putUUID("Original",cannon.getUUID());
                for(String name:new String[]{"TurretYRot","TurretXRot","GunYRot","GunXRot","TurretYRotLock"})
                    before.putFloat(name,((Number)cannon.getClass().getMethod("get"+name).invoke(cannon)).floatValue());
                if(index==1)
                {before.putBoolean("Active",(Boolean)cannon.getClass().getMethod("getActive").invoke(cannon));before.putString("Target",(String)cannon.getClass().getMethod("getTargetUUID").invoke(cannon));}
                state.setDirty();
            }
            if(index==1)cannon.getClass().getMethod("setActive",boolean.class).invoke(cannon,false);
            cannon.getPersistentData().putLong("TvMarineCannonGenerationR50",state.generation);return true;
        }
        catch(ReflectiveOperationException failure){ProjectSeele.LOGGER.error("Original marine cannon takeover rejected",failure);return false;}
    }
    public static boolean marineCannonControlledR50(Entity cannon)
    {
        if(!(cannon.level() instanceof ServerLevel level))return false;var state=TvMarineSavedDataR50.get(level);
        return state.phase.equals("active")&&cannon.getPersistentData().getLong("TvMarineCannonGenerationR50")==state.generation&&state.generation>0;
    }
    private static void restoreOriginalCannons(ServerLevel level,TvMarineSavedDataR50 state)
    {
        clearOwnedShots(level,state);
        var site=TvMarineSiteR50.site(level).orElse(null);
        if(site!=null&&site.id().equals(state.site))
        {
            var control=level.getBlockState(site.powerControl());
            if(control.getBlock() instanceof net.minecraft.world.level.block.LeverBlock&&control.hasProperty(net.minecraft.world.level.block.state.properties.BlockStateProperties.POWERED)&&control.getValue(net.minecraft.world.level.block.state.properties.BlockStateProperties.POWERED))
                level.setBlock(site.powerControl(),control.setValue(net.minecraft.world.level.block.state.properties.BlockStateProperties.POWERED,false),3);
        }
        boolean pending=false;
        for(int i=0;i<2;i++)
        {
            var before=state.cannonBefore[i];if(before.isEmpty())continue;
            Entity cannon=level.getEntity(ORIGINAL_CANNONS[i]);
            if(cannon==null){retain(level,BlockPos.containing(CANNON_POS[i]));pending=true;continue;}
            if(!before.hasUUID("Original")||!before.getUUID("Original").equals(cannon.getUUID())){pending=true;continue;}
            try
            {
                for(String name:new String[]{"TurretYRot","TurretXRot","GunYRot","GunXRot","TurretYRotLock"})
                    if(before.contains(name))cannon.getClass().getMethod("set"+name,float.class).invoke(cannon,before.getFloat(name));
                if(before.contains("Active"))
                {cannon.getClass().getMethod("setActive",boolean.class).invoke(cannon,before.getBoolean("Active"));cannon.getClass().getMethod("setTargetUUID",String.class).invoke(cannon,before.getString("Target"));}
                cannon.getPersistentData().remove("TvMarineCannonGenerationR50");state.cannonBefore[i]=new net.minecraft.nbt.CompoundTag();
            }
            catch(ReflectiveOperationException failure){pending=true;ProjectSeele.LOGGER.error("Original marine cannon handover pending",failure);}
        }
        state.cannonCleanupPending=pending;state.setDirty();
    }
    private static boolean physicalPowerSwitchR50(ServerLevel level,TvMarineSiteR50.Site site,TvMarineSavedDataR50 state)
    {
        if(!state.powerEnabled||!level.hasChunkAt(site.powerControl()))return false;
        var control=level.getBlockState(site.powerControl());
        return control.getBlock() instanceof net.minecraft.world.level.block.LeverBlock&&control.hasProperty(net.minecraft.world.level.block.state.properties.BlockStateProperties.POWERED)&&control.getValue(net.minecraft.world.level.block.state.properties.BlockStateProperties.POWERED);
    }
    private static void clearOwnedShots(ServerLevel level,TvMarineSavedDataR50 state)
    {
        var site=TvMarineSiteR50.site(level).orElse(null);if(site==null)return;
        var area=new net.minecraft.world.phys.AABB(CANNON_POS[0],CANNON_POS[1]).minmax(new net.minecraft.world.phys.AABB(site.spawn(),site.spawn())).inflate(160);
        for(Entity entity:level.getEntities((Entity)null,area,e->e instanceof Projectile&&e.getPersistentData().contains(SHOT)&&e.getPersistentData().getLong(GEN)==state.generation))entity.discard();
        for(int i=0;i<2;i++){state.shotTagBudget[i]=0;state.cannonOperator[i]=null;}
    }
    public static String operatePowerR50(ServerPlayer operator)
    {
        var level=operator.serverLevel();var campaign=TvCampaignSavedData.get(level);var state=TvMarineSavedDataR50.get(level);var site=TvMarineSiteR50.site(level).orElse(null);
        if(site==null||!state.bound(campaign)||campaign.phase.equals("failure")||operator.position().distanceTo(Vec3.atCenterOf(site.powerControl()))>6)return "请在本次海战的舰上电源岗位操作。";
        var control=level.getBlockState(site.powerControl());
        if(!(control.getBlock() instanceof net.minecraft.world.level.block.LeverBlock)||!control.hasProperty(net.minecraft.world.level.block.state.properties.BlockStateProperties.POWERED))return "实际舰桥电源开关不在原登记位置，无法接线。";
        state.powerEnabled=!control.getValue(net.minecraft.world.level.block.state.properties.BlockStateProperties.POWERED);
        level.setBlock(site.powerControl(),control.setValue(net.minecraft.world.level.block.state.properties.BlockStateProperties.POWERED,state.powerEnabled),3);
        state.setDirty();return state.powerEnabled?"舰上电源接通，双炮开始校准。":"舰上电源已断开，双炮失去充电。";
    }
    public static String fireOriginalCannonR50(ServerPlayer operator,int index)
    {
        if(index<0||index>1)return "无效舰炮岗位。";
        var level=operator.serverLevel();var campaign=TvCampaignSavedData.get(level);var state=TvMarineSavedDataR50.get(level);var site=TvMarineSiteR50.site(level).orElse(null);
        if(site==null||!state.bound(campaign)||operator.position().distanceTo(Vec3.atCenterOf(site.cannonControls()[index]))>6)return "请到实际舰炮岗位操作。";
        if(!(state.boss!=null&&level.getEntity(state.boss) instanceof GaghielEntity boss)||!damageAllowed(level,boss))return "本次海战目标已暂停或失联。";
        Entity cannon=originalCannon(level,index);if(cannon==null)return "原舰炮尚未加载、已受损或离开炮座，不能用替身发射。";
        if(state.cannonCharge[index]<CHARGE_TICKS||state.cannonCooldown[index]>0)return "舰炮尚未完成供电与装填。";
        Vec3 aim=boss.coreWorldPos(1);
        try
        {
            Object gun=cannon.getClass().getMethod("getGunData",String.class).invoke(cannon,"Main");
            if(gun==null)return "原舰炮武器数据不可用。";
            Entity supplier=(Entity)cannon.getClass().getMethod("getAmmoSupplier").invoke(cannon);
            Method ready=gun.getClass().getMethod("canShoot",Entity.class);
            if(!(Boolean)ready.invoke(gun,supplier))return "原舰炮弹药、能源或原生冷却尚未就绪。";
            Vec3 muzzle=(Vec3)cannon.getClass().getMethod("getShootPos",String.class,float.class).invoke(cannon,"Main",1F);
            double speed=((Number)cannon.getClass().getMethod("getProjectileVelocity",String.class).invoke(cannon,"Main")).doubleValue();
            double gravity=((Number)cannon.getClass().getMethod("getProjectileGravity",String.class).invoke(cannon,"Main")).doubleValue();
            Vec3 ballistic=ballisticDirectionR50(muzzle,aim,speed,gravity);
            if(ballistic==null)return "原舰炮实际弹速与重力无法形成该炮击弹道。";
            cannon.getClass().getMethod("turretAutoAimFromVector",Vec3.class).invoke(cannon,ballistic);
            Vec3 actual=(Vec3)cannon.getClass().getMethod("getShootVec",String.class,float.class).invoke(cannon,"Main",1F);
            if(actual.normalize().dot(ballistic)<.995)return "原炮口仍在转向，请再次确认射击。";
            int steps=Math.min(120,(int)Math.ceil(aim.subtract(muzzle).horizontalDistance()/Math.max(.1,speed*ballistic.horizontalDistance()))+1);
            Vec3 previous=muzzle,velocity=actual.normalize().scale(speed);
            for(int step=0;step<steps;step++)
            {
                Vec3 next=previous.add(velocity);var wall=level.clip(new ClipContext(previous,next,ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,cannon));
                if(wall.getType()!=HitResult.Type.MISS&&wall.getLocation().distanceTo(aim)>5.5*boss.modelScaleR50())return "原炮口的实际弹道被船体、岸线或海床遮挡。";
                previous=next;velocity=velocity.add(0,-gravity,0);
            }
            state.cannonFired[index]=level.getGameTime();state.cannonCharge[index]=0;state.cannonCooldown[index]=RELOAD_TICKS;
            state.cannonOperator[index]=operator.getUUID();state.shotTagBudget[index]=1;state.setDirty();
            cannon.getClass().getMethod("vehicleShoot",LivingEntity.class,String.class,UUID.class,Vec3.class).invoke(cannon,operator,"Main",boss.getUUID(),aim);
            return "第"+(index+1)+"炮已从原炮口发射。保持口部真实接触并完成另一炮。";
        }
        catch(ReflectiveOperationException failure)
        {ProjectSeele.LOGGER.error("Original SBW marine cannon API rejected",failure);return "原舰炮接口不符合安装版本，本次没有替代发射。";}
    }
    private static Vec3 ballisticDirectionR50(Vec3 from,Vec3 target,double speed,double gravity)
    {
        if(!Double.isFinite(speed)||!Double.isFinite(gravity)||speed<=0||gravity<0)return null;
        Vec3 delta=target.subtract(from);double horizontal=delta.horizontalDistance();
        if(gravity<1e-6||horizontal<1e-6)return delta.normalize();
        double squared=speed*speed,discriminant=squared*squared-gravity*(gravity*horizontal*horizontal+2*delta.y*squared);
        if(discriminant<0)return null;
        double angle=Math.atan((squared-Math.sqrt(discriminant))/(gravity*horizontal));
        Vec3 flat=delta.multiply(1,0,1).normalize();return flat.scale(Math.cos(angle)).add(0,Math.sin(angle),0).normalize();
    }
    @SubscribeEvent public static void interact(PlayerInteractEvent.RightClickBlock event)
    {
        if(!(event.getEntity() instanceof ServerPlayer player)||event.getHand()!=InteractionHand.MAIN_HAND)return;
        var site=TvMarineSiteR50.site(player.serverLevel()).orElse(null);if(site==null||!TvMarineSavedDataR50.get(player.serverLevel()).bound(TvCampaignSavedData.get(player.serverLevel())))return;
        String result=null;
        if(event.getPos().equals(site.powerControl()))result=operatePowerR50(player);
        else for(int i=0;i<2;i++)if(event.getPos().equals(site.cannonControls()[i]))result=fireOriginalCannonR50(player,i);
        if(result!=null)
        {
            event.setCanceled(true);event.setCancellationResult(InteractionResult.SUCCESS);
            var block=event.getLevel().getBlockState(event.getPos());
            if(result.contains("已从原炮口发射")&&block.getBlock() instanceof net.minecraft.world.level.block.ButtonBlock)
                block.use(event.getLevel(),player,event.getHand(),event.getHitVec());
            player.sendSystemMessage(Component.literal(result));
        }
    }
    @SubscribeEvent public static void joined(EntityJoinLevelEvent event)
    {
        if(!(event.getLevel() instanceof ServerLevel level)||!(event.getEntity() instanceof Projectile projectile)||event.loadedFromDisk())return;
        var state=TvMarineSavedDataR50.get(level);var campaign=TvCampaignSavedData.get(level);if(!state.bound(campaign)||!state.phase.equals("active"))return;
        if(!BuiltInRegistries.ENTITY_TYPE.getKey(projectile.getType()).getNamespace().equals("superbwarfare"))return;
        for(int i=0;i<2;i++)
        {
            Entity cannon=originalCannon(level,i);if(cannon==null||state.shotTagBudget[i]<=0||level.getGameTime()-state.cannonFired[i]>30)continue;
            Entity shooter=projectile.getOwner();
            if(shooter==null||shooter!=cannon&&!shooter.getUUID().equals(state.cannonOperator[i])||projectile.position().distanceTo(cannon.position())>18)continue;
            projectile.getPersistentData().putInt(SHOT,i);projectile.getPersistentData().putLong(GEN,state.generation);
            state.shotTagBudget[i]--;state.setDirty();
            try
            {
                float before=((Number)projectile.getClass().getMethod("getUnderwaterMotionScale").invoke(projectile)).floatValue();
                projectile.getPersistentData().putFloat("MarineWaterScaleBeforeR50",before);
                projectile.getClass().getMethod("setUnderwaterMotionScale",float.class).invoke(projectile,1F);
            }
            catch(ReflectiveOperationException failure){ProjectSeele.LOGGER.error("Pinned original marine round cannot accept underwater penetration calibration",failure);}
            break;
        }
    }
    @SubscribeEvent public static void impact(ProjectileImpactEvent event)
    {
        Projectile projectile=event.getProjectile();if(!(projectile.level() instanceof ServerLevel level)||!projectile.getPersistentData().contains(SHOT))return;
        var campaign=TvCampaignSavedData.get(level);var state=TvMarineSavedDataR50.get(level);
        if(!state.bound(campaign)||projectile.getPersistentData().getLong(GEN)!=state.generation)return;
        if(!(event.getRayTraceResult() instanceof EntityHitResult hit)||!(hit.getEntity() instanceof GaghielEntity boss)||!boss.getUUID().equals(state.boss))return;
        Vec3 from=projectile.position(),to=from.add(projectile.getDeltaMovement());
        var real=boss.clipBody(from,to,.35);
        if(real.isEmpty()){event.setCanceled(true);return;}
        Vec3 point=real.get();rememberProjectileContactR50(projectile,boss,point);
        originalProjectileDamageR50(level,boss,projectile,level.damageSources().indirectMagic(projectile,projectile.getOwner()));
        event.setCanceled(true);projectile.discard();
    }
    public static boolean isMarineShotR50(Projectile projectile)
    {return projectile.getPersistentData().contains(SHOT)&&projectile.getPersistentData().contains(GEN);}
    public static boolean waterPenetrationAllowedR50(Projectile projectile)
    {
        if(!(projectile.level() instanceof ServerLevel level)||!isMarineShotR50(projectile))return false;
        var state=TvMarineSavedDataR50.get(level);var campaign=TvCampaignSavedData.get(level);int gun=projectile.getPersistentData().getInt(SHOT);
        return gun>=0&&gun<2&&state.bound(campaign)&&state.phase.equals("active")&&projectile.getPersistentData().getLong(GEN)==state.generation;
    }
    public static void rememberProjectileContactR50(Projectile projectile,GaghielEntity boss,Vec3 point)
    {
        var data=projectile.getPersistentData();data.putUUID("MarineHitTargetR50",boss.getUUID());data.putDouble("MarineHitX",point.x);data.putDouble("MarineHitY",point.y);data.putDouble("MarineHitZ",point.z);data.putLong("MarineHitTick",projectile.level().getGameTime());
    }
    public static boolean originalProjectileDamageR50(ServerLevel level,GaghielEntity boss,Projectile projectile,net.minecraft.world.damagesource.DamageSource source)
    {
        var state=TvMarineSavedDataR50.get(level);var data=projectile.getPersistentData();var campaign=TvCampaignSavedData.get(level);
        if(!state.bound(campaign)||!damageAllowed(level,boss)||data.getLong(GEN)!=state.generation||!data.hasUUID("MarineHitTargetR50")||!data.getUUID("MarineHitTargetR50").equals(boss.getUUID())||data.getLong("MarineHitTick")!=level.getGameTime())return false;
        Vec3 point=new Vec3(data.getDouble("MarineHitX"),data.getDouble("MarineHitY"),data.getDouble("MarineHitZ"));
        int index=data.getInt(SHOT);if(index<0||index>1)return false;int other=1-index;
        boolean sync=state.coreHits[other]>0&&Math.abs(state.cannonFired[index]-state.cannonFired[other])<=DOUBLE_WINDOW;
        if(boss.coreContactR50(point)&&boss.mouthHeldR50()&&(state.coreHits[0]+state.coreHits[1]==0||sync))
        {
            state.coreHits[index]++;state.setDirty();
            boss.invulnerableTime=0;return boss.navalCoreHitR50(source,point);
        }
        else
        {state.notice="炮弹命中外壳，口部接触或双炮时序尚未形成。";state.setDirty();return boss.hurtAt(source,40,point);}
    }
    public static void cargoContactR50(ServerLevel level,GaghielEntity boss,Vec3 from,Vec3 to)
    {
        // This port relocation has no moving transport hull in the attack
        // volume. A distant departure point is never treated as a hit vessel.
    }
    @SubscribeEvent public static void death(LivingDeathEvent event)
    {
        if(!(event.getEntity() instanceof GaghielEntity boss)||!(boss.level() instanceof ServerLevel level))return;
        var campaign=TvCampaignSavedData.get(level);var state=TvMarineSavedDataR50.get(level);
        if(!state.bound(campaign)||!boss.getUUID().equals(state.boss)||!TvEncounterDirectorR45.owned(boss,campaign))return;
        boolean valid=damageAllowed(level,boss)&&campaign.phase.equals("combat");
        if(valid)
        {
            state.phase="return";state.powerEnabled=false;restoreOriginalCannons(level,state);state.setDirty();
            TvCampaignDirector.encounterCompleteR45(level,"gaghiel",campaign.owner,boss.getUUID());
            boss.getPersistentData().remove("TvGenerationR45");boss.getPersistentData().remove("TvOwnerR45");boss.removeTag(TvEncounterDirectorR45.tag("gaghiel"));
        }
        else {campaign.targetDeathConfirmedR45=true;fail(level,campaign,state,"原目标已死亡，但本次授权行动未满足完成条件，未计通关。");}
    }
    @SubscribeEvent public static void unloaded(net.minecraftforge.event.level.LevelEvent.Unload event)
    {if(event.getLevel() instanceof ServerLevel level){TvMarineSiteR50.clear(level);TvMarineWalkR50.clear(level);}}
    @SubscribeEvent public static void cleanup(net.minecraftforge.event.TickEvent.ServerTickEvent event)
    {
        if(event.phase!=net.minecraftforge.event.TickEvent.Phase.END||event.getServer().getTickCount()%20!=0)return;
        for(ServerLevel level:event.getServer().getAllLevels())
        {if(!level.dimension().equals(FacilitySchemaV2.DIMENSION))continue;var state=TvMarineSavedDataR50.get(level);if(state.cannonCleanupPending)restoreOriginalCannons(level,state);}
    }
    private TvMarineDirectorR50(){}
}
