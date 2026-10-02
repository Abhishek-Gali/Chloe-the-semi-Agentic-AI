import 'dart:convert';
import 'package:flutter/material.dart';
import 'glass_card.dart';

class ToolHud extends StatelessWidget {
  final String? activeTool;
  final Map<String, dynamic>? activeParams;
  final Map<String, dynamic>? lastResult;

  const ToolHud({
    Key? key,
    this.activeTool,
    this.activeParams,
    this.lastResult,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    if (activeTool == null && lastResult == null) {
      return const SizedBox.shrink();
    }

    final isExecuting = activeTool != null;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 6.0),
      child: GlassCard(
        borderColor: isExecuting ? const Color(0xFF10B981) : const Color(0xFF00F3FF),
        backgroundColor: (isExecuting ? const Color(0xFF10B981) : const Color(0xFF00F3FF)).withOpacity(0.08),
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                if (isExecuting) ...[
                  const SizedBox(
                    width: 12,
                    height: 12,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Color(0xFF10B981),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    "MCP EXECUTING: ${activeTool!.toUpperCase()}",
                    style: const TextStyle(
                      color: Color(0xFF10B981),
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                      letterSpacing: 1,
                    ),
                  ),
                ] else ...[
                  const Icon(Icons.check_circle_outline, color: Color(0xFF00F3FF), size: 14),
                  const SizedBox(width: 8),
                  Text(
                    "TOOL OUTPUT: ${lastResult?['tool'] ?? 'COMPLETED'}",
                    style: const TextStyle(
                      color: Color(0xFF00F3FF),
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ],
            ),
            if (isExecuting && activeParams != null) ...[
              const SizedBox(height: 4),
              Text(
                "Params: ${jsonEncode(activeParams)}",
                style: const TextStyle(color: Color(0xFF8A99AD), fontSize: 11),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ],
        ),
      ),
    );
  }
}
