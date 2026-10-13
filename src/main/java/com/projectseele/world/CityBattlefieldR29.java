package com.projectseele.world;

import com.google.gson.JsonParser;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.storage.LevelResource;
import java.nio.file.Files;
import java.util.Map;
import java.util.WeakHashMap;

/** The selected battle site carries its city interlock; older worlds keep their own site. */
public final class CityBattlefieldR29
{
    private static final Map<ServerLevel, Boolean> REQUIRED = new WeakHashMap<>();
    public static boolean required(ServerLevel level)
    {
        return REQUIRED.computeIfAbsent(level, key ->
        {
            var file = level.getServer().getWorldPath(LevelResource.ROOT).resolve("first_battle_site_r10.json");
            if (!Files.isRegularFile(file)) return false;
            try
            {
                var data = JsonParser.parseString(Files.readString(file)).getAsJsonObject();
                return data.has("requires_retracted_city") && data.get("requires_retracted_city").getAsBoolean()
                        && data.get("dimension").getAsString().equals(level.dimension().location().toString());
            }
            catch (Exception error) { throw new IllegalStateException("Invalid battle site", error); }
        });
    }
    public static String name(ServerLevel level)
    { return required(level) ? "城市中心迎击区" : "东北迎击大道"; }

    public static String obstruction(ServerLevel level)
    {
        if (!required(level)) return "";
        var origin = IntegratedNervMapBuilder.tokyo3Origin(level);
        var district = Tokyo3RetractionSavedData.get(level).get(origin).orElse(null);
        if (district == null || district.depth() != ThirdTokyoSurfaceBuilder.maximumRetractionDepth(origin)
                || district.targetDepth() != district.depth() || district.cursor() != 0 || district.voxelCursor() != 0)
            return "请联系冬月降下城市，等待迎击区展开";
        var floor = BattlefieldR21.state(level);
        if (!floor.hidden || !floor.job.isEmpty()) return "正在清理地表设施，等待迎击区就绪";
        if (floor.conflicts > 0) return "迎击区存在设施冲突，请先检查城市地表";
        return "";
    }
    public static boolean combatActive(ServerLevel level)
    {
        if (!required(level)) return false;
        var first = FirstBattleSavedData.get(level);
        var tv = TvCampaignSavedData.get(level);
        return first.active != null || first.missionAngel != null&&!SurfaceAngelPlanR52.handles(tv.active) || tv.phase.equals("combat");
    }
    public static boolean loweringRequested(ServerLevel level)
    {
        var origin=IntegratedNervMapBuilder.tokyo3Origin(level);
        return Tokyo3RetractionSavedData.get(level).get(origin)
                .map(d->d.targetDepth()==ThirdTokyoSurfaceBuilder.maximumRetractionDepth(origin)).orElse(false);
    }
    private CityBattlefieldR29() {}
}
