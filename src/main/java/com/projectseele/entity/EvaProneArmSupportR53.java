package com.projectseele.entity;

import com.projectseele.world.EvaOriginalMeshGeometryR52;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Support the original elbow surfaces without moving the shoulders or palms. */
public final class EvaProneArmSupportR53
{
    private static final Map<Integer,EvaOriginalMeshGeometryR52.ProneArmSurfacesR53> SOURCES=new HashMap<>();

    public static void apply(EvaUnit01Entity e,EvaBodyPose.Sample pose,float partial)
    {
        if(!EvaProneLegSupportR52.eligible(e,partial))return;
        apply(e.getUnitVariant(),pose,e.rifleStanceLevel(partial),EvaTerrainSupport.sample(e));
    }

    public static void apply(int variant,EvaBodyPose.Sample pose,float stance,Vector3f terrain)
    {
        if(variant<0||variant>2||stance<=1)return;
        var source=source(variant);
        var normal=new Quaternionf().rotationX(terrain.x).rotateZ(terrain.y).transform(new Vector3f(0,1,0));
        float plane=normal.y*terrain.z/EvaScale.RENDER_SCALE;
        // Elbow skin follows the common swivel exactly. Wrist skin also
        // follows the fixed hand, so re-evaluate that seam after correction.
        for(int pass=0;pass<3;pass++)
        {
            var surfaces=source.localSurfaces(pose);boolean changed=false;
            for(String side:List.of("l","r"))
                changed|=EvaProneLegSupportR52.supportChain(pose,surfaces,"arm_"+side,"forearm_"+side,"hand_"+side,
                        side.equals("l")?1:-1,0,normal,plane);
            if(!changed)break;
        }
    }

    private static synchronized EvaOriginalMeshGeometryR52.ProneArmSurfacesR53 source(int variant)
    {
        var cached=SOURCES.get(variant);if(cached!=null)return cached;
        // This also verifies the selected original model against its support
        // contract. Read that same model once, never a historical authoring file.
        EvaProneLegSupportR52.sourceVerticesR52(variant);
        try
        {
            cached=EvaOriginalMeshGeometryR52.loadProneArmSurfacesR53(variant);
            SOURCES.put(variant,cached);return cached;
        }
        catch(Exception failure){throw new IllegalStateException("Original arm support could not load",failure);}
    }

    private EvaProneArmSupportR53(){}
}
