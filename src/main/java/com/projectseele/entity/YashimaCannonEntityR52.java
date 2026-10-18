package com.projectseele.entity;

import com.projectseele.world.TvYashimaStationR52;
import net.minecraft.nbt.*;
import net.minecraft.network.protocol.Packet;
import net.minecraft.network.protocol.game.ClientGamePacketListener;
import net.minecraft.network.syncher.*;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.*;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.network.NetworkHooks;
import org.joml.Quaternionf;

/** The original preloaded cannon's fixed world body. No duplicate equipment or portable muzzle. */
public final class YashimaCannonEntityR52 extends Entity
{
    @Override
    protected boolean updateInWaterStateAndDoFluidPushing()
    {
        // The fixed cradle and its actuators own movement, never water currents.
        this.fluidHeight.clear();
        this.forgeFluidTypeHeight.clear();
        this.wasTouchingWater = false;
        return false;
    }

    private static final EntityDataAccessor<CompoundTag> GEOMETRY=SynchedEntityData.defineId(YashimaCannonEntityR52.class,EntityDataSerializers.COMPOUND_TAG);
    private static final EntityDataAccessor<CompoundTag> CRADLE=SynchedEntityData.defineId(YashimaCannonEntityR52.class,EntityDataSerializers.COMPOUND_TAG);
    private static final EntityDataAccessor<Quaternionf> AIM=SynchedEntityData.defineId(YashimaCannonEntityR52.class,EntityDataSerializers.QUATERNION);
    private static final EntityDataAccessor<Boolean> LOADED=SynchedEntityData.defineId(YashimaCannonEntityR52.class,EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Boolean> READY=SynchedEntityData.defineId(YashimaCannonEntityR52.class,EntityDataSerializers.BOOLEAN);
    private YashimaCannonGeometryR52.Geometry decoded;private CompoundTag decodedTag;private Quaternionf previousAim=new Quaternionf();
    private com.projectseele.world.FixedCannonCradleR52.Spec cradle;private CompoundTag cradleTag;
    public YashimaCannonEntityR52(EntityType<? extends YashimaCannonEntityR52> type,Level level)
    {super(type,level);setNoGravity(true);setInvulnerable(true);}
    @Override protected void defineSynchedData(){entityData.define(GEOMETRY,new CompoundTag());entityData.define(CRADLE,new CompoundTag());entityData.define(AIM,new Quaternionf());entityData.define(LOADED,false);entityData.define(READY,false);}
    public void configureR52(YashimaCannonGeometryR52.Geometry geometry)
    {if(!level().isClientSide){var encoded=YashimaCannonGeometryR52.encode(geometry);if(!encoded.equals(entityData.get(GEOMETRY)))entityData.set(GEOMETRY,encoded);updateBounds();}}
    public void configureCradleR52(com.projectseele.world.FixedCannonCradleR52.Spec spec)
    {if(!level().isClientSide){var tag=spec.encode();if(!tag.equals(entityData.get(CRADLE)))entityData.set(CRADLE,tag);updateBounds();}}
    public com.projectseele.world.FixedCannonCradleR52.Spec cradleR52()
    {var tag=entityData.get(CRADLE);if(tag.isEmpty())return null;if(cradle==null||cradleTag!=tag){cradle=com.projectseele.world.FixedCannonCradleR52.Spec.decode(tag);cradleTag=tag;}return cradle;}
    public YashimaCannonGeometryR52.Geometry geometryR52()
    {
        var tag=entityData.get(GEOMETRY);if(tag.isEmpty())return null;
        if(decoded==null||decodedTag!=tag){decoded=YashimaCannonGeometryR52.decode(tag);decodedTag=tag;}return decoded;
    }
    public Quaternionf aimR52(float partial){return new Quaternionf(previousAim).slerp(entityData.get(AIM),partial);}
    public void loadedR52(boolean value){if(!level().isClientSide)entityData.set(LOADED,value);}
    public boolean loadedR52(){return entityData.get(LOADED);}
    public void readyR52(boolean value){if(!level().isClientSide)entityData.set(READY,value);}
    public boolean readyR52(){return entityData.get(READY);}
    public Vec3 muzzleR52(){var g=geometryR52();return g==null?null:g.point(position(),entityData.get(AIM),g.muzzle());}
    public Vec3 boreR52(){var g=geometryR52();return g==null?null:g.boreWorld(entityData.get(AIM));}
    public Vec3 gripR52(boolean left){return gripR52(left,0);}
    public Vec3 gripR52(boolean left,float partial)
    {var g=geometryR52();return g==null?null:g.point(level().isClientSide?getPosition(partial):position(),level().isClientSide?aimR52(partial):entityData.get(AIM),left?g.left():g.right());}
    private boolean clearHull(Vec3 proposed,Quaternionf aim)
    {
        return level() instanceof ServerLevel server&&com.projectseele.world.YashimaCannonMeshR52.clear(server,this,proposed,aim);
    }
    public boolean liftStepR52(Vec3 destination,double maximumStep)
    {
        if(level().isClientSide||!Double.isFinite(destination.lengthSqr())||maximumStep<=0||maximumStep>.5)return false;
        Vec3 delta=destination.subtract(position());if(delta.length()>maximumStep)delta=delta.normalize().scale(maximumStep);
        if(!clearHull(position().add(delta),entityData.get(AIM)))return false;
        // Commit only the <=.5m actuator step admitted against native block
        // shapes and complete original triangles. Vanilla's global gun AABB
        // would fill the long diagonal barrel's surrounding empty air.
        setDeltaMovement(delta);setPos(position().add(delta));updateBounds();return position().distanceTo(destination)<=.01;
    }
    public boolean aimAtR52(Vec3 target)
    {
        if(!readyR52()||level().isClientSide||target==null||!Double.isFinite(target.lengthSqr()))return false;
        var g=geometryR52();if(g==null)return false;
        var base=g.boreWorld(new Quaternionf());var q=new Quaternionf(entityData.get(AIM));
        for(int i=0;i<8;i++)q.rotationTo(base.toVector3f(),target.subtract(g.point(position(),q,g.muzzle())).normalize().toVector3f());
        if(!Float.isFinite(q.lengthSquared()))return false;
        var before=new Quaternionf(entityData.get(AIM));double angle=2*Math.acos(Math.min(1,Math.abs(before.dot(q))));
        float step=angle<1e-6?1:(float)Math.min(1,Math.toRadians(2)/angle);q=before.slerp(q,step);
        for(int i=1;i<=4;i++)if(!clearHull(position(),new Quaternionf(entityData.get(AIM)).slerp(q,i/4F)))return false;
        entityData.set(AIM,q);updateBounds();return true;
    }
    public boolean resetAimR52()
    {
        if(level().isClientSide)return false;var before=new Quaternionf(entityData.get(AIM));double angle=2*Math.acos(Math.min(1,Math.abs(before.w)));
        float step=angle<1e-6?1:(float)Math.min(1,Math.toRadians(2)/angle);var next=new Quaternionf(before).slerp(new Quaternionf(),step);
        for(int i=1;i<=4;i++)if(!clearHull(position(),new Quaternionf(before).slerp(next,i/4F)))return false;
        entityData.set(AIM,next);updateBounds();return Math.abs(next.w)>1-1e-6;
    }
    private void updateBounds(){var g=geometryR52();if(g!=null){var bounds=g.worldBounds(position(),entityData.get(AIM));var spec=cradleR52();if(spec!=null)bounds=bounds.minmax(com.projectseele.world.FixedCannonCradleR52.bounds(g,spec,position(),entityData.get(AIM)));setBoundingBox(bounds);}}
    @Override public void tick(){previousAim.set(entityData.get(AIM));super.tick();updateBounds();}
    @Override public void onSyncedDataUpdated(EntityDataAccessor<?> key){super.onSyncedDataUpdated(key);if(key==GEOMETRY||key==CRADLE||key==AIM)updateBounds();}
    @Override protected void readAdditionalSaveData(CompoundTag tag)
    {if(tag.contains("GunGeometryR52"))entityData.set(GEOMETRY,tag.getCompound("GunGeometryR52").copy());if(tag.contains("GunCradleR52"))entityData.set(CRADLE,tag.getCompound("GunCradleR52").copy());var a=tag.getList("GunAimR52",Tag.TAG_FLOAT);if(a.size()==4)entityData.set(AIM,new Quaternionf(a.getFloat(0),a.getFloat(1),a.getFloat(2),a.getFloat(3)));entityData.set(LOADED,tag.getBoolean("GunLoadedR52"));entityData.set(READY,tag.getBoolean("GunReadyR52"));updateBounds();}
    @Override protected void addAdditionalSaveData(CompoundTag tag)
    {tag.put("GunGeometryR52",entityData.get(GEOMETRY).copy());tag.put("GunCradleR52",entityData.get(CRADLE).copy());var a=new ListTag();var q=entityData.get(AIM);for(float v:new float[]{q.x,q.y,q.z,q.w})a.add(FloatTag.valueOf(v));tag.put("GunAimR52",a);tag.putBoolean("GunLoadedR52",loadedR52());tag.putBoolean("GunReadyR52",readyR52());}
    @Override public InteractionResult interact(Player player,InteractionHand hand)
    {if(hand!=InteractionHand.MAIN_HAND)return InteractionResult.PASS;if(level().isClientSide)return InteractionResult.SUCCESS;if(player instanceof net.minecraft.server.level.ServerPlayer operator){operator.sendSystemMessage(net.minecraft.network.chat.Component.literal(TvYashimaStationR52.interact(operator,this)));return InteractionResult.CONSUME;}return InteractionResult.PASS;}
    @Override public boolean isPickable(){return loadedR52()&&readyR52();}
    @Override public boolean isPushable(){return false;}
    @Override public boolean canBeCollidedWith(){return geometryR52()!=null&&cradleR52()!=null;}
    @Override public Packet<ClientGamePacketListener> getAddEntityPacket(){return NetworkHooks.getEntitySpawningPacket(this);}
}
