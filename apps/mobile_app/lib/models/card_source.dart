class CardSourceOut {
  final String sourceId;
  final String name;
  final String url;
  final String trustTier;
  final String urlType;
  final String provenanceStatus;

  CardSourceOut({
    required this.sourceId,
    required this.name,
    required this.url,
    required this.trustTier,
    required this.urlType,
    required this.provenanceStatus,
  });

  factory CardSourceOut.fromJson(Map<String, dynamic> json) {
    return CardSourceOut(
      sourceId: json['source_id']?.toString() ?? '',
      name: json['name']?.toString() ?? 'Unknown',
      url: json['url']?.toString() ?? '',
      trustTier: json['trust_tier']?.toString() ?? '',
      urlType: json['url_type']?.toString() ?? 'direct',
      provenanceStatus: json['provenance_status']?.toString() ?? 'name_only_match',
    );
  }
}
