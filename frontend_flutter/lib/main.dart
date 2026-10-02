import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'screens/chat_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const ChloeApp());
}

class ChloeApp extends StatelessWidget {
  const ChloeApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Chloe AI',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: const Color(0xFF07090E),
        primaryColor: const Color(0xFF00F3FF),
        textTheme: GoogleFonts.interTextTheme(
          ThemeData.dark().textTheme,
        ),
      ),
      home: const ChatScreen(),
    );
  }
}
