import { Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import type { UserPrefs } from "../types";

type Props = {
  onRefresh: () => void;
  onResetOnboarding?: () => void;
  onClearSeen?: () => void;
  prefs?: UserPrefs;
};

export function CaughtUpScreen({ onRefresh, onResetOnboarding, onClearSeen, prefs }: Props) {
  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.badge}>
        <Text style={styles.badgeText}>FEED COMPLETE</Text>
      </View>
      <Text style={styles.title}>You're caught up</Text>
      <Text style={styles.sub}>
        No infinite scroll or filler. All currently available verified stories for your active filters have been viewed.
      </Text>

      {prefs && (
        <View style={styles.filterBox}>
          <Text style={styles.filterTitle}>Active Filters:</Text>
          <Text style={styles.filterText}>
            Location: {prefs.district ? `${prefs.district}, ${prefs.state}` : "All Regions"}
          </Text>
          <Text style={styles.filterText}>
            Categories: {prefs.categories?.length ? prefs.categories.join(", ") : "All"}
          </Text>
        </View>
      )}

      <View style={styles.btnGroup}>
        <Pressable onPress={onRefresh} style={styles.btnPrimary}>
          <Text style={styles.btnPrimaryText}>🔄 Check for New Stories</Text>
        </Pressable>

        {onClearSeen && (
          <Pressable onPress={onClearSeen} style={styles.btnSecondary}>
            <Text style={styles.btnSecondaryText}>👁️ Re-read Seen Stories</Text>
          </Pressable>
        )}

        {onResetOnboarding && (
          <Pressable onPress={onResetOnboarding} style={styles.btnDanger}>
            <Text style={styles.btnDangerText}>⚙️ Reset Onboarding & Clear Preferences</Text>
          </Pressable>
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: "#0B0F14",
    alignItems: "center",
    justifyContent: "center",
    padding: 28,
  },
  badge: {
    backgroundColor: "rgba(124, 219, 213, 0.15)",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
    marginBottom: 16,
  },
  badgeText: {
    color: "#7CDBD5",
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 1.5,
  },
  title: { color: "#F4F7FB", fontSize: 28, fontWeight: "800", textAlign: "center" },
  sub: { color: "#9AA8B8", fontSize: 15, textAlign: "center", marginTop: 12, lineHeight: 22, maxWidth: 360 },
  filterBox: {
    marginTop: 20,
    padding: 14,
    backgroundColor: "#16222F",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#2A3542",
    width: "100%",
    maxWidth: 360,
  },
  filterTitle: { color: "#7CDBD5", fontSize: 12, fontWeight: "700", marginBottom: 4 },
  filterText: { color: "#C5D0DC", fontSize: 13, lineHeight: 18 },
  btnGroup: {
    marginTop: 24,
    gap: 12,
    width: "100%",
    maxWidth: 360,
  },
  btnPrimary: {
    backgroundColor: "#7CDBD5",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
  },
  btnPrimaryText: { color: "#0B0F14", fontWeight: "700", fontSize: 15 },
  btnSecondary: {
    backgroundColor: "#1E2B3A",
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#3A4D62",
  },
  btnSecondaryText: { color: "#F4F7FB", fontWeight: "600", fontSize: 14 },
  btnDanger: {
    backgroundColor: "rgba(247, 37, 133, 0.12)",
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "rgba(247, 37, 133, 0.4)",
  },
  btnDangerText: { color: "#FF70A6", fontWeight: "600", fontSize: 13 },
});
