package com.projectseele.world;

import java.util.List;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.level.block.ButtonBlock;

/** Three destinations on the existing command console, one column per EVA. */
public final class NervOutletControlsR53
{
    public static final List<String> TARGETS=List.of("geofront","surface","hakone");
    public record Control(int variant,String target,BlockPos position) {}
    private NervOutletControlsR53() {}

    public static String intent(String requested)
    {
        if(requested.equals(StaffUndergroundChoiceR52.PREPARE_AND_DEPLOY))return "geofront";
        return requested.startsWith("deploy_")&&TARGETS.contains(requested.substring(7))?requested.substring(7):"surface";
    }
    public static BlockPos position(ServerLevel level,int variant,String target)
    {
        var frame=NervHeadquartersFrameR52.frame(level);int row=TARGETS.indexOf(target);
        return frame==null||variant<0||variant>2||row<0?null:frame.apply(new BlockPos(32,-408+row,287-variant));
    }
    public static Control at(ServerLevel level,BlockPos position)
    {
        for(int v=0;v<3;v++)for(String target:TARGETS)if(position.equals(position(level,v,target)))return new Control(v,target,position);
        return null;
    }
    public static EvaLogisticsDirector.ActionResult request(ServerPlayer caller,Control control)
    {
        var level=caller.serverLevel();var block=level.getBlockState(control.position());
        if(!NervStaffDialogue.authorized(caller)||!(block.getBlock() instanceof ButtonBlock)||!block.canSurvive(level,control.position()))
            return new EvaLogisticsDirector.ActionResult(false,"控制台按键或指挥权限尚未就绪。");
        EvaLogisticsDirector.loadControlTarget(level,control.variant());
        var order=StaffCommandBookR24.unitOrder(level,control.variant());
        if(!NervRouteRuntimeR52.pending(level,control.variant()))
        {
            var eva=EvaLogisticsDirector.canonicalUnit(level,control.variant());
            if(eva!=null&&EvaLogisticsDirector.inAssignedHangarR33(level,eva))AutoSortieR32.assignCommander(eva,caller);
            var result=NervRouteRuntimeR52.prepare(level,control.variant(),control.target());
            if(!result.accepted()||order!=null&&order.requested.equals("prepare"))return result;
        }
        return NervRouteRuntimeR52.launchToR53(level,control.variant(),control.target());
    }
}
