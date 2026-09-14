import { StatusBar } from "expo-status-bar";
import { useEffect, useState } from "react";
import { ActivityIndicator, StyleSheet, View } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { CategoryOrderScreen } from "./src/screens/CategoryOrderScreen";
import { FeedScreen } from "./src/screens/FeedScreen";
import { InterestsScreen } from "./src/screens/InterestsScreen";
import { LocationScreen } from "./src/screens/LocationScreen";
import { clearAllStorage, loadPrefs, savePrefs } from "./src/storage";
import type { UserPrefs } from "./src/types";

type Gate = "boot" | "location" | "interests" | "priority" | "feed";

export default function App() {
  const [gate, setGate] = useState<Gate>("boot");
  const [prefs, setPrefs] = useState<UserPrefs | null>(null);

  const init = async () => {
    // If URL contains ?reset=1 or ?onboard=1, force clear storage to show onboarding flow
    if (typeof window !== "undefined" && window.location?.search) {
      const search = window.location.search.toLowerCase();
      if (search.includes("reset=1") || search.includes("onboard=1")) {
        await clearAllStorage();
        if (window.history?.replaceState) {
          window.history.replaceState({}, document.title, window.location.pathname);
        }
      }
    }
    const loaded = await loadPrefs();
    setPrefs(loaded);
    setGate(loaded.onboarded ? "feed" : "location");
  };

  useEffect(() => {
    void init();
  }, []);

  const handleResetOnboarding = async () => {
    await clearAllStorage();
    const fresh = await loadPrefs();
    setPrefs(fresh);
    setGate("location");
  };

  if (!prefs || gate === "boot") {
    return (
      <View style={styles.boot}>
        <ActivityIndicator color="#EB7D00" />
      </View>
    );
  }

  return (
    <SafeAreaProvider>
      <StatusBar style="light" />
      {gate === "location" ? (
        <LocationScreen
          prefs={prefs}
          onNext={(next) => {
            setPrefs(next);
            setGate("interests");
          }}
        />
      ) : null}
      {gate === "interests" ? (
        <InterestsScreen
          prefs={prefs}
          onDone={(next) => {
            setPrefs(next);
            setGate("priority");
          }}
        />
      ) : null}
      {gate === "priority" ? (
        <CategoryOrderScreen
          prefs={prefs}
          onDone={async (next) => {
            const saved = { ...next, onboarded: true };
            await savePrefs(saved);
            setPrefs(saved);
            setGate("feed");
          }}
        />
      ) : null}
      {gate === "feed" ? (
        <FeedScreen prefs={prefs} onResetOnboarding={handleResetOnboarding} />
      ) : null}
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  boot: {
    flex: 1,
    backgroundColor: "#2E2910",
    alignItems: "center",
    justifyContent: "center",
  },
});
