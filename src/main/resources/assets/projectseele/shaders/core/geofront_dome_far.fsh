#version 150

// Far faces overlap the outer portion of the real terrain. The resolved depth selects the visible surface.
// Textures repeat once per block, using the unwrapped tiling coordinate to choose the mip level.
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
flat in vec3 meanTexel;
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
        vec2 dx = dFdx(tile), dy = dFdy(tile);
        float footprint = max(length(dx), length(dy));
        // At a one-block pixel footprint the last atlas mip borders adjacent sprites. Converge on the actual
        // sprite's opaque texel mean and retain the baked silhouette as its cutout detail becomes subpixel.
        float meanWeight = smoothstep(0.25, 1.0, footprint);
        vec4 texel = textureGrad(Sampler0, rect.xy + fract(tile) * size, dx * size, dy * size);
        if (mix(texel.a, 1.0, meanWeight) < 0.1) discard;
        c = mix(texel.rgb, meanTexel, meanWeight) * colour.rgb;
    }
    c *= Light;
    float fog = smoothstep(FogStart, FogEnd, length(relative));
    fragColor = vec4(mix(c, FogColor.rgb, fog * FogColor.a), 1.0);
}
