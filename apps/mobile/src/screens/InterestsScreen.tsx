import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { toggleCategory } from "../storage";
import { ALL_CATEGORIES, DEFAULT_CATEGORIES } from "../types";
import type { NewsCategory, UserPrefs } from "../types";

type Props = {
  prefs: UserPrefs;
  onDone: (prefs: UserPrefs) => void;
};

function label(cat: NewsCategory): string {
  return cat[0].toUpperCase() + cat.slice(1);
}

export function InterestsScreen({ prefs, onDone }: Props) {
  const [categories, setCategories] = useState<NewsCategory[]>(
    prefs.categories.length ? prefs.categories : [...DEFAULT_CATEGORIES],
  );

  return (
    <SafeAreaView style={styles.safe}>
      <Text style={styles.kicker}>Step 2 of 3</Text>
      <Text style={styles.title}>What do you want to follow?</Text>
      <Text style={styles.sub}>District through Tech are on by default. Science is optional.</Text>
      <View style={styles.chips}>
        {ALL_CATEGORIES.map((chip) => {
          const on = categories.includes(chip);
          return (
            <Pressable
              key={chip}
              onPress={() => setCategories(toggleCategory(categories, chip))}
              style={[styles.chip, on && styles.chipOn]}
            >
              <Text style={[styles.chipText, on && styles.chipTextOn]}>{label(chip)}</Text>
            </Pressable>
          );
        })}
      </View>
      <Pressable
        style={[styles.next, categories.length === 0 && styles.nextDisabled]}
        disabled={categories.length === 0}
        onPress={() => onDone({ ...prefs, categories })}
      >
        <Text style={styles.nextText}>Next: Priority Ranking</Text>
      </Pressable>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: "#2E2910", padding: 20 },
  kicker: { color: "#EB7D00", fontSize: 13, fontWeight: "600" },
  title: { color: "#EBE3A7", fontSize: 28, fontWeight: "700", marginTop: 8 },
  sub: { color: "#EBE3A7", fontSize: 16, marginTop: 8, marginBottom: 24, opacity: 0.8 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 10, flex: 1 },
  chip: {
    borderColor: "#2C5745",
    backgroundColor: "rgba(44, 87, 69, 0.3)",
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  chipOn: { backgroundColor: "#EB7D00", borderColor: "#EB7D00" },
  chipText: { color: "#EBE3A7", fontSize: 16 },
  chipTextOn: { color: "#2E2910", fontWeight: "700" },
  next: {
    backgroundColor: "#EB7D00",
    borderRadius: 14,
    paddingVertical: 14,
    alignItems: "center",
  },
  nextDisabled: { opacity: 0.4 },
  nextText: { color: "#2E2910", fontWeight: "700", fontSize: 16 },
});
