package com.projectseele.mixin.client;

import com.projectseele.client.FacilityPronunciationR22;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyArg;

@Pseudo
@Mixin(targets = "org.mtr.mod.InitClient", remap = false)
public abstract class MtrSpokenPlatformR25Mixin
{
    @ModifyArg(method = "lambda$init$37", at = @At(value = "INVOKE",
            target = "Lorg/mtr/mod/client/IDrawing;narrateOrAnnounce(Ljava/lang/String;Lorg/mtr/libraries/it/unimi/dsi/fastutil/objects/ObjectArrayList;)V"), index = 0, remap = false)
    private static String projectSeele$pronounceNerv(String text)
    { return FacilityPronunciationR22.spoken(text); }
}
