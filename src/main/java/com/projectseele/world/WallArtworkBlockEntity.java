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
    private Direction surfaceFacing;
    private boolean invalidSurface, tintDeclared;
    private int tint=0xffffffff;
    private BlockPos backing=BlockPos.ZERO;
    public WallArtworkBlockEntity(BlockPos pos, BlockState state) { super(ModBlockEntities.WALL_ARTWORK.get(),pos,state); }
    public String artwork(){return artwork;}
    public float width(){return width;}
    public float height(){return height;}
    public Vec3 offset(){return offset;}
    public Vec3 centre(){return Vec3.atLowerCornerOf(worldPosition).add(offset);}
    public Direction facing(){return facing;}
    public Direction surfaceFacingR52(){return surfaceFacing==null?facing:surfaceFacing;}
    public int tintR52(){return tint;}
    /** Right x up is the outward normal, including horizontal floor/ceiling planes. */
    public record SurfaceBasisR52(Vec3 normal,Vec3 right,Vec3 up){}
    public static SurfaceBasisR52 surfaceBasisR52(Direction surface)
    {
        var normal=Vec3.atLowerCornerOf(surface.getNormal());
        return surface==Direction.UP?new SurfaceBasisR52(normal,new Vec3(1,0,0),new Vec3(0,0,-1))
             :surface==Direction.DOWN?new SurfaceBasisR52(normal,new Vec3(1,0,0),new Vec3(0,0,1))
             :new SurfaceBasisR52(normal,new Vec3(normal.z,0,-normal.x),new Vec3(0,1,0));
    }
    public SurfaceBasisR52 surfaceBasisR52(){return surfaceBasisR52(surfaceFacingR52());}
    public static Vec3 surfacePointR52(Vec3 centre,SurfaceBasisR52 basis,double horizontal,double vertical)
    {return centre.add(basis.right().scale(horizontal)).add(basis.up().scale(vertical));}
    public static BlockPos supportingCellR52(Vec3 centre,SurfaceBasisR52 basis,double horizontal,double vertical)
    {return BlockPos.containing(surfacePointR52(centre,basis,horizontal,vertical).subtract(basis.normal().scale(.08)));}
    public static double nextTileBoundaryR52(double projectedCentre,double start,double limit)
    {return Math.min(limit,Math.floor(projectedCentre+start+1e-6)+1-projectedCentre);}

    public boolean supported(){return !invalidSurface&&level!=null&&level.hasChunkAt(backing)&&!level.getBlockState(backing).isAir();}
    public boolean supportsTile(double horizontal,double vertical)
    {
        if(level==null)return false;
        var basis=surfaceBasisR52();var at=supportingCellR52(centre(),basis,horizontal,vertical);
        return !invalidSurface&&level.hasChunkAt(at)&&level.getBlockState(at).isFaceSturdy(level,at,surfaceFacingR52());
    }
    @Override public void load(CompoundTag tag)
    {
        super.load(tag);var name=tag.getString("Artwork");artwork=name.equals("tree")||name.equals("tree_ink")?name:"nerv";
        surfaceFacing=tag.contains("SurfaceFacing")?Direction.byName(tag.getString("SurfaceFacing")):null;
        invalidSurface=tag.contains("SurfaceFacing")&&surfaceFacing==null;
        tintDeclared=tag.contains("Tint");tint=tintDeclared?tag.getInt("Tint"):0xffffffff;
        // Legacy dimensions remain bounded by24m; explicit six-face authored planes allow64m.
        float maximum=surfaceFacing==null?24:64;
        width=finiteSizeR52(tag.getFloat("Width"),maximum);height=finiteSizeR52(tag.getFloat("Height"),maximum);
        offset=new Vec3(Mth.clamp(tag.getDouble("OffsetX"),0,1),Mth.clamp(tag.getDouble("OffsetY"),0,1),Mth.clamp(tag.getDouble("OffsetZ"),0,1));
        facing=Direction.from2DDataValue(tag.getInt("Facing"));backing=BlockPos.of(tag.getLong("Backing"));
    }
    private static float finiteSizeR52(float size,float maximum)
    {return Float.isFinite(size)?Mth.clamp(size,.1F,maximum):.1F;}
    @Override protected void saveAdditional(CompoundTag tag)
    {
        super.saveAdditional(tag);tag.putString("Artwork",artwork);tag.putFloat("Width",width);tag.putFloat("Height",height);
        tag.putDouble("OffsetX",offset.x);tag.putDouble("OffsetY",offset.y);tag.putDouble("OffsetZ",offset.z);
        tag.putInt("Facing",facing.get2DDataValue());tag.putLong("Backing",backing.asLong());
        if(surfaceFacing!=null)tag.putString("SurfaceFacing",surfaceFacing.getName());
        if(tintDeclared)tag.putInt("Tint",tint);
    }
    @Override public CompoundTag getUpdateTag(){return saveWithoutMetadata();}
    @Override public ClientboundBlockEntityDataPacket getUpdatePacket(){return ClientboundBlockEntityDataPacket.create(this);}
    @Override public AABB getRenderBoundingBox()
    {
        Vec3 c=centre();var basis=surfaceBasisR52();var r=basis.right().scale(width*.5);var u=basis.up().scale(height*.5);var n=basis.normal().scale(.03);
        double x=Math.abs(r.x)+Math.abs(u.x)+Math.abs(n.x),y=Math.abs(r.y)+Math.abs(u.y)+Math.abs(n.y),z=Math.abs(r.z)+Math.abs(u.z)+Math.abs(n.z);
        return new AABB(c.x-x,c.y-y,c.z-z,c.x+x,c.y+y,c.z+z);
    }
}
