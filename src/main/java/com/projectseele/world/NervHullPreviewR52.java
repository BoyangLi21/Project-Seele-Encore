package com.projectseele.world;
import com.projectseele.entity.*;
import com.projectseele.world.NervRouteReservationsR52.Original;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;

/** Read-only, pre-lease facts for a stopped field hull. Its empty socket is
 * only a geometric reference: no separated capsule/person is adopted. */
public final class NervHullPreviewR52
{
    private final Original original;private final EvaMechanicalFrameR52.HullCapture capture;private final CompoundTag stopped,hands;private final RigidTransform frame;private final FootSupportFrameR52.Binding binding;
    private NervHullPreviewR52(Original o,EvaMechanicalFrameR52.HullCapture proof,EvaUnit01Entity e,CompoundTag hands,RigidTransform frame,FootSupportFrameR52.Binding binding)
    {original=o;capture=proof;stopped=EvaShutdownR30.pose(e).copy();this.hands=hands.copy();this.frame=frame;this.binding=binding;}
    public static NervHullPreviewR52 inspect(EvaUnit01Entity e,Original o)
    {
        var proof=EvaMechanicalFrameR52.prepareHullCapture(e,o);if(proof==null||!NervR50CarrierModeR53.enabled()&&(e.getWeapon()!=EvaUnit01Entity.WEAPON_FISTS||EvaShieldRigR47.equipped(e)||e.isBerserk()||EvaDorsalMechanism.open(e)>=.0001F||EvaDorsalMechanism.bow(e)>=.0001F||EvaBerserkMotionR34.mouth(e,1)!=0))return null;
        var provider=EvaOriginalMeshGeometryR52.readOnlySelectedProviderR52();var hands=EvaFrozenHandsR52.capture(e,1);var handPose=EvaFrozenHandsR52.decode(e.getUnitVariant(),provider.handContractFingerprint(e.getUnitVariant()),provider.handJoints(e.getUnitVariant()),hands);var body=EvaBodyPose.sample(e,1);var g=provider.evaluate(e.getUnitVariant(),body,handPose);
        float yaw=EvaAirTransportR31.frameYaw(e,1);var f=RigidTransform.of(e.position(),new Quaternionf().rotationY((float)Math.toRadians(180-yaw)));var socket=EvaMechanicalFrameR52.emptySocketReferenceR52(body,EvaRifleKinematics.frameWorldR52(e.position(),yaw),EvaDorsalProfile.of(e));var b=new FootSupportFrameR52.Binding(sole(g,"foot_l"),sole(g,"foot_r"),f.inverse().compose(socket));return new NervHullPreviewR52(o,proof,e,hands,f,b);
    }
    public boolean matches(EvaUnit01Entity e,Original o){return original.equals(o)&&!e.isNervLogisticsLocked()&&e.position().distanceToSqr(frame.translation())<1e-12&&EvaShutdownR30.pose(e).equals(stopped)&&EvaFrozenHandsR52.capture(e,1).equals(hands)&&Math.abs(net.minecraft.util.Mth.wrapDegrees(EvaAirTransportR31.frameYaw(e,1)-(180-yawDegrees(frame))))<.001;}
    private static double yawDegrees(RigidTransform f){var d=f.transformVector(new Vec3(0,0,1));return Math.toDegrees(Math.atan2(d.x,d.z));}
    public FootSupportFrameR52.Binding binding(){return binding;}
    public RigidTransform frame(){return frame;}
    public EvaMechanicalFrameR52.HullCapture capture(){return capture;}
    private static Vec3 sole(EvaOriginalMeshGeometryR52.Geometry g,String name)
    {var vertices=g.parts().stream().filter(p->p.bone().equals(name)).flatMap(p->p.vertices().stream()).toList();if(vertices.isEmpty())throw new IllegalStateException("Actual sole absent");double y=vertices.stream().mapToDouble(p->p.y).min().orElseThrow();double lx=Double.POSITIVE_INFINITY,lz=lx,hx=-lx,hz=hx;for(var p:vertices)if(p.y<=y+.02){lx=Math.min(lx,p.x);hx=Math.max(hx,p.x);lz=Math.min(lz,p.z);hz=Math.max(hz,p.z);}return new Vec3((lx+hx)/2,y,(lz+hz)/2);}
}
