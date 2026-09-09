import React, { Children, useRef, useState } from "react";
import {
  Dimensions,
  NativeScrollEvent,
  NativeSyntheticEvent,
  ScrollView,
  StyleProp,
  StyleSheet,
  View,
  ViewStyle,
} from "react-native";

type Props = {
  style?: StyleProp<ViewStyle>;
  onPageSelected?: (event: { nativeEvent: { position: number } }) => void;
  children: React.ReactNode;
};

export function VerticalPager({ style, onPageSelected, children }: Props) {
  const scrollRef = useRef<ScrollView>(null);
  const [containerHeight, setContainerHeight] = useState<number>(() => {
    if (typeof window !== "undefined") {
      return window.innerHeight;
    }
    return Dimensions.get("window").height;
  });
  const currentIndexRef = useRef<number>(0);
  const items = Children.toArray(children);

  const handleScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const y = e.nativeEvent.contentOffset.y;
    const height = containerHeight || 1;
    const pageIndex = Math.round(y / height);
    if (pageIndex !== currentIndexRef.current && pageIndex >= 0 && pageIndex < items.length) {
      currentIndexRef.current = pageIndex;
      onPageSelected?.({ nativeEvent: { position: pageIndex } });
    }
  };

  return (
    <View
      style={[styles.container, style]}
      onLayout={(e) => {
        const h = e.nativeEvent.layout.height;
        if (h > 0) setContainerHeight(h);
      }}
    >
      <ScrollView
        ref={scrollRef}
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        pagingEnabled
        showsVerticalScrollIndicator={false}
        onMomentumScrollEnd={handleScroll}
        onScroll={handleScroll}
        scrollEventThrottle={32}
      >
        {items.map((child, index) => (
          <View
            key={index}
            style={[
              styles.item,
              { height: containerHeight, minHeight: containerHeight },
            ]}
          >
            {child}
          </View>
        ))}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    width: "100%",
    height: "100%",
    overflow: "hidden",
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
  },
  item: {
    width: "100%",
  },
});
