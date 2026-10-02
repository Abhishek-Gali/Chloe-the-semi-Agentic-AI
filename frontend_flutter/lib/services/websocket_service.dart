import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:shared_preferences/shared_preferences.dart';

class WebSocketService {
  WebSocketChannel? _channel;
  String _serverHost = "192.168.1.100:8000";
  bool _isConnected = false;

  final _tokenController = StreamController<String>.broadcast();
  final _sentenceAudioController = StreamController<Map<String, dynamic>>.broadcast();
  final _transcriptionController = StreamController<String>.broadcast();
  final _toolStartController = StreamController<Map<String, dynamic>>.broadcast();
  final _toolResultController = StreamController<Map<String, dynamic>>.broadcast();
  final _doneController = StreamController<void>.broadcast();
  final _statusController = StreamController<bool>.broadcast();

  Stream<String> get onToken => _tokenController.stream;
  Stream<Map<String, dynamic>> get onSentenceAudio => _sentenceAudioController.stream;
  Stream<String> get onTranscription => _transcriptionController.stream;
  Stream<Map<String, dynamic>> get onToolStart => _toolStartController.stream;
  Stream<Map<String, dynamic>> get onToolResult => _toolResultController.stream;
  Stream<void> get onDone => _doneController.stream;
  Stream<bool> get onConnectionChanged => _statusController.stream;

  bool get isConnected => _isConnected;
  String get serverHost => _serverHost;

  Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    _serverHost = prefs.getString("chloe_server_host") ?? "192.168.1.100:8000";
    connect();
  }

  Future<void> updateHost(String newHost) async {
    _serverHost = newHost;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString("chloe_server_host", newHost);
    disconnect();
    connect();
  }

  void connect() {
    try {
      final wsUrl = Uri.parse("ws://$_serverHost/ws/audio");
      _channel = WebSocketChannel.connect(wsUrl);
      _isConnected = true;
      _statusController.add(true);

      _channel!.stream.listen(
        (message) {
          _handleMessage(message);
        },
        onDone: () {
          _isConnected = false;
          _statusController.add(false);
          _reconnect();
        },
        onError: (error) {
          _isConnected = false;
          _statusController.add(false);
          _reconnect();
        },
      );
    } catch (e) {
      _isConnected = false;
      _statusController.add(false);
      _reconnect();
    }
  }

  void _reconnect() {
    Future.delayed(const Duration(seconds: 3), () {
      if (!_isConnected) {
        connect();
      }
    });
  }

  void _handleMessage(dynamic message) {
    try {
      final data = jsonDecode(message);
      final type = data['type'];

      switch (type) {
        case 'token':
          _tokenController.add(data['token'] ?? '');
          break;
        case 'sentence_audio':
          _sentenceAudioController.add(data);
          break;
        case 'transcription':
          _transcriptionController.add(data['text'] ?? '');
          break;
        case 'tool_start':
          _toolStartController.add(data);
          break;
        case 'tool_result':
          _toolResultController.add(data);
          break;
        case 'done':
          _doneController.add(null);
          break;
      }
    } catch (e) {
      // Ignored
    }
  }

  void sendText(String text, String mode) {
    if (_isConnected && _channel != null) {
      _channel!.sink.add(jsonEncode({
        'text': text,
        'mode': mode,
      }));
    }
  }

  void sendAudioBytes(Uint8List bytes) {
    if (_isConnected && _channel != null) {
      _channel!.sink.add(bytes);
    }
  }

  void disconnect() {
    _channel?.sink.close();
    _isConnected = false;
    _statusController.add(false);
  }

  void dispose() {
    disconnect();
    _tokenController.close();
    _sentenceAudioController.close();
    _transcriptionController.close();
    _toolStartController.close();
    _toolResultController.close();
    _doneController.close();
    _statusController.close();
  }
}
