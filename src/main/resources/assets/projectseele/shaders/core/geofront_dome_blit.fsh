#version 150

uniform sampler2D Sampler0;
uniform sampler2D FarDepth;
uniform vec2 FarProjectionZ;
uniform mat4 SceneProjection;

in vec2 texCoord;
out vec4 fragColor;

void main() {
    vec4 color = texture(Sampler0, texCoord);
    if (color.a <= 0.0) discard;

    // Recover the baked fragment's actual eye-space Z. A gate or entity beyond the vanilla fog horizon
    // can still write nearer depth. Do not move the cavern in front of it.
    float ndc = 2.0 * texture(FarDepth, texCoord).r - 1.0;
    float meshZ = -FarProjectionZ.y / (ndc + FarProjectionZ.x);
    vec4 point = SceneProjection * vec4(0.0, 0.0, meshZ, 1.0);
    // Permit coincident terrain faces to replace their fogged colour within two D24 depth units.
    gl_FragDepth = clamp(0.5 * point.z / point.w + 0.5 - 2.0 / 16777215.0, 0.0, 1.0);
    fragColor = color;
}
