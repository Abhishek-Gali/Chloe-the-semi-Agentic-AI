import 'dart:math' as math;
import 'package:flutter/material.dart';

class WaveformVisualizer extends StatefulWidget {
  final bool isRecording;
  final bool isSpeaking;

  const WaveformVisualizer({
    Key? key,
    required this.isRecording,
    required this.isSpeaking,
  }) : super(key: key);

  @override
  State<WaveformVisualizer> createState() => _WaveformVisualizerState();
}

class _WaveformVisualizerState extends State<WaveformVisualizer>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 4),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final activeColor = widget.isRecording
        ? const Color(0xFFF43F5E)
        : (widget.isSpeaking ? const Color(0xFFA855F7) : const Color(0xFF00F3FF));

    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        return SizedBox(
          width: 140,
          height: 140,
          child: Stack(
            alignment: Alignment.center,
            children: [
              // Outer rotating ring
              Transform.rotate(
                angle: _controller.value * 2 * math.pi,
                child: Container(
                  width: 130,
                  height: 130,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: activeColor.withOpacity(0.3),
                      width: 1.5,
                      style: BorderStyle.solid,
                    ),
                  ),
                ),
              ),
              // Inner pulsing core
              Container(
                width: 80,
                height: 80,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: RadialGradient(
                    colors: [
                      activeColor.withOpacity(0.4),
                      const Color(0xFF07090E),
                    ],
                  ),
                  border: Border.all(
                    color: activeColor,
                    width: 2,
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: activeColor.withOpacity(0.5),
                      blurRadius: 20,
                      spreadRadius: 2,
                    ),
                  ],
                ),
                child: Center(
                  child: Icon(
                    widget.isRecording
                        ? Icons.mic
                        : (widget.isSpeaking ? Icons.volume_up : Icons.bolt),
                    color: Colors.white,
                    size: 32,
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
