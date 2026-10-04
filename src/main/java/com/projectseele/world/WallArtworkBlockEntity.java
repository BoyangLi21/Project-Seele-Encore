package com.projectseele.world;

import com.projectseele.registry.ModBlockEntities;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.protocol.game.ClientboundBlockEntityDataPacket;
import net.minecraft.util.Mth;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

public final class WallArtworkBlockEntity extends BlockEntity
{
    private String artwork="nerv";
    private float width=1, height=1;
    private Vec3 offset=new Vec3(.5,.5,.5);
    private Direction facing=Direction.SOUTH;
    private BlockPos backing=BlockPos.ZERO;
    public WallArtworkBlockEntity(BlockPos pos, BlockState state) { super(ModBlockEntities.WALL_ARTWORK.get(),pos,state); }
    public String artwork(){return artwork;}
    public float width(){return width;}
    public float height(){return height;}
    public Vec3 offset(){return offset;}
    public Vec3 centre(){return Vec3.atLowerCornerOf(worldPosition).add(offset);}
    public Direction facing(){return facing;}
    public boolean supported(){return level!=null&&level.hasChunkAt(backing)&&!level.getBlockState(backing).isAir();}
    public boolean supportsTile(double horizontal,double vertical)
    {
        if(level==null)return false;
        Vec3 normal=Vec3.atLowerCornerOf(facing.getNormal());
        Vec3 right=new Vec3(normal.z,0,-normal.x);
        BlockPos at=BlockPos.containing(centre().add(right.scale(horizontal)).add(0,vertical,0).subtract(normal.scale(.08)));
        return level.hasChunkAt(at)&&level.getBlockState(at).isFaceSturdy(level,at,facing);
    }
    @Override public void load(CompoundTag tag)
    {
        super.load(tag);artwork=tag.getString("Artwork").equals("tree")?"tree":"nerv";
        width=Mth.clamp(tag.getFloat("Width"),.1F,24);height=Mth.clamp(tag.getFloat("Height"),.1F,24);
        offset=new Vec3(Mth.clamp(tag.getDouble("OffsetX"),0,1),Mth.clamp(tag.getDouble("OffsetY"),0,1),Mth.clamp(tag.getDouble("OffsetZ"),0,1));
        facing=Direction.from2DDataValue(tag.getInt("Facing"));backing=BlockPos.of(tag.getLong("Backing"));
    }
    @Override protected void saveAdditional(CompoundTag tag)
    {
        super.saveAdditional(tag);tag.putString("Artwork",artwork);tag.putFloat("Width",width);tag.putFloat("Height",height);
        tag.putDouble("OffsetX",offset.x);tag.putDouble("OffsetY",offset.y);tag.putDouble("OffsetZ",offset.z);
        tag.putInt("Facing",facing.get2DDataValue());tag.putLong("Backing",backing.asLong());
    }
    @Override public CompoundTag getUpdateTag(){return saveWithoutMetadata();}
    @Override public ClientboundBlockEntityDataPacket getUpdatePacket(){return ClientboundBlockEntityDataPacket.create(this);}
    @Override public AABB getRenderBoundingBox()
    {
        Vec3 c=centre();double x=facing.getAxis()==Direction.Axis.Z?width*.5:.03,z=facing.getAxis()==Direction.Axis.X?width*.5:.03;
        return new AABB(c.x-x,c.y-height*.5,c.z-z,c.x+x,c.y+height*.5,c.z+z);
    }
}
