import 'dart:convert';

enum MessageRole { user, chloe, tool }

class ChatMessage {
  final String id;
  final MessageRole role;
  String content;
  final String mode;
  final DateTime timestamp;
  final Map<String, dynamic>? toolData;

  ChatMessage({
    required this.id,
    required this.role,
    required this.content,
    required this.mode,
    DateTime? timestamp,
    this.toolData,
  }) : timestamp = timestamp ?? DateTime.now();

  Map<String, dynamic> toJson() => {
        'id': id,
        'role': role.name,
        'content': content,
        'mode': mode,
        'timestamp': timestamp.toIso8601String(),
        'toolData': toolData,
      };

  factory ChatMessage.fromJson(Map<String, dynamic> json) => ChatMessage(
        id: json['id'] ?? '',
        role: MessageRole.values.firstWhere(
          (e) => e.name == json['role'],
          orElse: () => MessageRole.chloe,
        ),
        content: json['content'] ?? '',
        mode: json['mode'] ?? 'PARTIALLY_ISOLATED',
        timestamp: DateTime.tryParse(json['timestamp'] ?? '') ?? DateTime.now(),
        toolData: json['toolData'],
      );
}
