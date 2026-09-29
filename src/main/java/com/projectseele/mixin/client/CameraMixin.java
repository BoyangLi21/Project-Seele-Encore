package com.projectseele.mixin.client;

import com.projectseele.entity.EntryPlugCarrierEntity;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.world.EvaPilotResolver;
import com.projectseele.client.UltramanClientState;
import net.minecraft.client.player.AbstractClientPlayer;
import net.minecraft.client.Camera;
import net.minecraft.client.Minecraft;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.phys.Vec3;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.ModifyVariable;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * Third-person camera cannot frame a 60-block war machine at the vanilla
 * 4-block orbit. Scale the requested zoom distance while piloting; the
 * method's own raycast still clamps it against walls.
 */
@Mixin(Camera.class)
public abstract class CameraMixin
{
    @Shadow
    protected abstract void setPosition(double x, double y, double z);
    @Shadow protected abstract void setRotation(float yaw,float pitch);
    @Shadow private double getMaxZoom(double desired){throw new AssertionError();}
    @org.spongepowered.asm.mixin.Unique private int projectseele$carrierCameraId=-1;
    @org.spongepowered.asm.mixin.Unique private double projectseele$carrierZoom;
    @org.spongepowered.asm.mixin.Unique private double projectseele$carrierPivotHeight;
    @org.spongepowered.asm.mixin.Unique private long projectseele$carrierFrame;
    @org.spongepowered.asm.mixin.Unique private boolean projectseele$loosePlugCamera;

    @Inject(method = "setup", at = @At("TAIL"))
    private void projectseele$smoothEntryPlugCamera(BlockGetter level,
            Entity subject, boolean detached, boolean mirrored,
            float partialTick, CallbackInfo callback)
    {
        var airReview=com.projectseele.client.visual.AirLiftR40Client.cameraView(partialTick);
        if(airReview!=null)
        {
            Vec3 p=airReview.position(),d=airReview.target().subtract(p);this.setPosition(p.x,p.y,p.z);
            this.setRotation((float)Math.toDegrees(Math.atan2(-d.x,d.z)),(float)-Math.toDegrees(Math.atan2(d.y,d.horizontalDistance())));return;
        }
        var combatReview=com.projectseele.client.visual.CombatR31Client.cameraView(partialTick);
        if(combatReview!=null)
        {
            Vec3 p=combatReview.position(),d=combatReview.target().subtract(p);this.setPosition(p.x,p.y,p.z);
            this.setRotation((float)Math.toDegrees(Math.atan2(-d.x,d.z)),(float)-Math.toDegrees(Math.atan2(d.y,d.horizontalDistance())));return;
        }
        var factory=com.projectseele.client.visual.FactoryR20Client.cameraView();
        if(factory!=null)
        {
            Vec3 p=factory.position(),d=factory.target().subtract(p);this.setPosition(p.x,p.y,p.z);
            this.setRotation((float)Math.toDegrees(Math.atan2(-d.x,d.z)),(float)-Math.toDegrees(Math.atan2(d.y,d.horizontalDistance())));return;
        }
        var exterior=com.projectseele.client.visual.TransitExteriorR16Client.cameraView();
        if(exterior!=null)
        {
            Vec3 p=exterior.position(),d=exterior.target().subtract(p);this.setPosition(p.x,p.y,p.z);
            this.setRotation((float)Math.toDegrees(Math.atan2(-d.x,d.z)),(float)-Math.toDegrees(Math.atan2(d.y,d.horizontalDistance())));return;
        }
        var directed=com.projectseele.client.FirstBattleClient.camera((Camera)(Object)this,partialTick);
        if(directed!=null)
        {
            Vec3 p=directed.position(),d=directed.target().subtract(p);this.setPosition(p.x,p.y,p.z);
            this.setRotation((float)Math.toDegrees(Math.atan2(-d.x,d.z)),(float)-Math.toDegrees(Math.atan2(d.y,d.horizontalDistance())));return;
        }
        EvaUnit01Entity controlled=EvaPilotResolver.controlTarget(subject);
        if(detached&&subject.getVehicle() instanceof EntryPlugCarrierEntity loose&&!loose.isLockedToEva())
        {
            long now=System.nanoTime();double dt=Math.min(.1,Math.max(0,(now-projectseele$carrierFrame)/1e9));
            Vec3 pivot=loose.getInterpolatedPilotEyePosition(partialTick);
            this.setPosition(pivot.x,pivot.y,pivot.z);
            // The modelled pressure leaves project beyond their thin block
            // interlock. Keep the orbit off the visible leaf as well.
            double available=Math.max(.25,this.getMaxZoom(4)-2.0);
            int key=-loose.getId()-2;
            if(projectseele$carrierCameraId!=key)projectseele$carrierZoom=available;
            else projectseele$carrierZoom=Math.min(available,projectseele$carrierZoom+net.minecraft.util.Mth.clamp(available-projectseele$carrierZoom,-16*dt,12*dt));
            projectseele$carrierCameraId=key;projectseele$carrierFrame=now;projectseele$loosePlugCamera=true;
            Camera camera=(Camera)(Object)this;Vec3 p=pivot.add(Vec3.directionFromRotation(camera.getXRot(),camera.getYRot()).scale(-projectseele$carrierZoom));
            this.setPosition(p.x,p.y,p.z);return;
        }
        boolean lockedCapsule=!(subject.getVehicle() instanceof EntryPlugCarrierEntity capsule)||capsule.isLockedToEva();
        if (detached && controlled != null && (controlled.hasActiveCarrierMotion()||controlled.isNervLogisticsLocked()&&lockedCapsule))
        {
            // Both collision rays and orbit originate at the analytic optical
            // frame. Translating an already-clipped rider camera still shook
            // when the rider and EVA crossed a packet boundary separately.
            long now=System.nanoTime();
            double dt=Math.min(.1,Math.max(0,(now-projectseele$carrierFrame)/1e9));
            Vec3 base=controlled.hasActiveCarrierMotion()?controlled.carrierRenderPosition(partialTick):controlled.getPosition(partialTick);
            // A 60-metre EVA needs a chest-height orbit even when the silo
            // wall contracts its zoom. Never inherit the low rider seat or
            // ease back toward the old 30-metre waist pivot.
            projectseele$carrierPivotHeight=48;
            Vec3 pivot=com.projectseele.entity.EvaAirTransportR31.active(controlled)
                    ?com.projectseele.entity.EvaAirTransportR31.point(controlled,new Vec3(0,40,0),partialTick):base.add(0,projectseele$carrierPivotHeight,0);
            this.setPosition(pivot.x,pivot.y,pivot.z);
            double available=Math.max(.25,this.getMaxZoom(4)-2.0);
            double anticipated=available;
            if(controlled.hasActiveCarrierMotion()&&!com.projectseele.entity.EvaAirTransportR31.active(controlled))
            {
                // Read the already synchronized mechanical path ahead. A
                // descending camera contracts before reaching the surface
                // slab instead of jumping thirty metres on its first hit.
                for(float ahead:new float[]{8,20,36})
                {
                    Vec3 future=controlled.sampleCarrierMotion(partialTick-1+ahead).add(0,projectseele$carrierPivotHeight,0);
                    this.setPosition(future.x,future.y,future.z);anticipated=Math.min(anticipated,Math.max(.25,this.getMaxZoom(4)-2.0));
                }
                this.setPosition(pivot.x,pivot.y,pivot.z);
            }
            if(projectseele$carrierCameraId!=controlled.getId()&&!projectseele$loosePlugCamera)projectseele$carrierZoom=available;
            else
            {
                double difference=anticipated-projectseele$carrierZoom;
                projectseele$carrierZoom+=net.minecraft.util.Mth.clamp(difference,-24*dt,12*dt);
                projectseele$carrierZoom=Math.min(projectseele$carrierZoom,available);
            }
            projectseele$carrierCameraId=controlled.getId();projectseele$carrierFrame=now;projectseele$loosePlugCamera=false;
            Camera camera=(Camera)(Object)this;
            Vec3 position=pivot.add(Vec3.directionFromRotation(camera.getXRot(),camera.getYRot()).scale(-projectseele$carrierZoom));
            this.setPosition(position.x, position.y, position.z);
            return;
        }
        projectseele$carrierCameraId=-1;projectseele$loosePlugCamera=false;
        if(!detached&&controlled!=null&&com.projectseele.entity.EvaAirTransportR31.active(controlled))
        {
            Vec3 optical=controlled.getPilotCameraSeatPosition(subject,partialTick).add(0,subject.getEyeHeight(),0);
            optical=com.projectseele.client.PilotOpticsContinuity.apply(controlled,partialTick,optical);
            Camera camera=(Camera)(Object)this;
            float localYaw=camera.getYRot()-com.projectseele.entity.EvaAirTransportR31.frameYaw(controlled,partialTick)+180;
            Vec3 local=Vec3.directionFromRotation(camera.getXRot(),localYaw);
            var body=com.projectseele.entity.EvaBodyPose.sample(controlled,partialTick);
            var frame=com.projectseele.entity.EvaRifleKinematics.world(controlled,partialTick).mul(body.matrix("head"));
            Vec3 direction=new Vec3(frame.transformDirection(local.toVector3f()).normalize());
            float yaw=direction.horizontalDistanceSqr()<1e-6?camera.getYRot():(float)Math.toDegrees(Math.atan2(-direction.x,direction.z));
            this.setPosition(optical.x,optical.y,optical.z);
            this.setRotation(yaw,(float)-Math.toDegrees(Math.atan2(direction.y,direction.horizontalDistance())));return;
        }
        if(!detached&&controlled!=null&&controlled.isPoweredOn()&&!controlled.isActivationCinematicActive())
        {
            Vec3 optical=controlled.getPilotCameraSeatPosition(subject,partialTick).add(0,subject.getEyeHeight(),0);
            optical=com.projectseele.client.PilotOpticsContinuity.apply(controlled,partialTick,optical);
            this.setPosition(optical.x,optical.y,optical.z);return;
        }
        if(controlled==null)com.projectseele.client.PilotOpticsContinuity.clear();
        if (detached
                || !(subject.getVehicle() instanceof EntryPlugCarrierEntity plug))
        {
            return;
        }
        Vec3 eye = plug.getInterpolatedPilotEyePosition(partialTick);
        EvaUnit01Entity eva = plug.getLinkedEva();
        if (plug.isLockedToEva() && eva != null
                && eva.isActivationCinematicActive())
        {
            // Continue from the physical capsule eye into the EVA optical
            // socket during the final 30% of synchronization.  Both endpoints
            // are world-space positions, so no camera frame can escape the
            // cabin or jump to the exterior at the nested-ride transition.
            float raw = (eva.getActivationProgress(partialTick) - 0.70F)
                    / 0.30F;
            float t = Math.max(0.0F, Math.min(1.0F, raw));
            float blend = t * t * (3.0F - 2.0F * t);
            Vec3 evaEye = eva.getPilotCameraSeatPosition(subject,partialTick)
                    .add(0.0D, subject.getEyeHeight(), 0.0D);
            eye = eye.lerp(evaEye, blend);
        }
        this.setPosition(eye.x, eye.y, eye.z);
    }

    @ModifyVariable(method = "getMaxZoom", at = @At("HEAD"), argsOnly = true)
    private double projectseele$extendPlugZoom(double desired)
    {
        Entity subject = ((Camera) (Object) this).getEntity();
        if (subject != null
                && subject.getVehicle() instanceof EntryPlugCarrierEntity plug
                && !plug.isLockedToEva())
        {
            // F5 during black standby/insertion must frame the suspended
            // capsule and crane instead of remaining at vanilla arm's length.
            return desired * 8.0D;
        }
        EvaUnit01Entity eva = subject == null
                ? null : EvaPilotResolver.controlTarget(subject);
        if (eva != null)
        {
            if (eva.isPilotProne())
            {
                return desired * 24.0D;
            }
            // The forward-facing orbit sits in front of the cannon muzzle and
            // needs much more clearance. Keep the normal rear chase camera
            // close enough that the Unit still fills the frame.
            return desired * (Minecraft.getInstance().options.getCameraType().isMirrored()
                    ? 22.0D : 11.6D);
        }
        if (subject instanceof AbstractClientPlayer player)
        {
            float scale = UltramanClientState.scale(player, 0.0F);
            if (scale > 1.01F)
            {
                double multiplier = scale *
                        (Minecraft.getInstance().options.getCameraType()
                                .isMirrored() ? 0.55D : 0.42D);
                return desired * Math.max(1.0D, multiplier);
            }
        }
        return desired;
    }
}
