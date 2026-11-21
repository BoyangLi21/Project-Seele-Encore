package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.mojang.math.Axis;
import com.projectseele.entity.GaghielEntity;
import net.minecraft.client.renderer.LightTexture;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.entity.EntityRenderer;
import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;
import org.joml.Vector3f;

/**
 * R66: the Sixth Angel drawn from original geometry only (the private marine mesh is never read). Units are the
 * entity's model units (blocks at scale 1), front toward -z, laid over the six hulls the server collides with
 * ({@code GaghielEntity.BODY}): a heavy head whose lower jaw hinges at z -23 and opens to show the core at
 * (0, 1, -26), a long body that narrows into a swaying tail with a tall fin, broad side fins and a low dorsal crest.
 * <p>
 * The look follows episode 8: a whale-sized, dark, smooth sea creature, pale beneath, with a cavernous mouth and
 * the red core deep inside it.
 */
public final class GaghielRendererR66 extends EntityRenderer<GaghielEntity>
{
    private static final float[] BACK = AngelMeshR66.rgb(.20F, .27F, .38F);
    private static final float[] FLANK = AngelMeshR66.rgb(.30F, .38F, .50F);
    private static final float[] BELLY = AngelMeshR66.rgb(.68F, .72F, .76F);
    private static final float[] FIN = AngelMeshR66.rgb(.16F, .21F, .31F);
    private static final float[] THROAT = AngelMeshR66.rgb(.34F, .05F, .09F);
    private static final float[] TOOTH = AngelMeshR66.rgb(.90F, .88F, .82F);
    private static final float[] MARK = AngelMeshR66.rgb(.05F, .05F, .07F);
    private static final float[] SOCKET = AngelMeshR66.rgb(.26F, .05F, .08F);
    private static final float[] CORE = AngelMeshR66.rgb(.96F, .10F, .10F);

    public GaghielRendererR66(EntityRendererProvider.Context context)
    {
        super(context);
        this.shadowRadius = 10;
    }

    @Override
    public ResourceLocation getTextureLocation(GaghielEntity entity)
    {
        return AngelMeshR66.WHITE;
    }

    @Override
    public void render(GaghielEntity actor, float yaw, float partial, PoseStack pose, MultiBufferSource buffers, int light)
    {
        float bodyYaw = Mth.rotLerp(partial, actor.yRotO, actor.getYRot());
        float phase = actor.swimPhase(partial), mouth = actor.mouthOpen(partial), time = actor.tickCount + partial;
        VertexConsumer solid = buffers.getBuffer(RenderType.entityCutoutNoCull(AngelMeshR66.WHITE));
        pose.pushPose();
        pose.mulPose(Axis.YP.rotationDegrees(180 - bodyYaw));
        float scale = actor.modelScaleR50();
        pose.scale(scale, scale, scale);

        drawBody(pose, solid, light, phase);
        drawJaw(pose, solid, light, mouth);

        VertexConsumer glow = buffers.getBuffer(RenderType.entityTranslucentEmissive(AngelMeshR66.WHITE));
        float pulse = actor.isDeadOrDying() ? .1F : .8F + .2F * Mth.sin(time * .16F);
        // the core is deep in the throat; with the mouth shut only a faint glow shows between the lips
        float shown = Mth.clamp(mouth / .65F, .25F, 1);
        AngelMeshR66.ellipsoid(pose, glow, new Vector3f(0, 1, -26), 5.5F, 5.5F, 5.5F, AngelMeshR66.mix(SOCKET, CORE, pulse * shown),
                LightTexture.FULL_BRIGHT, 8);
        pose.popPose();
        super.render(actor, yaw, partial, pose, buffers, light);
    }

    /** Head, body and tail; the tail bends segment by segment with the swim phase. */
    private static void drawBody(PoseStack pose, VertexConsumer out, int light, float phase)
    {
        // z, half width, half height, centre y
        float[][] spine = {{-36, 7, 6, 9}, {-30, 11.5F, 11, 9}, {-22, 13, 15, 7}, {-12, 15, 15, 4}, {0, 16, 13, 1},
                {12, 14.5F, 11, 0}, {25, 9.5F, 8, 0}, {38, 6.5F, 6.5F, 0}, {50, 4.6F, 5.5F, 0}, {60, 2.6F, 3.4F, 0}};
        AngelMeshR66.Ring[] rings = new AngelMeshR66.Ring[spine.length];
        float x = 0, heading = 0;
        float[] tailX = new float[spine.length];
        for (int i = 0; i < spine.length; i++)
        {
            if (spine[i][0] > 4)
            {
                int segment = Math.min(4, (int) ((spine[i][0] - 4) / 12));
                heading += Mth.sin(phase - segment * .65F) * (.07F + segment * .035F);
                x += Mth.sin(heading) * (spine[i][0] - spine[i - 1][0]);
            }
            tailX[i] = x;
            float[] colour = i < 3 ? BACK : i % 2 == 0 ? BACK : FLANK;
            rings[i] = new AngelMeshR66.Ring(new Vector3f(x, spine[i][3], spine[i][0]), spine[i][1], spine[i][2], colour);
        }
        AngelMeshR66.loft(pose, out, rings, 16, light, true);
        // pale underside of the head and body
        AngelMeshR66.ellipsoid(pose, out, new Vector3f(0, -5.5F, -6), 13.5F, 7.5F, 25, BELLY, light, 10);
        // skull ridge and the eye marks set back from the lips
        AngelMeshR66.ellipsoid(pose, out, new Vector3f(0, 15, -22), 9, 6, 15, BACK, light, 8);
        for (int side : new int[]{-1, 1})
        {
            AngelMeshR66.ellipsoid(pose, out, new Vector3f(side * 10.5F, 11, -31), 2.6F, 2.2F, 2.6F, MARK, light, 5);
            AngelMeshR66.ellipsoid(pose, out, new Vector3f(side * 12.5F, 6.5F, -26), 2F, 1.8F, 2F, MARK, light, 5);
        }
        // tall tail fin, upright like a shark's
        float tx = tailX[spine.length - 1], fan = Mth.sin(phase - 3.2F) * 3;
        AngelMeshR66.plate(pose, out, new Vector3f(tx, 0, 56), new Vector3f(tx + fan, 15, 71), new Vector3f(tx + fan, 2, 66),
                new Vector3f(tx, -1, 60), FIN, light);
        AngelMeshR66.plate(pose, out, new Vector3f(tx, 0, 56), new Vector3f(tx, 1, 60), new Vector3f(tx + fan, -2, 66),
                new Vector3f(tx + fan, -12, 70), FIN, light);
        // broad side fins (hulls at x ±21, z 3) and the low dorsal crest
        float flap = Mth.sin(phase * .7F) * 3.2F;
        for (int side : new int[]{-1, 1})
            AngelMeshR66.plate(pose, out, new Vector3f(side * 13, -1, -8), new Vector3f(side * 31, -2 + flap, -2),
                    new Vector3f(side * 32, -1 + flap, 14), new Vector3f(side * 13, 0, 13), FIN, light);
        float crest = Mth.sin(phase - .4F) * 1.2F;
        AngelMeshR66.plate(pose, out, new Vector3f(0, 13, -10), new Vector3f(crest, 24, -1), new Vector3f(crest, 21, 8),
                new Vector3f(0, 12, 14), FIN, light);
    }

    /** The lower jaw turns about its hinge at z -23; the throat and the upper teeth are fixed to the head. */
    private static void drawJaw(PoseStack pose, VertexConsumer out, int light, float mouth)
    {
        // throat lining, seen only when the jaw drops
        AngelMeshR66.ellipsoid(pose, out, new Vector3f(0, 0, -27), 9.5F, 6.5F, 11, THROAT, light, 8);
        upperTeeth(pose, out, light);
        pose.pushPose();
        pose.translate(0, -.5F, -23);
        pose.mulPose(Axis.XP.rotation(-1.05F * mouth));
        AngelMeshR66.ellipsoid(pose, out, new Vector3f(0, -5.5F, -6.5F), 11.5F, 5.5F, 14, BELLY, light, 8);
        AngelMeshR66.ellipsoid(pose, out, new Vector3f(0, -2.5F, -6), 8.5F, 2.4F, 11, THROAT, light, 6);
        for (int i = 0; i < 7; i++)
        {
            float z = -15.5F + i * 2.2F;
            for (int side : new int[]{-1, 1})
            {
                float x = side * (3 + i * 1.1F);
                AngelMeshR66.plate(pose, out, new Vector3f(x - .8F, -1.2F, z), new Vector3f(x + .8F, -1.2F, z),
                        new Vector3f(x, 2.6F, z + .3F), new Vector3f(x, 2.6F, z + .3F), TOOTH, light);
            }
        }
        pose.popPose();
    }

    private static void upperTeeth(PoseStack pose, VertexConsumer out, int light)
    {
        for (int i = 0; i < 7; i++)
        {
            float z = -38 + i * 2.2F;
            for (int side : new int[]{-1, 1})
            {
                float x = side * (3 + i * 1.1F);
                AngelMeshR66.plate(pose, out, new Vector3f(x - .8F, 2.4F, z), new Vector3f(x + .8F, 2.4F, z),
                        new Vector3f(x, -1.4F, z + .3F), new Vector3f(x, -1.4F, z + .3F), TOOTH, light);
            }
        }
    }
}
