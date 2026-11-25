#version 150

// Only beyond the vanilla render distance (NearCut, horizontal): nearer, the real chunks are drawn and win.
// Textured faces repeat their sprite once per block (Tile counts blocks across the face); the mip level comes from the
// tiling coordinate's own derivatives, so the wrap at each block edge does not show. Colour alpha 0 = a flat colour.
uniform sampler2D Sampler0;
uniform float NearCut;
uniform float FogStart;
uniform float FogEnd;
uniform vec4 FogColor;
uniform float Light;

in vec2 tile;
flat in vec4 rect;
flat in vec4 colour;
in vec3 relative;

out vec4 fragColor;

void main() {
    if (length(relative.xz) < NearCut) {
        discard;
    }
    vec3 c;
    if (colour.a < 0.5) {
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
