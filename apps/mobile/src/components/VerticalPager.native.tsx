import React from "react";
import { StyleProp, ViewStyle } from "react-native";
import PagerView from "react-native-pager-view";

type Props = {
  style?: StyleProp<ViewStyle>;
  onPageSelected?: (event: { nativeEvent: { position: number } }) => void;
  children: React.ReactNode;
};

export function VerticalPager({ style, onPageSelected, children }: Props) {
  return (
    <PagerView
      style={style}
      orientation="vertical"
      onPageSelected={onPageSelected}
    >
      {children}
    </PagerView>
  );
}
