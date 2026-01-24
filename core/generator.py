"""
Video/Image to Reel Generator - Premium "Economika" Design.
Creates vertical 1080x1920 videos with blurred background, 
branded Economika overlays, and high-impact text.
"""
import os
from PIL import Image, ImageFilter, ImageDraw, ImageFont
from moviepy import VideoFileClip, ImageClip, CompositeVideoClip, TextClip
from .subtitler import get_subtitles
import numpy as np

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Reel dimensions (9:16 vertical)
REEL_WIDTH = 1080
REEL_HEIGHT = 1920
REEL_DURATION = 10  # seconds for image-based reels

# Colors
ECONOMIKA_RED = (227, 30, 36)  # #E31E24
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

def get_font(name: str, size: int):
    """Attempt to load a specific font, falling back to alternatives."""
    fonts_to_try = [
        name,
        f"C:/Windows/Fonts/{name}",
        "arial.ttf",
        "C:/Windows/Fonts/arial.ttf"
    ]
    for font_path in fonts_to_try:
        try:
            return ImageFont.truetype(font_path, size)
        except:
            continue
    return ImageFont.load_default()

def create_blurred_background(image: Image.Image) -> Image.Image:
    """Create a blurred, darkened background that fills 1080x1920."""
    img_ratio = image.width / image.height
    reel_ratio = REEL_WIDTH / REEL_HEIGHT
    
    if img_ratio > reel_ratio:
        new_height = REEL_HEIGHT
        new_width = int(new_height * img_ratio)
    else:
        new_width = REEL_WIDTH
        new_height = int(new_width / img_ratio)
    
    resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    left = (new_width - REEL_WIDTH) // 2
    top = (new_height - REEL_HEIGHT) // 2
    cropped = resized.crop((left, top, left + REEL_WIDTH, top + REEL_HEIGHT))
    
    blurred = cropped.filter(ImageFilter.GaussianBlur(radius=40))
    darkened = Image.blend(blurred, Image.new('RGB', blurred.size, (0, 0, 0)), alpha=0.5)
    
    return darkened

def conform_video_to_cfr(input_path: str) -> str:
    """
    Converts video to Constant Frame Rate (30fps) to avoid MoviePy desync/slowdown issues.
    Saves a temporary file and returns its path.
    """
    import subprocess
    output_path = input_path.rsplit('.', 1)[0] + "_cfr.mp4"
    
    # Check if already conformed to avoid redundant work
    if "_cfr.mp4" in input_path:
        return input_path

    print(f"[GENERATOR] Conforming {os.path.basename(input_path)} to 30fps CFR...")
    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-filter:v', 'fps=fps=30',
        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '18',
        '-c:a', 'copy',
        output_path
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return output_path
    except Exception as e:
        print(f"[GENERATOR] CFR Conformation failed: {e}. Using original.")
        return input_path

# Zone Definitions
# Ultra-tight layout
ZONE_TOP_HEIGHT = 400
ZONE_MIDDLE_HEIGHT = 900
ZONE_BOTTOM_HEIGHT = 620

def create_foreground_image(image: Image.Image, max_width: int = 1000, max_height: int = 950) -> Image.Image:
    """Resize the main image to fit within the MIDDLE zone."""
    img_ratio = image.width / image.height
    target_ratio = max_width / max_height
    
    if img_ratio > target_ratio:
        new_width = max_width
        new_height = int(max_width / img_ratio)
    else:
        new_height = max_height
        new_width = int(max_height * img_ratio)
    
    return image.resize((new_width, new_height), Image.Resampling.LANCZOS)

def draw_branding(draw: ImageDraw.Draw):
    """Draw the Economika branding centered in the TOP zone - COMPACT VERSION."""
    # "ECONÓMIKA" Text
    font_large = get_font("ariblk.ttf", 90)  # Reduced for compactness
    brand_text = "ECONÓMIKA"
    bbox = draw.textbbox((0, 0), brand_text, font=font_large)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    
    # Start lower for more headspace (approx 220px from top)
    brand_y_start = 220
    
    x = (REEL_WIDTH - w) // 2
    draw.text((x, brand_y_start), brand_text, font=font_large, fill=WHITE)
    
    # "NOTICIAS" Box - Integrated closer
    font_small = get_font("arialbd.ttf", 55)
    news_text = "NOTICIAS"
    bbox_news = draw.textbbox((0, 0), news_text, font=font_small)
    nw, nh = bbox_news[2] - bbox_news[0], bbox_news[3] - bbox_news[1]
    
    padding_x, padding_y = 40, 10
    box_w = nw + (padding_x * 2)
    box_h = nh + (padding_y * 2)
    box_x = (REEL_WIDTH - box_w) // 2
    box_y = brand_y_start + h + 15
    
    draw.rectangle([box_x, box_y, box_x + box_w, box_y + box_h], fill=ECONOMIKA_RED)
    
    text_x = box_x + (box_w - nw) // 2
    text_y = box_y + (box_h - nh) // 2 - 4
    draw.text((text_x, text_y), news_text, font=font_small, fill=WHITE)

    # SUBTLE HANDLE - @economika.noticias
    font_handle = get_font("arial.ttf", 35)
    handle_text = "@economika.noticias"
    bh = draw.textbbox((0, 0), handle_text, font=font_handle)
    hw = bh[2] - bh[0]
    draw.text(((REEL_WIDTH - hw)//2, box_y + box_h + 15), handle_text, font=font_handle, fill=(200, 200, 200, 180))

def add_premium_overlay(image: Image.Image, headline: str, media_bottom_y: int, handle: str = ""):
    """Add branding and the new 'Characteristic' Headline Card."""
    draw = ImageDraw.Draw(image, 'RGBA')
    
    # 1. Draw TOP Branding
    draw_branding(draw)
    
    # 2. Draw 'Characteristic' Headline Card
    base_font_size = 34
    card_width = 860 # Wider to be more elongated horizontally
    card_max_height = 400
    text_margin_x = 100
    text_margin_y = 40
    
    max_w_text = card_width - (text_margin_x * 2)
    
    def try_fit(text, font_size):
        f = get_font("segoeuib.ttf", font_size)
        if f.getname() == "Arial":
             f = get_font("calibrib.ttf", font_size)
             
        words = text.split()
        lines = []
        curr = []
        for word in words:
            test = " ".join(curr + [word])
            bbox = draw.textbbox((0, 0), test, font=f)
            if (bbox[2] - bbox[0]) < max_w_text:
                curr.append(word)
            else:
                lines.append(" ".join(curr))
                curr = [word]
        if curr: lines.append(" ".join(curr))
        
        wrapped = "\n".join(lines)
        t_bbox = draw.multiline_textbbox((0, 0), wrapped, font=f, spacing=24)
        return lines, f, (t_bbox[3] - t_bbox[1]), (t_bbox[2] - t_bbox[0]), wrapped

    font_size = base_font_size
    lines, f_headline, text_h, text_w, wrapped = try_fit(headline, font_size)
    
    while (text_h > (card_max_height - text_margin_y*2) or len(lines) > 7) and font_size > 30:
        font_size -= 2
        lines, f_headline, text_h, text_w, wrapped = try_fit(headline, font_size)
    
    card_height = text_h + (text_margin_y * 2)
    # Remove min height constraint to make it compact
    
    # Position Card: Anchor exactly relative to the media bottom
    # Use a relaxed gap of 100px
    card_y = media_bottom_y + 100
    
    # Safety check: if card goes off screen, push it up
    # Safety check: if card goes off screen or overlaps bottom UI
    # Instagram bottom UI is approx 280-350px from bottom on various devices
    MAX_CONTENT_Y = REEL_HEIGHT - 380 
    
    if card_y + card_height > MAX_CONTENT_Y:
        card_y = MAX_CONTENT_Y - card_height

    box_cx = REEL_WIDTH // 2
    box_x0 = box_cx - (card_width // 2)
    box_y0 = card_y
    box_x1 = box_cx + (card_width // 2)
    box_y1 = card_y + card_height
    
    # Draw Floating Box (Rounded Rect)
    shadow_offset = 12
    # Re-Draw Shadow FIRST
    draw.rounded_rectangle(
        [box_x0 + shadow_offset, box_y0 + shadow_offset, box_x1 + shadow_offset, box_y1 + shadow_offset],
        radius=40, fill=(0, 0, 0, 90)
    )
    # Redraw Main Box ON TOP
    draw.rounded_rectangle(
        [box_x0, box_y0, box_x1, box_y1],
        radius=40, fill=(25, 25, 25, 240), outline=ECONOMIKA_RED, width=4
    )
    
    # Draw Text centered
    text_x = box_cx - (text_w // 2)
    text_y = card_y + (card_height - text_h) // 2 - 5
    
    draw.multiline_text((text_x, text_y), wrapped, font=f_headline, fill=WHITE, align="center", spacing=24)
    
    return card_y

def generate_reel_from_image(image_path: str, headline: str, handle: str = "", output_name: str = "reel.mp4") -> str:
    """Generate a vertical Reel. Handles missing images gracefully with a branded background."""
    
    if image_path and os.path.exists(image_path):
        original = Image.open(image_path).convert('RGB')
        background = create_blurred_background(original)
        foreground = create_foreground_image(original, max_width=1000, max_height=950)
        fg_x = (REEL_WIDTH - foreground.width) // 2
        fg_y = 500 # Lowered start position
        composite = background.copy()
        composite.paste(foreground, (fg_x, fg_y))
        media_bottom = fg_y + foreground.height
    else:
        # Create a branded "Economika" background for text-only tweets
        composite = Image.new('RGB', (REEL_WIDTH, REEL_HEIGHT), (15, 15, 15))
        draw = ImageDraw.Draw(composite)
        # Subtle red gradient or accent
        draw.rectangle([0, 0, REEL_WIDTH, 40], fill=ECONOMIKA_RED)
        draw.rectangle([0, REEL_HEIGHT-40, REEL_WIDTH, REEL_HEIGHT], fill=ECONOMIKA_RED)
        media_bottom = 400 # Theoretical bottom of empty media space
    
    # Static overlays
    card_y = add_premium_overlay(composite, headline, media_bottom, handle)
    
    frame = np.array(composite)
    clip = ImageClip(frame).with_duration(REEL_DURATION)
    
    # --- BACKGROUND MUSIC FOR IMAGES ---
    music_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "music")
    audio_clip = None
    if os.path.exists(music_folder):
        import random
        from moviepy import AudioFileClip, afx
        
        music_files = [f for f in os.listdir(music_folder) if f.lower().endswith(('.mp3', '.wav'))]
        if music_files:
            try:
                music_path = os.path.join(music_folder, random.choice(music_files))
                print(f"[GENERATOR] Adding background music: {os.path.basename(music_path)}")
                
                audio_clip = AudioFileClip(music_path)
                # Loop audio to match duration
                audio_clip = audio_clip.with_duration(REEL_DURATION).with_effects([afx.AudioLoop(duration=REEL_DURATION)])
                # Moderate volume
                audio_clip = audio_clip.with_volume_scaled(0.4) 
                clip = clip.with_audio(audio_clip)
            except Exception as e:
                print(f"[GENERATOR] Failed to add audio: {e}")

    output_path = os.path.join(OUTPUT_DIR, output_name)
    print(f"[GENERATOR] Encoding image-reel to {output_name}...")
    
    clip.write_videofile(output_path, fps=30, codec='libx264', audio_codec='aac', 
                        pixel_format='yuv420p', audio=True if audio_clip else False, logger=None)
    
    if audio_clip: audio_clip.close()
    clip.close()
    
    # Force delete the big numpy array to free memory
    del frame
    return output_path

def process_video_for_reel(video_path: str, headline: str, handle: str = "", output_name: str = "reel.mp4", skip_subtitles: bool = False) -> str:
    """Process video with PRO-TIGHT zone management and duration capping."""
    print(f"[GENERATOR] Starting video processing: {os.path.basename(video_path)}")
    
    # PRE-PROCESS: Conform to CFR to avoid desync/slow-motion
    conformed_path = conform_video_to_cfr(video_path)
    
    clip = VideoFileClip(conformed_path)
    
    # CAP DURATION to 60 seconds max to avoid infinite rendering hangs
    if clip.duration > 60:
        print(f"[GENERATOR] Video exceeds 60s ({clip.duration:.1f}s), capping...")
        clip = clip.subclipped(0, 60)
    
    duration = clip.duration
    print(f"[GENERATOR] Duration: {duration:.1f}s | Resolution: {clip.w}x{clip.h}")
    
    try:
        # Background
        print("[GENERATOR] Creating blurred background...")
        frame_0 = clip.get_frame(0)
        bg_img = Image.fromarray(frame_0)
        background = create_blurred_background(bg_img)
        
        # Foreground Video Positioning
        scale = min(1080 / clip.w, 950 / clip.h)
        resized_clip = clip.resized(scale)
        resized_h = resized_clip.h
        
        # Position Lowered
        fg_y = 500
        
        # Common Overlay
        print("[GENERATOR] Creating branding overlay...")
        overlay_img = Image.new('RGBA', (REEL_WIDTH, REEL_HEIGHT), (0, 0, 0, 0))
        card_y = add_premium_overlay(overlay_img, headline, fg_y + resized_h, handle)
        overlay_array = np.array(overlay_img)
        overlay_clip = ImageClip(overlay_array).with_duration(duration)
        
        bg_array = np.array(background)
        bg_clip = ImageClip(bg_array).with_duration(duration)
        
        # Subtitles Integration (only if not skipped)
        subtitle_clips = []
        if not skip_subtitles:
            print("[GENERATOR] Transcribing audio for subtitles...")
            try:
                segments = get_subtitles(conformed_path)
                
                # --- PREMIUM "TRUMP-STYLE" SUBTITLE DESIGN ---
                current_font = get_font("ariblk.ttf", 48) # Bold sans-serif
                
                for seg in segments:
                    text_content = seg['text'].strip().upper() 
                    if not text_content: continue
                    
                    start = seg['start']
                    end = min(seg['end'], duration)
                    if start >= duration: continue
                    
                    # Create Subtitle Box using PIL for perfect control
                    box_margin = 100
                    max_box_width = REEL_WIDTH - (box_margin * 2)
                    
                    # Wrap text manually
                    words = text_content.split()
                    lines = []
                    curr_line = []
                    
                    # Temp image for measuring
                    temp_draw = ImageDraw.Draw(Image.new('RGBA', (1,1)))
                    
                    for word in words:
                        test_line = " ".join(curr_line + [word])
                        bbox = temp_draw.textbbox((0, 0), test_line, font=current_font)
                        if (bbox[2] - bbox[0]) < (max_box_width - 60): # 30px padding
                            curr_line.append(word)
                        else:
                            if curr_line: lines.append(" ".join(curr_line))
                            curr_line = [word]
                    if curr_line: lines.append(" ".join(curr_line))
                    
                    wrapped_text = "\n".join(lines)
                    
                    # Calculate final box size
                    t_bbox = temp_draw.multiline_textbbox((0, 0), wrapped_text, font=current_font, spacing=10)
                    tw = t_bbox[2] - t_bbox[0]
                    th = t_bbox[3] - t_bbox[1]
                    
                    padding_x, padding_y = 40, 25
                    box_w = min(max_box_width, tw + (padding_x * 2))
                    box_h = th + (padding_y * 2)
                    
                    # --- NEW STEALTH ENGAGEMENT STYLE ---
                    # No box, just high-contrast text with outline and shadow
                    
                    # Create Alpha Image for the subtitle
                    sub_img = Image.new('RGBA', (REEL_WIDTH, REEL_HEIGHT), (0, 0, 0, 0))
                    sub_draw = ImageDraw.Draw(sub_img)
                    
                    # Position: Lower-Middle (slightly below the center of the video)
                    text_x = REEL_WIDTH // 2
                    text_y = fg_y + (resized_h * 0.75)
                    
                    # Draw Outline/Stroke for readability (thick black outline)
                    stroke_width = 4
                    sub_draw.multiline_text(
                        (text_x, text_y),
                        wrapped_text,
                        font=current_font,
                        fill=BLACK,
                        anchor="mm",
                        align="center",
                        spacing=10,
                        stroke_width=stroke_width,
                        stroke_fill=BLACK
                    )
                    
                    # Draw Subtle Shadow
                    shadow_offset = 5
                    sub_draw.multiline_text(
                        (text_x + shadow_offset, text_y + shadow_offset),
                        wrapped_text,
                        font=current_font,
                        fill=(0, 0, 0, 150),
                        anchor="mm",
                        align="center",
                        spacing=10
                    )
                    
                    # Draw Main Text (White)
                    sub_draw.multiline_text(
                        (text_x, text_y),
                        wrapped_text,
                        font=current_font,
                        fill=WHITE,
                        anchor="mm",
                        align="center",
                        spacing=10
                    )
                    
                    sub_array = np.array(sub_img)
                    sub_clip = ImageClip(sub_array).with_start(start).with_end(end)
                    subtitle_clips.append(sub_clip)
                    
            except Exception as e:
                print(f"[GENERATOR] Subtitles failed: {e}")
        else:
            print("[GENERATOR] Skipping subtitles as requested.")

        # IMPORTANT: Subtitles use absolute canvas coordinates, so they must be 
        # added to the FINAL composite, not the center video segment
        center_video_segment = resized_clip

        final = CompositeVideoClip([
            bg_clip, 
            center_video_segment.with_position(('center', fg_y)), 
            overlay_clip
        ] + subtitle_clips, size=(REEL_WIDTH, REEL_HEIGHT)).with_duration(duration)
        
        output_path = os.path.join(OUTPUT_DIR, output_name)
        print(f"[GENERATOR] Encoding video to {output_name}...")
        
        # PERFORMANCE OPTIONS
        # We set temp_audiofile and remove_temp to be explicit and avoid race conditions
        # We also use a more stable 'p1' or 'p2' preset for NVENC
        common_params = {
            'fps': 30,
            'audio_codec': 'aac',
            'pixel_format': 'yuv420p',
            'audio': True,
            'logger': None,
            'threads': 4, # Reduced from 8 to avoid memory contention
        }

        try:
            print("[GENERATOR] Attempting NVIDIA NVENC Acceleration...")
            final.write_videofile(output_path, codec='h264_nvenc', 
                                 ffmpeg_params=['-preset', 'p2', '-tune', 'hq', '-rc', 'vbr', '-cq', '24'],
                                 **common_params)
        except Exception as e:
            print(f"[GENERATOR] NVENC failed or not available ({e}). Falling back to CPU...")
            final.write_videofile(output_path, codec='libx264', 
                                 preset='faster', # Better than ultrafast for final quality
                                 **common_params)
        print(f"[GENERATOR] Encoding complete.")
        
        # Explicit cleanup
        final.close()
        bg_clip.close()
        overlay_clip.close()
        resized_clip.close()
        
        # DO NOT DELETE conformed_path here if it's the original, 
        # but if it's the temp _cfr.mp4, we could. 
        # However, for safety and traceability, we'll let existing cleanup handle it.
        
    finally:
        clip.close()
        
    return output_path

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        path = sys.argv[1]
        headline = sys.argv[2]
        handle = sys.argv[3] if len(sys.argv) > 3 else ""
        
        if path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
            result = generate_reel_from_image(path, headline, handle)
        else:
            result = process_video_for_reel(path, headline, handle)
        print(f"Generated: {result}")
