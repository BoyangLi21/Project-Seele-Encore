package com.projectseele.world;

import java.util.*;
import net.minecraft.world.phys.Vec3;

/** Uninstalled spatial candidate. Does not replace a runtime profile or grant movement. */
public final class CandidateAboveFloorCarrierProfileR53
{
    public static final double LOAD_Y=4.25,BAY_STROKE=1;
    private final CarrierRearGuideR53.Hardware baseline;
    private final List<CarrierRearGuideR53.Template> parts;

    public CandidateAboveFloorCarrierProfileR53(CarrierRearGuideR53.Hardware baseline)
    {
        this.baseline=baseline;var result=new ArrayList<CarrierRearGuideR53.Template>();
        for(var p:baseline.parts())
        {
            if(!p.name().endsWith("/lift_rod")){result.add(p);continue;}
            double top=p.mesh().bounds().maxY;double[] rgb=p.rgb().clone();
            for(int i=0;i<rgb.length;i+=6)if(Math.abs(rgb[i+1]-top)<1e-8)rgb[i+1]+=LOAD_Y;
            double[] xyz=new double[rgb.length/2];
            for(int i=0,j=0;i<rgb.length;i+=6)for(int k=0;k<3;k++)xyz[j++]=rgb[i+k];
            result.add(new CarrierRearGuideR53.Template(p.name(),p.frame(),p.role(),new NervRigidMeshSweepR52(xyz),rgb));
        }
        parts=List.copyOf(result);
    }

    public List<CarrierRearGuideR53.Template> templates(){return parts;}
    public CarrierRearGuideR53.Hardware baseline(){return baseline;}
    public static double bodyDrop(float rise)
    {
        if(!Float.isFinite(rise)||rise<0||rise>1)throw new IllegalArgumentException("Bounded candidate rise required");
        return -BAY_STROKE*Math.max(0,1-rise/(double)CarrierAssemblyR53.RISE_END);
    }
    public static RigidTransform loadFrame(RigidTransform controllerRoot)
    {return controllerRoot.compose(translation(LOAD_Y));}
    private static RigidTransform translation(double y)
    {return new RigidTransform(new Vec3(0,y,0),0,0,0,1);}

    public Map<String,RigidTransform> carrierFrames(RigidTransform controllerRoot,float rise,float release)
    {
        var selected=Objects.requireNonNull(CarrierAssemblyR53.selected());var frames=new LinkedHashMap<String,RigidTransform>();
        for(String name:selected.parts().keySet())
        {
            var original=selected.frame(name,rise,release,0).translation();
            double y=LOAD_Y+(name.equals("deck")||name.startsWith("toe_")?0:bodyDrop(rise));
            frames.put(name,controllerRoot.compose(new RigidTransform(new Vec3(original.x,y,original.z),0,0,0,1)));
        }
        return Collections.unmodifiableMap(frames);
    }

    public List<NervLegacyCarrierRideR52.Piece> rearPartsAt(RigidTransform root,float rise,Vec3 direction,double slide,double worldLift)
    {
        if(!Double.isFinite(worldLift)||worldLift<0||worldLift>CarrierRearGuideR53.STOW_LIFT
            ||!Double.isFinite(slide)||slide<-.65||slide>0)throw new IllegalArgumentException("Bounded original head motion required");
        var body=root.compose(translation(LOAD_Y+bodyDrop(rise)));
        // Actual head travel remains 0..7 m in the old controller frame.
        // Relative to the raised body this is -4.25..+2.75 m, not a raised rail.
        var lifted=root.compose(translation(bodyDrop(rise)+worldLift));
        var frames=new HashMap<String,RigidTransform>();frames.put("ROOT",body);frames.put("LIFT",lifted);
        for(var mount:baseline.mounts())frames.put(mount.name(),baseline.headFrame(lifted,mount.name(),direction));
        var result=new ArrayList<NervLegacyCarrierRideR52.Piece>();
        for(var part:parts)
        {
            var frame=Objects.requireNonNull(frames.get(part.frame()));
            if(NervBankHeadTransferR53.slides(part.role()))frame=frame.compose(new RigidTransform(new Vec3(0,0,slide),0,0,0,1));
            result.add(new NervLegacyCarrierRideR52.Piece(part.name(),part.mesh(),part.rgb(),frame,part.role()));
        }
        return List.copyOf(result);
    }
}
