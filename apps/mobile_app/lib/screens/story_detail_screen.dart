import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../models/card.dart';
import '../models/card_source.dart';

class StoryDetailScreen extends StatelessWidget {
  final CardOut card;

  const StoryDetailScreen({super.key, required this.card});

  Future<void> _launchUrl(String url) async {
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('NEWZZ', style: TextStyle(fontWeight: FontWeight.bold, letterSpacing: 1.5)),
        centerTitle: true,
        backgroundColor: theme.scaffoldBackgroundColor,
        elevation: 0,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
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
                      fontSize: 12,
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
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        color: theme.colorScheme.secondary,
                      ),
                    ),
                  ),
                ],
              ],
            ),
            const SizedBox(height: 16),
            Text(
              card.headline,
              style: theme.textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.bold,
                height: 1.3,
              ),
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 12,
              runSpacing: 4,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.access_time, size: 16, color: Colors.grey[500]),
                    const SizedBox(width: 4),
                    Text(
                      card.publishedAt != null
                          ? 'Source: ${card.publishedAt!.toLocal().toString().split('.')[0]}'
                          : 'Date unavailable',
                      style: theme.textTheme.bodySmall?.copyWith(color: Colors.grey[500]),
                    ),
                  ],
                ),
                if (card.impactEvidence?['latest_independent_report_at'] != null)
                  Text(
                    'Updated: ${card.impactEvidence!['latest_independent_report_at'].toString().split('.')[0].replaceAll('T', ' ')}',
                    style: theme.textTheme.bodySmall?.copyWith(color: Colors.grey[500]),
                  ),
                if (card.newzzPublishedAt != null)
                  Text(
                    'Curated: ${card.newzzPublishedAt!.toLocal().toString().split('.')[0]}',
                    style: theme.textTheme.bodySmall?.copyWith(color: Colors.grey[500]),
                  ),
              ],
            ),
            const SizedBox(height: 24),
            Text(
              'Summary',
              style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold, color: theme.colorScheme.primary),
            ),
            const SizedBox(height: 8),
            Text(
              card.summary,
              style: theme.textTheme.bodyLarge?.copyWith(height: 1.6),
            ),
            if (card.priorityReason.isNotEmpty) ...[
              const SizedBox(height: 24),
              Text(
                'Why It Matters',
                style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold, color: theme.colorScheme.primary),
              ),
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.05),
                  borderRadius: BorderRadius.circular(8),
                  border: Border(left: BorderSide(color: theme.colorScheme.primary, width: 4)),
                ),
                child: Text(
                  card.priorityReason,
                  style: theme.textTheme.bodyMedium?.copyWith(height: 1.5, fontStyle: FontStyle.italic),
                ),
              ),
            ],
            const SizedBox(height: 32),
            const Divider(),
            const SizedBox(height: 16),
            Text(
              'Sources & Citations',
              style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),
            ...card.sources.map((source) => _buildSourceTile(context, source)),
          ],
        ),
      ),
    );
  }

  Widget _buildSourceTile(BuildContext context, CardSourceOut source) {
    final theme = Theme.of(context);

    IconData icon = Icons.article_outlined;
    Color iconColor = Colors.grey;
    String typeLabel = 'News Source';

    if (source.provenanceStatus == 'verified_identity') {
      iconColor = Colors.green;
      icon = Icons.verified;
      typeLabel = 'Original Reporting';
    } else if (source.urlType == 'aggregator') {
      iconColor = Colors.orange;
      icon = Icons.copy;
      typeLabel = 'Syndicated / Aggregator';
    } else if (source.trustTier == '1' || source.trustTier == 'Tier 1') {
      iconColor = Colors.blue;
      icon = Icons.account_balance;
      typeLabel = 'Official Source';
    }

    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: CircleAvatar(
        backgroundColor: iconColor.withValues(alpha: 0.1),
        child: Icon(icon, color: iconColor, size: 20),
      ),
      title: Text(source.name, style: const TextStyle(fontWeight: FontWeight.w600)),
      subtitle: Text(typeLabel, style: theme.textTheme.bodySmall?.copyWith(color: iconColor)),
      trailing: IconButton(
        icon: const Icon(Icons.open_in_new),
        onPressed: () => _launchUrl(source.url),
      ),
      onTap: () => _launchUrl(source.url),
    );
  }
}
