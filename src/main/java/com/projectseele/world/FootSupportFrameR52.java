package com.projectseele.world;

import java.util.Objects;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Pure rigid placement around two original posed foot contacts, in metres.
 * No actor, joint, pose, world, clock, or collision state is changed or cached. */
public final class FootSupportFrameR52
{
    public static Binding sourceSoleBindingR52(EvaOriginalMeshGeometryR52.Geometry geometry,RigidTransform plugLocal){return new Binding(sourceSoleR52(geometry,"foot_l"),sourceSoleR52(geometry,"foot_r"),plugLocal);}
    public static Vec3 sourceSoleR52(EvaOriginalMeshGeometryR52.Geometry geometry,String bone){var points=new java.util.ArrayList<Vec3>();for(var p:geometry.parts())if(p.bone().equals(bone))points.addAll(p.vertices());if(points.isEmpty())throw new IllegalStateException("Actual sole mesh absent: "+bone);double low=points.stream().mapToDouble(p->p.y).min().orElseThrow(),x=Double.POSITIVE_INFINITY,z=x,X=Double.NEGATIVE_INFINITY,Z=X;for(var p:points)if(p.y<=low+.02){x=Math.min(x,p.x);X=Math.max(X,p.x);z=Math.min(z,p.z);Z=Math.max(Z,p.z);}return new Vec3((x+X)*.5,low,(z+Z)*.5);}
    /** The original posed points and seated plug frame are EVA-local, after
     * model/render scale. Neither foot is assumed to be the entity origin. */
    public record Binding(Vec3 leftFoot,Vec3 rightFoot,RigidTransform plugInEva)
    {
        public Binding
        {
            finite(leftFoot);finite(rightFoot);finite(plugInEva);
            var span=rightFoot.subtract(leftFoot);finite(span);double squared=span.lengthSqr();
            if(!Double.isFinite(squared)||squared<1e-12)throw new IllegalArgumentException("Distinct finite original foot contacts required");
        }
        public Vec3 contactCentre(){return leftFoot.scale(.5).add(rightFoot.scale(.5));}
    }
    /** All four outputs belong to the same caller-supplied sample instant. */
    public record Sample(RigidTransform evaRoot,Vec3 leftContact,Vec3 rightContact,RigidTransform plugWorld){}

    public record RootPose(Quaternionf rotation,Vector3f offset){}
    /** Express a full world rigid turn through the existing model root bone,
     * retaining its actual pivot and the caller's frozen articulated pose. */
    public static RootPose composeModelRoot(Vector3f pivot,Vector3f frozenOffset,Quaternionf frozenRotation,
                                             Quaternionf outerWorldBasis,Quaternionf wantedWorldBasis)
    {
        Objects.requireNonNull(pivot);Objects.requireNonNull(frozenOffset);
        if(!Float.isFinite(pivot.x+pivot.y+pivot.z+frozenOffset.x+frozenOffset.y+frozenOffset.z))
            throw new IllegalArgumentException("Finite original model root required");
        var turn=unit(outerWorldBasis).conjugate().mul(unit(wantedWorldBasis)).normalize();
        var offset=turn.transform(new Vector3f(frozenOffset).add(pivot)).sub(pivot);
        return new RootPose(turn.mul(unit(frozenRotation)).normalize(),offset);
    }

    /** footFrame's origin is the measured bearing midpoint, not the carrier
     * actor's origin. Its rotation supplies the measured carrier/world basis.
     * If a measured device frame has a different origin, the caller must first
     * compose its measured local bearing offset; this helper invents no offset.
     * from/to are EVA orientations relative to that basis. Both must preserve
     * the original foot span: a rigid 90-degree turn can keep both feet fixed
     * only around their actual connecting axis. An incompatible turn fails
     * rather than silently sliding the feet, resizing, or altering joints. */
    public static Sample sample(Binding original,RigidTransform footFrame,
                                Quaternionf from,Quaternionf to,double fraction)
    {
        Objects.requireNonNull(original,"Original pose binding required");finite(footFrame);
        if(!Double.isFinite(fraction)||fraction<0||fraction>1)throw new IllegalArgumentException("Fraction must be finite and within [0,1]");
        var first=unit(from);var last=unit(to);
        var span=original.rightFoot().subtract(original.leftFoot());
        var initial=RigidTransform.of(Vec3.ZERO,first).transformVector(span);
        var finalSpan=RigidTransform.of(Vec3.ZERO,last).transformVector(span);
        // Only float quaternion representation roundoff; this does not adjust
        // any collision tolerance or move an accepted original contact point.
        double rounding=Math.max(1e-7,span.length()*2e-6);
        if(initial.distanceTo(finalSpan)>rounding)throw new IllegalArgumentException("Turn does not preserve the original two-foot bearing axis");
        if(first.dot(last)<0)last.mul(-1); // Explicit shortest quaternion path.
        var relative=fraction==0?first:fraction==1?last:first.slerp(last,(float)fraction).normalize();
        var worldRotation=RigidTransform.of(Vec3.ZERO,footFrame.rotation().mul(relative));
        var root=RigidTransform.of(footFrame.translation().subtract(worldRotation.transformVector(original.contactCentre())),worldRotation.rotation());
        finite(root);
        var left=root.transformPoint(original.leftFoot());var right=root.transformPoint(original.rightFoot());
        var expectedLeft=footFrame.transformPoint(initial.scale(-.5));var expectedRight=footFrame.transformPoint(initial.scale(.5));
        if(left.distanceTo(expectedLeft)>rounding||right.distanceTo(expectedRight)>rounding)
            throw new IllegalArgumentException("Intermediate turn changed an original foot contact");
        var plug=root.compose(original.plugInEva());finite(plug);
        return new Sample(root,left,right,plug);
    }
    private static Quaternionf unit(Quaternionf value)
    {
        Objects.requireNonNull(value,"Original orientation required");
        double length=Math.sqrt((double)value.x*value.x+(double)value.y*value.y+(double)value.z*value.z+(double)value.w*value.w);
        if(!Double.isFinite(length)||length<1e-12)throw new IllegalArgumentException("Finite nonzero quaternion required");
        return new Quaternionf((float)(value.x/length),(float)(value.y/length),(float)(value.z/length),(float)(value.w/length));
    }
    private static void finite(Vec3 value)
    {if(value==null||!Double.isFinite(value.x)||!Double.isFinite(value.y)||!Double.isFinite(value.z))throw new IllegalArgumentException("Finite original point required");}
    private static void finite(RigidTransform value)
    {if(value==null)throw new IllegalArgumentException("Measured rigid frame required");finite(value.translation());}
    private FootSupportFrameR52(){}
}
