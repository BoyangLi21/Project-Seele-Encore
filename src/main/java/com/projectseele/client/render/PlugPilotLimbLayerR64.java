package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.projectseele.client.EntryPlugPilotPoseR47;
import com.projectseele.client.cockpit.PilotSeatPoseR64;
import net.minecraft.client.model.PlayerModel;
import net.minecraft.client.model.geom.ModelPart;
import net.minecraft.client.model.geom.PartPose;
import net.minecraft.client.model.geom.builders.CubeDeformation;
import net.minecraft.client.model.geom.builders.CubeListBuilder;
import net.minecraft.client.model.geom.builders.LayerDefinition;
import net.minecraft.client.model.geom.builders.MeshDefinition;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.entity.LivingEntityRenderer;
import net.minecraft.client.renderer.entity.RenderLayerParent;
import net.minecraft.client.renderer.entity.layers.RenderLayer;
import net.minecraft.world.entity.LivingEntity;
import org.joml.Quaternionf;

/**
 * R64: the seated pilot's limbs, bent. The game's own arms and legs are one straight box each; a pilot in the
 * plug's seat has the knees up and the forearms forward to the yokes. While a figure lies in the seat its own
 * four limbs are not drawn (PlayerModelGendoPoseMixin) and this layer draws each in two pieces, with the same
 * skin: the upper half of the limb's texture on the upper piece and the lower half on the lower.
 * The joints are PilotSeatPoseR64's; the same way of drawing as the commander's folded arms (GendoPoseArmLayer).
 */
public final class PlugPilotLimbLayerR64<T extends LivingEntity> extends RenderLayer<T, PlayerModel<T>>
{
    private static final float HALF = PilotSeatPoseR64.HALF_LIMB;
    /** Texture origins of the right arm, left arm, right leg, left leg, and of their second layers. */
    private static final int[][] SKIN = {{40, 16}, {32, 48}, {0, 16}, {16, 48}}, OVER = {{40, 32}, {48, 48}, {0, 32}, {0, 48}};
    /** [limb][upper or lower][skin or second layer] */
    private final ModelPart[][][] pieces = new ModelPart[4][2][2];
    /** The models whose renderer has this layer: only their own straight limbs are hidden while seated. */
    private static final java.util.Set<Object> MODELS = java.util.Collections.newSetFromMap(new java.util.WeakHashMap<>());

    public static boolean drawnFor(Object model)
    {
        return MODELS.contains(model);
    }

    public PlugPilotLimbLayerR64(RenderLayerParent<T, PlayerModel<T>> parent, boolean slim)
    {
        super(parent);
        MODELS.add(parent.getModel());
        for (int limb = 0; limb < 4; limb++)
        {
            float width = limb < 2 && slim ? 3 : 4;
            for (int lower = 0; lower < 2; lower++)
            {
                // The lower piece starts half a limb down the texture, so that hands and boots are where they belong.
                pieces[limb][lower][0] = piece(SKIN[limb][0], SKIN[limb][1] + lower * (int) HALF, width, 0);
                pieces[limb][lower][1] = piece(OVER[limb][0], OVER[limb][1] + lower * (int) HALF, width, .25F);
            }
        }
    }

    @Override
    public void render(PoseStack poses, MultiBufferSource buffers, int light, T entity, float limbSwing, float limbSwingAmount,
                       float partial, float age, float headYaw, float headPitch)
    {
        if (!EntryPlugPilotPoseR47.seated(entity) || entity.isInvisible()) return;
        VertexConsumer skin = buffers.getBuffer(RenderType.entityTranslucent(this.getTextureLocation(entity)));
        int overlay = LivingEntityRenderer.getOverlayCoords(entity, 0);
        for (int left = 0; left < 2; left++)
        {
            int side = left == 0 ? -1 : 1;
            float[][] arm = PilotSeatPoseR64.armJoints(side), leg = PilotSeatPoseR64.legJoints(side);
            for (int lower = 0; lower < 2; lower++)
            {
                draw(poses, skin, light, overlay, pieces[left][lower], arm[lower], arm[lower + 1]);
                draw(poses, skin, light, overlay, pieces[2 + left][lower], leg[lower], leg[lower + 1]);
            }
        }
    }

    private static void draw(PoseStack poses, VertexConsumer buffer, int light, int overlay, ModelPart[] piece, float[] from, float[] to)
    {
        float dx = to[0] - from[0], dy = to[1] - from[1], dz = to[2] - from[2];
        float length = (float) Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (length < 1e-4F) return;
        poses.pushPose();
        poses.translate(from[0] / 16, from[1] / 16, from[2] / 16);
        // The piece hangs down its own Y: turn that onto the line from one joint to the next.
        poses.mulPose(new Quaternionf().rotationTo(0, 1, 0, dx / length, dy / length, dz / length));
        poses.scale(1, length / HALF, 1);
        piece[0].render(poses, buffer, light, overlay);
        piece[1].render(poses, buffer, light, overlay);
        poses.popPose();
    }

    private static ModelPart piece(int u, int v, float width, float deformation)
    {
        MeshDefinition mesh = new MeshDefinition();
        mesh.getRoot().addOrReplaceChild("piece", CubeListBuilder.create().texOffs(u, v)
                .addBox(-width * .5F, 0, -2, width, HALF, 4, new CubeDeformation(deformation)), PartPose.ZERO);
        return LayerDefinition.create(mesh, 64, 64).bakeRoot().getChild("piece");
    }
}
