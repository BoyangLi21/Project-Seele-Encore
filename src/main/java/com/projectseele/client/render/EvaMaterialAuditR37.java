package com.projectseele.client.render;

import com.google.gson.*;
import com.projectseele.visual.CombatR31Review;
import net.minecraft.client.renderer.ShaderInstance;
import net.minecraft.resources.ResourceLocation;
import org.lwjgl.opengl.*;
import java.nio.file.*;
import java.util.*;

/** Read-only witness of the real shader samplers, enabled only in a review. */
final class EvaMaterialAuditR37
{
    private static final boolean ENABLED_R37=Boolean.getBoolean("projectseele.r37MaterialAudit");

    private static final JsonObject DATA=new JsonObject();
    static void capture(ResourceLocation texture,ShaderInstance shader)
    {
        if(!ENABLED_R37||CombatR31Review.mediaFolder.isEmpty()
                ||!texture.getPath().contains("eva_")||texture.getPath().endsWith("_eyes.png")||DATA.has(texture.toString()))return;
        if(GL20.glGetUniformLocation(shader.getId(),"normals")<0||GL20.glGetUniformLocation(shader.getId(),"specular")<0)return;
        int active=GL11.glGetInteger(GL13.GL_ACTIVE_TEXTURE);var row=new JsonObject();
        try
        {
            for(String name:List.of("normals","specular"))
            {
                int location=GL20.glGetUniformLocation(shader.getId(),name);var value=new JsonObject();value.addProperty("uniform",location);
                if(location>=0)
                {
                    int unit=GL20.glGetUniformi(shader.getId(),location);GL13.glActiveTexture(GL13.GL_TEXTURE0+unit);
                    value.addProperty("texture_id",GL11.glGetInteger(GL11.GL_TEXTURE_BINDING_2D));value.addProperty("width",GL11.glGetTexLevelParameteri(GL11.GL_TEXTURE_2D,0,GL11.GL_TEXTURE_WIDTH));value.addProperty("height",GL11.glGetTexLevelParameteri(GL11.GL_TEXTURE_2D,0,GL11.GL_TEXTURE_HEIGHT));
                }
                row.add(name,value);
            }
            DATA.add(texture.toString(),row);var folder=Path.of(CombatR31Review.mediaFolder);Files.createDirectories(folder);Files.writeString(folder.resolve("material_samplers_r37.json"),new GsonBuilder().setPrettyPrinting().create().toJson(DATA));
        }
        catch(Exception error){throw new IllegalStateException("Material sampler audit failed",error);}
        finally{GL13.glActiveTexture(active);}
    }
    private EvaMaterialAuditR37(){}
}
