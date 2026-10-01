package com.projectseele.world;

import com.projectseele.entity.NervLiftDoorEntity;
import com.projectseele.item.NervAccessCardR44;
import com.projectseele.registry.ModBlockEntities;
import net.minecraft.core.*;
import net.minecraft.nbt.*;
import net.minecraft.network.chat.Component;
import net.minecraft.network.protocol.game.ClientboundBlockEntityDataPacket;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.sounds.*;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.*;
import java.util.UUID;

/** Short swipe, permission decision, obstacle-safe leaf motion and a stored door lease. */
public final class NervAccessReaderEntityR44 extends BlockEntity
{
    private BlockPos gate=BlockPos.ZERO;
    private BlockPos exit=BlockPos.ZERO;
    private int width=3,height=3,clearance=1,style=NervLiftDoorEntity.STYLE_NERV_BLACK,doorId;
    private boolean alongX=true,linked;
    private long openUntil,swipeAt=-1,indicateUntil;
    private int presented,status;
    private UUID user;
    private InteractionHand presentedHand=InteractionHand.MAIN_HAND;
    private String label="NERV 门禁";
    public NervAccessReaderEntityR44(BlockPos pos,BlockState state){super(ModBlockEntities.NERV_ACCESS_READER.get(),pos,state);}
    public int indicator(){return status;}
    public int presentedClearance(){return presented;}
    public float swipeProgress(float partial)
    {return level==null||swipeAt<0?-1:(level.getGameTime()-swipeAt+partial)/12F;}
    public boolean isOpen(){return level!=null&&level.getGameTime()<openUntil;}
    public void present(Player player,InteractionHand hand,int tier)
    {
        if(!linked){player.displayClientMessage(Component.literal("读卡器未连接门体。"),true);return;}
        if(swipeAt>=0&&level.getGameTime()-swipeAt<12)return;
        swipeAt=level.getGameTime();presented=tier;presentedHand=hand;user=player.getUUID();status=1;indicateUntil=swipeAt+32;sync();
    }
    public void requestExit()
    {if(level!=null&&!level.isClientSide){openUntil=level.getGameTime()+120;status=2;indicateUntil=openUntil;sync();}}
    private AABB opening()
    {return new AABB(gate.getX(),gate.getY(),gate.getZ(),gate.getX()+(alongX?width:1),gate.getY()+height,gate.getZ()+(alongX?1:width));}
    private BlockPos cell(int span,int y){return gate.offset(alongX?span:0,y,alongX?0:span);}
    public static void tick(Level raw,BlockPos pos,BlockState state,NervAccessReaderEntityR44 reader)
    {
        if(!(raw instanceof ServerLevel level)||!reader.linked)return;
        long now=level.getGameTime();
        if(!reader.exit.equals(BlockPos.ZERO))
        {
            var button=level.getBlockState(reader.exit);
            if(button.hasProperty(net.minecraft.world.level.block.state.properties.BlockStateProperties.POWERED)
                    &&button.getValue(net.minecraft.world.level.block.state.properties.BlockStateProperties.POWERED))reader.requestExit();
        }
        if(reader.swipeAt>=0&&now-reader.swipeAt==6)
        {
            Player player=reader.user==null?null:level.getPlayerByUUID(reader.user);
            boolean nearby=player!=null&&player.distanceToSqr(Vec3.atCenterOf(pos))<16;
            int heldTier=player!=null&&player.getItemInHand(reader.presentedHand).getItem() instanceof NervAccessCardR44 card?card.clearance():0;
            boolean permit=nearby&&reader.presented>=reader.clearance&&heldTier>=reader.clearance;
            reader.status=permit?2:3;
            if(permit)reader.openUntil=now+120;
            if(player!=null)player.displayClientMessage(Component.literal(permit?reader.label+" · 可以通行":"权限不足，请使用对应通行证。"),true);
            level.playSound(null,pos,permit?SoundEvents.NOTE_BLOCK_PLING.value():SoundEvents.NOTE_BLOCK_BASS.value(),SoundSource.BLOCKS,.35F,permit?1.3F:.75F);
            reader.sync();
        }
        if(reader.swipeAt>=0&&now-reader.swipeAt>=12){reader.swipeAt=-1;reader.sync();}
        if(reader.status!=0&&now>reader.indicateUntil){reader.status=0;reader.sync();}
        boolean open=now<reader.openUntil;
        // Occupancy extends an already clear passage; it cannot grant entry at a closed door.
        boolean passageWasClear=level.getBlockState(reader.gate).isAir();
        if(!open&&passageWasClear&&!level.getEntitiesOfClass(LivingEntity.class,reader.opening().inflate(.15),e->e.isAlive()).isEmpty())
        {reader.openUntil=now+15;open=true;}
        var centre=new Vec3(reader.gate.getX()+(reader.alongX?reader.width*.5:.5),reader.gate.getY(),reader.gate.getZ()+(reader.alongX?.5:reader.width*.5));
        var door=NervLiftDoorEntity.reconcile(level,reader.doorId,reader.alongX,reader.width,reader.height,reader.style,centre);
        if(door!=null)door.setOpen(open);
        boolean clear=open&&door!=null&&door.getOpenProgress(1)>=.72F;
        boolean owned=true;
        for(int i=0;i<reader.width;i++)for(int y=0;y<reader.height;y++)
        {var block=level.getBlockState(reader.cell(i,y));if(!block.isAir()&&!block.is(Blocks.BARRIER))owned=false;}
        if(!owned)return;
        for(int i=0;i<reader.width;i++)for(int y=0;y<reader.height;y++)
        {
            var p=reader.cell(i,y);var wanted=(clear?Blocks.AIR:Blocks.BARRIER).defaultBlockState();
            if(!level.getBlockState(p).equals(wanted))level.setBlock(p,wanted,2);
        }
    }
    private void sync(){setChanged();if(level!=null)level.sendBlockUpdated(worldPosition,getBlockState(),getBlockState(),2);}
    @Override protected void saveAdditional(CompoundTag tag)
    {
        super.saveAdditional(tag);tag.putLong("Gate",gate.asLong());tag.putLong("Exit",exit.asLong());tag.putInt("Width",width);tag.putInt("Height",height);tag.putInt("Clearance",clearance);
        tag.putInt("Style",style);tag.putInt("DoorId",doorId);tag.putBoolean("AlongX",alongX);tag.putBoolean("Linked",linked);tag.putString("Label",label);
        tag.putLong("OpenUntil",openUntil);tag.putLong("SwipeAt",swipeAt);tag.putLong("IndicateUntil",indicateUntil);tag.putInt("Presented",presented);tag.putInt("Status",status);
        tag.putBoolean("OffHand",presentedHand==InteractionHand.OFF_HAND);
        if(user!=null)tag.putUUID("User",user);
    }
    @Override public void load(CompoundTag tag)
    {
        super.load(tag);gate=BlockPos.of(tag.getLong("Gate"));exit=tag.contains("Exit")?BlockPos.of(tag.getLong("Exit")):BlockPos.ZERO;width=Math.max(1,Math.min(7,tag.getInt("Width")));height=Math.max(2,Math.min(9,tag.getInt("Height")));
        clearance=Math.max(1,Math.min(3,tag.getInt("Clearance")));style=tag.getInt("Style");doorId=tag.getInt("DoorId");alongX=tag.getBoolean("AlongX");linked=tag.getBoolean("Linked");label=tag.getString("Label");
        openUntil=tag.getLong("OpenUntil");swipeAt=tag.contains("SwipeAt")?tag.getLong("SwipeAt"):-1;indicateUntil=tag.getLong("IndicateUntil");presented=tag.getInt("Presented");status=tag.getInt("Status");user=tag.hasUUID("User")?tag.getUUID("User"):null;
        presentedHand=tag.getBoolean("OffHand")?InteractionHand.OFF_HAND:InteractionHand.MAIN_HAND;
    }
    @Override public CompoundTag getUpdateTag(){return saveWithoutMetadata();}
    @Override public ClientboundBlockEntityDataPacket getUpdatePacket(){return ClientboundBlockEntityDataPacket.create(this);}
}
