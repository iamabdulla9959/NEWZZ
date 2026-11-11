import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_app/core/utils/text_sanitizer.dart';

void main() {
  group('TextSanitizer.cleanSummary Tests', () {
    test('Strips exact headline prefix with period', () {
      const headline = 'Cabinet approves extension of metro line from Noida Sector 51 to Greater Noida Sector 4';
      const summary = 'Cabinet approves extension of metro line from Noida Sector 51 to Greater Noida Sector 4. Once the corridor is open, Noida and Greater Noida cities will be connected seamlessly.';

      final cleaned = TextSanitizer.cleanSummary(headline, summary);
      expect(cleaned.startsWith('Once the corridor is open'), isTrue);
      expect(cleaned.contains('Cabinet approves extension of metro line from Noida Sector 51 to Greater Noida Sector 4'), isFalse);
    });

    test('Strips word-level prefix with punctuation tolerance', () {
      const headline = 'Cyclone Murasu damages over 274 hectares of crop area in Prakasam district';
      const summary = 'Cyclone Murasu damages over 274 hectares of crop area in Prakasam district. District Agriculture Officer says maize suffered the major impact.';

      final cleaned = TextSanitizer.cleanSummary(headline, summary);
      expect(cleaned.startsWith('District Agriculture Officer says'), isTrue);
      expect(cleaned.contains('Cyclone Murasu damages over 274 hectares'), isFalse);
    });

    test('Strips headline followed by publisher tag (Google News RSS artifact)', () {
      const headline = 'Thousands of hoax bomb alerts sent to schools in Italy, U.K. and Ireland';
      const summary = 'Thousands of hoax bomb alerts sent to schools in Italy, U.K. and Ireland NBC News Hundreds of Italian schools hit by threats in suspected bomb hoax BBC';

      final cleaned = TextSanitizer.cleanSummary(headline, summary);
      expect(cleaned.startsWith('Hundreds of Italian schools hit by threats'), isTrue);
      expect(cleaned.contains('Thousands of hoax bomb alerts'), isFalse);
      expect(cleaned.startsWith('NBC News'), isFalse);
    });

    test('Provides graceful fallback if entire summary was just the headline', () {
      const headline = 'Cabinet approves extension of metro line';
      const summary = 'Cabinet approves extension of metro line.';

      final cleaned = TextSanitizer.cleanSummary(headline, summary);
      expect(cleaned, equals('Read the verified journalistic reporting and full timeline developments in the dossier below.'));
    });

    test('Leaves already clean, distinct summaries intact', () {
      const headline = 'Sensex jumps 800 points in early trade';
      const summary = 'Indian benchmark indices surged on Tuesday morning driven by strong buying in banking and IT shares.';

      final cleaned = TextSanitizer.cleanSummary(headline, summary);
      expect(cleaned, equals(summary));
    });
  });
}
