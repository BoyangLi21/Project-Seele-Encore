package com.projectseele.network;

import com.projectseele.ProjectSeele;
import net.minecraft.resources.ResourceLocation;
import net.minecraftforge.network.NetworkDirection;
import net.minecraftforge.network.NetworkRegistry;
import net.minecraftforge.network.simple.SimpleChannel;

/**
 * The mod's single wire protocol. All cross-side interaction goes through
 * here — clients never guess server state.
 */
public final class SeeleNetwork
{
    private static final String PROTOCOL_VERSION = "45";

    public static final SimpleChannel CHANNEL = NetworkRegistry.newSimpleChannel(
            new ResourceLocation(ProjectSeele.MODID, "main"),
            () -> PROTOCOL_VERSION, PROTOCOL_VERSION::equals, PROTOCOL_VERSION::equals);

    private SeeleNetwork() {}

    public static void register()
    {
        int id = 0;
        CHANNEL.messageBuilder(ClientboundCombatImpactR36.class,id++,NetworkDirection.PLAY_TO_CLIENT)
                .encoder(ClientboundCombatImpactR36::encode).decoder(ClientboundCombatImpactR36::new).consumerMainThread(ClientboundCombatImpactR36::handle).add();
        CHANNEL.messageBuilder(ClientboundCombatBodyPose.class,id++,NetworkDirection.PLAY_TO_CLIENT)
                .encoder(ClientboundCombatBodyPose::encode).decoder(ClientboundCombatBodyPose::new).consumerMainThread(ClientboundCombatBodyPose::handle).add();
        CHANNEL.messageBuilder(ClientboundCombatFeelR31.class,id++,NetworkDirection.PLAY_TO_CLIENT)
                .encoder(ClientboundCombatFeelR31::encode).decoder(ClientboundCombatFeelR31::new).consumerMainThread(ClientboundCombatFeelR31::handle).add();
        CHANNEL.messageBuilder(ServerboundEntryPlugScrapR31.class,id++,NetworkDirection.PLAY_TO_SERVER)
                .encoder(ServerboundEntryPlugScrapR31::encode).decoder(ServerboundEntryPlugScrapR31::new).consumerMainThread(ServerboundEntryPlugScrapR31::handle).add();
        CHANNEL.messageBuilder(ServerboundUNCommandPacket.class,id++,NetworkDirection.PLAY_TO_SERVER)
                .encoder(ServerboundUNCommandPacket::encode).decoder(ServerboundUNCommandPacket::new).consumerMainThread(ServerboundUNCommandPacket::handle).add();
        CHANNEL.messageBuilder(ClientboundUNStatusPacket.class,id++,NetworkDirection.PLAY_TO_CLIENT)
                .encoder(ClientboundUNStatusPacket::encode).decoder(ClientboundUNStatusPacket::new).consumerMainThread(ClientboundUNStatusPacket::handle).add();
        CHANNEL.messageBuilder(ClientboundBattleFinalePacket.class,id++,NetworkDirection.PLAY_TO_CLIENT)
                .encoder(ClientboundBattleFinalePacket::encode).decoder(ClientboundBattleFinalePacket::new)
                .consumerMainThread(ClientboundBattleFinalePacket::handle).add();
        CHANNEL.messageBuilder(ClientboundImpactResponsePacket.class,id++,NetworkDirection.PLAY_TO_CLIENT)
                .encoder(ClientboundImpactResponsePacket::encode).decoder(ClientboundImpactResponsePacket::new)
                .consumerMainThread(ClientboundImpactResponsePacket::handle).add();
        CHANNEL.messageBuilder(ClientboundCrossExplosionPacket.class, id++, NetworkDirection.PLAY_TO_CLIENT)
                .encoder(ClientboundCrossExplosionPacket::encode)
                .decoder(ClientboundCrossExplosionPacket::new)
                .consumerMainThread(ClientboundCrossExplosionPacket::handle)
                .add();
        CHANNEL.messageBuilder(ClientboundAlarmPacket.class, id++, NetworkDirection.PLAY_TO_CLIENT)
                .encoder(ClientboundAlarmPacket::encode)
                .decoder(ClientboundAlarmPacket::new)
                .consumerMainThread(ClientboundAlarmPacket::handle)
                .add();
        CHANNEL.messageBuilder(ClientboundAtFieldRipplePacket.class, id++, NetworkDirection.PLAY_TO_CLIENT)
                .encoder(ClientboundAtFieldRipplePacket::encode)
                .decoder(ClientboundAtFieldRipplePacket::new)
                .consumerMainThread(ClientboundAtFieldRipplePacket::handle)
                .add();
        CHANNEL.messageBuilder(ClientboundCannonBeamPacket.class, id++, NetworkDirection.PLAY_TO_CLIENT)
                .encoder(ClientboundCannonBeamPacket::encode)
                .decoder(ClientboundCannonBeamPacket::new)
                .consumerMainThread(ClientboundCannonBeamPacket::handle)
                .add();
        CHANNEL.messageBuilder(ClientboundRifleTracerPacket.class, id++, NetworkDirection.PLAY_TO_CLIENT)
                .encoder(ClientboundRifleTracerPacket::encode)
                .decoder(ClientboundRifleTracerPacket::new)
                .consumerMainThread(ClientboundRifleTracerPacket::handle)
                .add();
        CHANNEL.messageBuilder(ClientboundNukeFxPacket.class, id++, NetworkDirection.PLAY_TO_CLIENT)
                .encoder(ClientboundNukeFxPacket::encode)
                .decoder(ClientboundNukeFxPacket::new)
                .consumerMainThread(ClientboundNukeFxPacket::handle)
                .add();
        CHANNEL.messageBuilder(ClientboundThirdImpactPacket.class, id++, NetworkDirection.PLAY_TO_CLIENT)
                .encoder(ClientboundThirdImpactPacket::encode)
                .decoder(ClientboundThirdImpactPacket::new)
                .consumerMainThread(ClientboundThirdImpactPacket::handle)
                .add();
        CHANNEL.messageBuilder(ClientboundVisualCapturePacket.class, id++, NetworkDirection.PLAY_TO_CLIENT)
                .encoder(ClientboundVisualCapturePacket::encode)
                .decoder(ClientboundVisualCapturePacket::new)
                .consumerMainThread(ClientboundVisualCapturePacket::handle)
                .add();
        CHANNEL.messageBuilder(ClientboundSiloCapturePacket.class, id++, NetworkDirection.PLAY_TO_CLIENT)
                .encoder(ClientboundSiloCapturePacket::encode)
                .decoder(ClientboundSiloCapturePacket::new)
                .consumerMainThread(ClientboundSiloCapturePacket::handle)
                .add();
        CHANNEL.messageBuilder(ClientboundTokyo3CapturePacket.class, id++, NetworkDirection.PLAY_TO_CLIENT)
                .encoder(ClientboundTokyo3CapturePacket::encode)
                .decoder(ClientboundTokyo3CapturePacket::new)
                .consumerMainThread(ClientboundTokyo3CapturePacket::handle)
                .add();
        CHANNEL.messageBuilder(ClientboundGeoFrontCapturePacket.class, id++, NetworkDirection.PLAY_TO_CLIENT)
                .encoder(ClientboundGeoFrontCapturePacket::encode)
                .decoder(ClientboundGeoFrontCapturePacket::new)
                .consumerMainThread(ClientboundGeoFrontCapturePacket::handle)
                .add();
        CHANNEL.messageBuilder(ClientboundS20CapturePacket.class, id++, NetworkDirection.PLAY_TO_CLIENT)
                .encoder(ClientboundS20CapturePacket::encode)
                .decoder(ClientboundS20CapturePacket::new)
                .consumerMainThread(ClientboundS20CapturePacket::handle)
                .add();
        CHANNEL.messageBuilder(ClientboundGeoFrontSortieCapturePacket.class, id++, NetworkDirection.PLAY_TO_CLIENT)
                .encoder(ClientboundGeoFrontSortieCapturePacket::encode)
                .decoder(ClientboundGeoFrontSortieCapturePacket::new)
                .consumerMainThread(ClientboundGeoFrontSortieCapturePacket::handle)
                .add();
        CHANNEL.messageBuilder(ClientboundEvaArrivalSyncPacket.class, id++, NetworkDirection.PLAY_TO_CLIENT)
                .encoder(ClientboundEvaArrivalSyncPacket::encode)
                .decoder(ClientboundEvaArrivalSyncPacket::new)
                .consumerMainThread(ClientboundEvaArrivalSyncPacket::handle)
                .add();
        CHANNEL.messageBuilder(ClientboundEvaPoseRecorderPacket.class, id++,
                        NetworkDirection.PLAY_TO_CLIENT)
                .encoder(ClientboundEvaPoseRecorderPacket::encode)
                .decoder(ClientboundEvaPoseRecorderPacket::new)
                .consumerMainThread(ClientboundEvaPoseRecorderPacket::handle)
                .add();
        CHANNEL.messageBuilder(ServerboundEvaControlPacket.class, id++, NetworkDirection.PLAY_TO_SERVER)
                .encoder(ServerboundEvaControlPacket::encode)
                .decoder(ServerboundEvaControlPacket::new)
                .consumerMainThread(ServerboundEvaControlPacket::handle)
                .add();
        CHANNEL.messageBuilder(ServerboundEntryPlugPacket.class, id++, NetworkDirection.PLAY_TO_SERVER)
                .encoder(ServerboundEntryPlugPacket::encode)
                .decoder(ServerboundEntryPlugPacket::new)
                .consumerMainThread(ServerboundEntryPlugPacket::handle)
                .add();
        CHANNEL.messageBuilder(ServerboundGeoFrontCameraPacket.class, id++, NetworkDirection.PLAY_TO_SERVER)
                .encoder(ServerboundGeoFrontCameraPacket::encode)
                .decoder(ServerboundGeoFrontCameraPacket::new)
                .consumerMainThread(ServerboundGeoFrontCameraPacket::handle)
                .add();
        CHANNEL.messageBuilder(ServerboundEvaVideoFramePacket.class, id++, NetworkDirection.PLAY_TO_SERVER)
                .encoder(ServerboundEvaVideoFramePacket::encode)
                .decoder(ServerboundEvaVideoFramePacket::new)
                .consumerMainThread(ServerboundEvaVideoFramePacket::handle)
                .add();
        CHANNEL.messageBuilder(ClientboundEvaVideoFramePacket.class, id++, NetworkDirection.PLAY_TO_CLIENT)
                .encoder(ClientboundEvaVideoFramePacket::encode)
                .decoder(ClientboundEvaVideoFramePacket::new)
                .consumerMainThread(ClientboundEvaVideoFramePacket::handle)
                .add();
        CHANNEL.messageBuilder(ClientboundEvaVideoDemandPacket.class, id++, NetworkDirection.PLAY_TO_CLIENT)
                .encoder(ClientboundEvaVideoDemandPacket::encode)
                .decoder(ClientboundEvaVideoDemandPacket::new)
                .consumerMainThread(ClientboundEvaVideoDemandPacket::handle)
                .add();
        CHANNEL.messageBuilder(ClientboundCommandScreenStatePacket.class, id++, NetworkDirection.PLAY_TO_CLIENT)
                .encoder(ClientboundCommandScreenStatePacket::encode)
                .decoder(ClientboundCommandScreenStatePacket::new)
                .consumerMainThread(ClientboundCommandScreenStatePacket::handle)
                .add();
        CHANNEL.messageBuilder(ClientboundPilotStatusPacket.class, id++, NetworkDirection.PLAY_TO_CLIENT)
                .encoder(ClientboundPilotStatusPacket::encode)
                .decoder(ClientboundPilotStatusPacket::new)
                .consumerMainThread(ClientboundPilotStatusPacket::handle)
                .add();
        CHANNEL.messageBuilder(ServerboundCommandSeatPosePacket.class, id++,
                        NetworkDirection.PLAY_TO_SERVER)
                .encoder(ServerboundCommandSeatPosePacket::encode)
                .decoder(ServerboundCommandSeatPosePacket::new)
                .consumerMainThread(ServerboundCommandSeatPosePacket::handle)
                .add();
        CHANNEL.messageBuilder(ClientboundCommandSeatPosePacket.class, id++,
                        NetworkDirection.PLAY_TO_CLIENT)
                .encoder(ClientboundCommandSeatPosePacket::encode)
                .decoder(ClientboundCommandSeatPosePacket::new)
                .consumerMainThread(ClientboundCommandSeatPosePacket::handle)
                .add();
        CHANNEL.messageBuilder(ServerboundUltramanTogglePacket.class, id++,
                        NetworkDirection.PLAY_TO_SERVER)
                .encoder(ServerboundUltramanTogglePacket::encode)
                .decoder(ServerboundUltramanTogglePacket::new)
                .consumerMainThread(ServerboundUltramanTogglePacket::handle)
                .add();
        CHANNEL.messageBuilder(ClientboundUltramanStatePacket.class, id++,
                        NetworkDirection.PLAY_TO_CLIENT)
                .encoder(ClientboundUltramanStatePacket::encode)
                .decoder(ClientboundUltramanStatePacket::new)
                .consumerMainThread(ClientboundUltramanStatePacket::handle)
                .add();
        CHANNEL.messageBuilder(ClientboundStaffConversationPacket.class, id++, NetworkDirection.PLAY_TO_CLIENT)
                .encoder(ClientboundStaffConversationPacket::encode).decoder(ClientboundStaffConversationPacket::new)
                .consumerMainThread(ClientboundStaffConversationPacket::handle).add();
        CHANNEL.messageBuilder(ServerboundStaffConversationPacket.class, id++, NetworkDirection.PLAY_TO_SERVER)
                .encoder(ServerboundStaffConversationPacket::encode).decoder(ServerboundStaffConversationPacket::new)
                .consumerMainThread(ServerboundStaffConversationPacket::handle).add();
        CHANNEL.messageBuilder(ServerboundEvaFrozenPoseR30.class,id++,NetworkDirection.PLAY_TO_SERVER)
                .encoder(ServerboundEvaFrozenPoseR30::encode).decoder(ServerboundEvaFrozenPoseR30::new)
                .consumerMainThread(ServerboundEvaFrozenPoseR30::handle).add();
    }
}
