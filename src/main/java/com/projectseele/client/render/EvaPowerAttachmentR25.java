package com.projectseele.client.render;

import com.projectseele.entity.EvaScale;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import java.util.Map;
import java.util.WeakHashMap;

/** The final torso palette owns the cable plug, including crouch and prone. */
final class EvaPowerAttachmentR25
{
    record Frame(Vec3 mount,Vec3 socket,Vec3 right,Vec3 up,Vec3 rear,Vec3 cableDirection,long tick) {}
    private static final Map<EvaUnit01Entity,Frame> FRAMES=new WeakHashMap<>();
    private static Vec3 point(Matrix4f m,double y,double z)
    {
        var p=m.transformPosition(new Vector3f(0,(float)(y/EvaScale.RENDER_SCALE),(float)(z/EvaScale.RENDER_SCALE)));
        return new Vec3(p.x,p.y,p.z);
    }
    private static Vec3 axis(Matrix4f m,float x,float y,float z)
    {var p=m.transformDirection(new Vector3f(x,y,z)).normalize();return new Vec3(p.x,p.y,p.z);}
    static void capture(EvaUnit01Entity eva,BakedGeoModel model,Matrix4f root)
    {
        if(root==null)return;var torso=model.getBone("torso_upper").orElse(null);if(torso==null)return;
        var m=new Matrix4f(root).mul(EvaRigTransforms.model(torso));
        var fitted=com.projectseele.entity.EvaPowerPortsR48.of(eva);
        if(fitted!=null)
        {
            var direction=fitted.cableDirection();
            FRAMES.put(eva,new Frame(new Vec3(m.transformPosition(fitted.mountPixels().scale(1D/16).toVector3f())),
                    new Vec3(m.transformPosition(fitted.cableTailPixels().scale(1D/16).toVector3f())),
                    axis(m,1,0,0),axis(m,0,1,0),axis(m,0,0,1),axis(m,(float)direction.x,(float)direction.y,(float)direction.z),eva.level().getGameTime()));
            return;
        }
        FRAMES.put(eva,new Frame(point(m,EvaScale.UMBILICAL_MOUNT_HEIGHT,eva.powerMountRearOffset()),
                point(m,EvaScale.UMBILICAL_SOCKET_HEIGHT,eva.powerSocketRearOffset()),
                axis(m,1,0,0),axis(m,0,1,0),axis(m,0,0,1),axis(m,0,0,1),eva.level().getGameTime()));
    }
    static Frame frame(EvaUnit01Entity eva,float partial)
    {
        var value=FRAMES.get(eva);if(value!=null&&eva.level().getGameTime()-value.tick()<=1)return value;
        var fitted=com.projectseele.entity.EvaPowerPortsR48.of(eva);
        if(fitted!=null)
        {
            var body=com.projectseele.entity.EvaBodyPose.sample(eva,partial);
            var matrix=com.projectseele.entity.EvaRifleKinematics.world(eva,partial).mul(body.matrix("torso_upper"));
            var direction=fitted.cableDirection();
            return new Frame(new Vec3(matrix.transformPosition(fitted.mountPixels().scale(1D/16).toVector3f())),
                    new Vec3(matrix.transformPosition(fitted.cableTailPixels().scale(1D/16).toVector3f())),
                    axis(matrix,1,0,0),axis(matrix,0,1,0),axis(matrix,0,0,1),
                    axis(matrix,(float)direction.x,(float)direction.y,(float)direction.z),eva.level().getGameTime());
        }
        Vec3 shift=eva.getPosition(partial).subtract(eva.position()),rear=eva.getRearDirection();
        return new Frame(eva.getUmbilicalMountPosition().add(shift),eva.getUmbilicalSocketPosition().add(shift),
                new Vec3(-rear.z,0,rear.x),new Vec3(0,1,0),rear,rear,eva.level().getGameTime());
    }
    private EvaPowerAttachmentR25() {}
}
