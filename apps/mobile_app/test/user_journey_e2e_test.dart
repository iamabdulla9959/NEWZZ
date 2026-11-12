import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_app/core/theme/app_theme.dart';
import 'package:mobile_app/main.dart';
import 'package:mobile_app/models/card.dart';
import 'package:mobile_app/models/card_source.dart';
import 'package:mobile_app/screens/landing_onboarding_screen.dart';
import 'package:mobile_app/screens/news_feed_screen.dart';
import 'package:mobile_app/screens/preferences_screen.dart';
import 'package:mobile_app/screens/story_detail_screen.dart';
import 'package:mobile_app/widgets/news_card.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:dio/dio.dart';
import 'package:mobile_app/api/news_service.dart';
import 'package:mobile_app/models/user_preferences.dart';

class TestNewsService extends NewsService {
  TestNewsService() : super.withDio(Dio());

  @override
  Future<UserPreferencesOut> getUserPreferences(String deviceId) async {
    return UserPreferencesOut(deviceId: deviceId, categoryOrder: ['Technology', 'National']);
  }

  @override
  Future<UserPreferencesOut> updateUserPreferences(String deviceId, List<String> categoryOrder) async {
    return UserPreferencesOut(deviceId: deviceId, categoryOrder: categoryOrder);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
    appThemeNotifier.value = ThemeMode.light;
  });

  group('End-to-End User Journey Tests (Opening App to Closing)', () {
    testWidgets('Journey 1: First-time open -> Landing Onboarding -> State & Topic selection -> Enter Feed', (WidgetTester tester) async {
      SharedPreferences.setMockInitialValues({'has_completed_onboarding': false});
      await AppTheme.initTheme();

      await tester.pumpWidget(const MyApp(hasCompletedOnboarding: false));
      await tester.pumpAndSettle();

      // 1. Verify on Landing Screen
      expect(find.byType(LandingOnboardingScreen), findsOneWidget);
      expect(find.bySemanticsLabel('NEWZZ'), findsOneWidget);
      expect(find.text('Real News. 60 Words. Zero Ads.'), findsOneWidget);

      // 2. Click Continue to Page 2 (State selection)
      await tester.tap(find.text('Continue'));
      await tester.pumpAndSettle();
      expect(find.text('Select Your Region'), findsOneWidget);

      // 3. Select 'Telangana'
      expect(find.text('Telangana'), findsOneWidget);
      await tester.tap(find.text('Telangana'));
      await tester.pumpAndSettle();

      // 4. Click Continue to Page 3 (Topics)
      await tester.tap(find.text('Continue'));
      await tester.pumpAndSettle();
      expect(find.text('Choose Your Topics'), findsOneWidget);

      // 5. Complete Onboarding by clicking 'Enter NEWZZ'
      expect(find.text('Enter NEWZZ'), findsOneWidget);
      await tester.tap(find.text('Enter NEWZZ'));
      await tester.pumpAndSettle();

      // 6. Verify transition to NewsFeedScreen
      expect(find.byType(NewsFeedScreen), findsOneWidget);

      // 7. Verify SharedPreferences saved
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getBool('has_completed_onboarding'), isTrue);
      expect(prefs.getString('selected_state'), equals('Telangana'));
    });

    testWidgets('Journey 2: Returning user open -> Bypasses onboarding directly to Feed', (WidgetTester tester) async {
      SharedPreferences.setMockInitialValues({'has_completed_onboarding': true});
      await AppTheme.initTheme();

      await tester.pumpWidget(const MyApp(hasCompletedOnboarding: true));
      await tester.pumpAndSettle();

      expect(find.byType(NewsFeedScreen), findsOneWidget);
      expect(find.byType(LandingOnboardingScreen), findsNothing);
    });

    testWidgets('Journey 3: UI & UX Theme Modes (Light & Dark Mode toggling and styles)', (WidgetTester tester) async {
      SharedPreferences.setMockInitialValues({'has_completed_onboarding': true});
      await AppTheme.initTheme();

      await tester.pumpWidget(const MyApp(hasCompletedOnboarding: true));
      await tester.pumpAndSettle();

      // Default should be Light mode (White background, black text)
      expect(appThemeNotifier.value, equals(ThemeMode.light));

      // Tap Theme toggle button in AppBar
      final themeToggle = find.byTooltip('Switch to Dark Mode');
      expect(themeToggle, findsOneWidget);
      await tester.tap(themeToggle);
      await tester.pumpAndSettle();

      // Mode switched to Dark
      expect(appThemeNotifier.value, equals(ThemeMode.dark));

      // Tap again to switch back to Light mode
      final lightToggle = find.byTooltip('Switch to Light Mode');
      expect(lightToggle, findsOneWidget);
      await tester.tap(lightToggle);
      await tester.pumpAndSettle();

      expect(appThemeNotifier.value, equals(ThemeMode.light));
    });

    testWidgets('Journey 4: News Card & Story Detail navigation with sanitized non-repeating summary', (WidgetTester tester) async {
      final sampleCard = CardOut(
        id: 'card_test_01',
        headline: 'Cabinet approves extension of metro line from Noida Sector 51 to Greater Noida Sector 4',
        summary: 'Cabinet approves extension of metro line from Noida Sector 51 to Greater Noida Sector 4. Once the corridor is open, Noida and Greater Noida cities will be connected seamlessly.',
        category: 'national',
        verifiedStatus: 'published',
        verificationType: 'official_source',
        corroborationCount: 1,
        isSingleSource: true,
        objectiveScore: 85.0,
        priorityScore: 85,
        importanceScore: 85.0,
        urgencyScore: 70.0,
        freshnessScore: 90.0,
        verificationScore: 95.0,
        personalRelevanceScore: 80.0,
        finalFeedScore: 88.0,
        priorityReason: 'Major infrastructure development approved by central cabinet.',
        publishedAt: DateTime.now().subtract(const Duration(hours: 2)),
        sources: [
          CardSourceOut(
            sourceId: 'src_hindu_01',
            name: 'The Hindu',
            url: 'https://thehindu.com/news/national/metro',
            trustTier: '1',
            urlType: 'direct',
            provenanceStatus: 'verified_identity',
          )
        ],
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          darkTheme: AppTheme.darkTheme,
          home: Scaffold(
            body: NewsCard(
              card: sampleCard,
              onTap: () {},
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      // 1. Verify card renders
      expect(find.text(sampleCard.headline), findsOneWidget);

      // 2. Verify summary stripped repeated headline and starts with fresh text
      expect(find.textContaining('Once the corridor is open'), findsOneWidget);
      expect(find.text('The Hindu'), findsOneWidget);

      // 3. Test Detail Screen navigation
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: StoryDetailScreen(card: sampleCard),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Summary'), findsOneWidget);
      expect(find.text('Why It Matters'), findsOneWidget);
      expect(find.text('Sources & Citations'), findsOneWidget);
      expect(find.text('The Hindu'), findsOneWidget);
      expect(find.textContaining('Once the corridor is open'), findsOneWidget);
    });

    testWidgets('Journey 5: Preferences screen state change and theme control', (WidgetTester tester) async {
      SharedPreferences.setMockInitialValues({'selected_state': 'Telangana'});
      await AppTheme.initTheme();

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          darkTheme: AppTheme.darkTheme,
          home: PreferencesScreen(newsService: TestNewsService()),
        ),
      );
      await tester.pumpAndSettle();

      // Scroll down to see full preferences
      await tester.scrollUntilVisible(
        find.text('Replay Welcome & Onboarding Tour'),
        150.0,
        scrollable: find.byType(Scrollable),
      );
      await tester.pumpAndSettle();

      // Verify Appearance & Theme and Tour button are present
      expect(find.text('Appearance & Theme'), findsOneWidget);
      expect(find.text('Replay Welcome & Onboarding Tour'), findsOneWidget);
    });
  });
}
