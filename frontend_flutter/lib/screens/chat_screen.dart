import 'dart:async';
import 'package:flutter/material.dart';
import '../models/message.dart';
import '../services/websocket_service.dart';
import '../services/audio_service.dart';
import '../widgets/glass_card.dart';
import '../widgets/waveform_visualizer.dart';
import '../widgets/mode_selector.dart';
import '../widgets/tool_hud.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({Key? key}) : super(key: key);

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final WebSocketService _wsService = WebSocketService();
  final AudioService _audioService = AudioService();
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  final List<ChatMessage> _messages = [];
  String _currentMode = "PARTIALLY_ISOLATED";
  bool _isConnected = false;
  String? _activeTool;
  Map<String, dynamic>? _activeParams;
  Map<String, dynamic>? _lastToolResult;

  @override
  void initState() {
    super.initState();
    _initServices();
  }

  void _initServices() async {
    await _wsService.init();

    _wsService.onConnectionChanged.listen((connected) {
      if (mounted) setState(() => _isConnected = connected);
    });

    _wsService.onTranscription.listen((text) {
      _addMessage(ChatMessage(
        id: DateTime.now().toIso8601String(),
        role: MessageRole.user,
        content: text,
        mode: _currentMode,
      ));
    });

    ChatMessage? activeAssistantMsg;

    _wsService.onToken.listen((token) {
      if (mounted) {
        setState(() {
          if (activeAssistantMsg == null || activeAssistantMsg!.role != MessageRole.chloe) {
            activeAssistantMsg = ChatMessage(
              id: DateTime.now().toIso8601String(),
              role: MessageRole.chloe,
              content: token,
              mode: _currentMode,
            );
            _messages.add(activeAssistantMsg!);
          } else {
            activeAssistantMsg!.content += token;
          }
        });
        _scrollToBottom();
      }
    });

    _wsService.onSentenceAudio.listen((data) {
      final b64 = data['audio_base64'];
      if (b64 != null && b64.isNotEmpty) {
        _audioService.enqueueAudio(b64);
      }
    });

    _wsService.onToolStart.listen((data) {
      if (mounted) {
        setState(() {
          _activeTool = data['tool'];
          _activeParams = data['params'];
        });
      }
    });

    _wsService.onToolResult.listen((data) {
      if (mounted) {
        setState(() {
          _lastToolResult = data;
          _activeTool = null;
          _activeParams = null;
        });
      }
    });

    _wsService.onDone.listen((_) {
      activeAssistantMsg = null;
      if (mounted) {
        setState(() {
          _activeTool = null;
        });
      }
    });

    // Welcome initial message
    _messages.add(ChatMessage(
      id: 'init_1',
      role: MessageRole.chloe,
      content: 'Project Chloe online, Abhishek. Sub-second neural voice pipeline and MCP tools ready. What are we building today?',
      mode: _currentMode,
    ));
  }

  void _addMessage(ChatMessage msg) {
    if (mounted) {
      setState(() => _messages.add(msg));
      _scrollToBottom();
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _sendMessage() {
    final text = _textController.text.trim();
    if (text.isEmpty) return;

    _addMessage(ChatMessage(
      id: DateTime.now().toIso8601String(),
      role: MessageRole.user,
      content: text,
      mode: _currentMode,
    ));

    _wsService.sendText(text, _currentMode);
    _textController.clear();
  }

  void _toggleMic() async {
    if (_audioService.isRecording) {
      final audioBytes = await _audioService.stopRecording();
      if (audioBytes != null) {
        _wsService.sendAudioBytes(audioBytes);
      }
    } else {
      await _audioService.startRecording((bytes) {
        _wsService.sendAudioBytes(bytes);
      });
      if (mounted) setState(() {});
    }
  }

  void _showSettingsDialog() {
    final controller = TextEditingController(text: _wsService.serverHost);
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF0D121D),
        title: const Text("Remote Gateway IP", style: TextStyle(color: Color(0xFF00F3FF))),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              "Enter your PC's LAN or Tailscale IP (e.g. 192.168.1.5:8000 or 100.x.x.x:8000):",
              style: TextStyle(color: Color(0xFF8A99AD), fontSize: 13),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: controller,
              style: const TextStyle(color: Colors.white),
              decoration: InputDecoration(
                hintText: "192.168.1.100:8000",
                hintStyle: TextStyle(color: Colors.white.withOpacity(0.3)),
                enabledBorder: const OutlineInputBorder(borderSide: BorderSide(color: Color(0xFF00F3FF))),
                focusedBorder: const OutlineInputBorder(borderSide: BorderSide(color: Color(0xFF00F3FF), width: 2)),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text("Cancel", style: TextStyle(color: Colors.grey)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF00F3FF)),
            onPressed: () {
              _wsService.updateHost(controller.text.trim());
              Navigator.pop(ctx);
            },
            child: const Text("Connect", style: TextStyle(color: Colors.black)),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _wsService.dispose();
    _audioService.dispose();
    _textController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF07090E),
      appBar: AppBar(
        backgroundColor: const Color(0xFF07090E).withOpacity(0.9),
        elevation: 0,
        title: Row(
          children: [
            Container(
              width: 10,
              height: 10,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: _isConnected ? const Color(0xFF00F3FF) : const Color(0xFFF43F5E),
                boxShadow: [
                  BoxShadow(
                    color: _isConnected ? const Color(0xFF00F3FF) : const Color(0xFFF43F5E),
                    blurRadius: 8,
                  ),
                ],
              ),
            ),
            const SizedBox(width: 10),
            const Text(
              "CHLOE v2.0",
              style: TextStyle(
                fontFamily: 'Orbitron',
                color: Color(0xFF00F3FF),
                fontWeight: FontWeight.bold,
                fontSize: 16,
                letterSpacing: 1.5,
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings, color: Color(0xFF8A99AD)),
            onPressed: _showSettingsDialog,
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            // Mode Selector Bar
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8.0),
              child: ModeSelector(
                currentMode: _currentMode,
                onModeSelected: (mode) => setState(() => _currentMode = mode),
              ),
            ),

            // Waveform Visualizer
            StreamBuilder<bool>(
              stream: _audioService.isPlayingStream,
              builder: (context, playingSnap) {
                final isPlaying = playingSnap.data ?? false;
                return WaveformVisualizer(
                  isRecording: _audioService.isRecording,
                  isSpeaking: isPlaying,
                );
              },
            ),

            // Live Tool HUD
            ToolHud(
              activeTool: _activeTool,
              activeParams: _activeParams,
              lastResult: _lastToolResult,
            ),

            // Chat Messages List
            Expanded(
              child: ListView.builder(
                controller: _scrollController,
                padding: const EdgeInsets.all(16),
                itemCount: _messages.length,
                itemBuilder: (context, index) {
                  final msg = _messages[index];
                  final isUser = msg.role == MessageRole.user;
                  return Align(
                    alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
                    child: Container(
                      margin: const EdgeInsets.symmetric(vertical: 6),
                      constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.8),
                      child: GlassCard(
                        borderRadius: 16,
                        borderColor: isUser ? const Color(0xFFA855F7).withOpacity(0.4) : const Color(0xFF00F3FF).withOpacity(0.3),
                        backgroundColor: isUser ? const Color(0xFFA855F7).withOpacity(0.15) : const Color(0xFF00F3FF).withOpacity(0.08),
                        child: Text(
                          msg.content,
                          style: const TextStyle(color: Color(0xFFF0F4F8), fontSize: 14.5, height: 1.4),
                        ),
                      ),
                    ),
                  );
                },
              ),
            ),

            // Bottom Input Dock
            Padding(
              padding: const EdgeInsets.all(12.0),
              child: GlassCard(
                borderRadius: 30,
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                child: Row(
                  children: [
                    IconButton(
                      icon: Icon(
                        _audioService.isRecording ? Icons.stop_circle : Icons.mic,
                        color: _audioService.isRecording ? const Color(0xFFF43F5E) : const Color(0xFF00F3FF),
                        size: 26,
                      ),
                      onPressed: _toggleMic,
                    ),
                    Expanded(
                      child: TextField(
                        controller: _textController,
                        style: const TextStyle(color: Colors.white),
                        decoration: const InputDecoration(
                          hintText: "Speak or command Chloe...",
                          hintStyle: TextStyle(color: Color(0xFF8A99AD)),
                          border: InputBorder.none,
                        ),
                        onSubmitted: (_) => _sendMessage(),
                      ),
                    ),
                    IconButton(
                      icon: const Icon(Icons.send_rounded, color: Color(0xFF00F3FF)),
                      onPressed: _sendMessage,
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
