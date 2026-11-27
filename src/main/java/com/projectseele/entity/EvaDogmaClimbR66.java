package com.projectseele.entity;

import com.projectseele.world.FacilitySchemaV2;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.MoverType;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.phys.Vec3;
import org.joml.Vector3f;

/** Ridden main-shaft wall. The server sweeps the actual chassis; both ends are real landings. */
final class EvaDogmaClimbR66
{
    private record Wall(BlockPos marker,double foot,double top,double face,double minZ,double maxZ)
    {
        double lip() { return face+10; }
    }
    private static final Wall LOWER=new Wall(new BlockPos(146,-1054,242),-1264,-1051,145,240,244);
    private static final Wall UPPER=new Wall(new BlockPos(151,-469,188),-1051,-466,150,185,190);

    private static Wall wall(EvaUnit01Entity eva)
    {
        if (eva.getZ()>=LOWER.minZ && eva.getZ()<=LOWER.maxZ) return LOWER;
        if (eva.getZ()>=UPPER.minZ && eva.getZ()<=UPPER.maxZ) return UPPER;
        return null;
    }

    static void define(SynchedEntityData data) { data.define(EvaUnit01Entity.DOGMA_GRIP_R66, false); }
    static boolean active(EvaUnit01Entity eva) { return eva.getEntityData().get(EvaUnit01Entity.DOGMA_GRIP_R66); }

    private static boolean installed(EvaUnit01Entity eva,Wall wall)
    {
        return wall!=null && eva.level() instanceof net.minecraft.server.level.ServerLevel server
                && com.projectseele.world.DogmaInterlocks.released(server) && eva.level().dimension().equals(FacilitySchemaV2.DIMENSION)
                && eva.level().hasChunkAt(wall.marker)
                && eva.level().getBlockState(wall.marker).is(Blocks.CHISELED_POLISHED_BLACKSTONE);
    }

    static boolean toggle(EvaUnit01Entity eva, ServerPlayer pilot)
    {
        if (eva.getControllingPassenger() != pilot) return false;
        if (active(eva))
        {
            release(eva);
            return true;
        }
        double feet = eva.getY();
        Wall wall=wall(eva);
        if (eva.isPilotControlLocked() || eva.isPilotProne() || eva.isPilotCrouching()
                || !installed(eva,wall) || feet < wall.foot - .5) return false;
        boolean byWall = Math.abs(eva.getBoundingBox().maxX - wall.face) <= 2.5;
        boolean onLip = feet >= wall.top - .1 && feet <= wall.top+3
                && eva.getX() >= wall.face - 9 && eva.getX() <= wall.lip() + 3;
        if ((!byWall || feet>wall.top+.6) && !onLip) return false;
        eva.getEntityData().set(EvaUnit01Entity.DOGMA_GRIP_R66,true);
        eva.dogmaDirectionR66=0;
        eva.setDeltaMovement(Vec3.ZERO);
        eva.resetFallDistance();
        pilot.displayClientMessage(Component.translatable("message.projectseele.dogma_climb.controls",
                Component.keybind("key.forward"),Component.keybind("key.back"),Component.keybind("key.jump")),true);
        return true;
    }

    static boolean hint(EvaUnit01Entity eva)
    {
        Wall wall=wall(eva);
        if (wall==null || active(eva) || eva.getX()<wall.face-12 || eva.getX()>wall.lip()+3
                || eva.getY()<wall.foot-.5 || eva.getY()>wall.top+3
                || !(eva.getControllingPassenger() instanceof ServerPlayer pilot) || !installed(eva,wall)) return false;
        pilot.displayClientMessage(Component.translatable("message.projectseele.dogma_climb.grip",Component.keybind("key.jump")),true);
        return true;
    }

    private static void release(EvaUnit01Entity eva)
    {
        eva.getEntityData().set(EvaUnit01Entity.DOGMA_GRIP_R66,false);
        eva.dogmaDirectionR66=0;
        eva.setDeltaMovement(Vec3.ZERO);
        eva.resetFallDistance();
    }

    static void step(EvaUnit01Entity eva)
    {
        Wall wall=wall(eva);
        if (!(eva.getControllingPassenger() instanceof Player) || eva.isPilotControlLocked()
                || eva.isPilotProne() || eva.isPilotCrouching() || !installed(eva,wall))
        {
            release(eva);
            return;
        }
        eva.setYRot(-90);
        eva.yBodyRot = -90;
        eva.setDeltaMovement(Vec3.ZERO);
        eva.resetFallDistance();
        int forward=eva.level().getGameTime()<=eva.dogmaInputUntilR66?eva.dogmaDirectionR66:0;
        if (forward == 0) return;
        double y = eva.getY();
        // The posed chassis can extend beyond the nominal 17-block width.
        // Leave room for its actual forward extent before moving it vertically.
        double gripX=eva.getX()+wall.face-eva.getBoundingBox().maxX-1.5;
        Vec3 delta;
        if (eva.getX()>gripX+.02 && (y<wall.top-.05 || forward<0))
            delta = new Vec3(Math.max(gripX-eva.getX(),-.95),0,0);
        else if (forward > 0 && y >= wall.top - .05)
            delta = new Vec3(Math.min(wall.lip() - eva.getX(), forward * .95),0,0);
        else
        {
            int handY = Mth.clamp(Mth.floor(y) + 30, (int)wall.foot + 4, (int)wall.top - 2);
            BlockPos contact = new BlockPos((int)wall.face,handY,Mth.floor(eva.getZ()));
            var state = eva.level().getBlockState(contact);
            if (state.getCollisionShape(eva.level(),contact).isEmpty())
            {
                release(eva);
                return;
            }
            delta = new Vec3(0,Mth.clamp(forward*.85,wall.foot-y,wall.top-y),0);
        }
        eva.move(MoverType.SELF,delta);
        eva.setDeltaMovement(Vec3.ZERO);
        eva.resetFallDistance();
        if (forward < 0 && eva.getY() <= wall.foot + .01 || forward > 0 && eva.getX() >= wall.lip() - .01)
        {
            eva.finishCapturedActionEndpointR45();
            release(eva);
        }
    }

    static EvaBodyPose.Sample pose(EvaUnit01Entity eva, EvaBodyPose.Sample base, float partial)
    {
        var pose = EvaBodyPose.copy(base);
        double height = Mth.lerp(partial,eva.yo,eva.getY());
        Wall wall=wall(eva);
        float swing = (float)Math.sin(height*Math.PI/8);
        for (String side : new String[]{"l","r"})
        {
            float phase = side.equals("r") ? swing : -swing;
            bend(pose,"arm_"+side,123+28*phase);
            bend(pose,"forearm_"+side,41-19*phase);
            bend(pose,"leg_"+side,40-21*phase);
            bend(pose,"shin_"+side,-53+20*phase);
            bend(pose,"foot_"+side,17-6*phase);
        }
        bend(pose,"torso_lower",-7);
        EvaBodyPose.preserveJointCentres(pose);
        if (wall!=null)
        {
            double x=Mth.lerp(partial,eva.xo,eva.getX());
            float face=(float)((wall.face-x)/EvaScale.RENDER_SCALE);
            float weight=Mth.clamp(face/.9F,0,1);
            for (String side : new String[]{"l","r"})
            {
                String upper="arm_"+side;
                if (!pose.rig.containsKey(upper)) continue;
                var shoulder=pose.matrix(upper).transformPosition(new Vector3f(pose.rig.get(upper).pivot()));
                double offset=side.equals("l") ? 0 : 8;
                double cycle=(height-wall.foot+offset)/16;
                double index=Math.floor(cycle);
                double t=Mth.clamp((cycle-index-.5)*2,0,1);
                double hold=wall.foot+index*16-offset+56+16*t*t*(3-2*t);
                var wrist=new Vector3f(shoulder.x*1.14F,(float)((hold-height)/EvaScale.RENDER_SCALE),-face+.24F);
                EvaKeyPosesR57.reach(pose,upper,"forearm_"+side,"hand_"+side,wrist,
                        new Vector3f(Math.signum(shoulder.x)*.55F,-.3F,1),weight);
            }
        }
        return pose;
    }

    private static void bend(EvaBodyPose.Sample pose,String bone,float degrees)
    {
        var rotation = pose.rotations.get(bone);
        if (rotation != null) rotation.rotationX(degrees*Mth.DEG_TO_RAD);
    }

    private EvaDogmaClimbR66() {}
}
