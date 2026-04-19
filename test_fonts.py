#!/usr/bin/env python3
import tkinter as tk
import tkinter.font as tkfont

root = tk.Tk()
root.withdraw()  # Hide the window

print("Available fonts:")
fonts = tkfont.families()
print(f"Total fonts: {len(fonts)}")

# Search for Chinese fonts
chinese_fonts = []
for font in fonts:
    font_lower = font.lower()
    # 更精确的中文检测
    if 'ti' in font_lower and any(keyword in font_lower for keyword in ['fangsong', 'song']):
        chinese_fonts.append(font)

print("\nChinese fonts found:")
if chinese_fonts:
    for font in chinese_fonts:
        print(f"- {font}")
else:
    print("No Chinese fonts found")

print("\nAll fonts:")
for font in fonts:
    print(f"- {font}")

root.destroy()