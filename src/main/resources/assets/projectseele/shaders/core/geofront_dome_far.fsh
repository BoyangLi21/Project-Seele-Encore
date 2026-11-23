#version 150

// Only beyond the vanilla render distance (NearCut, horizontal): nearer, the real chunks are drawn and win.
uniform vec4 ColorModulator;
uniform float FogStart;
uniform float FogEnd;
uniform vec4 FogColor;
uniform float NearCut;

in vec4 vertexColor;
in vec3 relative;

out vec4 fragColor;

void main() {
    if (length(relative.xz) < NearCut) {
        discard;
    }
    vec4 colour = vertexColor * ColorModulator;
    float fog = smoothstep(FogStart, FogEnd, length(relative));
    fragColor = vec4(mix(colour.rgb, FogColor.rgb, fog * FogColor.a), 1.0);
}
