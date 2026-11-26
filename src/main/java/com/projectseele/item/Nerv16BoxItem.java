package com.projectseele.item;

import com.projectseele.world.NervAirportR21;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.item.BlockItem;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.context.BlockPlaceContext;
import net.minecraft.world.item.context.UseOnContext;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraftforge.registries.ForgeRegistries;

/** Places Superb Warfare's own vehicle container, which handles opening, obstruction and commissioning. */
public final class Nerv16BoxItem extends Item {
    public static final ResourceLocation AIRFRAME = new ResourceLocation("superbwarfare", "j_16");
    private static final ResourceLocation CONTAINER = new ResourceLocation("superbwarfare", "container");

    public Nerv16BoxItem(Properties properties) {
        super(properties);
    }

    public static boolean available() {
        return ForgeRegistries.ITEMS.getValue(CONTAINER) instanceof BlockItem
                && ForgeRegistries.BLOCK_ENTITY_TYPES.containsKey(CONTAINER)
                && ForgeRegistries.ENTITY_TYPES.containsKey(AIRFRAME);
    }

    @Override
    public void appendHoverText(ItemStack stack, net.minecraft.world.level.Level level, java.util.List<Component> lines,
                                net.minecraft.world.item.TooltipFlag flag) {
        lines.add(Component.translatable("tooltip.projectseele.nerv_16_box"));
    }

    @Override
    public InteractionResult useOn(UseOnContext context) {
        var player = context.getPlayer();
        if (player == null) return InteractionResult.PASS;
        if (!available()) {
            if (!context.getLevel().isClientSide) player.displayClientMessage(Component.translatable("message.projectseele.nerv16_requires_sbw"), true);
            return InteractionResult.FAIL;
        }
        var container = (BlockItem) ForgeRegistries.ITEMS.getValue(CONTAINER);
        var nativeStack = new ItemStack(container);
        var data = new CompoundTag();
        data.putString("EntityType", AIRFRAME.toString());
        if (context.getLevel() instanceof ServerLevel level) {
            var jet = ForgeRegistries.ENTITY_TYPES.getValue(AIRFRAME).create(level);
            if (jet == null) return InteractionResult.FAIL;
            NervAirportR21.identifyFighter(jet);
            try {
                var vehicle = NervAirportR21.commissioningData(jet);
                vehicle.remove("UUID");
                data.put("Entity", vehicle);
            } catch (ReflectiveOperationException e) {
                com.projectseele.ProjectSeele.LOGGER.warn("NERV-16 crate cannot read Superb Warfare airframe energy", e);
                return InteractionResult.FAIL;
            }
        }
        BlockItem.setBlockEntityData(nativeStack, ForgeRegistries.BLOCK_ENTITY_TYPES.getValue(CONTAINER), data);
        var hit = new BlockHitResult(context.getClickLocation(), context.getClickedFace(), context.getClickedPos(), context.isInside());
        var result = container.place(new BlockPlaceContext(player, context.getHand(), nativeStack, hit));
        if (result.consumesAction() && !context.getLevel().isClientSide && !player.getAbilities().instabuild)
            context.getItemInHand().shrink(1);
        return result;
    }
}