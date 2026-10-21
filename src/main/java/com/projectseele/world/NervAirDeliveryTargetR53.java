package com.projectseele.world;

import com.projectseele.world.NervAirTransportManifestR52.*;
import java.util.*;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.*;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.phys.*;

/** A requested X/Z destination retains its measured native landing surface. */
final class NervAirDeliveryTargetR53
{
    static boolean selected(Mission m){return m.id().startsWith("r53/surface-delivery/")||m.id().startsWith("r53/coordinate/");}

    static boolean prepare(ServerLevel level,NervFlightProofR52.FlightPickupPreview pickup,Receiver template,int x,int z,CompoundTag data)
    {
        if(data.contains("DeliveryTargetR53"))return true;
        level.getChunk(x>>4,z>>4);
        var geometry=pickup.geometry();
        if(pickup.kind()==TransportMembershipR52.Kind.OCCUPIED
                &&level.getEntity(pickup.original().eva()) instanceof com.projectseele.entity.EvaUnit01Entity eva)
        {
            var provider=EvaOriginalMeshGeometryR52.readOnlySelectedProviderR52();
            geometry=provider.evaluate(eva.getUnitVariant(),com.projectseele.entity.EvaBodyPose.neutralForTransportR32(eva),
                    com.projectseele.entity.EvaAnatomicalHandsR45.ordinaryReleaseTargetR52(eva.getUnitVariant(),false));
        }
        var origin=RigidTransform.of(Vec3.ZERO,template.stopped().rotation());
        double low=Double.POSITIVE_INFINITY,minX=low,minZ=low,maxX=-low,maxZ=-low;
        for(var part:geometry.parts())if(part.bone().equals("foot_l")||part.bone().equals("foot_r"))for(var v:part.vertices())
        {var p=origin.transformPoint(v);low=Math.min(low,p.y);minX=Math.min(minX,p.x);maxX=Math.max(maxX,p.x);minZ=Math.min(minZ,p.z);maxZ=Math.max(maxZ,p.z);}
        if(!Double.isFinite(low)||maxX-minX>32||maxZ-minZ>32)return false;
        double footY=level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES,x,z);
        if(data.contains("DeliveryYR53"))
        {
            int requested=data.getInt("DeliveryYR53");boolean found=false;
            for(int distance=0;distance<=16&&!found;distance++)for(int sign:new int[]{-1,1})
            {
                int y=requested+distance*sign-1;
                var pos=new BlockPos(x,y,z);var shape=level.getBlockState(pos).getCollisionShape(level,pos);
                if(!shape.isEmpty()&&level.getBlockState(pos.above()).getCollisionShape(level,pos.above()).isEmpty())
                {footY=y+shape.max(net.minecraft.core.Direction.Axis.Y);found=true;break;}
            }
            if(!found)return false;
        }
        var root=RigidTransform.of(new Vec3(x+.5,footY-low,z+.5),origin.rotation());
        int floor=(int)Math.floor(root.translation().y+low-1e-5);
        var supports=new ArrayList<AABB>();var cells=new ListTag();
        for(int bx=(int)Math.floor(x+.5+minX);bx<=(int)Math.floor(x+.5+maxX);bx++)for(int bz=(int)Math.floor(z+.5+minZ);bz<=(int)Math.floor(z+.5+maxZ);bz++)
        {
            level.getChunk(bx>>4,bz>>4);
            var pos=new BlockPos(bx,floor,bz);var state=level.getBlockState(pos);
            var shapes=state.getCollisionShape(level,pos).toAabbs();if(shapes.isEmpty())continue;
            for(var shape:shapes)supports.add(shape.move(pos));
            var cell=new CompoundTag();cell.putLong("Pos",pos.asLong());cell.putString("State",net.minecraft.commands.arguments.blocks.BlockStateParser.serialize(state));cells.add(cell);
        }
        if(!NervFlightProofR52.finiteDeliverySolesR53(geometry,root,supports))return false;
        var target=new CompoundTag();target.put("Root",NervAircraftFrameR52.encodeRigid(root));target.put("Cells",cells);data.put("DeliveryTargetR53",target);return true;
    }

    static Receiver receiver(Receiver template,CompoundTag data)
    {
        var target=data.getCompound("DeliveryTargetR53");if(target.isEmpty())return template;
        var cells=new ArrayList<Cell>();for(var value:target.getList("Cells",Tag.TAG_COMPOUND)){var cell=(CompoundTag)value;cells.add(new Cell(BlockPos.of(cell.getLong("Pos")),cell.getString("State")));}
        return new Receiver(template.port(),template.region(),template.node(),NervAircraftFrameR52.decodeRigid(target.getCompound("Root")),Map.of(),true,cells,target.getBoolean("PreserveTemplateGates")?template.gates():Set.of());
    }

    /** Revalidate changed paving at the already reached authorized landing frame.
     * No height search, alternate landing point or cargo movement is permitted. */
    static boolean refreshStoppedSupports(ServerLevel level,NervFlightProofR52.FlightPickupPreview preview,Receiver receiver,CompoundTag data)
    {
        if(preview==null||receiver==null||!receiver.delivery()||!preview.current(level)
                ||!NervAirTransportManifestR52.same(preview.root(),receiver.stopped())
                ||!(level.getEntity(preview.original().eva()) instanceof com.projectseele.entity.EvaUnit01Entity eva))return false;
        var supports=new ArrayList<AABB>();var cells=new ListTag();boolean changed=false;
        for(var original:receiver.supports())
        {
            var pos=original.position();if(!level.hasChunkAt(pos))return false;
            var state=level.getBlockState(pos);String serialized=net.minecraft.commands.arguments.blocks.BlockStateParser.serialize(state);
            changed|=!serialized.equals(original.state());
            for(var box:state.getCollisionShape(level,pos,net.minecraft.world.phys.shapes.CollisionContext.of(eva)).toAabbs())supports.add(box.move(pos));
            var cell=new CompoundTag();cell.putLong("Pos",pos.asLong());cell.putString("State",serialized);cells.add(cell);
        }
        if(!changed||!NervFlightProofR52.finiteDeliverySolesR53(preview.geometry(),receiver.stopped(),supports)
                ||!com.projectseele.entity.EvaMechanicalReleaseR52.actualGroundBearingR52(level,eva,preview.geometry(),receiver.stopped()))return false;
        var target=new CompoundTag();target.put("Root",NervAircraftFrameR52.encodeRigid(receiver.stopped()));target.put("Cells",cells);target.putBoolean("PreserveTemplateGates",!receiver.gates().isEmpty());
        data.put("DeliveryTargetR53",target);data.putLong("DeliverySupportReadbackTickR53",level.getGameTime());
        return true;
    }

    static Frame frame(Mission mission,String node,Receiver template,Frame current,CompoundTag data)
    {
        if(data.getCompound("DeliveryTargetR53").isEmpty()||node.equals(mission.pickupNode())||node.startsWith(mission.pickupNode()+"/")||!(node.equals(template.node())||node.startsWith(template.node()+"/")))return current;
        var delta=receiver(template,data).stopped().translation().subtract(template.stopped().translation());
        var plane=RigidTransform.of(current.plane().translation().add(delta),current.plane().rotation());
        var cargo=current.cargo()==null?null:RigidTransform.of(current.cargo().translation().add(delta),current.cargo().rotation());
        return new Frame(plane,cargo,current.rig());
    }
    private NervAirDeliveryTargetR53(){}
}
