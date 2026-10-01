package com.projectseele.world;

import com.projectseele.registry.ModBlocks;
import net.minecraft.core.Direction;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.DoorBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.level.block.state.properties.BedPart;
import net.minecraft.world.level.block.state.properties.DoorHingeSide;
import net.minecraft.world.level.block.state.properties.DoubleBlockHalf;

/** Original modular facades for the private TV preview, in the active EVA scale. */
public final class TvTokyo3Architecture
{
    public static final int FLOOR_SPACING = 6;
    private TvTokyo3Architecture() {}

    public static ThirdTokyoSurfaceBuilder.TowerSpec spec(ThirdTokyoSurfaceBuilder.TowerSpec original)
    {
        int x = original.x(), z = original.z();
        int hash = Math.floorMod(x / 40 * 31 + z / 40 * 17, 97);
        int height = original.outerWard() ? 20 + (hash % 4) * 7
                : hash % 11 == 0 ? 96 + (hash % 4) * 8 : 44 + (hash % 6) * 6;
        return new ThirdTokyoSurfaceBuilder.TowerSpec(x, z, height,
                original.outerWard() ? 9 : hash % 11 == 0 ? 10 : 9,
                original.outerWard(), true);
    }

    public static BlockState wall(int y, int span, ThirdTokyoSurfaceBuilder.TowerSpec tower)
    {
        int style = Math.floorMod(tower.x() / 40 * 17 + tower.z() / 40 * 13, 6);
        int edge = Math.abs(span), half = tower.halfSize();
        BlockState pale = (style == 1 || style == 4 ? Blocks.WHITE_CONCRETE : Blocks.LIGHT_GRAY_CONCRETE).defaultBlockState();
        BlockState frame = Blocks.POLISHED_ANDESITE.defaultBlockState();
        BlockState dark = Blocks.DEEPSLATE_TILES.defaultBlockState();
        BlockState glass = Blocks.GRAY_STAINED_GLASS.defaultBlockState();
        if (y <= 4) return edge >= half - 1 && y == 3
                ? Blocks.RED_TERRACOTTA.defaultBlockState() : dark;
        if (edge == half) return frame;
        if (y > tower.height() - 7)
            return edge % 3 == 0 || y == tower.height() - 6 ? frame : dark;
        if (tower.outerWard())
            return edge >= half - 1 || y % 5 == 0 ? pale : y % 5 <= 2 ? glass : frame;
        return switch (style)
        {
            // Paired narrow service slots, broad opaque armour cheeks.
            case 0 -> edge == 2 || edge == 6 ? dark : y % 12 == 0 ? frame : pale;
            // Vertical structural rhythm with small, deeply shaded openings.
            case 1 -> span % 4 == 0 ? frame : y % 7 == 3 || y % 7 == 4 ? glass : pale;
            // Repeated equipment cassettes, with their seams held in shadow.
            case 2 -> y % 14 <= 1 || edge >= half - 1 ? dark
                    : y % 14 == 3 || y % 14 == 11 ? frame : edge % 5 == 0 ? dark : pale;
            // Quiet civilian office bands within the same restrained palette.
            case 3 -> edge % 5 == 0 ? frame : y % 6 <= 1 ? glass : pale;
            // Opaque armoured spine with intermittent horizontal ventilation.
            case 4 -> edge <= 1 ? dark : y % 10 == 2 && edge <= half - 2 ? dark : pale;
            default -> y % 9 <= 1 ? frame : edge == 4 || edge == 5 ? glass
                    : edge >= half - 1 ? dark : pale;
        };
    }

    /** Full original room cell, including the circulation voids between floors. */
    public static BlockState interior(int x, int y, int z, ThirdTokyoSurfaceBuilder.TowerSpec tower)
    {
        int half=tower.halfSize();
        if(Math.abs(x)>=half||Math.abs(z)>=half||y<0||y>tower.height())return null;
        BlockState air=Blocks.AIR.defaultBlockState();
        int lastFloor=(tower.height()-3)/FLOOR_SPACING*FLOOR_SPACING;
        int coreLeft=-half+1, coreRight=-half+9, north=-half+2, south=-half+12;
        boolean core=x>=coreLeft&&x<=coreRight&&z>=north&&z<=south;
        BlockState state=y%FLOOR_SPACING==0&&y<=lastFloor
                ? Blocks.SMOOTH_STONE.defaultBlockState():air;
        // Both landing rows span the two stair lanes and the return passage.
        if(core&&y%FLOOR_SPACING==0&&y>0&&y<=lastFloor
                &&z>north+2&&z<south-1&&x<coreRight)
        {
            boolean incomingNorth=((y/FLOOR_SPACING-1)%2)==0;
            int incomingLane=-half+(incomingNorth?3:7);
            boolean sideBearing=x==coreLeft||x==-half+5;
            boolean unusedTopBay=y==lastFloor&&Math.abs(x-incomingLane)>1;
            boolean closedLip=Math.abs(x-incomingLane)<=1&&z==(incomingNorth?south-2:north+3);
            if(!sideBearing&&!unusedTopBay&&!closedLip)state=air;
        }
        for(int floor=0;floor<lastFloor;floor+=FLOOR_SPACING)
        {
            boolean toNorth=(floor/FLOOR_SPACING)%2==0;
            int laneX=-half+(toNorth?3:7), startZ=toNorth?south-2:north+3;
            Direction facing=toNorth?Direction.NORTH:Direction.SOUTH;
            for(int step=0;step<FLOOR_SPACING;step++)
            {
                int tread=floor+step+1, zz=startZ+(toNorth?-step:step);
                if(Math.abs(x-laneX)>1||z!=zz)continue;
                if(y>=floor&&y<tread)state=Blocks.POLISHED_DEEPSLATE.defaultBlockState();
                else if(y==tread)state=Blocks.POLISHED_DEEPSLATE_STAIRS.defaultBlockState()
                        .setValue(BlockStateProperties.HORIZONTAL_FACING,facing);
                else if(y>tread&&y<=tread+3)state=air;
            }
        }
        if(core)
        {
            int floor=y/FLOOR_SPACING*FLOOR_SPACING,local=y%FLOOR_SPACING;
            if(floor>0&&floor<=lastFloor&&(local==1||local==2))
            {
                boolean incomingNorth=((floor/FLOOR_SPACING-1)%2)==0;
                int incomingLane=-half+(incomingNorth?3:7),closedLip=incomingNorth?south-2:north+3;
                if(Math.abs(x-incomingLane)<=1&&z==closedLip)
                    return Blocks.IRON_BARS.defaultBlockState().setValue(BlockStateProperties.EAST,true).setValue(BlockStateProperties.WEST,true);
            }
            if((x==coreLeft||x==-half+5||x==coreRight)&&z>north+2&&z<south-1
                    &&y%FLOOR_SPACING>=1&&y%FLOOR_SPACING<=2&&y<=lastFloor+2)
                return Blocks.IRON_BARS.defaultBlockState()
                        .setValue(BlockStateProperties.NORTH,true).setValue(BlockStateProperties.SOUTH,true);
            if(x==coreRight&&z==north+1&&y%FLOOR_SPACING==4&&y<lastFloor+5)
                return Blocks.SEA_LANTERN.defaultBlockState();
            return state;
        }
        int floor=y/FLOOR_SPACING*FLOOR_SPACING, local=y%FLOOR_SPACING;
        if(floor>lastFloor)return air;
        if(local==4&&x==half-3&&(z==-half+3||z==half-3))return Blocks.SEA_LANTERN.defaultBlockState();
        // A continuous south-to-north lobby aisle reaches the stair passage.
        if(x<=coreRight+2||Math.abs(z)<=1)return state;
        int family=Math.floorMod(tower.x()/40*17+tower.z()/40*13,6);
        if(floor==0)
        {
            if(local==1&&x>=half-5&&z==half-3)return Blocks.SMOOTH_QUARTZ.defaultBlockState();
            if(local==1&&x==half-2&&z==half-4)return Blocks.BARREL.defaultBlockState();
            if(local==1&&x==half-3&&z==-half+3)return Blocks.CRAFTING_TABLE.defaultBlockState();
            if(local==1&&x==half-2&&z==-half+4)return Blocks.WATER_CAULDRON.defaultBlockState()
                    .setValue(BlockStateProperties.LEVEL_CAULDRON,3);
            if(local==1&&x==half-4&&z==-half+4)return Blocks.DARK_OAK_STAIRS.defaultBlockState()
                    .setValue(BlockStateProperties.HORIZONTAL_FACING,Direction.SOUTH);
            return state;
        }
        if(family==1||family==4)
        {
            if(local==1&&x==half-5&&(z==-half+3||z==-half+4))return Blocks.WHITE_BED.defaultBlockState()
                    .setValue(BlockStateProperties.HORIZONTAL_FACING,Direction.SOUTH)
                    .setValue(BlockStateProperties.BED_PART,z==-half+3?BedPart.FOOT:BedPart.HEAD);
            if(local==1&&x==half-3&&(z==-half+4||z==half-4))return Blocks.CRAFTING_TABLE.defaultBlockState();
            if(local==1&&x==half-2&&(z==-half+4||z==half-4))return Blocks.BARREL.defaultBlockState();
            if(local>=1&&local<=3&&x==half-1&&(z==-half+5||z==half-5))return Blocks.BOOKSHELF.defaultBlockState();
        }
        else
        {
            if(local==1&&x>=half-5&&x<=half-3&&(z==-half+4||z==half-4))return Blocks.SMOOTH_QUARTZ.defaultBlockState();
            if(local==2&&x==half-4&&(z==-half+4||z==half-4))return Blocks.BLACK_STAINED_GLASS.defaultBlockState();
            if(local==1&&x==half-4&&(z==-half+5||z==half-5))return Blocks.DARK_OAK_STAIRS.defaultBlockState()
                    .setValue(BlockStateProperties.HORIZONTAL_FACING,z<0?Direction.NORTH:Direction.SOUTH);
            if(local==1&&x==half-2&&z==-half+3)return Blocks.BARREL.defaultBlockState();
        }
        return state;
    }

    public static BlockState entrance(int x,int y,int z,ThirdTokyoSurfaceBuilder.TowerSpec tower)
    {
        if(z!=tower.halfSize()||x<0||x>1||y<1||y>2)return null;
        return ModBlocks.CITY_PERSONNEL_DOOR.get().defaultBlockState()
                .setValue(DoorBlock.FACING,Direction.SOUTH)
                .setValue(DoorBlock.HALF,y==1?DoubleBlockHalf.LOWER:DoubleBlockHalf.UPPER)
                .setValue(DoorBlock.HINGE,x==0?DoorHingeSide.LEFT:DoorHingeSide.RIGHT);
    }
}
