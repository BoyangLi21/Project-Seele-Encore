package com.projectseele.world;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Set;
import java.util.TreeSet;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Stream;

/**
 * R65 owner: with allPlayersAuthorized on (the default), only the gates and the lifts still ask for a NERV card.
 * Read from the sources: the card lanes of nerv_staff_gate and the "nerv_card" MTR barriers ask carriesCard(), which
 * does not look at the config; free (exit) lanes and barriers without a pass row stay free; the HQ card lifts keep their
 * swiped Dogma card; nothing else moved off authorized(). The gates themselves have to be walked through in the game.
 */
public final class NervCardGatesR65Test
{
    private static int checked;

    private static void that(boolean condition, String message)
    {
        if (!condition) throw new AssertionError(message);
        checked++;
    }

    private static String read(String name) throws Exception
    {
        return Files.readString(Path.of("src/main/java/com/projectseele/world/" + name + ".java"), StandardCharsets.UTF_8);
    }

    /** The body of the first method whose declaration contains the given text, braces balanced. */
    private static String body(String source, String declaration)
    {
        int at = source.indexOf(declaration);
        that(at >= 0, "no " + declaration);
        int open = source.indexOf('{', at), depth = 0;
        for (int i = open; i < source.length(); i++)
        {
            char c = source.charAt(i);
            if (c == '{') depth++;
            else if (c == '}' && --depth == 0) return source.substring(open, i + 1);
        }
        throw new AssertionError("unbalanced " + declaration);
    }

    public static void main(String[] args) throws Exception
    {
        String dialogue = read("NervStaffDialogue");
        String card = body(dialogue, "public static boolean carriesCard(ServerPlayer player)");
        that(!card.contains("ALL_PLAYERS_AUTHORIZED") && !card.contains("authorized("), "carriesCard must not consult allPlayersAuthorized");
        that(card.contains("hasPermission(2)"), "an operator (permission 2) passes a card gate");
        that(card.contains("getInventory().items") && card.contains("getInventory().offhand"), "a card anywhere in the inventory or offhand counts");
        that(card.contains("ModItems.NERV_EMPLOYEE_CARD.get()") && card.contains("ModItems.TERMINAL_DOGMA_ACCESS_CARD.get()"), "both NERV cards count");
        String authorized = body(dialogue, "public static boolean authorized(ServerPlayer player)");
        that(authorized.contains("!player.isSpectator()&&com.projectseele.config.SeeleConfig.ALL_PLAYERS_AUTHORIZED.get())return true;")
                && authorized.contains("return carriesCard(player);"), "authorized() keeps the config bypass in front of the card check");

        String gate = read("NervStaffGateEntityR65");
        that(!gate.contains("authorized("), "the staff gate must not ask authorized()");
        that(gate.contains("if (!card || e instanceof NervStaffEntity || NervStaffDialogue.carriesCard((ServerPlayer) e))"),
                "a card lane opens for staff or a card holder; a free lane (card=false) for anyone");
        that(gate.contains("Component.translatable(\"message.projectseele.surface.card\")"), "the refusal text is the old one");

        String barriers = read("PublicStationGatesR44");
        that(!barriers.contains("NervStaffDialogue.authorized("), "the MTR card barriers must not ask authorized()");
        that(Pattern.compile("CARD_GATES\\.getOrDefault\\(level\\.getServer\\(\\), Set\\.of\\(\\)\\)\\.contains\\(position\\)\\s*&& !NervStaffDialogue\\.carriesCard\\(player\\)\\)")
                .matcher(barriers).find(), "only barriers listed with \"pass\": \"nerv_card\" ask for the card");
        that(barriers.contains("if (row.has(\"pass\"))") && barriers.contains("card.add(new BlockPos(position[0], position[1], position[2]));"),
                "a barrier is a card barrier only through its pass row");
        that(barriers.contains(".translatable(\"message.projectseele.surface.card\")"), "the barrier's refusal text is the old one");

        // The HQ card lifts never followed allPlayersAuthorized: the swipe and the restricted floors need the Dogma card in hand.
        for (String lift : new String[]{"SeeleConferenceAccessR47", "S20MovingElevatorsAdapter", "S20LiftDirectoryR52", "NervAccessReaderR44", "NervAccessReaderEntityR44"})
        {
            String source = read(lift);
            that(!source.contains("authorized(") && !source.contains("carriesCard(") && !source.contains("ALL_PLAYERS_AUTHORIZED"), lift + " must keep its physical card check");
        }
        that(read("SeeleConferenceAccessR47").contains("instanceof NervAccessCardR44 card && card.clearance() >= 3"), "the office reader takes a Dogma card in hand");
        that(body(read("S20MovingElevatorsAdapter"), "private static boolean hasHighestClearanceCard(Player player)").contains("ModItems.TERMINAL_DOGMA_ACCESS_CARD.get()"),
                "restricted floors open for the Dogma card");

        // Only the two gates use the card-only check; every other authorized() caller is unchanged.
        Set<String> cardCallers = new TreeSet<>(), authorizedCallers = new TreeSet<>();
        try (Stream<Path> files = Files.walk(Path.of("src/main/java")))
        {
            for (Path file : (Iterable<Path>) files.filter(p -> p.toString().endsWith(".java"))::iterator)
            {
                String source = Files.readString(file, StandardCharsets.UTF_8), name = file.getFileName().toString().replace(".java", "");
                if (source.contains("NervStaffDialogue.carriesCard(")) cardCallers.add(name);
                Matcher call = Pattern.compile("NervStaffDialogue\\.authorized\\(").matcher(source);
                if (call.find()) authorizedCallers.add(name);
            }
        }
        that(cardCallers.equals(Set.of("NervStaffGateEntityR65", "PublicStationGatesR44")), "card-only callers: " + cardCallers);
        for (String kept : new String[]{"FacilityDoorControlsR49", "StaffPilotOrdersR25", "TvMissionEquipmentR45", "TvSortiesR32", "AutoSortieR32", "StaffConversationR24", "TvCampaignDirector"})
            that(authorizedCallers.contains(kept), kept + " (doors, formations, equipment, sorties, phone) must keep authorized()");
        System.out.println("NervCardGatesR65Test: " + checked + " checks passed.");
    }
}
