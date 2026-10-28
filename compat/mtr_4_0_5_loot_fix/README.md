# MTR 4.0.5 cargo-block loot compatibility

MTR 4.0.5 registers the two cargo blocks without matching block items, but their bundled loot tables refer to those absent item IDs. Forge rejects both tables at startup. These empty block-loot overrides preserve the existing no-drop result while removing the invalid references; registered blocks, trains and inventories are unchanged.

The private review world enables this data pack. Remove it when upgrading to a version that supplies valid cargo loot tables.
