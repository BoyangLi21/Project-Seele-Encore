package com.projectseele.visual;

import com.projectseele.ProjectSeele;
import com.projectseele.world.FacilitySchemaV2;
import com.projectseele.world.MilitaryR07Director;
import net.minecraft.commands.Commands;
import net.minecraft.network.chat.Component;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Operator navigation and the same physical wet-cell controls used by the wall panel. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class MilitaryR07Commands
{
    @SubscribeEvent public static void register(RegisterCommandsEvent event)
    {
        var root=Commands.literal("military");
        for(String action:new String[]{"status","drain","door","fill","defense","power"})
            root.then(Commands.literal(action).executes(c->{
                var level=c.getSource().getServer().getLevel(FacilitySchemaV2.DIMENSION);
                if(level==null)return 0;
                String message=MilitaryR07Director.request(level,action,c.getSource().getPlayerOrException());
                c.getSource().sendSuccess(()->Component.literal(message),false);return 1;
            }));
        var visit=Commands.literal("visit");
        String[] names={"port","base","hangar","gantry"};
        Vec3[] points={new Vec3(1264.5,69,504.5),new Vec3(6560.5,75,-5968.5),new Vec3(6402.5,77,-6132.5),new Vec3(6446.5,127,-6217.5)};
        for(int i=0;i<names.length;i++)
        {
            Vec3 p=points[i];float yaw=names[i].equals("gantry")?90:180;visit.then(Commands.literal(names[i]).executes(c->{
                var level=c.getSource().getServer().getLevel(FacilitySchemaV2.DIMENSION);
                if(level==null||!MilitaryR07Director.state(level).commissioned){c.getSource().sendFailure(Component.literal("此存档尚未安装 R07 设施"));return 0;}
                var player=c.getSource().getPlayerOrException();player.stopRiding();player.teleportTo(level,p.x,p.y,p.z,yaw,0);player.fallDistance=0;player.setDeltaMovement(Vec3.ZERO);return 1;
            }));
        }
        if(DevelopmentCommandsR43.enabled())root.then(visit);
        event.getDispatcher().register(Commands.literal("seele").requires(s->s.hasPermission(2)).then(root));
    }
}
