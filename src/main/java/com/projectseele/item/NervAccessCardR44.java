package com.projectseele.item;

import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.UseAnim;

/** The same persistent item ids now carry an explicit clearance and a short card presentation. */
public final class NervAccessCardR44 extends Item
{
    private final int clearance;
    public NervAccessCardR44(Properties properties,int clearance){super(properties);this.clearance=clearance;}
    public int clearance(){return clearance;}
    @Override public int getUseDuration(ItemStack stack){return 12;}
    @Override public UseAnim getUseAnimation(ItemStack stack){return UseAnim.NONE;}
    @Override public void initializeClient(java.util.function.Consumer<net.minecraftforge.client.extensions.common.IClientItemExtensions> consumer)
    {consumer.accept(new com.projectseele.client.NervCardPresentationR44());}
}
