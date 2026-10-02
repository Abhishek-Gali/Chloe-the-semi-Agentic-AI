import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:audioplayers/audioplayers.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

class AudioService {
  final AudioRecorder _recorder = AudioRecorder();
  final AudioPlayer _player = AudioPlayer();
  
  bool _isRecording = false;
  bool _isPlaying = false;
  final List<String> _audioQueue = [];
  
  final _recordingStateController = StreamController<bool>.broadcast();
  final _playingStateController = StreamController<bool>.broadcast();

  Stream<bool> get isRecordingStream => _recordingStateController.stream;
  Stream<bool> get isPlayingStream => _playingStateController.stream;
  bool get isRecording => _isRecording;
  bool get isPlaying => _isPlaying;

  AudioService() {
    _player.onPlayerComplete.listen((_) {
      _playNextInQueue();
    });
  }

  Future<void> startRecording(Function(Uint8List) onAudioReady) async {
    try {
      if (await _recorder.hasPermission()) {
        final tempDir = await getTemporaryDirectory();
        final filePath = '${tempDir.path}/chloe_input_${DateTime.now().millisecondsSinceEpoch}.m4a';

        await _recorder.start(
          const RecordConfig(encoder: AudioEncoder.aacLc, bitRate: 128000, sampleRate: 44100),
          path: filePath,
        );
        _isRecording = true;
        _recordingStateController.add(true);
      }
    } catch (e) {
      _isRecording = false;
      _recordingStateController.add(false);
    }
  }

  Future<Uint8List?> stopRecording() async {
    try {
      final path = await _recorder.stop();
      _isRecording = false;
      _recordingStateController.add(false);

      if (path != null) {
        final file = File(path);
        if (await file.exists()) {
          final bytes = await file.readAsBytes();
          await file.delete();
          return bytes;
        }
      }
    } catch (e) {
      _isRecording = false;
      _recordingStateController.add(false);
    }
    return null;
  }

  void enqueueAudio(String base64Audio) {
    if (base64Audio.isEmpty) return;
    _audioQueue.add(base64Audio);
    if (!_isPlaying) {
      _playNextInQueue();
    }
  }

  Future<void> _playNextInQueue() async {
    if (_audioQueue.isEmpty) {
      _isPlaying = false;
      _playingStateController.add(false);
      return;
    }

    _isPlaying = true;
    _playingStateController.add(true);

    try {
      final b64 = _audioQueue.removeAt(0);
      final bytes = base64Decode(b64);
      final tempDir = await getTemporaryDirectory();
      final tempFile = File('${tempDir.path}/temp_tts_${DateTime.now().millisecondsSinceEpoch}.mp3');
      await tempFile.writeAsBytes(bytes);

      await _player.play(DeviceFileSource(tempFile.path));
    } catch (e) {
      _playNextInQueue();
    }
  }

  void stopPlayback() {
    _audioQueue.clear();
    _player.stop();
    _isPlaying = false;
    _playingStateController.add(false);
  }

  void dispose() {
    _recorder.dispose();
    _player.dispose();
    _recordingStateController.close();
    _playingStateController.close();
  }
}
