import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

final ValueNotifier<ThemeMode> appThemeNotifier = ValueNotifier<ThemeMode>(ThemeMode.light);

class AppTheme {
  static const Color brandRedLight = Color(0xFFD9232D);
  static const Color brandRedDark = Color(0xFFFF3B4E);

  static Future<void> initTheme() async {
    final prefs = await SharedPreferences.getInstance();
    final savedMode = prefs.getString('app_theme_mode');
    if (savedMode == 'dark') {
      appThemeNotifier.value = ThemeMode.dark;
    } else {
      // Default to light as requested: White background, black letters
      appThemeNotifier.value = ThemeMode.light;
    }
  }

  static Future<void> toggleTheme() async {
    final newMode = appThemeNotifier.value == ThemeMode.dark ? ThemeMode.light : ThemeMode.dark;
    appThemeNotifier.value = newMode;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('app_theme_mode', newMode == ThemeMode.dark ? 'dark' : 'light');
  }

  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      scaffoldBackgroundColor: const Color(0xFFFFFFFF),
      cardColor: const Color(0xFFFFFFFF),
      primaryColor: brandRedLight,
      colorScheme: const ColorScheme.light(
        primary: brandRedLight,
        onPrimary: Colors.white,
        secondary: Color(0xFFE53935),
        onSecondary: Colors.white,
        surface: Color(0xFFFFFFFF),
        onSurface: Color(0xFF111111),
        outline: Color(0xFFE5E7EB),
        surfaceContainerHighest: Color(0xFFF3F4F6),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: Color(0xFFFFFFFF),
        foregroundColor: Color(0xFF111111),
        elevation: 0,
        surfaceTintColor: Colors.transparent,
      ),
      cardTheme: const CardThemeData(
        color: Color(0xFFFFFFFF),
        elevation: 0,
      ),
      tabBarTheme: const TabBarThemeData(
        indicatorColor: brandRedLight,
        labelColor: brandRedLight,
        unselectedLabelColor: Color(0xFF6B7280),
        indicatorSize: TabBarIndicatorSize.label,
      ),
      dividerTheme: const DividerThemeData(
        color: Color(0xFFEEEEEE),
        thickness: 1,
      ),
      textTheme: const TextTheme(
        titleLarge: TextStyle(color: Color(0xFF111111), fontWeight: FontWeight.bold),
        titleMedium: TextStyle(color: Color(0xFF111111), fontWeight: FontWeight.bold),
        bodyLarge: TextStyle(color: Color(0xFF1F2937)),
        bodyMedium: TextStyle(color: Color(0xFF374151)),
        bodySmall: TextStyle(color: Color(0xFF6B7280)),
      ),
    );
  }

  static ThemeData get darkTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: const Color(0xFF0F1015),
      cardColor: const Color(0xFF181A20),
      primaryColor: brandRedDark,
      colorScheme: const ColorScheme.dark(
        primary: brandRedDark,
        onPrimary: Colors.white,
        secondary: Color(0xFFFF5252),
        onSecondary: Colors.white,
        surface: Color(0xFF181A20),
        onSurface: Color(0xFFF3F4F6),
        outline: Color(0xFF2E323D),
        surfaceContainerHighest: Color(0xFF22252E),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: Color(0xFF131419),
        foregroundColor: Colors.white,
        elevation: 0,
        surfaceTintColor: Colors.transparent,
      ),
      cardTheme: const CardThemeData(
        color: Color(0xFF181A20),
        elevation: 0,
      ),
      tabBarTheme: const TabBarThemeData(
        indicatorColor: brandRedDark,
        labelColor: brandRedDark,
        unselectedLabelColor: Color(0xFF9CA3AF),
        indicatorSize: TabBarIndicatorSize.label,
      ),
      dividerTheme: const DividerThemeData(
        color: Color(0xFF262930),
        thickness: 1,
      ),
      textTheme: const TextTheme(
        titleLarge: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
        titleMedium: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
        bodyLarge: TextStyle(color: Color(0xFFE5E7EB)),
        bodyMedium: TextStyle(color: Color(0xFFD1D5DB)),
        bodySmall: TextStyle(color: Color(0xFF9CA3AF)),
      ),
    );
  }
}

