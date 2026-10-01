package com.projectseele.client;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.CombatMotionResourcesR44;
import com.projectseele.network.ClientboundCombatContractR44;
import com.projectseele.network.CombatBundleGateR44;
import com.projectseele.network.SeeleNetwork;
import com.projectseele.network.ServerboundCombatContractR44;
import net.minecraft.client.Minecraft;
import net.minecraft.network.chat.Component;

public final class CombatContractClientR44
{
    public static void receive(ClientboundCombatContractR44 packet)
    {
        var connection=Minecraft.getInstance().getConnection();if(connection==null)return;
        try
        {
            var resources=CombatMotionResourcesR44.fingerprints();
            if(!resources.equals(packet.resources()))
            {
                String difference=CombatBundleGateR44.mismatch(packet.resources(),resources);
                ProjectSeele.LOGGER.warn("Combat resource client rejected: {}",difference);
                connection.getConnection().disconnect(Component.literal(difference));return;
            }
            SeeleNetwork.CHANNEL.sendToServer(new ServerboundCombatContractR44(resources));
            ProjectSeele.LOGGER.info("Combat resource client matched: profiles={}",resources.size());
        }
        catch(Exception failure)
        {
            ProjectSeele.LOGGER.error("Required client combat bundle could not be verified",failure);
            connection.getConnection().disconnect(Component.literal("客户端 EVA 动作资源校验失败："+failure.getMessage()+"。请安装与服务器同批的动作资源包。"));
        }
    }
    private CombatContractClientR44(){}
}
