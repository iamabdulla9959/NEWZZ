import 'card_source.dart';

class CardOut {
  final String id;
  final String headline;
  final String summary;
  final String category;
  final String verifiedStatus;
  final String? verificationType;
  final int corroborationCount;
  final bool isSingleSource;
  final DateTime? createdAt;
  final DateTime? publishedAt;
  final DateTime? newzzPublishedAt;
  final String? district;
  final String? state;
  final double objectiveScore;
  final int priorityScore;
  final double importanceScore;
  final double urgencyScore;
  final double freshnessScore;
  final double verificationScore;
  final double personalRelevanceScore;
  final double finalFeedScore;
  final String priorityReason;
  final Map<String, dynamic>? impactEvidence;
  final String? imageUrl;
  final String? imageAuthor;
  final String? imageAuthorUrl;
  final List<CardSourceOut> sources;

  CardOut({
    required this.id,
    required this.headline,
    required this.summary,
    required this.category,
    required this.verifiedStatus,
    this.verificationType,
    required this.corroborationCount,
    required this.isSingleSource,
    this.createdAt,
    this.publishedAt,
    this.newzzPublishedAt,
    this.district,
    this.state,
    required this.objectiveScore,
    required this.priorityScore,
    required this.importanceScore,
    required this.urgencyScore,
    required this.freshnessScore,
    required this.verificationScore,
    required this.personalRelevanceScore,
    required this.finalFeedScore,
    required this.priorityReason,
    this.impactEvidence,
    this.imageUrl,
    this.imageAuthor,
    this.imageAuthorUrl,
    required this.sources,
  });

  factory CardOut.fromJson(Map<String, dynamic> json) {
    return CardOut(
      id: json['id']?.toString() ?? '',
      headline: json['headline']?.toString() ?? 'No Headline',
      summary: json['summary']?.toString() ?? '',
      category: json['category']?.toString() ?? 'General',
      verifiedStatus: json['verified_status']?.toString() ?? 'draft',
      verificationType: json['verification_type']?.toString(),
      corroborationCount: json['corroboration_count'] as int? ?? 1,
      isSingleSource: json['is_single_source'] as bool? ?? true,
      createdAt: json['created_at'] != null ? DateTime.tryParse(json['created_at'].toString()) : null,
      publishedAt: json['published_at'] != null ? DateTime.tryParse(json['published_at'].toString()) : null,
      newzzPublishedAt: json['newzz_published_at'] != null ? DateTime.tryParse(json['newzz_published_at'].toString()) : null,
      district: json['district']?.toString(),
      state: json['state']?.toString(),
      objectiveScore: (json['objective_score'] as num?)?.toDouble() ?? 0.0,
      priorityScore: json['priority_score'] as int? ?? 5,
      importanceScore: (json['importance_score'] as num?)?.toDouble() ?? 0.0,
      urgencyScore: (json['urgency_score'] as num?)?.toDouble() ?? 0.0,
      freshnessScore: (json['freshness_score'] as num?)?.toDouble() ?? 0.0,
      verificationScore: (json['verification_score'] as num?)?.toDouble() ?? 0.0,
      personalRelevanceScore: (json['personal_relevance_score'] as num?)?.toDouble() ?? 0.0,
      finalFeedScore: (json['final_feed_score'] as num?)?.toDouble() ?? 0.0,
      priorityReason: json['priority_reason']?.toString() ?? '',
      impactEvidence: json['impact_evidence'] as Map<String, dynamic>?,
      imageUrl: json['image_url']?.toString(),
      imageAuthor: json['image_author']?.toString(),
      imageAuthorUrl: json['image_author_url']?.toString(),
      sources: (json['sources'] as List?)?.map((i) => CardSourceOut.fromJson(i as Map<String, dynamic>)).toList() ?? [],
    );
  }
}
