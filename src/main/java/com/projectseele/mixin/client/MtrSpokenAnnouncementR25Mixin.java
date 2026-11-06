package com.projectseele.mixin.client;

import com.projectseele.client.FacilityPronunciationR22;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyArg;

/** Normalize at MTR's call site even if the native narrator was loaded early. */
@Pseudo
@Mixin(targets = {"org.mtr.mod.data.VehicleExtension",
        "org.mtr.mod.block.BlockTrainAnnouncer$BlockEntity"}, remap = false)
public abstract class MtrSpokenAnnouncementR25Mixin
{
    @ModifyArg(method = "*", at = @At(value = "INVOKE",
            target = "Lorg/mtr/mod/client/IDrawing;narrateOrAnnounce(Ljava/lang/String;Lorg/mtr/libraries/it/unimi/dsi/fastutil/objects/ObjectArrayList;)V"), index = 0, remap = false)
    private String projectSeele$pronounceNerv(String text)
    { return FacilityPronunciationR22.spoken(text); }
}
