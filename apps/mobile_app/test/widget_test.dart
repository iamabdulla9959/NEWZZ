import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_app/main.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  testWidgets('App builds and shows NEWZZ branding and onboarding', (WidgetTester tester) async {
    await tester.pumpWidget(const MyApp());
    await tester.pumpAndSettle();

    expect(find.bySemanticsLabel('NEWZZ'), findsOneWidget);
    expect(find.text('Real News. 60 Words. Zero Ads.'), findsOneWidget);
  });
}
