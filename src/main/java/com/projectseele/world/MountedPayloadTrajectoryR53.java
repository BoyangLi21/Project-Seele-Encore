package com.projectseele.world;

import com.projectseele.entity.NervCarrierPlatformEntity;
import java.util.*;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.phys.Vec3;

/** A load view of an unchanged installed controller trajectory. This is proof
 * input, never an actuator update or permission to commission a mount. */
public final class MountedPayloadTrajectoryR53
{
    public static final class Mount
    {
        private final UUID carrier;private final CompoundTag source;private final CarrierMountProfileR53.State state;
        private Mount(UUID carrier,CompoundTag source,CarrierMountProfileR53.State state)
        {this.carrier=carrier;this.source=source.copy();this.state=Objects.requireNonNull(state);}
        public static Mount legacy(){return new Mount(null,new CompoundTag(),CarrierMountProfileR53.LEGACY);}
        public static Mount capture(NervCarrierPlatformEntity carrier)
        {return carrier==null?legacy():new Mount(carrier.getUUID(),carrier.carrierMountProfileR53(),CarrierMountProfileR53.read(carrier,1));}
        public CarrierMountProfileR53.State state(){return state;}
        public UUID carrier(){return carrier;}
        public CompoundTag source(){return source.copy();}
        public boolean matches(NervCarrierPlatformEntity actual)
        {return equals(capture(actual));}
        @Override public boolean equals(Object other)
        {return other instanceof Mount m&&Objects.equals(carrier,m.carrier)&&source.equals(m.source)&&state.equals(m.state);}
        @Override public int hashCode(){return Objects.hash(carrier,source,state);}
    }

    private final DirectoryTrajectoryR52 controller;private final Mount mount;private final double rounding;
    private final Map<Double,FootSupportFrameR52.Sample> samples=new HashMap<>();
    public MountedPayloadTrajectoryR53(DirectoryTrajectoryR52 controller,Mount mount)
    {
        this.controller=Objects.requireNonNull(controller);this.mount=Objects.requireNonNull(mount);
        // Composition uses the represented float quaternion. Keep its extra
        // offset roundoff outside the reducible curve chord budget.
        double elevation=mount.state().elevation(),extent=Math.max(controller.sample(0).evaRoot().translation().length(),controller.sample(1).evaRoot().translation().length());
        rounding=elevation==0?0:Math.nextUp(elevation*128*Math.scalb(1D,-24)+Math.ulp(extent+elevation)*32);
    }
    public static MountedPayloadTrajectoryR53 legacy(DirectoryTrajectoryR52 path){return new MountedPayloadTrajectoryR53(path,Mount.legacy());}
    public static List<MountedPayloadTrajectoryR53> views(List<DirectoryTrajectoryR52> paths,Mount mount)
    {return paths.stream().map(p->new MountedPayloadTrajectoryR53(p,mount)).toList();}
    public DirectoryTrajectoryR52 controller(){return controller;}
    public Mount mount(){return mount;}
    public NervRouteDirectoryR52 directory(){return controller.directory();}
    public NervRouteDirectoryR52.Leg leg(){return controller.leg();}
    public FootSupportFrameR52.Binding binding(){return controller.binding();}
    public double fromFraction(){return controller.fromFraction();}
    public double toFraction(){return controller.toFraction();}
    public boolean pureTranslation(){return controller.pureTranslation();}
    public Vec3 footCentreLocal(){return controller.footCentreLocal().subtract(0,mount.state().elevation(),0);}
    public int divisions(double radius,double maximumError){return controller.divisions(radius,maximumError-rounding);}
    public double error(double radius,int divisions){return controller.error(radius,divisions)+rounding;}
    public synchronized FootSupportFrameR52.Sample sample(double time)
    {
        var original=controller.sample(time);if(mount.state().elevation()==0)return original;
        var known=samples.get(time);if(known!=null)return known;
        var result=sample(original,binding(),mount.state());if(samples.size()<8192)samples.put(time,result);return result;
    }
    public static FootSupportFrameR52.Sample sample(FootSupportFrameR52.Sample controller,FootSupportFrameR52.Binding binding,CarrierMountProfileR53.State state)
    {
        if(state.elevation()==0)return controller;var root=state.payloadFrame(controller.evaRoot());
        return new FootSupportFrameR52.Sample(root,root.transformPoint(binding.leftFoot()),root.transformPoint(binding.rightFoot()),root.compose(binding.plugInEva()));
    }
    /** Keep the controller source and clock portable; explicitly encode the
     * payload binding rather than hiding an offset in renderer coordinates. */
    public static CompoundTag encodePortable(List<DirectoryTrajectoryR52> paths,Mount mount)
    {
        var encoded=DirectoryTrajectoryR52.encodePortableR52(paths);
        if(mount.state().elevation()==0)return encoded;
        if(mount.carrier()==null||mount.source().isEmpty())throw new IllegalArgumentException("Explicit actual payload binding required");
        var tag=new CompoundTag();tag.putString("Type","r53-mounted-payload-window-v1");tag.put("Controller",encoded);tag.putUUID("Carrier",mount.carrier());tag.put("Mount",mount.source());tag.putDouble("Elevation",mount.state().elevation());return tag;
    }
}
