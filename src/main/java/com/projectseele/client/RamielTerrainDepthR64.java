package com.projectseele.client;

import com.projectseele.ProjectSeele;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import org.joml.Matrix4f;
import org.joml.Matrix4fc;
import org.lwjgl.opengl.GL;
import static org.lwjgl.opengl.GL33C.*;

/** Lend the current world depth attachment the opaque DH surface for the distant Angel draw. */
public final class RamielTerrainDepthR64
{
    private static Object terrainPass;
    private static Field projection, m22, m23;
    private static Method depthTexture;
    private static boolean unavailable, reported;
    private static int program, vao, frameBuffer, sampler, sizeUniform, transformUniform, restoringUniform;
    private static int before, after, width, height, worldDepth, dhDepth;
    private static float scale, offset;

    private static float shaderProjectionA, shaderProjectionB;
    public static void newFrame() { terrainPass = null; shaderProjectionB = 0; }
    public static void observeShaderProjection(Matrix4fc actual)
    {
        if (actual.m23() == -1F && !com.projectseele.client.render.ShaderShadowPassR44.active()) {
            shaderProjectionA = actual.m22();
            shaderProjectionB = actual.m32();
        }
    }

    public static void observe(Object parameters) { terrainPass = parameters; }

    static DepthSample sample(Matrix4f worldProjection)
    {
        if (terrainPass == null || unavailable || !GL.getCapabilities().OpenGL33) return null;
        try {
            if (projection == null) {
                projection = terrainPass.getClass().getField("dhProjectionMatrix");
                m22 = projection.getType().getField("m22");
                m23 = projection.getType().getField("m23");
                depthTexture = Class.forName("com.seibel.distanthorizons.core.render.renderer.LodRenderer")
                        .getMethod("getActiveDepthTextureId");
            }
            Object dh = projection.get(terrainPass);
            // Oculus 1.8 rebuilds the projection from the event clip distances.
            // DH 2.3.4-b can clamp only the matrix near plane to 7.5 blocks. Use
            // the projection supplied to the program that actually wrote this depth.
            float dhA = shaderProjectionB < 0F ? shaderProjectionA : m22.getFloat(dh);
            float dhB = shaderProjectionB < 0F ? shaderProjectionB : m23.getFloat(dh);
            if (!(dhB < 0 && worldProjection.m32() < 0 && worldProjection.m23() == -1)) return null;
            int dhDepth = (int) depthTexture.invoke(null);
            if (dhDepth <= 0) return null;
            // Both depth functions are affine in reciprocal eye-space Z.
            double ratio = worldProjection.m32() / (double) dhB;
            float scale = (float) ratio;
            float offset = (float) ((1.0 - worldProjection.m22() + ratio * (dhA - 1.0)) * 0.5);
            if (!Float.isFinite(scale) || !Float.isFinite(offset)) return null;

            return new DepthSample(dhDepth, scale, offset);
        } catch (ReflectiveOperationException | LinkageError | IllegalStateException failure) {
            unavailable = true;
            ProjectSeele.LOGGER.warn("Could not read distant terrain depth", failure);
            return null;
        }
    }

    record DepthSample(int texture, float scale, float offset) {}

    public static boolean beginScenery(Matrix4f projection)
    {
        return !GiantFarViewR61.usingTerrainDepth() && begin(projection);
    }

    static boolean begin(Matrix4f worldProjection)
    {
        DepthSample sample = sample(worldProjection);
        if (sample == null) return false;
        dhDepth = sample.texture();
        scale = sample.scale();
        offset = sample.offset();
        try {
            try (State state = new State()) {
                if (state.draw == 0 || glGetFramebufferAttachmentParameteri(GL_DRAW_FRAMEBUFFER, GL_DEPTH_ATTACHMENT,
                        GL_FRAMEBUFFER_ATTACHMENT_OBJECT_TYPE) != GL_TEXTURE) return false;
                worldDepth = glGetFramebufferAttachmentParameteri(GL_DRAW_FRAMEBUFFER, GL_DEPTH_ATTACHMENT,
                        GL_FRAMEBUFFER_ATTACHMENT_OBJECT_NAME);
                if (worldDepth == dhDepth) return false;
                int[] view = new int[4];
                glGetIntegerv(GL_VIEWPORT, view);
                if (view[0] != 0 || view[1] != 0 || view[2] == 0 || view[3] == 0) return false;
                if (program == 0) initialize();
                glBindFramebuffer(GL_FRAMEBUFFER, frameBuffer);
                glFramebufferTexture2D(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_TEXTURE_2D, worldDepth, 0);
                if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE) return false;
                allocate(view[2], view[3]);
                copyDepth(before);
                pass(false);
                if (!reported) {
                    reported = true;
                    ProjectSeele.LOGGER.info("Ramiel terrain depth active: {}x{}, LOD texture {}, projection scale {}",
                            width, height, dhDepth, scale);
                }
                return true;
            }
        } catch (LinkageError | IllegalStateException e) {
            unavailable = true;
            ProjectSeele.LOGGER.warn("Could not read distant terrain depth for Ramiel", e);
            return false;
        }
    }

    public static void end()
    {
        try (State state = new State()) {
            glBindFramebuffer(GL_FRAMEBUFFER, frameBuffer);
            copyDepth(after);
            pass(true);
            // The world renderer owns the depth texture and may replace it on resize or pack reload.
            glFramebufferTexture2D(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_TEXTURE_2D, 0, 0);
        }
    }

    private static void copyDepth(int target)
    {
        glActiveTexture(GL_TEXTURE0);
        glBindTexture(GL_TEXTURE_2D, target);
        glCopyTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, 0, 0, width, height);
    }

    private static void pass(boolean restore)
    {
        glUseProgram(program);
        glBindVertexArray(vao);
        glUniform2f(sizeUniform, width, height);
        glUniform2f(transformUniform, scale, offset);
        glUniform1i(restoringUniform, restore ? 1 : 0);
        bind(0, dhDepth);
        bind(1, before);
        bind(2, after);
        glDisable(GL_CULL_FACE);
        glDisable(GL_STENCIL_TEST);
        glDisable(GL_POLYGON_OFFSET_FILL);
        glEnable(GL_DEPTH_TEST);
        glDepthMask(true);
        glDepthFunc(restore ? GL_ALWAYS : GL_LESS);
        glDrawArrays(GL_TRIANGLES, 0, 3);
    }

    private static void bind(int index, int texture)
    {
        glActiveTexture(GL_TEXTURE0 + index);
        glBindTexture(GL_TEXTURE_2D, texture);
        glBindSampler(index, sampler);
    }

    private static void allocate(int w, int h)
    {
        if (width == w && height == h) return;
        glActiveTexture(GL_TEXTURE0);
        for (int texture : new int[] {before, after}) {
            glBindTexture(GL_TEXTURE_2D, texture);
            glTexImage2D(GL_TEXTURE_2D, 0, GL_DEPTH_COMPONENT32F, w, h, 0, GL_DEPTH_COMPONENT, GL_FLOAT, 0L);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAX_LEVEL, 0);
        }
        width = w;
        height = h;
    }

    private static void initialize()
    {
        int vs = compile(GL_VERTEX_SHADER, """
                #version 150
                void main() {
                    vec2 corner = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
                    gl_Position = vec4(corner * 2.0 - 1.0, 0.0, 1.0);
                }
                """);
        int fs = compile(GL_FRAGMENT_SHADER, """
                #version 150
                uniform sampler2D lod, original, drawn;
                uniform vec2 viewportSize, depthTransform;
                uniform bool restore;
                void main() {
                    float d = texture(lod, gl_FragCoord.xy / viewportSize).r;
                    if (d >= 1.0) discard;
                    float terrain = depthTransform.x * d + depthTransform.y;
                    if (terrain < 0.0 || terrain >= 1.0) discard;
                    if (!restore) { gl_FragDepth = terrain; return; }
                    ivec2 pixel = ivec2(gl_FragCoord.xy);
                    float old = texelFetch(original, pixel, 0).r;
                    float post = texelFetch(drawn, pixel, 0).r;
                    // Undo only the temporary terrain write. Keep closer native and Angel fragments.
                    if (old <= terrain || abs(post - terrain) > 0.00000006) discard;
                    gl_FragDepth = old;
                }
                """);
        program = glCreateProgram();
        glAttachShader(program, vs);
        glAttachShader(program, fs);
        glLinkProgram(program);
        glDeleteShader(vs);
        glDeleteShader(fs);
        if (glGetProgrami(program, GL_LINK_STATUS) == GL_FALSE)
            throw new IllegalStateException(glGetProgramInfoLog(program));
        glUseProgram(program);
        glUniform1i(glGetUniformLocation(program, "lod"), 0);
        glUniform1i(glGetUniformLocation(program, "original"), 1);
        glUniform1i(glGetUniformLocation(program, "drawn"), 2);
        sizeUniform = glGetUniformLocation(program, "viewportSize");
        transformUniform = glGetUniformLocation(program, "depthTransform");
        restoringUniform = glGetUniformLocation(program, "restore");
        vao = glGenVertexArrays();
        sampler = glGenSamplers();
        glSamplerParameteri(sampler, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
        glSamplerParameteri(sampler, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
        before = glGenTextures();
        after = glGenTextures();
        frameBuffer = glGenFramebuffers();
        glBindFramebuffer(GL_FRAMEBUFFER, frameBuffer);
        glDrawBuffer(GL_NONE);
        glReadBuffer(GL_NONE);
    }

    private static int compile(int type, String source)
    {
        int id = glCreateShader(type);
        glShaderSource(id, source);
        glCompileShader(id);
        if (glGetShaderi(id, GL_COMPILE_STATUS) == GL_FALSE) {
            String log = glGetShaderInfoLog(id);
            glDeleteShader(id);
            throw new IllegalStateException(log);
        }
        return id;
    }

    /** Iris and RenderSystem cache GL state. Restore every binding changed by our private pass. */
    private static final class State implements AutoCloseable
    {
        final int draw = glGetInteger(GL_DRAW_FRAMEBUFFER_BINDING), read = glGetInteger(GL_READ_FRAMEBUFFER_BINDING);
        final int shader = glGetInteger(GL_CURRENT_PROGRAM), array = glGetInteger(GL_VERTEX_ARRAY_BINDING);
        final int active = glGetInteger(GL_ACTIVE_TEXTURE), func = glGetInteger(GL_DEPTH_FUNC);
        final boolean mask = glGetBoolean(GL_DEPTH_WRITEMASK), depth = glIsEnabled(GL_DEPTH_TEST),
                cull = glIsEnabled(GL_CULL_FACE), stencil = glIsEnabled(GL_STENCIL_TEST),
                polygonOffset = glIsEnabled(GL_POLYGON_OFFSET_FILL);
        final int[] textures = new int[3], samplers = new int[3];

        State() {
            for (int i = 0; i < 3; i++) {
                glActiveTexture(GL_TEXTURE0 + i);
                textures[i] = glGetInteger(GL_TEXTURE_BINDING_2D);
                samplers[i] = glGetIntegeri(GL_SAMPLER_BINDING, i);
            }
        }
        public void close() {
            for (int i = 0; i < 3; i++) {
                glActiveTexture(GL_TEXTURE0 + i);
                glBindTexture(GL_TEXTURE_2D, textures[i]);
                glBindSampler(i, samplers[i]);
            }
            glActiveTexture(active);
            glBindFramebuffer(GL_DRAW_FRAMEBUFFER, draw);
            glBindFramebuffer(GL_READ_FRAMEBUFFER, read);
            glUseProgram(shader);
            glBindVertexArray(array);
            glDepthFunc(func);
            glDepthMask(mask);
            set(GL_DEPTH_TEST, depth);
            set(GL_CULL_FACE, cull);
            set(GL_STENCIL_TEST, stencil);
            set(GL_POLYGON_OFFSET_FILL, polygonOffset);
        }
        private static void set(int cap, boolean enabled) {
            if (enabled) glEnable(cap); else glDisable(cap);
        }
    }

    private RamielTerrainDepthR64() {}
}
