package com.projectseele.mixin.client;

import com.projectseele.client.RailAnnouncementsR65;
import com.projectseele.client.RailAnnouncementSpeechR65;
import java.util.List;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.ModifyArg;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Coerce;
import org.spongepowered.asm.mixin.injection.Redirect;

@Pseudo
@Mixin(targets = "org.mtr.mod.data.VehicleExtension", remap = false)
public abstract class MtrVehicleLanguageR65Mixin
{
    @Inject(method = "getInterchangeText", at = @At("HEAD"), cancellable = true)
    private static void projectSeele$groupRoutesByLanguage(@Coerce Object names, CallbackInfoReturnable<String> cir)
    {
        String translated = RailAnnouncementSpeechR65.interchangeNames((List<?>)names);
        if (translated != null) cir.setReturnValue(translated);
    }

    @ModifyArg(method = "lambda$simulate$3", index = 0, at = @At(value = "INVOKE",
            target = "Lorg/mtr/mod/data/IGui;mergeStations(Ljava/util/List;Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;"))
    private List<String> projectSeele$prepareSpeech(List<String> clauses)
    {
        return RailAnnouncementsR65.prepare(clauses);
    }
    @Redirect(method = {"getStationText", "lambda$simulate$2", "lambda$simulate$0"}, at = @At(value = "INVOKE",
            target = "Lorg/mtr/mod/data/IGui;insertTranslation(Lorg/mtr/mod/generated/lang/TranslationProvider$TranslationHolder;Lorg/mtr/mod/generated/lang/TranslationProvider$TranslationHolder;I[Ljava/lang/String;)Ljava/lang/String;"))
    private static String projectSeele$stationText(@Coerce Object cjk, @Coerce Object latin, int count, String[] args)
    {
        return RailAnnouncementsR65.format(cjk, latin, count, args, null);
    }

    @Redirect(method = "lambda$simulate$3", at = @At(value = "INVOKE",
            target = "Lorg/mtr/mod/data/IGui;insertTranslation(Lorg/mtr/mod/generated/lang/TranslationProvider$TranslationHolder;Lorg/mtr/mod/generated/lang/TranslationProvider$TranslationHolder;I[Ljava/lang/String;)Ljava/lang/String;"))
    private String projectSeele$vehicleAnnouncement(@Coerce Object cjk, @Coerce Object latin, int count, String[] args)
    {
        return RailAnnouncementsR65.format(cjk, latin, count, args, this);
    }
}
