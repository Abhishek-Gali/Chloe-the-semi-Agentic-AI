import 'package:flutter/material.dart';

class ModeSelector extends StatelessWidget {
  final String currentMode;
  final Function(String) onModeSelected;

  const ModeSelector({
    Key? key,
    required this.currentMode,
    required this.onModeSelected,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: Colors.black.withOpacity(0.4),
        borderRadius: BorderRadius.circular(30),
        border: Border.all(color: Colors.white.withOpacity(0.08)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _buildChip("FULLY_ISOLATED", "🛡️ Air-Gapped", const Color(0xFF10B981)),
          const SizedBox(width: 4),
          _buildChip("PARTIALLY_ISOLATED", "⚡ Hybrid", const Color(0xFF00F3FF)),
          const SizedBox(width: 4),
          _buildChip("COMPLETELY_OPEN", "🧠 Cloud", const Color(0xFFA855F7)),
        ],
      ),
    );
  }

  Widget _buildChip(String modeKey, String label, Color activeColor) {
    final isSelected = currentMode == modeKey;
    return GestureDetector(
      onTap: () => onModeSelected(modeKey),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: isSelected ? activeColor.withOpacity(0.15) : Colors.transparent,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: isSelected ? activeColor.withOpacity(0.5) : Colors.transparent,
            width: 1,
          ),
          boxShadow: isSelected
              ? [
                  BoxShadow(
                    color: activeColor.withOpacity(0.25),
                    blurRadius: 8,
                  ),
                ]
              : [],
        ),
        child: Text(
          label,
          style: TextStyle(
            color: isSelected ? activeColor : const Color(0xFF8A99AD),
            fontSize: 12,
            fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
          ),
        ),
      ),
    );
  }
}
