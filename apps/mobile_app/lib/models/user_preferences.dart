class UserPreferencesOut {
  final String deviceId;
  final List<String> categoryOrder;
  final DateTime? createdAt;
  final DateTime? updatedAt;

  UserPreferencesOut({
    required this.deviceId,
    required this.categoryOrder,
    this.createdAt,
    this.updatedAt,
  });

  factory UserPreferencesOut.fromJson(Map<String, dynamic> json) {
    return UserPreferencesOut(
      deviceId: json['device_id']?.toString() ?? '',
      categoryOrder: (json['category_order'] as List?)?.map((e) => e.toString()).toList() ?? [],
      createdAt: json['created_at'] != null ? DateTime.tryParse(json['created_at'].toString()) : null,
      updatedAt: json['updated_at'] != null ? DateTime.tryParse(json['updated_at'].toString()) : null,
    );
  }
}
