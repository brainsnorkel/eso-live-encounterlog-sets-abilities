#!/usr/bin/env python3
"""
Create a simple icon for the ESO Analyzer application
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_icon():
    """Create a simple icon for the application"""
    # Create a 256x256 image with a dark blue background
    size = 256
    img = Image.new('RGBA', (size, size), (25, 25, 112, 255))  # Dark blue background
    draw = ImageDraw.Draw(img)
    
    # Draw a circle for the main icon
    margin = 20
    draw.ellipse([margin, margin, size-margin, size-margin], 
                fill=(70, 130, 180, 255), outline=(255, 255, 255, 255), width=4)
    
    # Draw "ESO" text in the center
    try:
        # Try to use a system font
        font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 48)  # macOS
    except:
        try:
            font = ImageFont.truetype("arial.ttf", 48)  # Windows
        except:
            font = ImageFont.load_default()
    
    text = "ESO"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = (size - text_width) // 2
    y = (size - text_height) // 2 - 10
    
    draw.text((x, y), text, fill=(255, 255, 255, 255), font=font)
    
    # Draw "LOG" below ESO
    log_text = "LOG"
    bbox = draw.textbbox((0, 0), log_text, font=font)
    log_width = bbox[2] - bbox[0]
    
    log_x = (size - log_width) // 2
    log_y = y + text_height + 5
    
    draw.text((log_x, log_y), log_text, fill=(255, 255, 255, 255), font=font)
    
    # Save as ICO for Windows
    img.save("icon.ico", format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])
    
    # Save as PNG for macOS
    img.save("icon.png", format='PNG')
    
    print("Icon created: icon.ico and icon.png")
    return True

if __name__ == "__main__":
    try:
        from PIL import Image, ImageDraw, ImageFont
        create_icon()
    except ImportError:
        print("PIL (Pillow) not installed. Installing...")
        import subprocess
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
        from PIL import Image, ImageDraw, ImageFont
        create_icon()
