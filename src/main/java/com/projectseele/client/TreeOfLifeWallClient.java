package com.projectseele.client;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

import com.mojang.blaze3d.platform.NativeImage;
import com.projectseele.ProjectSeele;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.texture.DynamicTexture;
import net.minecraft.resources.ResourceLocation;

/**
 * Local image plates used by the command room and commander's office.
 *
 * <p>The image is read from the game directory rather than the mod jar, so the
 * plate can be replaced without a rebuild and no third-party artwork is
 * committed to this repository.  Drop the file at
 * {@code projectseele-local-maps/tree_of_life.png} and
 * {@code projectseele-local-maps/nerv_logo.png}; if either is absent only that
 * plate is omitted and its authored wall remains visible.</p>
 */
public final class TreeOfLifeWallClient
{
    private static final Path TREE_SOURCE = Paths.get(
            "projectseele-local-maps", "tree_of_life.png");
    private static final Path NERV_SOURCE = Paths.get(
            "projectseele-local-maps", "nerv_logo.png");
    private static final Path NERV_REFINED = Paths.get("projectseele-local-maps", "nerv_logo_r04.png");
    private static final ResourceLocation TREE_TEXTURE_ID = new ResourceLocation(
            ProjectSeele.MODID, "dynamic/tree_of_life_wall");
    private static final ResourceLocation NERV_TEXTURE_ID = new ResourceLocation(
            ProjectSeele.MODID, "dynamic/nerv_logo_wall");

    private static float treeImageAspect = 0.75F;
    private static float nervImageAspect = 1.0F;

    private static DynamicTexture treeTexture,treeInkTexture;
    private static final ResourceLocation TREE_INK_TEXTURE_ID=new ResourceLocation(ProjectSeele.MODID,"dynamic/tree_of_life_ink_r52");
    private static boolean treeInkChecked;
    private static float treeInkAspect=.75F;
    private static DynamicTexture nervTexture;
    private static boolean treeSourceChecked;
    private static boolean nervSourceChecked;

    private TreeOfLifeWallClient() {}




    private static boolean ensureTreeTexture(Minecraft minecraft)
    {
        if (treeTexture != null)
        {
            return true;
        }
        if (treeSourceChecked)
        {
            return false;
        }
        treeSourceChecked = true;
        if (!Files.isRegularFile(TREE_SOURCE))
        {
            ProjectSeele.LOGGER.info(
                    "Tree-of-life wall idle: no image at {}", TREE_SOURCE);
            return false;
        }
        try (InputStream stream = Files.newInputStream(TREE_SOURCE))
        {
            NativeImage image = NativeImage.read(stream);
            // Derive the plate from the image rather than stretching the
            // image to a guessed plate: a different scan can be dropped in
            // later without it going oval.
            treeImageAspect = image.getWidth() / (float) image.getHeight();
            treeTexture = new DynamicTexture(image);
            minecraft.getTextureManager().register(
                    TREE_TEXTURE_ID, treeTexture);
            ProjectSeele.LOGGER.info(
                    "Tree-of-life walls loaded {}x{} from {}",
                    image.getWidth(), image.getHeight(), TREE_SOURCE);
            return true;
        }
        catch (IOException | RuntimeException exception)
        {
            ProjectSeele.LOGGER.error(
                    "Tree-of-life wall image unreadable", exception);
            return false;
        }
    }

    /** White ink with coverage alpha; original image/tree texture and all files remain unchanged. */
    public static int treeInkPixelR52(int pixel)
    {
        int red=pixel&255,green=pixel>>>8&255,blue=pixel>>>16&255,alpha=pixel>>>24;
        int luminance=(54*red+183*green+19*blue+128)>>>8;
        int coverage=Math.max(0,245-luminance)*255/245;
        return (alpha*coverage/255)<<24|0x00ffffff;
    }
    private static boolean ensureTreeInkR52(Minecraft minecraft)
    {
        if(treeInkTexture!=null)return true;if(treeInkChecked)return false;treeInkChecked=true;
        if(!Files.isRegularFile(TREE_SOURCE))return false;
        try(InputStream stream=Files.newInputStream(TREE_SOURCE))
        {
            var image=NativeImage.read(stream);treeInkAspect=image.getWidth()/(float)image.getHeight();
            for(int y=0;y<image.getHeight();y++)for(int x=0;x<image.getWidth();x++)image.setPixelRGBA(x,y,treeInkPixelR52(image.getPixelRGBA(x,y)));
            treeInkTexture=new DynamicTexture(image);minecraft.getTextureManager().register(TREE_INK_TEXTURE_ID,treeInkTexture);return true;
        }
        catch(IOException|RuntimeException error){ProjectSeele.LOGGER.warn("Local tree ink image unavailable",error);return false;}
    }

    private static boolean ensureNervTexture(Minecraft minecraft)
    {
        if (nervTexture != null)
        {
            return true;
        }
        if (nervSourceChecked)
        {
            return false;
        }
        nervSourceChecked = true;
        if (!Files.isRegularFile(NERV_SOURCE))
        {
            ProjectSeele.LOGGER.info(
                    "NERV office wall idle: no image at {}", NERV_SOURCE);
            return false;
        }
        try (InputStream stream = Files.newInputStream(Files.isRegularFile(NERV_REFINED) ? NERV_REFINED : NERV_SOURCE))
        {
            NativeImage image = NativeImage.read(stream);
            removeBakedCheckerboard(image);
            nervImageAspect = image.getWidth() / (float) image.getHeight();
            nervTexture = new DynamicTexture(image);
            minecraft.getTextureManager().register(
                    NERV_TEXTURE_ID, nervTexture);
            ProjectSeele.LOGGER.info(
                    "NERV office wall loaded {}x{} from {}",
                    image.getWidth(), image.getHeight(), NERV_SOURCE);
            return true;
        }
        catch (IOException | RuntimeException exception)
        {
            ProjectSeele.LOGGER.error(
                    "NERV office wall image unreadable", exception);
            return false;
        }
    }

    /** Shared local-only logo texture for moving NERV machinery. */
    public static ResourceLocation nervLogoTexture(Minecraft minecraft)
    {
        return ensureNervTexture(minecraft) ? NERV_TEXTURE_ID : null;
    }
    public static ResourceLocation artworkTexture(String artwork)
    {
        Minecraft mc=Minecraft.getInstance();
        return artwork.equals("tree_ink")?(ensureTreeInkR52(mc)?TREE_INK_TEXTURE_ID:null):artwork.equals("tree")?(ensureTreeTexture(mc)?TREE_TEXTURE_ID:null):nervLogoTexture(mc);
    }
    public static float artworkAspect(String artwork)
    {return artwork.equals("tree_ink")?treeInkAspect:artwork.equals("tree")?treeImageAspect:nervImageAspect;}

    /**
     * The supplied logo has a light checkerboard baked into its RGB pixels.
     * Remove only nearly neutral light pixels at load time, preserving the
     * original red artwork and its antialiased edge over the black wall.
     */
    private static void removeBakedCheckerboard(NativeImage image)
    {
        for (int y = 0; y < image.getHeight(); y++)
        {
            for (int x = 0; x < image.getWidth(); x++)
            {
                int pixel = image.getPixelRGBA(x, y);
                // NativeImage#getPixelRGBA uses native ABGR ordering.
                int red = pixel & 0xFF;
                int green = pixel >> 8 & 0xFF;
                int blue = pixel >> 16 & 0xFF;
                int brightest = Math.max(red, Math.max(green, blue));
                int darkest = Math.min(red, Math.min(green, blue));
                if (brightest >= 180 && brightest - darkest <= 48)
                {
                    image.setPixelRGBA(x, y, 0);
                }
            }
        }
    }

    /** Forces a re-read after the file on disk has been replaced. */
    public static void reload()
    {
        if (treeTexture != null)
        {
            Minecraft.getInstance().getTextureManager().release(
                    TREE_TEXTURE_ID);
            treeTexture.close();
            treeTexture = null;
        }
        if (nervTexture != null)
        {
            Minecraft.getInstance().getTextureManager().release(
                    NERV_TEXTURE_ID);
            nervTexture.close();
            nervTexture = null;
        }
        treeSourceChecked = false;
        nervSourceChecked = false;
    }


}
