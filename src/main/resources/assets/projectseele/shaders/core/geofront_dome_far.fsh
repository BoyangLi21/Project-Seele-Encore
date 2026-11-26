#version 150

// Only beyond the vanilla render distance (NearCut) in three dimensions: the terrain renderer leaves out sections past its
// fog distance in 3D too, so the floor far below a camera high in the cavity is not drawn though it lies within the
// horizontal render distance (R65 feedback 2, item 37). Wherever the real chunks are drawn, they win.
// Textured faces repeat their sprite once per block (Tile counts blocks across the face); the mip level comes from the
// tiling coordinate's own derivatives, so the wrap at each block edge does not show. Colour alpha 0 = a flat colour.
uniform sampler2D Sampler0;
uniform float NearCut;
uniform float FogStart;
uniform float FogEnd;
uniform vec4 FogColor;
uniform float Light;
// rgb: the lake's colour under a shader pack; a = 1 to use it (water faces carry colour alpha 0.5)
uniform vec4 Water;

in vec2 tile;
flat in vec4 rect;
flat in vec4 colour;
in vec3 relative;

out vec4 fragColor;

void main() {
    if (length(relative) < NearCut) {
        discard;
    }
    vec3 c;
    if (colour.a > 0.25 && colour.a < 0.75) {
        c = Water.a > 0.5 ? Water.rgb : colour.rgb;
    } else if (colour.a < 0.25) {
        c = colour.rgb;
    } else {
        vec2 size = rect.zw - rect.xy;
        vec4 t = textureGrad(Sampler0, rect.xy + fract(tile) * size, dFdx(tile) * size, dFdy(tile) * size);
        if (t.a < 0.1) {
            discard;
        }
        c = t.rgb * colour.rgb;
    }
    c *= Light;
    float fog = smoothstep(FogStart, FogEnd, length(relative));
    fragColor = vec4(mix(c, FogColor.rgb, fog * FogColor.a), 1.0);
}
