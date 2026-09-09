import React, { useState } from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { updateUserPreferences } from "../api";
import type { NewsCategory, UserPrefs } from "../types";

type Props = {
  prefs: UserPrefs;
  onDone: (prefs: UserPrefs) => void;
  isSettings?: boolean;
};

const label = (cat: NewsCategory) => cat.charAt(0).toUpperCase() + cat.slice(1);

export function CategoryOrderScreen({ prefs, onDone, isSettings = false }: Props) {
  const initialOrder = prefs.categoryOrder?.length
    ? [
        ...prefs.categoryOrder.filter((c) => prefs.categories.includes(c)),
        ...prefs.categories.filter((c) => !prefs.categoryOrder!.includes(c)),
      ]
    : [...prefs.categories];

  const [order, setOrder] = useState<NewsCategory[]>(initialOrder);
  const [hasReordered, setHasReordered] = useState(!!prefs.categoryOrder?.length);

  const swap = (i: number, j: number) => {
    const next = [...order];
    [next[i], next[j]] = [next[j], next[i]];
    setOrder(next);
    setHasReordered(true);
  };

  const moveUp = (i: number) => i > 0 && swap(i, i - 1);
  const moveDown = (i: number) => i < order.length - 1 && swap(i, i + 1);

  const handleFinish = async () => {
    const categoryOrder = hasReordered ? order : [];
    
    if (prefs.deviceId && hasReordered) {
      try {
        await updateUserPreferences(prefs.deviceId, categoryOrder);
      } catch (e) {
        console.warn("Failed syncing priority preferences", e);
      }
    }

    onDone({ ...prefs, categoryOrder });
  };

  return (
    <SafeAreaView style={styles.safe}>
      <Text style={styles.kicker}>{isSettings ? "Settings" : "Step 3 of 3"}</Text>
      <Text style={styles.title}>Priority Ranking</Text>
      <Text style={styles.sub}>
        Rank topics from highest to lowest priority to personalize your feed order.
      </Text>

      {!hasReordered ? (
        <View style={styles.infoBanner}>
          <Text style={styles.infoTitle}>⚖️ Equal Weight by Default</Text>
          <Text style={styles.infoDesc}>
            All your selected topics currently have equal weight with no hardcoded bias.
            Use the arrows below to set your preferred priority.
          </Text>
        </View>
      ) : (
        <View style={styles.activeBanner}>
          <Text style={styles.activeTitle}>⭐ Custom Priority Active</Text>
          <Text style={styles.activeDesc}>
            Cards from #{1} {label(order[0])} will receive the highest boost in your feed.
          </Text>
        </View>
      )}

      <ScrollView style={styles.list} contentContainerStyle={styles.listContent}>
        {order.map((cat, idx) => {
          const isFirst = idx === 0;
          const isLast = idx === order.length - 1;

          return (
            <View key={cat} style={[styles.itemCard, isFirst && hasReordered && styles.topCard]}>
              <View style={styles.rankBadge}>
                <Text style={styles.rankNumber}>{idx + 1}</Text>
              </View>

              <View style={styles.itemInfo}>
                <Text style={styles.itemTitle}>{label(cat)}</Text>
                <Text style={styles.itemSub}>
                  {hasReordered ? (isFirst ? "Highest Priority" : `Priority Level ${idx + 1}`) : "Equal Weight"}
                </Text>
              </View>

              <View style={styles.controls}>
                <Pressable
                  onPress={() => moveUp(idx)}
                  disabled={isFirst}
                  style={[styles.arrowButton, isFirst && styles.arrowDisabled]}
                  accessibilityLabel={`Move ${label(cat)} up`}
                >
                  <Text style={[styles.arrowText, isFirst && styles.arrowTextDisabled]}>▲</Text>
                </Pressable>
                <Pressable
                  onPress={() => moveDown(idx)}
                  disabled={isLast}
                  style={[styles.arrowButton, isLast && styles.arrowDisabled]}
                  accessibilityLabel={`Move ${label(cat)} down`}
                >
                  <Text style={[styles.arrowText, isLast && styles.arrowTextDisabled]}>▼</Text>
                </Pressable>
              </View>
            </View>
          );
        })}
      </ScrollView>

      <Pressable style={styles.next} onPress={handleFinish}>
        <Text style={styles.nextText}>{isSettings ? "Save Changes" : "Start Reading"}</Text>
      </Pressable>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: "#0B0F14", padding: 20 },
  kicker: { color: "#EB7D00", fontSize: 13, fontWeight: "600" },
  title: { color: "#F4F7FB", fontSize: 28, fontWeight: "700", marginTop: 8 },
  sub: { color: "#9AA8B8", fontSize: 15, marginTop: 8, marginBottom: 16 },
  infoBanner: {
    backgroundColor: "#16222F",
    borderRadius: 10,
    padding: 12,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: "#1E3A4B",
  },
  infoTitle: { color: "#EB7D00", fontSize: 14, fontWeight: "600", marginBottom: 4 },
  infoDesc: { color: "#9AA8B8", fontSize: 13, lineHeight: 18 },
  activeBanner: {
    backgroundColor: "#1E2A20",
    borderRadius: 10,
    padding: 12,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: "#2D5A34",
  },
  activeTitle: { color: "#68D391", fontSize: 14, fontWeight: "600", marginBottom: 4 },
  activeDesc: { color: "#BEE3F8", fontSize: 13, lineHeight: 18 },
  list: { flex: 1 },
  listContent: { gap: 10, paddingBottom: 20 },
  itemCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#141B22",
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: "#222D3D",
  },
  topCard: {
    borderColor: "#EB7D00",
    backgroundColor: "#17232B",
  },
  rankBadge: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: "#1F2B38",
    alignItems: "center",
    justifyContent: "center",
    marginRight: 14,
  },
  rankNumber: { color: "#F4F7FB", fontSize: 15, fontWeight: "700" },
  itemInfo: { flex: 1 },
  itemTitle: { color: "#F4F7FB", fontSize: 17, fontWeight: "600" },
  itemSub: { color: "#6C7D93", fontSize: 13, marginTop: 2 },
  controls: { flexDirection: "row", gap: 8 },
  arrowButton: {
    width: 38,
    height: 38,
    borderRadius: 8,
    backgroundColor: "#1F2B38",
    alignItems: "center",
    justifyContent: "center",
  },
  arrowDisabled: { opacity: 0.3 },
  arrowText: { color: "#EB7D00", fontSize: 16, fontWeight: "700" },
  arrowTextDisabled: { color: "#6C7D93" },
  next: {
    backgroundColor: "#EB7D00",
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: "center",
    marginTop: 10,
  },
  nextText: { color: "#0B0F14", fontSize: 16, fontWeight: "700" },
});
