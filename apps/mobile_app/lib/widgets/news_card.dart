import 'package:flutter/material.dart';
import '../models/card.dart';
import '../core/utils/text_sanitizer.dart';

class NewsCard extends StatelessWidget {
  final CardOut card;
  final VoidCallback onTap;

  const NewsCard({super.key, required this.card, required this.onTap});

  String _getTimeAgo(DateTime? date) {
    if (date == null) return 'Date unavailable';
    final diff = DateTime.now().difference(date);
    if (diff.inSeconds < 0) {
      return 'Date unverified';
    } else if (diff.inMinutes < 60) {
      return '${diff.inMinutes}m ago';
    } else if (diff.inHours < 24) {
      return '${diff.inHours}h ago';
    } else {
      return '${diff.inDays}d ago';
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      elevation: 0,
      color: theme.cardColor,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(10),
        side: BorderSide(
          color: theme.colorScheme.outline,
          width: 1,
        ),
      ),
      clipBehavior: Clip.antiAlias,
      child: IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Container(width: 4, color: theme.colorScheme.primary),
            Expanded(
              child: InkWell(
                onTap: onTap,
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: theme.colorScheme.primary.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          card.category.toUpperCase(),
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                            color: theme.colorScheme.primary,
                          ),
                        ),
                      ),
                      if (card.state != null) ...[
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                          decoration: BoxDecoration(
                            color: theme.colorScheme.secondary.withValues(alpha: 0.1),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            card.state!.toUpperCase(),
                            style: TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.bold,
                              color: theme.colorScheme.secondary,
                            ),
                          ),
                        ),
                      ]
                    ],
                  ),
                  Row(
                    children: [
                      if (card.importanceScore >= 70)
                        Icon(Icons.local_fire_department, color: theme.colorScheme.primary, size: 16),
                      const SizedBox(width: 4),
                      Text(
                        _getTimeAgo(card.publishedAt),
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: isDark ? const Color(0xFF9CA3AF) : const Color(0xFF6B7280),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Text(
                card.headline,
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                  height: 1.3,
                  color: isDark ? Colors.white : const Color(0xFF111111),
                ),
              ),
              const SizedBox(height: 8),
              Text(
                TextSanitizer.cleanSummary(card.headline, card.summary),
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: isDark ? const Color(0xFFCBD5E1) : const Color(0xFF4B5563),
                  height: 1.45,
                ),
              ),
              const SizedBox(height: 16),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Expanded(
                    child: Text(
                      _getSourcesText(),
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: isDark ? const Color(0xFF9CA3AF) : const Color(0xFF6B7280),
                        fontWeight: FontWeight.w500,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  _buildVerificationBadge(theme),
                ],
              ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _getSourcesText() {
    if (card.sources.isEmpty) return 'Unknown source';
    if (card.sources.length == 1) return card.sources.first.name;
    return '${card.sources.first.name} +${card.sources.length - 1} more';
  }

  Widget _buildVerificationBadge(ThemeData theme) {
    Color badgeColor = Colors.grey;
    IconData icon = Icons.help_outline;
    String label = 'Unverified';

    final vType = card.verificationType?.toLowerCase() ?? '';

    if (vType == 'official_source') {
      badgeColor = Colors.blue;
      icon = Icons.account_balance;
      label = 'Official Source';
    } else if (vType == 'conflicting_reports') {
      badgeColor = Colors.red;
      icon = Icons.warning;
      label = 'Conflicting Reports';
    } else if ((vType == 'cross_verified' || vType == 'independently_corroborated' || vType == 'multi_source') && !card.isSingleSource) {
      badgeColor = Colors.green;
      icon = Icons.check_circle;
      label = 'Corroborated';
    } else if (vType == 'single_source' || card.isSingleSource) {
      badgeColor = Colors.amber;
      icon = Icons.info_outline;
      label = 'Single Source';
    } else if (card.verifiedStatus == 'published') {
      badgeColor = Colors.amber;
      icon = Icons.info_outline;
      label = 'Single Source';
    }

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 14, color: badgeColor),
        const SizedBox(width: 4),
        Text(
          label,
          style: theme.textTheme.bodySmall?.copyWith(
            color: badgeColor,
            fontWeight: FontWeight.bold,
          ),
        ),
      ],
    );
  }
}
