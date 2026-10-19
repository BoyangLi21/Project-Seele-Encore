package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.projectseele.entity.NervHangarDoorEntity;
import com.projectseele.registry.ModBlocks;
import net.minecraft.core.BlockPos;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.world.phys.Vec3;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/** Original plate and service-detail finish, without changing door kinematics. */
final class LaunchChamberFinishR53
{
    private static RigidMachineryPartR44 leaf, header;
    private static final Map<UUID, RigidMachineryPartR44> SERVICES = new HashMap<>();

    static boolean applies(NervHangarDoorEntity door)
    {
        return door.level().dimension().location().toString().equals("projectseele:geofront")
                && Math.abs(door.getY() + 1030) < .01
                && Math.abs(door.visualWidth() - 33) < .01
                && Math.abs(door.visualHeight() - 75) < .01
                && (Math.abs(door.getZ() - 106.5) < .01 || Math.abs(door.getZ() - 58.5) < .01);
    }

    static void clear()
    {
        SERVICES.clear();leaf = null;header = null;
    }

    static void moving(PoseStack poses, MultiBufferSource buffers, int light, float open)
    {
        if(leaf == null)
        {
            var builder = new RigidMachineryPartR44.Builder();
            for(int x = 0; x < 2; x++)for(int y = 0; y < 4; y++)
            {
                double left = x * 8.25, bottom = y * 16.25;
                for(double z : new double[]{-.925, .425})
                {
                    box(builder,left+.045,bottom+.055,z,8.16,16.14,.012,0x9ba493);
                    box(builder,left+.09,bottom+.10,z-.002,.045,16.04,.016,0xc2c6b5);
                    for(double bx:new double[]{left+.38,left+7.87})
                        for(double by:new double[]{bottom+.40,bottom+15.85})
                            box(builder,bx,by,z-.006,.12,.12,.024,0x475345);
                    box(builder,left+.65,bottom+1.35,z-.004,1.7,2.1,.022,0x788773);
                    box(builder,left+.72,bottom+1.42,z-.009,1.56,1.96,.030,0x9aa28f);
                }
            }
            leaf = builder.finish();
        }
        for(int side:new int[]{-1,1})
        {
            poses.pushPose();poses.scale(side,1,1);poses.translate(open*17,0,0);
            leaf.draw(poses,buffers,light);poses.popPose();
        }
    }

    static void fixed(NervHangarDoorEntity door, PoseStack poses, MultiBufferSource buffers, int light)
    {
        if(header == null)
        {
            var builder = new RigidMachineryPartR44.Builder();
            // The declared rear gates face +Z into their chamber. Keep the
            // service beam above the 65-unit leaf and below the upper hatch.
            box(builder,-16.5,65.08,1.52,33,1.82,.22,0x566350);
            tube(builder,new Vec3(-16.3,66,2.02),new Vec3(16.3,66,2.02),.32,0x963d30);
            for(int side:new int[]{-1,1})for(double x:new double[]{4,12})
            {
                tube(builder,new Vec3(side*x,65.25,2.22),new Vec3(side*x,66.65,1.7),.16,0x9aa58c);
                box(builder,side*x-.32,65.08,1.52,.64,.25,.82,0x394336);
            }
            header = builder.finish();
        }
        header.draw(poses,buffers,light);
        var services = SERVICES.computeIfAbsent(door.getUUID(), ignored ->
        {
            var builder = new RigidMachineryPartR44.Builder();
            for(int side:new int[]{-1,1})for(int z=4;z<33;z++)
            {
                // Only dress an existing solid wall. Personnel openings remain open.
                var point=door.actualFrameR52().transformPoint(new Vec3(side*17,2,z));
                if(!door.level().getBlockState(BlockPos.containing(point)).is(ModBlocks.NERV_LAUNCH_ARMOR.get()))continue;
                for(int pipe=0;pipe<3;pipe++)
                    tube(builder,new Vec3(side*16.43,1.8+pipe*1.25,z),
                            new Vec3(side*16.43,1.8+pipe*1.25,z+1),.24,
                            pipe==0?0x8c4339:pipe==1?0x455d76:0x56614e);
            }
            return builder.finish();
        });
        services.draw(poses,buffers,light);
    }

    private static void tube(RigidMachineryPartR44.Builder b, Vec3 a, Vec3 end, double radius, int color)
    {
        Vec3 axis=end.subtract(a).normalize();
        Vec3 u=axis.cross(Math.abs(axis.y)<.9?new Vec3(0,1,0):new Vec3(1,0,0)).normalize().scale(radius);
        Vec3 v=axis.cross(u);
        for(int i=0;i<12;i++)
        {
            double p=i*Math.PI/6,q=(i+1)*Math.PI/6;
            Vec3 r=u.scale(Math.cos(p)).add(v.scale(Math.sin(p)));
            Vec3 s=u.scale(Math.cos(q)).add(v.scale(Math.sin(q)));
            b.quad(a.add(r),a.add(s),end.add(s),end.add(r),color);
        }
    }

    private static void box(RigidMachineryPartR44.Builder b,double x,double y,double z,double w,double h,double d,int color)
    {
        Vec3[] p={new Vec3(x,y,z),new Vec3(x+w,y,z),new Vec3(x+w,y+h,z),new Vec3(x,y+h,z),
                new Vec3(x,y,z+d),new Vec3(x+w,y,z+d),new Vec3(x+w,y+h,z+d),new Vec3(x,y+h,z+d)};
        for(int[] f:new int[][]{{0,3,2,1},{4,5,6,7},{0,4,7,3},{1,2,6,5},{0,1,5,4},{3,7,6,2}})
            b.quad(p[f[0]],p[f[1]],p[f[2]],p[f[3]],color);
    }
    private LaunchChamberFinishR53(){}
}
