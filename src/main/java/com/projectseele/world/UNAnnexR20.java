package com.projectseele.world;

import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.EvaBayRepairR33;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.NervHangarDoorEntity;
import com.projectseele.entity.NervCarrierPlatformEntity;
import com.projectseele.entity.EvaPrototypeEntity;
import com.projectseele.registry.ModEntities;
import com.projectseele.registry.ModItems;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.*;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.saveddata.SavedData;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.*;
import net.minecraftforge.event.*;
import net.minecraftforge.event.entity.player.PlayerInteractEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.Files;
import java.util.*;

/** Independent UN-01 wet cell, airframe and capsule; no canonical NERV fleet slot. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class UNAnnexR20
{
    public static final Vec3 HOME=new Vec3(6282.5,77,-6205.5),DOOR=new Vec3(6282.5,77,-6135.5);
    private static final BlockPos[] BUTTONS={new BlockPos(6234,78,-6141),new BlockPos(6238,78,-6141),new BlockPos(6246,78,-6141)};
    private static final TicketType<ChunkPos> TICKET=TicketType.create("seele_un01_annex",Comparator.comparingLong(ChunkPos::toLong),100);
    private static final Map<ServerLevel,UUID> HOISTS=new WeakHashMap<>();
    public static final class State extends SavedData
    {
        public MilitaryR07Director.Phase phase=MilitaryR07Director.Phase.WET;public int cursor,poolWidth=33;public UUID unitId;
        static State load(CompoundTag t){State s=new State();try{s.phase=MilitaryR07Director.Phase.valueOf(t.getString("Phase"));}catch(Exception ignored){}s.cursor=t.getInt("Cursor");s.poolWidth=t.contains("PoolWidth")?t.getInt("PoolWidth"):33;if(t.hasUUID("Unit"))s.unitId=t.getUUID("Unit");return s;}
        @Override public CompoundTag save(CompoundTag t){t.putString("Phase",phase.name());t.putInt("Cursor",cursor);t.putInt("PoolWidth",poolWidth);if(unitId!=null)t.putUUID("Unit",unitId);return t;}
    }
    public static State state(ServerLevel l){return l.getDataStorage().computeIfAbsent(State::load,State::new,"projectseele_un01_annex_r20");}
    public static boolean installed(ServerLevel l){return Files.isRegularFile(l.getServer().getWorldPath(LevelResource.ROOT).resolve("un01_annex_r20.json"));}
    public static boolean modelsInstalled(ServerLevel l){return Files.isRegularFile(l.getServer().getWorldPath(LevelResource.ROOT).resolve("un_models_r21.json"));}
    public static EvaPrototypeEntity airframe(ServerLevel l)
    {UUID id=state(l).unitId;return id!=null&&l.getEntity(id) instanceof EvaPrototypeEntity eva?eva:null;}
    private static void commission(ServerLevel l,State s)
    {
        if(!modelsInstalled(l)||s.unitId!=null)return;
        l.getChunkAt(BlockPos.containing(HOME));
        for(var existing:l.getEntitiesOfClass(EvaPrototypeEntity.class,new AABB(HOME,HOME).inflate(100),u->u.getUNSerial()==1))
        {s.unitId=existing.getUUID();s.setDirty();return;}
        var eva=ModEntities.EVA_PROTOTYPE.get().create(l);if(eva==null)return;
        eva.setUNSerial(1);eva.moveTo(HOME.x,HOME.y,HOME.z,0,0);eva.setYBodyRot(0);eva.setYHeadRot(0);
        eva.setCustomName(Component.literal("EVA-UN-01"));eva.setPersistenceRequired();eva.setNoAi(true);
        eva.setNervLogisticsLocked(true);eva.setNoGravity(true);eva.enterHangarStandby();eva.addTag("seele_r21_un01");
        if(l.addFreshEntity(eva)){s.unitId=eva.getUUID();s.setDirty();ProjectSeele.LOGGER.info("EVA-UN-01 commissioned with independent identity {}",s.unitId);}
    }
    private static boolean card(Player p)
    {
        if(p==null||p.isCreative())return true;
        for(int i=0;i<p.getInventory().getContainerSize();i++){var s=p.getInventory().getItem(i);if(s.is(ModItems.NERV_EMPLOYEE_CARD.get())||s.is(ModItems.TERMINAL_DOGMA_ACCESS_CARD.get()))return true;}return false;
    }
    private static boolean occupied(ServerLevel l){return !l.getEntities((net.minecraft.world.entity.Entity)null,UNHangarDimensionsR31.sweep(l,1),e->e.isAlive()&&!e.isSpectator()&&!(e instanceof NervHangarDoorEntity)&&!(e instanceof NervCarrierPlatformEntity)).isEmpty();}
    public static String request(ServerLevel l,String action,Player p)
    {
        if(!installed(l))return "此存档未安装 UN-01 试验舱";if(!card(p))return "需要工作人员身份卡";State s=state(l);
        var repairId=UNRecoveryR22.identity(l,1);
        if(repairId!=null&&l.getEntity(repairId) instanceof EvaUnit01Entity repairing&&EvaBayRepairR33.active(repairing))return "机体正在检修，请等待机械臂撤回。";
        switch(action)
        {
            case "drain" -> {if(s.phase!=MilitaryR07Director.Phase.WET&&s.phase!=MilitaryR07Director.Phase.FILLING)return "当前无需排液";s.phase=MilitaryR07Director.Phase.DRAINING;s.cursor=0;}
            case "door" ->
            {
                if(s.phase==MilitaryR07Director.Phase.DRY){s.phase=MilitaryR07Director.Phase.OPENING;s.cursor=0;}
                else if(s.phase==MilitaryR07Director.Phase.OPEN){if(occupied(l))return "舱门区域有人员或载具";s.phase=MilitaryR07Director.Phase.CLOSING;}
                else return "请等待排液或舱门动作完成";
            }
            case "fill" -> {if(s.phase!=MilitaryR07Director.Phase.DRY)return "请先关闭舱门";var unit=airframe(l);if(modelsInstalled(l)&&(unit==null||unit.position().distanceTo(HOME)>3||unit.isVehicle()))return "UN-01 须归位并解除驾驶";if(!l.getEntitiesOfClass(Player.class,UNHangarDimensionsR31.pit(l,1),q->!q.isSpectator()).isEmpty())return "请先离开 LCL 试验区";s.phase=MilitaryR07Director.Phase.FILLING;s.cursor=0;}
            default -> {return status(s);}
        }
        s.setDirty();return status(s);
    }
    public static String status(State s)
    {
        String label=switch(s.phase){case WET->"LCL 保管";case DRAINING->"排液中";case DRY->"干燥，舱门关闭";case OPENING->"舱门开启中";case OPEN->"允许进出";case CLOSING->"舱门关闭中";case FILLING->"注液中";};return "EVA-UN-01 试验舱 · "+label;
    }
    private static void tickets(ServerLevel l,boolean enabled)
    {
        for(int x=6224>>4;x<=6340>>4;x++)for(int z=-6288>>4;z<=-6135>>4;z++){var p=new ChunkPos(x,z);if(enabled)l.getChunkSource().addRegionTicket(TICKET,p,2,p);else l.getChunkSource().removeRegionTicket(TICKET,p,2,p);}
    }
    private static void seal(ServerLevel l,boolean closed)
    {
        for(BlockPos p:BlockPos.betweenClosed(UNHangarDimensionsR31.minimum(l,1).getX(),77,-6136,UNHangarDimensionsR31.maximum(l,1).getX(),141,-6136)){var s=l.getBlockState(p);if(s.isAir()||s.is(Blocks.BARRIER))l.setBlock(p,(closed?Blocks.BARRIER:Blocks.AIR).defaultBlockState(),2);}
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent e)
    {
        if(e.phase!=TickEvent.Phase.END)return;var l=e.getServer().getLevel(FacilitySchemaV2.DIMENSION);if(l==null||!installed(l))return;var s=state(l);boolean active=s.phase==MilitaryR07Director.Phase.DRAINING||s.phase==MilitaryR07Director.Phase.FILLING||s.phase==MilitaryR07Director.Phase.OPENING||s.phase==MilitaryR07Director.Phase.CLOSING;
        int width=UNHangarDimensionsR31.width(l),layerSize=UNHangarDimensionsR31.layer(l),total=UNHangarDimensionsR31.total(l);
        if(s.poolWidth!=width){s.poolWidth=width;if(s.phase==MilitaryR07Director.Phase.DRAINING||s.phase==MilitaryR07Director.Phase.FILLING)s.cursor=0;s.setDirty();}
        if(active){tickets(l,true);l.resetEmptyTime();}if(!l.hasChunkAt(BUTTONS[0]))return;
        commission(l,s);
        FacilityAudioR21.auxiliary(l,"UN01",s.phase,DOOR);
        boolean open=s.phase==MilitaryR07Director.Phase.OPEN||s.phase==MilitaryR07Director.Phase.OPENING;NervHangarDoorEntity.reconcile(l,3,DOOR,open);
        if(s.phase==MilitaryR07Director.Phase.DRAINING||s.phase==MilitaryR07Director.Phase.FILLING)
        {
            var liquid=com.projectseele.registry.ModBlocks.LCL_BLOCK.get();
            var minimum=UNHangarDimensionsR31.minimum(l,1);
            for(int i=0;i<512&&s.cursor<total;i++,s.cursor++)
            {
                int layer=s.cursor/layerSize,within=s.cursor%layerSize;var p=new BlockPos(minimum.getX()+within%width,s.phase==MilitaryR07Director.Phase.DRAINING?120-layer:77+layer,minimum.getZ()+within/width);var old=l.getBlockState(p);
                if(s.phase==MilitaryR07Director.Phase.DRAINING&&old.is(liquid))l.setBlock(p,Blocks.AIR.defaultBlockState(),18);
                else if(s.phase==MilitaryR07Director.Phase.FILLING&&old.isAir())l.setBlock(p,liquid.defaultBlockState(),18);
            }
            if(s.cursor==total){s.phase=s.phase==MilitaryR07Director.Phase.DRAINING?MilitaryR07Director.Phase.DRY:MilitaryR07Director.Phase.WET;tickets(l,false);}s.setDirty();
        }
        else if(s.phase==MilitaryR07Director.Phase.OPENING||s.phase==MilitaryR07Director.Phase.CLOSING)
        {
            var doors=l.getEntitiesOfClass(NervHangarDoorEntity.class,new AABB(DOOR,DOOR).inflate(3),d->d.getVariant()==3);
            if(!doors.isEmpty())
            {
                float t=doors.get(0).getOpenProgress(1);
                if(s.phase==MilitaryR07Director.Phase.OPENING&&t>=.99){seal(l,false);s.phase=MilitaryR07Director.Phase.OPEN;tickets(l,false);s.setDirty();}
                else if(s.phase==MilitaryR07Director.Phase.CLOSING){if(occupied(l)){s.phase=MilitaryR07Director.Phase.OPENING;s.setDirty();}else{seal(l,true);if(t<=.001){s.phase=MilitaryR07Director.Phase.DRY;tickets(l,false);s.setDirty();}}}
            }
        }
        var unit=airframe(l);
        if(unit!=null&&!UNAirLiftR29.ownsMotion(l,1))
        {
            UUID old=HOISTS.remove(l);if(old!=null&&l.getEntity(old) instanceof NervCarrierPlatformEntity crane)crane.discard();
            if(s.phase==MilitaryR07Director.Phase.OPEN&&!EvaBayRepairR33.active(unit)){unit.setNervLogisticsLocked(false);unit.setNoGravity(false);}
            else if(unit.position().distanceTo(HOME)<4&&!unit.isVehicle())
            {
                unit.setNervLogisticsLocked(true);unit.setNoGravity(true);
                if(unit.isUmbilicalSevered()||unit.isEntryPlugInserted()||unit.getWeapon()!=com.projectseele.entity.EvaUnit01Entity.WEAPON_FISTS)unit.enterHangarStandby();
            }
        }
        // Before an approved model is installed, retain the empty bay's hoist.
        else if(!modelsInstalled(l)&&l.getGameTime()%20==0)
        {
            NervCarrierPlatformEntity crane=HOISTS.containsKey(l)&&l.getEntity(HOISTS.get(l)) instanceof NervCarrierPlatformEntity c?c:null;
            if(crane==null){crane=ModEntities.NERV_CARRIER_PLATFORM.get().create(l);if(crane!=null){crane.configurePlugCrane(1,-18);crane.moveControlled(6282.5,150,-6217.5);l.addFreshEntity(crane);HOISTS.put(l,crane.getUUID());}}
        }
    }
    @SubscribeEvent public static void interact(PlayerInteractEvent.RightClickBlock e)
    {
        if(!(e.getLevel() instanceof ServerLevel l)||!installed(l))return;
        for(int i=0;i<BUTTONS.length;i++)if(e.getPos().equals(BUTTONS[i])){e.setCanceled(true);e.setCancellationResult(net.minecraft.world.InteractionResult.SUCCESS);if(e.getHand()==net.minecraft.world.InteractionHand.MAIN_HAND)e.getEntity().displayClientMessage(Component.literal(request(l,new String[]{"drain","door","fill"}[i],e.getEntity())),true);return;}
    }
    @SubscribeEvent public static void commands(RegisterCommandsEvent e)
    {
        var branch=net.minecraft.commands.Commands.literal("un01");
        for(String a:new String[]{"status","drain","door","fill"})branch.then(net.minecraft.commands.Commands.literal(a).executes(c->{var l=c.getSource().getServer().getLevel(FacilitySchemaV2.DIMENSION);String text=l==null?"地下维度未加载":request(l,a,c.getSource().getPlayerOrException());c.getSource().sendSuccess(()->Component.literal(text),false);return 1;}));
        if(com.projectseele.visual.DevelopmentCommandsR43.enabled())for(String destination:new String[]{"control","gantry"})branch.then(net.minecraft.commands.Commands.literal("visit").then(net.minecraft.commands.Commands.literal(destination).executes(c->{
            var l=c.getSource().getServer().getLevel(FacilitySchemaV2.DIMENSION);if(l==null||!installed(l))return 0;
            var p=c.getSource().getPlayerOrException();Vec3 at=destination.equals("gantry")?HOME.add(4,50,-12):new Vec3(6242.5,77,-6136.5);
            p.stopRiding();p.teleportTo(l,at.x,at.y,at.z,destination.equals("gantry")?90:180,0);p.fallDistance=0;p.setDeltaMovement(Vec3.ZERO);return 1;
        })));
        e.getDispatcher().register(net.minecraft.commands.Commands.literal("seele").requires(s->s.hasPermission(2)).then(net.minecraft.commands.Commands.literal("military").then(branch)));
    }
    private UNAnnexR20(){}
}
