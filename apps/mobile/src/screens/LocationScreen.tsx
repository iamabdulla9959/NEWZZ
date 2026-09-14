import { useState } from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { INDIAN_STATES_LIST } from "../types";
import type { UserPrefs } from "../types";

type Props = {
  prefs: UserPrefs;
  onNext: (prefs: UserPrefs) => void;
};

export function LocationScreen({ prefs, onNext }: Props) {
  const [selectedState, setSelectedState] = useState<string>(prefs.state || "");

  return (
    <SafeAreaView style={styles.safe}>
      <Text style={styles.kicker}>Step 1 of 3</Text>
      <Text style={styles.title}>Select Your State</Text>
      <Text style={styles.sub}>
        Pick your State to receive local state updates alongside national and international news reels.
      </Text>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <Text style={styles.label}>Indian States & Union Territories (28+)</Text>
        <View style={styles.chips}>
          {INDIAN_STATES_LIST.map((name) => (
            <Pressable
              key={name}
              onPress={() => setSelectedState(name)}
              style={[styles.chip, selectedState === name && styles.chipOn]}
            >
              <Text style={[styles.chipText, selectedState === name && styles.chipTextOn]}>
                {name}
              </Text>
            </Pressable>
          ))}
        </View>
      </ScrollView>
      <Pressable
        style={[styles.next, !selectedState && styles.nextDisabled]}
        disabled={!selectedState}
        onPress={() => onNext({ ...prefs, state: selectedState })}
      >
        <Text style={styles.nextText}>Next: Choose Interests</Text>
      </Pressable>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: "#2E2910", padding: 20 },
  kicker: { color: "#EB7D00", fontSize: 13, fontWeight: "600" },
  title: { color: "#EBE3A7", fontSize: 28, fontWeight: "700", marginTop: 8 },
  sub: { color: "#EBE3A7", fontSize: 15, marginTop: 8, marginBottom: 16, opacity: 0.8 },
  scroll: { paddingBottom: 24 },
  label: { color: "#EBE3A7", fontSize: 14, marginBottom: 12, marginTop: 4, opacity: 0.9, fontWeight: "600" },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    borderColor: "#2C5745",
    backgroundColor: "rgba(44, 87, 69, 0.3)",
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  chipOn: { backgroundColor: "#EB7D00", borderColor: "#EB7D00" },
  chipText: { color: "#EBE3A7", fontSize: 14 },
  chipTextOn: { color: "#2E2910", fontWeight: "700" },
  next: {
    backgroundColor: "#EB7D00",
    borderRadius: 14,
    paddingVertical: 14,
    alignItems: "center",
    marginTop: 10,
  },
  nextDisabled: { opacity: 0.45 },
  nextText: { color: "#2E2910", fontWeight: "700", fontSize: 16 },
});
