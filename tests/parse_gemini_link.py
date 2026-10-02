import re
import json
from pathlib import Path
from bs4 import BeautifulSoup

file_path = Path(r"C:\Users\galia\.gemini\antigravity\brain\a1a520fc-c616-4698-ad90-be6c49e97f5a\.system_generated\steps\349\content.md")
with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
    content = f.read()

soup = BeautifulSoup(content, "html.parser")
scripts = soup.find_all("script")

for i, s in enumerate(scripts):
    text = s.get_text()
    if "AF_initDataCallback" in text or "c_[" in text or "data:" in text:
        print(f"=== Script {i} (len: {len(text)}) ===")
        # Look for JSON arrays or strings inside AF_initDataCallback
        matches = re.findall(r'AF_initDataCallback\((.*?)\);', text, re.DOTALL)
        for m in matches:
            print("Found AF_initDataCallback call:")
            print(m[:1000])
            print("...\n")

# Let's search across all content for unicode escaped strings or text blocks
decoded = content.encode('utf-8').decode('unicode_escape', errors='ignore')
for kw in ["chloe", "abhishek", "latency", "stt", "tts", "whisper", "groq", "ollama", "langgraph", "terabox"]:
    found = [m.start() for m in re.finditer(kw, decoded, re.IGNORECASE)]
    if found:
        print(f"Decoded match for '{kw}' count: {len(found)}")
        for pos in found[:3]:
            print(f"[{kw}] -> " + decoded[max(0, pos-100):min(len(decoded), pos+300)])
