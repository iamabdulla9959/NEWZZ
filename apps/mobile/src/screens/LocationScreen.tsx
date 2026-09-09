import { useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import * as Location from "expo-location";

import { INDIAN_STATES } from "../types";
import type { UserPrefs } from "../types";

type Props = {
  prefs: UserPrefs;
  onNext: (prefs: UserPrefs) => void;
};

export function LocationScreen({ prefs, onNext }: Props) {
  const [stateName, setStateName] = useState(prefs.state || Object.keys(INDIAN_STATES)[0]);
  const districts = useMemo(() => INDIAN_STATES[stateName] ?? [], [stateName]);
  const [district, setDistrict] = useState(prefs.district || districts[0]);
  
  const [loading, setLoading] = useState(false);
  const [useFallback, setUseFallback] = useState(false);

  const requestLocation = async () => {
    setLoading(true);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        setUseFallback(true);
        setLoading(false);
        return;
      }

      const location = await Location.getCurrentPositionAsync({});
      const geocode = await Location.reverseGeocodeAsync({
        latitude: location.coords.latitude,
        longitude: location.coords.longitude,
      });

      if (geocode && geocode.length > 0) {
        const place = geocode[0];
        const stateFound = place.region || place.adminArea;
        const districtFound = place.subregion || place.city;
        
        onNext({ 
          ...prefs, 
          state: stateFound || stateName, 
          district: districtFound || district 
        });
      } else {
        onNext({ ...prefs, state: stateName, district });
      }
    } catch (e) {
      console.warn("Location error", e);
      onNext({ ...prefs, state: stateName, district });
    }
    setLoading(false);
  };

  if (!useFallback) {
    return (
      <SafeAreaView style={styles.safe}>
        <Text style={styles.kicker}>Step 1 of 2</Text>
        <Text style={styles.title}>Where should we start?</Text>
        <Text style={styles.sub}>Allow location access to instantly find local verified news for your area.</Text>
        <View style={styles.centerContent}>
          <Pressable style={styles.gpsButton} onPress={requestLocation} disabled={loading}>
            {loading ? (
              <ActivityIndicator color="#0B0F14" />
            ) : (
              <Text style={styles.gpsButtonText}>Allow Location Access</Text>
            )}
          </Pressable>
          <Pressable onPress={() => setUseFallback(true)} style={styles.skipLink}>
            <Text style={styles.skipLinkText}>Select location manually</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      <Text style={styles.kicker}>Step 1 of 2</Text>
      <Text style={styles.title}>Manual Selection</Text>
      <Text style={styles.sub}>Pick your state and district for local verified cards.</Text>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.label}>State</Text>
        <View style={styles.chips}>
          {Object.keys(INDIAN_STATES).map((name) => (
            <Pressable
              key={name}
              onPress={() => {
                setStateName(name);
                setDistrict(INDIAN_STATES[name][0]);
              }}
              style={[styles.chip, stateName === name && styles.chipOn]}
            >
              <Text style={[styles.chipText, stateName === name && styles.chipTextOn]}>{name}</Text>
            </Pressable>
          ))}
        </View>
        <Text style={styles.label}>District</Text>
        <View style={styles.chips}>
          {districts.map((name) => (
            <Pressable
              key={name}
              onPress={() => setDistrict(name)}
              style={[styles.chip, district === name && styles.chipOn]}
            >
              <Text style={[styles.chipText, district === name && styles.chipTextOn]}>{name}</Text>
            </Pressable>
          ))}
        </View>
      </ScrollView>
      <Pressable
        style={styles.next}
        onPress={() => onNext({ ...prefs, state: stateName, district })}
      >
        <Text style={styles.nextText}>Continue</Text>
      </Pressable>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: "#0B0F14", padding: 20 },
  kicker: { color: "#EB7D00", fontSize: 13, fontWeight: "600" },
  title: { color: "#F4F7FB", fontSize: 28, fontWeight: "700", marginTop: 8 },
  sub: { color: "#9AA8B8", fontSize: 16, marginTop: 8, marginBottom: 20 },
  scroll: { paddingBottom: 24 },
  label: { color: "#C5D0DC", fontSize: 14, marginBottom: 8, marginTop: 12 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    borderColor: "#2A3542",
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  chipOn: { backgroundColor: "rgba(235,125,0,0.15)", borderColor: "#EB7D00" },
  chipText: { color: "#C5D0DC" },
  chipTextOn: { color: "#EB7D00", fontWeight: "600" },
  centerContent: { flex: 1, justifyContent: "center", alignItems: "center" },
  gpsButton: {
    backgroundColor: "#EB7D00",
    borderRadius: 14,
    paddingVertical: 16,
    paddingHorizontal: 32,
    alignItems: "center",
    width: "100%",
  },
  gpsButtonText: { color: "#0B0F14", fontWeight: "700", fontSize: 16 },
  skipLink: { marginTop: 24, padding: 10 },
  skipLinkText: { color: "#EB7D00", fontSize: 14, fontWeight: "600" },
  next: {
    backgroundColor: "#EB7D00",
    borderRadius: 14,
    paddingVertical: 14,
    alignItems: "center",
  },
  nextText: { color: "#0B0F14", fontWeight: "700", fontSize: 16 },
});
