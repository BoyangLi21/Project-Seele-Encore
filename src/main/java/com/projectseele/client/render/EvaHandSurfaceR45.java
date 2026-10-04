package com.projectseele.client.render;

import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.resources.ResourceLocation;

/** Private native admission for the continuous hand candidate. */
final class EvaHandSurfaceR45
{
    static ResourceLocation mesh(EvaUnit01Entity eva)
    {return new ResourceLocation("projectseele","mesh/eva_unit0"+eva.getUnitVariant()
            +(com.projectseele.entity.EvaAnatomicalHandsR45.enabled(eva)?"_anatomical_hands_r45.mesh.json":"_original_hands_r45.mesh.json"));}
    static boolean applies(EvaUnit01Entity eva)
    {
        // Rejected by the owner: the voxel/box replacement changed the hand's
        // original silhouette. Retained review flags must not reactivate it.
        return (com.projectseele.entity.EvaAnatomicalHandsR45.enabled(eva)||com.projectseele.entity.EvaOriginalHandsR45.enabled(eva))
                &&LocalTriangleMeshLayer.hasPart(mesh(eva),"hand_l")
                &&LocalTriangleMeshLayer.hasPart(mesh(eva),"hand_r");
    }
    static boolean oldSurface(String name){return name.startsWith("hand_")||name.startsWith("finger_");}
    private EvaHandSurfaceR45() {}
}
