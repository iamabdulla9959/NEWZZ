import { Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import type { UserPrefs } from "../types";

type Props = {
  onRefresh: () => void;
  onResetOnboarding?: () => void;
  onClearSeen?: () => void;
  prefs?: UserPrefs;
  fallbackLevel?: string | null;
  emptyReason?: string | null;
};

export function CaughtUpScreen({ onRefresh, onResetOnboarding, onClearSeen, prefs, fallbackLevel, emptyReason }: Props) {
  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.badge}>
        <Text style={styles.badgeText}>FEED COMPLETE</Text>
      </View>
      <Text style={styles.title}>You're caught up</Text>
      {fallbackLevel ? (
        <Text style={styles.sub}>
          No more {fallbackLevel} news available. We checked for your local district first, but there was no verified local news today.
        </Text>
      ) : (
        <Text style={styles.sub}>
          {emptyReason === "no_eligible_stories"
            ? "There are no verified stories matching these interests and location right now. Try another category or check again later."
            : "No infinite scroll or filler. All currently available verified stories for your active filters have been viewed."}
        </Text>
      )}

      {prefs && (
        <View style={styles.filterBox}>
          <Text style={styles.filterTitle}>Active Filters:</Text>
          <Text style={styles.filterText}>
            Location: {prefs.state || "All Regions"}
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
    backgroundColor: "#2E2910",
    alignItems: "center",
    justifyContent: "center",
    padding: 28,
  },
  badge: {
    backgroundColor: "rgba(44, 87, 69, 0.3)",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
    marginBottom: 16,
  },
  badgeText: {
    color: "#EBE3A7",
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 1.5,
  },
  title: { color: "#EBE3A7", fontSize: 28, fontWeight: "800", textAlign: "center" },
  sub: { color: "#EBE3A7", fontSize: 15, textAlign: "center", marginTop: 12, lineHeight: 22, maxWidth: 360, opacity: 0.8 },
  filterBox: {
    marginTop: 20,
    padding: 14,
    backgroundColor: "rgba(44, 87, 69, 0.2)",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#2C5745",
    width: "100%",
    maxWidth: 360,
  },
  filterTitle: { color: "#EB7D00", fontSize: 12, fontWeight: "700", marginBottom: 4 },
  filterText: { color: "#EBE3A7", fontSize: 13, lineHeight: 18 },
  btnGroup: {
    marginTop: 24,
    gap: 12,
    width: "100%",
    maxWidth: 360,
  },
  btnPrimary: {
    backgroundColor: "#EB7D00",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
  },
  btnPrimaryText: { color: "#2E2910", fontWeight: "700", fontSize: 15 },
  btnSecondary: {
    backgroundColor: "rgba(44, 87, 69, 0.3)",
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#2C5745",
  },
  btnSecondaryText: { color: "#EBE3A7", fontWeight: "600", fontSize: 14 },
  btnDanger: {
    backgroundColor: "rgba(235,125,0,0.12)",
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "rgba(235,125,0,0.4)",
  },
  btnDangerText: { color: "#EBE3A7", fontWeight: "600", fontSize: 13 },
});

