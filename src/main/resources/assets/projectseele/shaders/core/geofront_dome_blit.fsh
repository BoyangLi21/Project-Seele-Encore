#version 150

uniform sampler2D Sampler0;

in vec2 texCoord;

out vec4 fragColor;

void main() {
    vec4 color = texture(Sampler0, texCoord);
    if (color.a < 0.5) {
        discard;
    }
    fragColor = vec4(color.rgb, 1.0);
}
