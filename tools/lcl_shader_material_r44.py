"""One material definition for fresh and already-patched Complementary packs."""


def material_patch():
    # User's 2026-09-30 direction supersedes R35's see-through cage water.
    # RGB still comes from the game's LclFluidType tint, before scene lighting.
    return '''    // Project SEELE LCL R44: dense orange-red cage liquid.
    if (mat == 32001) {
        color.a = 242.0 / 255.0;
        translucentMult = vec4(0.070, 0.018, 0.006, 1.0);
        translucentMultCalculated = true;
        reflectMult = 0.12;
        smoothnessG = 0.58;
        highlightMult = 0.28;
    }

'''
