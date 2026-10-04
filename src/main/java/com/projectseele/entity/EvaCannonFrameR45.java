package com.projectseele.entity;

import net.minecraft.world.phys.Vec3;
import org.joml.Matrix3f;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Private pose candidate: the visible barrel and gameplay ray share one frame. */
public final class EvaCannonFrameR45
{
    public static final String MESH_SHA256 = "6e61de763863b313e5d9b9b933e21b41903bb2899c482018bb60e2fe30932c3d";
    private static final Vector3f PART_PIVOT = new Vector3f(-24.25F,88.34F,.875F);
    // The twelve triangles of the barrel end are coplanar at Y=-90.93669.
    // The support hook projects farther forward and is not the muzzle.
    private static final Vector3f MUZZLE = local(.311045F,-90.93669F,-3.629085F);
    // Initial stock and palm blocking; these require a separate surface fit.
    private static final Vector3f STOCK = local(.31F,31F,4.5F);
    private static final Vector3f RIGHT_PAD = local(-1.1F,5.5F,5.5F);
    private static final Vector3f LEFT_PAD = local(.31F,-20F,1F);

    public record Frame(EvaBodyPose.Sample body, Matrix4f weaponToWorld,
                        Vec3 muzzle, Vec3 stock, Vec3 forward, Vec3 right, Vec3 up,
                        Vector3f rightPad, Vector3f leftPad) {}

    public static boolean enabled(EvaUnit01Entity eva)
    {
        return com.projectseele.config.PortableRuntimeOwnersR45.cannonContact()
                && !eva.isExperimentalUnit() && eva.getUnitVariant()==1
                && eva.getWeapon()==EvaUnit01Entity.WEAPON_CANNON;
    }

    private static Vector3f local(float x,float y,float z)
    {
        return new Vector3f(x,y,z).add(PART_PIVOT).mul(-1,1,1).div(16);
    }

    public static Frame sample(EvaUnit01Entity eva,float partial,Vec3 aim)
    {
        return sample(eva,partial,aim,EvaBodyPose.sample(eva,partial),EvaRifleKinematics.world(eva,partial));
    }

    public static Frame sample(EvaUnit01Entity eva,float partial,Vec3 aim,
                               EvaBodyPose.Sample body,Matrix4f world)
    {
        // A heavy rifle needs a bladed shoulder stance, not two fully extended
        // arms on an unchanged square torso. Work on a private pose copy so
        // multiple render/server queries cannot accumulate another turn.
        var braced=new EvaBodyPose.Sample(body.rig);
        body.rotations.forEach((name,q)->braced.rotations.put(name,new Quaternionf(q)));
        body.positions.forEach((name,p)->braced.positions.put(name,new Vector3f(p)));
        float stance=eva.rifleStanceLevel(partial);
        float low=Math.max(0,Math.min(1,stance)),prone=Math.max(0,Math.min(1,(stance-1)/2));
        low=low*low*(3-2*low);prone=prone*prone*(3-2*prone);
        float yaw=(-25F-5F*low)*(1-prone)-10F*prone;
        String chest="torso_upper",parent=braced.rig.get(chest).parent();
        var upModel=new Matrix4f(world).invert().transformDirection(new Vector3f(0,1,0)).normalize();
        var current=braced.matrix(chest).getUnnormalizedRotation(new Quaternionf()).normalize();
        var parentRotation=parent==null?new Quaternionf():braced.matrix(parent).getUnnormalizedRotation(new Quaternionf()).normalize();
        var desired=new Quaternionf().fromAxisAngleRad(upModel,(float)Math.toRadians(yaw)).mul(current);
        braced.rotations.put(chest,parentRotation.invert().mul(desired));braced.dirty();body=braced;
        Vec3 forward=aim.normalize();
        if(!Double.isFinite(forward.x)||!Double.isFinite(forward.y)||!Double.isFinite(forward.z)
                ||forward.lengthSqr()<.99)throw new IllegalArgumentException("Cannon needs a finite aim direction");
        Vec3 right=forward.cross(new Vec3(0,1,0));
        if(right.lengthSqr()<1e-8)
        {
            var lateral=world.transformDirection(new Vector3f(1,0,0)).normalize();
            right=new Vec3(lateral.x,lateral.y,lateral.z);
        }
        else right=right.normalize();
        Vec3 up=right.cross(forward).normalize();
        var shoulder=new Matrix4f(world).mul(body.matrix("arm_r"))
                .transformPosition(new Vector3f(body.rig.get("arm_r").pivot()));
        Vec3 stock=new Vec3(shoulder.x,shoulder.y,shoulder.z)
                .add(right.scale(.2)).add(forward.scale(.5)).add(up.scale(.5));
        var basis=new Matrix3f().setColumn(0,right.toVector3f())
                .setColumn(1,forward.scale(-1).toVector3f()).setColumn(2,up.scale(-1).toVector3f());
        var weapon=new Matrix4f().translation(stock.toVector3f())
                .rotate(new Quaternionf().setFromNormalized(basis)).scale(EvaScale.RENDER_SCALE)
                .translate(new Vector3f(STOCK).negate());
        Vector3f tip=weapon.transformPosition(new Vector3f(MUZZLE));
        return new Frame(body,weapon,new Vec3(tip.x,tip.y,tip.z),stock,forward,right,up,
                weapon.transformPosition(new Vector3f(RIGHT_PAD)),weapon.transformPosition(new Vector3f(LEFT_PAD)));
    }

    private EvaCannonFrameR45() {}
}
