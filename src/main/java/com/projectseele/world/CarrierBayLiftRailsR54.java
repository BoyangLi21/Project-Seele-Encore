package com.projectseele.world;

import java.util.*;
import net.minecraft.core.BlockPos;
import net.minecraft.world.phys.*;

/** Two source-box bridge rails descend into the rear equipment slot. */
public final class CarrierBayLiftRailsR54
{
    public static final double START = 6, END = 23, DROP = CarrierMountProfileR53.SUBMERGED_BAY_STROKE;
    private static final Map<CarrierBayTrayR53.Bay,List<NervLegacyCarrierRideR52.Piece>> SOURCE = new IdentityHashMap<>();

    public static double drop(float rise)
    {
        if (!Float.isFinite(rise) || rise < 0 || rise > 1) throw new IllegalArgumentException("Finite bay actuator clock required");
        return -DROP * (1 - Math.max(0, (rise - (double)CarrierAssemblyR53.RISE_END) / (1 - CarrierAssemblyR53.RISE_END)));
    }

    static boolean mainRail(NervLegacyCarrierRideR52.Piece part)
    { return part.name().endsWith("/left") || part.name().endsWith("/right"); }
    public static boolean bridge(NervLegacyCarrierRideR52.Piece part)
    { return part.name().endsWith("/lift_bridge"); }

    static synchronized List<NervLegacyCarrierRideR52.Piece> source(CarrierBayTrayR53.Bay bay)
    {
        var known=SOURCE.get(bay);if(known!=null)return known;
        var pieces=new ArrayList<NervLegacyCarrierRideR52.Piece>();int count=0;
        for(var part:bay.rails())
        {
            if(!mainRail(part)){pieces.add(part);continue;}
            var box=part.mesh().bounds();
            if(!CarrierRearLateralR53.rectangular(part.mesh())||box.minZ>=START||box.maxZ<=END)
                throw new IllegalStateException("Complete original rail must span both slot bearings");
            pieces.add(slice(part,box.minZ,START,"front_fixed"));
            pieces.add(slice(part,START,END,"lift_bridge"));
            pieces.add(slice(part,END,box.maxZ,"rear_fixed"));count++;
        }
        if(count!=2)throw new IllegalStateException("Exactly two original bay rails required");
        var result=List.copyOf(pieces);SOURCE.put(bay,result);return result;
    }

    private static NervLegacyCarrierRideR52.Piece slice(NervLegacyCarrierRideR52.Piece part,double low,double high,String suffix)
    {
        var box=part.mesh().bounds();var rgb=part.rgb().clone();var xyz=new double[rgb.length/2];
        for(int i=0,n=0;i<rgb.length;i+=6)
        {
            double z=rgb[i+2];
            if(z!=box.minZ&&z!=box.maxZ)throw new IllegalStateException("Only declared twelve-triangle box rails may be divided");
            rgb[i+2]=z==box.minZ?low:high;
            for(int k=0;k<3;k++)xyz[n++]=rgb[i+k];
        }
        return new NervLegacyCarrierRideR52.Piece(part.name()+"/"+suffix,new NervRigidMeshSweepR52(xyz),rgb,part.frame(),part.role());
    }

    public static List<NervLegacyCarrierRideR52.Piece> at(CarrierBayTrayR53.Bay bay,float rise)
    {
        var out=new ArrayList<NervLegacyCarrierRideR52.Piece>();
        for(var p:source(bay))out.add(bridge(p)?new NervLegacyCarrierRideR52.Piece(p.name(),p.mesh(),p.rgb(),
                p.frame().compose(new RigidTransform(new Vec3(0,drop(rise),0),0,0,0,1)),p.role()):p);
        return List.copyOf(out);
    }

    /** Only bridge footprints retire their former continuous floor support.
     * The unchanged fixed sections still require native bearing at both ends. */
    public static Set<BlockPos> retiredSupports(CarrierBayTrayR53.Bay bay)
    {
        var result=new HashSet<BlockPos>();
        for(var p:source(bay))if(bridge(p))
        {
            var box=p.mesh().envelope(p.frame(),p.frame());int y=(int)Math.floor(box.minY-.001);
            for(int x=(int)Math.floor(box.minX);x<Math.ceil(box.maxX);x++)
                for(int z=(int)Math.floor(box.minZ);z<Math.ceil(box.maxZ);z++)result.add(new BlockPos(x,y,z));
        }
        return Set.copyOf(result);
    }

    static boolean deckSeat(NervOriginalCarrierR52.Part deck,NervOriginalCarrierR52.Part end,
                            NervOriginalCarrierR52.Part rail,NervOriginalCarrierR52.Part railEnd,
                            CarrierBayTrayR53.Bay bay,RigidTransform root,RigidTransform endRoot)
    {
        if(!deck.name().equals("deck")||!rail.name().contains("/lift_bridge")
                ||!deck.frame().equals(root)||!end.frame().equals(endRoot)
                ||!CarrierBayTrayR53.bears(bay,root)||!CarrierBayTrayR53.bears(bay,endRoot))return false;
        double top=rail.mesh().bounds().maxY;
        // The bridge approaches the original deck bearing plane from below;
        // the source's float bottom differs from that plane by under 1e-6 m.
        return rail.frame().translation().y+top<=root.translation().y-4.0078125+1e-6
                &&railEnd.frame().translation().y+top<=endRoot.translation().y-4.0078125+1e-6;
    }
    private CarrierBayLiftRailsR54(){}
}
