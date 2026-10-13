package com.projectseele.entity;

import com.projectseele.world.NervStaffDialogue;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.syncher.*;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.*;
import net.minecraft.world.entity.ai.attributes.*;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.Level;
import net.minecraft.core.BlockPos;

/** Persistent posted personnel. Only an active, nearby operator task runs navigation. */
public final class NervStaffEntity extends PathfinderMob
{
    private static final EntityDataAccessor<String> SKIN=SynchedEntityData.defineId(NervStaffEntity.class,EntityDataSerializers.STRING);
    private static final EntityDataAccessor<Integer> ACTIVITY=SynchedEntityData.defineId(NervStaffEntity.class,EntityDataSerializers.INT);
    private static final EntityDataAccessor<BlockPos> PRESS_TARGET=SynchedEntityData.defineId(NervStaffEntity.class,EntityDataSerializers.BLOCK_POS);
    private static final EntityDataAccessor<Long> PRESS_START=SynchedEntityData.defineId(NervStaffEntity.class,EntityDataSerializers.LONG);
    private String memberId="",role="technician";
    private BlockPos station=BlockPos.ZERO;
    private java.util.UUID requester;
    private String operation="";
    private int variant,taskTicks,pressTicks,returnTicks,pressCount,settleTicks=10;
    private float stationYaw;
    private boolean returning;
    private BlockPos control,approach;
    public NervStaffEntity(EntityType<? extends NervStaffEntity> type,Level level)
    {
        super(type,level);setPersistenceRequired();setInvulnerable(true);
    }
    public static AttributeSupplier.Builder createAttributes()
    {
        return PathfinderMob.createMobAttributes().add(Attributes.MAX_HEALTH,20).add(Attributes.MOVEMENT_SPEED,.25).add(Attributes.FOLLOW_RANGE,16);
    }
    @Override protected void defineSynchedData(){super.defineSynchedData();entityData.define(SKIN,"technician");entityData.define(ACTIVITY,0);entityData.define(PRESS_TARGET,BlockPos.ZERO);entityData.define(PRESS_START,-1L);}
    public void assign(String id,String name,String role,String skin,BlockPos station)
    {
        this.memberId=id;this.role=role;this.station=station;entityData.set(SKIN,skin.matches("[a-z0-9_]{1,40}")?skin:"technician");setCustomName(net.minecraft.network.chat.Component.literal(name));setCustomNameVisible(false);
    }
    public String memberId(){return memberId;}
    public String staffRole(){return role;}
    public String skin(){return entityData.get(SKIN);}
    public int activity(){return entityData.get(ACTIVITY);}
    public int pressCount(){return pressCount;}
    public BlockPos pressTarget(){return entityData.get(PRESS_TARGET);}
    public float pressBlend(float partial)
    {
        long start=entityData.get(PRESS_START);if(start<0||activity()!=2)return 0;
        float age=level().getGameTime()-start+partial;
        float t=age<6?net.minecraft.util.Mth.clamp(age/6,0,1):age<10?1:net.minecraft.util.Mth.clamp((16-age)/6,0,1);
        return t*t*(3-2*t);
    }
    @Override protected net.minecraft.world.entity.ai.navigation.PathNavigation createNavigation(Level level)
    {return new StaffNavigationR26(this,level);}
    public boolean beginPressGesture(BlockPos target)
    {
        if(entityData.get(PRESS_START)<0){entityData.set(PRESS_TARGET,target.immutable());entityData.set(PRESS_START,level().getGameTime());entityData.set(ACTIVITY,2);}
        return level().getGameTime()-entityData.get(PRESS_START)>=6;
    }
    public BlockPos station(){return station;}
    public boolean busy(){return requester!=null;}
    public java.util.UUID requester(){return requester;}
    public void stationYaw(float yaw){stationYaw=yaw;}
    public void begin(java.util.UUID requester,String operation,int variant,BlockPos control,BlockPos approach)
    {
        this.requester=requester;this.operation=operation;this.variant=variant;this.control=control;this.approach=approach;taskTicks=pressTicks=0;returning=false;setNoAi(false);entityData.set(ACTIVITY,1);getNavigation().moveTo(approach.getX()+.5,approach.getY(),approach.getZ()+.5,.9);
    }
    public void finishTask()
    {
        requester=null;operation="";control=approach=null;getNavigation().stop();
        returning=distanceToSqr(net.minecraft.world.phys.Vec3.atBottomCenterOf(station))>1;
        returnTicks=0;setNoAi(true);if(pressTicks==0){entityData.set(ACTIVITY,0);entityData.set(PRESS_START,-1L);}
    }
    @Override public void tick()
    {
        if(level() instanceof net.minecraft.server.level.ServerLevel server&&com.projectseele.world.NervRouteRuntimeR52.claimed(server)
                &&!com.projectseele.world.NervOriginalActorsR52.mappedPersonnel(server))
        {getNavigation().stop();setDeltaMovement(net.minecraft.world.phys.Vec3.ZERO);setNoAi(true);}
        super.tick();if(level().isClientSide)return;
        if(level() instanceof net.minecraft.server.level.ServerLevel server&&com.projectseele.world.NervRouteRuntimeR52.claimed(server))return;
        if(settleTicks>0)
        {
            setNoAi(false);if(--settleTicks==0||onGround()){settleTicks=0;if(requester==null)setNoAi(true);}return;
        }
        if(requester!=null)NervStaffDialogue.tickTask(this,requester,operation,variant,control,approach,++taskTicks);
        else if(pressTicks>0){if(--pressTicks==0){entityData.set(ACTIVITY,0);entityData.set(PRESS_START,-1L);}}
        else if(returning)
        {
            // Never teleport a staff member through a locked door to restore a post.
            if(!level().hasChunkAt(station)||++returnTicks>240||distanceToSqr(net.minecraft.world.phys.Vec3.atBottomCenterOf(station))<.4)
            {returning=false;getNavigation().stop();setNoAi(true);entityData.set(ACTIVITY,0);setYRot(stationYaw);yBodyRot=stationYaw;setYHeadRot(stationYaw);}
            else if(returnTicks%20==1){setNoAi(false);entityData.set(ACTIVITY,1);getNavigation().moveTo(station.getX()+.5,station.getY(),station.getZ()+.5,.8);}
        }
        else if(tickCount%40==getId()%40)
        {
            var player=level().getNearestPlayer(this,7);if(player!=null){double dx=player.getX()-getX(),dz=player.getZ()-getZ();setYHeadRot((float)Math.toDegrees(Math.atan2(-dx,dz)));}
        }
    }
    public void pressing(){pressCount++;pressTicks=10;entityData.set(ACTIVITY,2);if(entityData.get(PRESS_START)<0)entityData.set(PRESS_START,level().getGameTime()-6);}
    @Override protected InteractionResult mobInteract(Player player,InteractionHand hand)
    {
        if(hand!=InteractionHand.MAIN_HAND)return InteractionResult.PASS;
        if(player instanceof net.minecraft.server.level.ServerPlayer server)
        {NervStaffDialogue.greet(server,this);}
        return InteractionResult.sidedSuccess(level().isClientSide);
    }
    @Override public boolean removeWhenFarAway(double distance){return false;}
    @Override public boolean shouldRenderAtSqrDistance(double distance){return distance<72*72&&super.shouldRenderAtSqrDistance(distance);}
    @Override public boolean isPushable(){return busy();}
    @Override public void addAdditionalSaveData(CompoundTag tag)
    {
        super.addAdditionalSaveData(tag);tag.putString("StaffId",memberId);tag.putString("StaffRole",role);tag.putString("StaffSkin",skin());tag.putLong("StaffStation",station.asLong());tag.putFloat("StaffStationYaw",stationYaw);
        // A reload cancels unconfirmed operations; it never repeats a physical press.
        tag.putBoolean("HadPendingStaffTask",busy());tag.putInt("StaffPressCount",pressCount);
    }
    @Override public void readAdditionalSaveData(CompoundTag tag)
    {
        super.readAdditionalSaveData(tag);memberId=tag.getString("StaffId");role=tag.getString("StaffRole");String s=tag.getString("StaffSkin");entityData.set(SKIN,s.matches("[a-z0-9_]{1,40}")?s:"technician");station=BlockPos.of(tag.getLong("StaffStation"));stationYaw=tag.getFloat("StaffStationYaw");pressCount=tag.getInt("StaffPressCount");pressTicks=0;finishTask();
    }
}
