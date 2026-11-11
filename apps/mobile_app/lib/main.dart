import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'screens/news_feed_screen.dart';
import 'screens/landing_onboarding_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final prefs = await SharedPreferences.getInstance();
  final hasCompletedOnboarding = prefs.getBool('has_completed_onboarding') ?? false;
  runApp(MyApp(hasCompletedOnboarding: hasCompletedOnboarding));
}

class MyApp extends StatelessWidget {
  final bool hasCompletedOnboarding;
  const MyApp({super.key, this.hasCompletedOnboarding = false});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'NEWZZ',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark(useMaterial3: true).copyWith(
        scaffoldBackgroundColor: const Color(0xFF080808),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF0D0D0D),
          foregroundColor: Colors.white,
          elevation: 0,
        ),
        cardTheme: const CardThemeData(
          color: Color(0xFF141414),
          elevation: 0,
        ),
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFFFF7A00),
          onPrimary: Colors.black,
          secondary: Color(0xFFFF9533),
          surface: Color(0xFF121212),
          onSurface: Color(0xFFEDEDED),
        ),
        tabBarTheme: const TabBarThemeData(
          indicatorColor: Color(0xFFFF7A00),
          labelColor: Color(0xFFFF7A00),
          unselectedLabelColor: Color(0xFF737373),
        ),
      ),
      home: hasCompletedOnboarding ? const NewsFeedScreen() : const LandingOnboardingScreen(),
    );
  }
}
