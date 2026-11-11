import 'card.dart';

class FeedOut {
  final List<CardOut> items;
  final int offset;
  final int limit;
  final int total;
  final bool fallbackUsed;
  final String? fallbackLevel;
  final String? emptyReason;

  FeedOut({
    required this.items,
    required this.offset,
    required this.limit,
    required this.total,
    this.fallbackUsed = false,
    this.fallbackLevel,
    this.emptyReason,
  });

  factory FeedOut.fromJson(Map<String, dynamic> json) {
    return FeedOut(
      items: (json['items'] as List?)?.map((i) => CardOut.fromJson(i as Map<String, dynamic>)).toList() ?? [],
      offset: json['offset'] as int? ?? 0,
      limit: json['limit'] as int? ?? 10,
      total: json['total'] as int? ?? 0,
      fallbackUsed: json['fallback_used'] as bool? ?? false,
      fallbackLevel: json['fallback_level']?.toString(),
      emptyReason: json['empty_reason']?.toString(),
    );
  }
}
