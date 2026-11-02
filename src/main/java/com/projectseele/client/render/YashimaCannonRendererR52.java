package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.projectseele.entity.YashimaCannonEntityR52;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.entity.*;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.phys.Vec3;

/** Original standalone cannon triangles in the same declared moving/aiming frame used by server ballistics. */
public final class YashimaCannonRendererR52 extends EntityRenderer<YashimaCannonEntityR52>
{
    private static final ResourceLocation MESH=new ResourceLocation("projectseele","mesh/positron_cannon_payload_r50.mesh.json");
    private static final ResourceLocation TEXTURE=new ResourceLocation("projectseele","textures/entity/positron_cannon.png");
    private static final java.util.Map<com.projectseele.world.NervAirframeGeometryR52.Part,RigidMachineryPartR44> CRADLE_PARTS=new java.util.IdentityHashMap<>();
    public YashimaCannonRendererR52(EntityRendererProvider.Context context){super(context);shadowRadius=0;}
    @Override public void render(YashimaCannonEntityR52 gun,float yaw,float partial,PoseStack poses,MultiBufferSource buffers,int light)
    {
        var g=gun.geometryR52();var spec=gun.cradleR52();if(g==null||spec==null)return;var aim=gun.aimR52(partial);var origin=gun.getPosition(partial);
        // The operator's scope is the fire-control picture; the gun body and
        // cradle sit on that sight line and would fill the zoomed view.
        if(scopedByLocalOperatorR55(gun))return;
        if(gun.loadedR52()){poses.pushPose();poses.mulPoseMatrix(g.matrix(Vec3.ZERO,aim));LocalTriangleMeshLayer.renderStandalone(poses,buffers,MESH,TEXTURE,light,OverlayTexture.NO_OVERLAY);poses.popPose();}
        for(var part:com.projectseele.world.FixedCannonCradleR52.pieces(g,spec,origin,aim))
        {
            var mesh=CRADLE_PARTS.computeIfAbsent(part.part(),p->{var values=new com.google.gson.JsonArray();for(double v:p.vertices())values.add(v);return RigidMachineryPartR44.triangles(values);});
            poses.pushPose();var f=part.frame();var at=f.translation().subtract(origin);poses.translate(at.x,at.y,at.z);poses.mulPose(new org.joml.Quaternionf(f.qx(),f.qy(),f.qz(),f.qw()));mesh.draw(poses,buffers,light);
            poses.popPose();
        }
        super.render(gun,yaw,partial,poses,buffers,light);
    }
    @Override public ResourceLocation getTextureLocation(YashimaCannonEntityR52 gun){return TEXTURE;}
    private static boolean scopedByLocalOperatorR55(YashimaCannonEntityR52 gun)
    {
        var minecraft=net.minecraft.client.Minecraft.getInstance();var camera=minecraft.getCameraEntity();
        if(camera==null||!minecraft.options.getCameraType().isFirstPerson()||ShaderShadowPassR44.active())return false;
        var eva=com.projectseele.world.EvaPilotResolver.controlTarget(camera);
        return eva!=null&&eva.fixedCannonOperatingR52()&&eva.fixedCannonBodyR52()==gun&&com.projectseele.client.ClientForgeEvents.isCannonScopeActive(eva);
    }
}
