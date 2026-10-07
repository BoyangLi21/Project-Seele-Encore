package com.projectseele.world;

import com.projectseele.entity.*;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.*;
import java.util.*;

/** Sweeps both ends of every angular substep, including the aircraft's turn. */
final class AirCradleClearanceR31
{
    private static Vec3 point(EvaUnit01Entity eva,Vec3 root,Vec3 local,float pitch,float yaw)
    {
        var p=EvaAirTransportR31.transformLocal(eva,local,pitch);
        double heading=(180-yaw)*Mth.DEG_TO_RAD;
        return root.add(p.x*Math.cos(heading)+p.z*Math.sin(heading),p.y,-p.x*Math.sin(heading)+p.z*Math.cos(heading));
    }
    private static AABB transformed(EvaUnit01Entity eva,AABB box,Vec3 root,float pitch,float yaw)
    {
        double x0=Double.POSITIVE_INFINITY,y0=x0,z0=x0,x1=Double.NEGATIVE_INFINITY,y1=x1,z1=x1;
        for(double x:new double[]{box.minX,box.maxX})for(double y:new double[]{box.minY,box.maxY})for(double z:new double[]{box.minZ,box.maxZ})
        {var p=point(eva,root,new Vec3(x,y,z),pitch,yaw);x0=Math.min(x0,p.x);y0=Math.min(y0,p.y);z0=Math.min(z0,p.z);x1=Math.max(x1,p.x);y1=Math.max(y1,p.y);z1=Math.max(z1,p.z);}
        return new AABB(x0,y0,z0,x1,y1,z1);
    }
    private static List<AABB> sections(EvaUnit01Entity eva)
    {
        if(EvaAirTransportR31.adaptive(eva))return EvaBodyPose.posedCarrierHulls(eva,EvaAirTransportR31.origin(eva));
        List<AABB> measured=EvaBodyPose.carrierHulls(eva),result=new ArrayList<>();
        double fallback=Math.max(11,eva.getBbWidth()/2D+1.5);
        for(int i=0;i<4;i++)
        {
            double bottom=i*16,top=bottom+16;AABB section=null;
            for(var hull:measured)if(hull.maxY>bottom&&hull.minY<top)
            {
                var cut=new AABB(hull.minX,Math.max(bottom,hull.minY),hull.minZ,hull.maxX,Math.min(top,hull.maxY),hull.maxZ);
                section=section==null?cut:section.minmax(cut);
            }
            if(section==null)section=new AABB(-fallback,bottom,-10,fallback,top,10);
            result.add(new AABB(section.minX-.18,Math.max(0,section.minY),section.minZ-.18,section.maxX+.18,section.maxY+.18,section.maxZ+.18));
        }
        return result;
    }
    private static List<Double> initialSupports(EvaUnit01Entity eva,Vec3 root,float pitch,float yaw)
    {
        if(Math.abs(pitch)>.5F)return List.of();
        var contacts=new ArrayList<AABB>();var heights=new ArrayList<Double>();
        for(var hull:sections(eva))if(hull.minY<.25)
        {
            var sole=transformed(eva,new AABB(hull.minX,Math.max(0,hull.minY),hull.minZ,hull.maxX,Math.max(0,hull.minY)+.01,hull.maxZ),root,pitch,yaw);
            contacts.add(new AABB(sole.minX,sole.minY-.16,sole.minZ,sole.maxX,sole.minY+.16,sole.maxZ));
        }
        if(contacts.isEmpty())
        {
            double half=eva.getBbWidth()/2D;
            contacts.add(new AABB(root.x-half,root.y-.16,root.z-half,root.x+half,root.y+.16,root.z+half));
        }
        for(var sole:contacts)for(var shape:eva.level().getBlockCollisions(eva,sole))for(var block:shape.toAabbs())
            if(block.maxY>=sole.minY&&block.maxY<=sole.maxY&&block.minY<(sole.minY+sole.maxY)*.5+.002
                    &&heights.stream().noneMatch(y->Math.abs(y-block.maxY)<.002))heights.add(block.maxY);
        return heights;
    }
    private static boolean existingSupport(AABB block,List<Double> supportPlanes)
    {
        // The broad foot-section AABB spans the air between the two feet.
        // Exempt its already-contacted bearing plane, including that gap;
        // a taller side wall or any ceiling still blocks the angular sweep.
        for(double height:supportPlanes)if(Math.abs(block.maxY-height)<.002&&block.minY<height-.001)return true;
        return false;
    }
    static boolean clear(EvaUnit01Entity eva,Vec3 delta,float targetYaw)
    {
        float startPitch=EvaAirTransportR31.active(eva)?EvaAirTransportR31.acceptedPitch(eva):0;
        float endPitch=EvaAirTransportR31.active(eva)?EvaAirTransportR31.pitch(eva,0):0;
        float startYaw=eva.getYRot(),turn=Mth.wrapDegrees(targetYaw-startYaw);
        if(delta.lengthSqr()>1e-12&&Math.abs(endPitch-startPitch)<1e-4&&Math.abs(turn)<1e-4
                &&eva.level() instanceof net.minecraft.server.level.ServerLevel level)
        {
            var pose=EvaAirTransportR31.active(eva)?EvaAirTransportR31.origin(eva):EvaBodyPose.sample(eva,0);
            Boolean measured=VerticalCarrierSweepR40.clearTranslationAt(level,eva,pose,startPitch,startYaw,eva.position(),delta);
            if(measured!=null)
            {
                if(measured)EvaAirTransportR31.acceptPitch(eva,endPitch);else EvaAirTransportR31.holdAtPitch(eva,startPitch);
                return measured;
            }
        }
        float rotationRatio=EvaAirTransportR31.adaptive(eva)?2:1;
        int pitchSteps=Math.max(1,Mth.ceil(Math.abs(endPitch-startPitch)*rotationRatio/.5F));
        int yawSteps=Math.max(1,Mth.ceil(Math.abs(turn)/.5F));
        var root=eva.position();var contacts=initialSupports(eva,root,startPitch,startYaw);var shapes=sections(eva);
        // Pitch, heading and translation have different easing clocks. Cover
        // their product interval instead of assuming they share one parameter.
        double arc=(Math.abs(endPitch-startPitch)*rotationRatio/pitchSteps+Math.abs(turn)/yawSteps)*Mth.DEG_TO_RAD;
        double pad=.012+140*arc*arc/8;
        for(int ip=0;ip<pitchSteps;ip++)for(int iy=0;iy<yawSteps;iy++)
        {
            float pa=Mth.lerp(ip/(float)pitchSteps,startPitch,endPitch),pb=Mth.lerp((ip+1)/(float)pitchSteps,startPitch,endPitch);
            float ya=startYaw+turn*iy/yawSteps,yb=startYaw+turn*(iy+1)/yawSteps;
            for(var local:shapes)
            {
                AABB sweep=transformed(eva,local,root,pa,ya).minmax(transformed(eva,local,root,pa,yb))
                        .minmax(transformed(eva,local,root,pb,ya)).minmax(transformed(eva,local,root,pb,yb))
                        .expandTowards(delta).inflate(pad);
                if(sweep.minY>=eva.level().getMaxBuildHeight()||sweep.maxY<eva.level().getMinBuildHeight())continue;
                for(var collision:eva.level().getBlockCollisions(eva,sweep))for(var box:collision.toAabbs())
                    if(box.intersects(sweep)&&!existingSupport(box,contacts))
                    {
                        // A captured sole may already slightly overlap its bearing floor.
                        // Permit only vertical separation from that existing floor contact.
                        AABB before=transformed(eva,local,root,startPitch,startYaw).inflate(.015);
                        boolean separating=delta.y>0&&delta.horizontalDistanceSqr()<1e-8
                                &&Math.abs(endPitch-startPitch)<1e-4&&Math.abs(turn)<1e-4
                                &&box.maxY<=root.y+.25&&before.intersects(box)
                                &&Math.min(before.maxY+delta.y,box.maxY)-Math.max(before.minY+delta.y,box.minY)
                                  <=Math.min(before.maxY,box.maxY)-Math.max(before.minY,box.minY)+1e-6;
                        if(separating)continue;
                        com.projectseele.ProjectSeele.LOGGER.warn("AIR CONTACT root={} delta={} pitch={}/{} yaw={}/{} local={} sweep={} obstacle={} supports={}",root,delta,startPitch,endPitch,startYaw,targetYaw,local,sweep,box,contacts);
                        EvaAirTransportR31.holdAtPitch(eva,startPitch);return false;
                    }
            }
        }
        EvaAirTransportR31.acceptPitch(eva,endPitch);return true;
    }
    /** Complete posed cargo sweep for airspace admission and dynamic occupants. */
    static AABB envelopeR50(EvaUnit01Entity eva,Vec3 delta,float targetYaw)
    {
        float a=EvaAirTransportR31.acceptedPitch(eva),b=EvaAirTransportR31.pitch(eva,0);
        var root=eva.position();AABB result=null;
        for(var part:sections(eva))for(float pitch:new float[]{a,b})for(float yaw:new float[]{eva.getYRot(),targetYaw})
        {
            var box=transformed(eva,part,root,pitch,yaw).minmax(transformed(eva,part,root.add(delta),pitch,yaw));
            result=result==null?box:result.minmax(box);
        }
        double arc=(Math.abs(b-a)*2+Math.abs(Mth.wrapDegrees(targetYaw-eva.getYRot())))*Mth.DEG_TO_RAD;
        if(result==null)throw new IllegalStateException("Original cargo geometry is unavailable");
        return result.inflate(.02+140*arc*arc/8);
    }
    /** Position the lowest measured carried part above the receiving surface. */
    static Vec3 landingRoot(EvaUnit01Entity eva,Vec3 floor,float yaw)
    {
        double lowest=Double.POSITIVE_INFINITY;
        for(var local:sections(eva))lowest=Math.min(lowest,transformed(eva,local,floor,0,yaw).minY);
        double lift=Math.max(0,floor.y+.035-lowest);
        if(!Double.isFinite(lift)||lift>4)throw new IllegalStateException("运输姿态与落点高度不相容，请检查机体姿态");
        return floor.add(0,lift,0);
    }
    /** Real bearing surface under the lowest carried parts, including a prone
     * body. Transport positions are kinematic, so Entity.onGround is stale. */
    static Vec3 touchdownContact(EvaUnit01Entity eva)
    {return touchdownContact(eva,null);}
    static Vec3 touchdownContact(EvaUnit01Entity eva,UNTransportEntity receiver)
    {
        float pitch=EvaAirTransportR31.active(eva)?EvaAirTransportR31.acceptedPitch(eva):0;
        if(Math.abs(pitch)>.5F)return null;
        var hulls=new ArrayList<AABB>();double lowest=Double.POSITIVE_INFINITY;
        for(var local:sections(eva))
        {
            var box=transformed(eva,local,eva.position(),pitch,eva.getYRot());
            hulls.add(box);lowest=Math.min(lowest,box.minY);
        }
        for(var hull:hulls)
        {
            if(hull.minY>lowest+.12)continue;
            var sole=new AABB(hull.minX,hull.minY-.16,hull.minZ,hull.maxX,hull.minY+.05,hull.maxZ);
            for(var shape:eva.level().getBlockCollisions(eva,sole))for(var floor:shape.toAabbs())
            {
                if(floor.maxY<sole.minY||floor.maxY>sole.maxY||!floor.intersects(sole))continue;
                return new Vec3((Math.max(sole.minX,floor.minX)+Math.min(sole.maxX,floor.maxX))*.5,
                        floor.maxY,(Math.max(sole.minZ,floor.minZ)+Math.min(sole.maxZ,floor.maxZ))*.5);
            }
        }
        if(receiver!=null&&receiver.groundCart()&&receiver.level()==eva.level())
        {
            Vec3 articulated=UNReceivingCradleR40.contact(eva,receiver);
            if(articulated!=null)return articulated;
            // The owned ground dolly is a kinematic mechanical support, not a
            // terrain block. These are the rendered un_ground_carrier deck
            // dimensions; never invent a ground plane at the nominal endpoint.
            double top=receiver.getY()+.02;AABB deck=null;
            for(double x:new double[]{-12.2,12.2})for(double z:new double[]{-14,14})
            {
                var corner=new org.joml.Vector3f((float)x,0,(float)z).rotateY(-receiver.getYRot()*Mth.DEG_TO_RAD);
                var point=receiver.position().add(corner.x,0,corner.z);var box=new AABB(point.x,top-.4,point.z,point.x,top,point.z);
                deck=deck==null?box:deck.minmax(box);
            }
            for(var hull:hulls)
                if(Math.abs(hull.minY-top)<.16&&hull.maxX>deck.minX&&hull.minX<deck.maxX&&hull.maxZ>deck.minZ&&hull.minZ<deck.maxZ)
                    return new Vec3((Math.max(hull.minX,deck.minX)+Math.min(hull.maxX,deck.maxX))*.5,top,
                            (Math.max(hull.minZ,deck.minZ)+Math.min(hull.maxZ,deck.maxZ))*.5);
        }
        return null;
    }
    static float landingYaw(EvaUnit01Entity eva,Vec3 destination,float preferred)
    {
        for(float yaw:new float[]{preferred,preferred+90,preferred-90,preferred+180})
        {
            if(eva.level() instanceof net.minecraft.server.level.ServerLevel level)
            {
                var pose=EvaAirTransportR31.active(eva)?EvaAirTransportR31.origin(eva):EvaBodyPose.sample(eva,0);
                Boolean corridor=VerticalCarrierSweepR40.clearAt(level,eva,pose,0,yaw,destination,Math.max(1,level.getMaxBuildHeight()-destination.y+1));
                if(Boolean.FALSE.equals(corridor))continue;
            }
            boolean clear=true;
            for(var local:sections(eva))
            {
                var hull=transformed(eva,local,destination,0,yaw).inflate(.03);
                for(var shape:eva.level().getBlockCollisions(eva,hull))for(var box:shape.toAabbs())
                    if(box.maxY>destination.y+.18&&box.intersects(hull)){clear=false;break;}
                if(!clear)break;
            }
            if(clear)return yaw;
        }
        return Float.NaN;
    }
    private AirCradleClearanceR31() {}
}
