#version 150

uniform sampler2D NativeDepth;
uniform sampler2D DhDepth;
uniform bool HasDh;
uniform vec2 SceneZ;
uniform vec2 DhToScene;
uniform vec3 Haze;
in vec3 relative;
in vec3 colour;
in float valid;
out vec4 fragColor;

void main() {
    if (valid < 0.9999 || length(relative.xz) > 3072.0) discard;
    ivec2 p = ivec2(gl_FragCoord.xy);
    // The hole can expose a real, already drawn cavern wall hundreds of metres beyond the
    // missing hillside. Compare distances at this pixel, retaining nearer real geometry
    // and giving small surface differences to the full-resolution renderer.
    float eyeDepth = 1.0 / gl_FragCoord.w;
    float retained = eyeDepth + max(12.0, eyeDepth * 0.035);
    float limit = 0.5 * (1.0 - SceneZ.x + SceneZ.y / retained);
    float nativeZ = texelFetch(NativeDepth, p, 0).r;
    if (nativeZ < 1.0 && nativeZ <= limit) discard;
    if (HasDh) {
        float dhZ = texelFetch(DhDepth, p, 0).r;
        if (dhZ < 1.0 && dhZ * DhToScene.x + DhToScene.y <= limit) discard;
    }
    vec3 normal = normalize(cross(dFdx(relative), dFdy(relative)));
    normal *= normal.y < 0.0 ? -1.0 : 1.0;
    float shading = 0.56 + 0.35 * max(0.0, dot(normal, normalize(vec3(-0.4, 0.85, -0.35))));
    float fog = smoothstep(180.0, 3300.0, length(relative));
    fragColor = vec4(mix(colour * shading, Haze, 0.77 * fog), 1.0);
}
