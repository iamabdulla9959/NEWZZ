import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_app/models/card.dart';
import 'package:mobile_app/models/card_source.dart';
import 'package:mobile_app/widgets/news_card.dart';

void main() {
  group('B52 Dart Model & UI Verification Tests', () {
    test('CardOut.fromJson parses published_at and newzz_published_at correctly', () {
      final json = {
        'id': 'card-123',
        'headline': 'Test Headline',
        'summary': 'Test Summary',
        'category': 'national',
        'verified_status': 'published',
        'verification_type': 'single_source',
        'corroboration_count': 1,
        'is_single_source': true,
        'published_at': '2026-08-24T10:00:00.000Z',
        'newzz_published_at': '2026-11-08T12:00:00.000Z',
        'objective_score': 0.0,
        'priority_score': 5,
        'importance_score': 50.0,
        'urgency_score': 20.0,
        'freshness_score': 10.0,
        'verification_score': 70.0,
        'personal_relevance_score': 50.0,
        'final_feed_score': 45.0,
        'priority_reason': 'Standard coverage.',
        'sources': []
      };

      final card = CardOut.fromJson(json);
      expect(card.id, 'card-123');
      expect(card.publishedAt, DateTime.parse('2026-08-24T10:00:00.000Z'));
      expect(card.isSingleSource, isTrue);
    });

    testWidgets('NewsCard displays Date unavailable when publishedAt is null', (WidgetTester tester) async {
      final card = CardOut(
        id: 'card-1',
        headline: 'Null Date Test',
        summary: 'Null date summary.',
        category: 'tech',
        verifiedStatus: 'published',
        verificationType: 'single_source',
        corroborationCount: 1,
        isSingleSource: true,
        publishedAt: null,
        objectiveScore: 0.0,
        priorityScore: 5,
        importanceScore: 30.0,
        urgencyScore: 10.0,
        freshnessScore: 25.0,
        verificationScore: 60.0,
        personalRelevanceScore: 50.0,
        finalFeedScore: 35.0,
        priorityReason: 'Standard news.',
        sources: [
          CardSourceOut(
            sourceId: 'src-1',
            name: 'The Hindu',
            url: 'https://thehindu.com',
            trustTier: '1',
            urlType: 'direct',
            provenanceStatus: 'verified_identity',
          )
        ],
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: NewsCard(card: card, onTap: () {}),
          ),
        ),
      );

      expect(find.text('Date unavailable'), findsOneWidget);
    });

    testWidgets('NewsCard displays Single Source badge for published single source card (never green Verified)', (WidgetTester tester) async {
      final card = CardOut(
        id: 'card-2',
        headline: 'Single Source Test',
        summary: 'Summary text.',
        category: 'business',
        verifiedStatus: 'published',
        verificationType: 'single_source',
        corroborationCount: 1,
        isSingleSource: true,
        publishedAt: DateTime.parse('2026-09-01T12:00:00Z'),
        objectiveScore: 0.0,
        priorityScore: 5,
        importanceScore: 40.0,
        urgencyScore: 15.0,
        freshnessScore: 10.0,
        verificationScore: 60.0,
        personalRelevanceScore: 50.0,
        finalFeedScore: 38.0,
        priorityReason: 'Single source report.',
        sources: [
          CardSourceOut(
            sourceId: 'src-2',
            name: 'Reuters',
            url: 'https://reuters.com',
            trustTier: '1',
            urlType: 'direct',
            provenanceStatus: 'verified_identity',
          )
        ],
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: NewsCard(card: card, onTap: () {}),
          ),
        ),
      );

      expect(find.text('Single Source'), findsOneWidget);
      expect(find.text('Verified'), findsNothing);
    });

    testWidgets('NewsCard displays Official Source badge for official source card', (WidgetTester tester) async {
      final card = CardOut(
        id: 'card-3',
        headline: 'Official Government Release',
        summary: 'Official press release.',
        category: 'national',
        verifiedStatus: 'published',
        verificationType: 'official_source',
        corroborationCount: 1,
        isSingleSource: true,
        publishedAt: DateTime.parse('2026-09-02T12:00:00Z'),
        objectiveScore: 0.0,
        priorityScore: 5,
        importanceScore: 60.0,
        urgencyScore: 20.0,
        freshnessScore: 15.0,
        verificationScore: 90.0,
        personalRelevanceScore: 50.0,
        finalFeedScore: 55.0,
        priorityReason: 'Official wire.',
        sources: [
          CardSourceOut(
            sourceId: 'src-3',
            name: 'PIB Delhi',
            url: 'https://pib.gov.in',
            trustTier: '1',
            urlType: 'direct',
            provenanceStatus: 'verified_identity',
          )
        ],
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: NewsCard(card: card, onTap: () {}),
          ),
        ),
      );

      expect(find.text('Official Source'), findsOneWidget);
    });

    testWidgets('NewsCard displays Corroborated badge for multi-source card', (WidgetTester tester) async {
      final card = CardOut(
        id: 'card-4',
        headline: 'Multi Source Corroborated News',
        summary: 'Multi source summary.',
        category: 'national',
        verifiedStatus: 'published',
        verificationType: 'cross_verified',
        corroborationCount: 2,
        isSingleSource: false,
        publishedAt: DateTime.parse('2026-09-03T12:00:00Z'),
        objectiveScore: 0.0,
        priorityScore: 5,
        importanceScore: 70.0,
        urgencyScore: 25.0,
        freshnessScore: 20.0,
        verificationScore: 95.0,
        personalRelevanceScore: 50.0,
        finalFeedScore: 65.0,
        priorityReason: 'Corroborated news.',
        sources: [
          CardSourceOut(sourceId: 's1', name: 'BBC News', url: 'https://bbc.com', trustTier: '1', urlType: 'direct', provenanceStatus: 'verified_identity'),
          CardSourceOut(sourceId: 's2', name: 'Reuters', url: 'https://reuters.com', trustTier: '1', urlType: 'direct', provenanceStatus: 'verified_identity'),
        ],
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: NewsCard(card: card, onTap: () {}),
          ),
        ),
      );

      expect(find.text('Corroborated'), findsOneWidget);
    });
  });
}
