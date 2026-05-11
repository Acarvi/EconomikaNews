"""
Video/Image to Reel Generator - Premium "Economika" Design.
Creates vertical 1080x1920 videos with blurred background, 
branded Economika overlays, and high-impact text.
"""
import os
from PIL import Image, ImageFilter, ImageDraw, ImageFont
try:
    from moviepy import VideoFileClip, ImageClip, CompositeVideoClip, TextClip, concatenate_videoclips
except ImportError:
    from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, TextClip, concatenate_videoclips
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

    # SOURCE ATTRIBUTION (New)
    # Passed via global or argument? We need to pass it to draw_branding or handle it in add_premium_overlay
    # Since draw_branding is a helper, we'll strip this if we move it to add_premium_overlay
    # But for now, let's leave handle here and add source in add_premium_overlay


def add_premium_overlay(image: Image.Image, headline: str, media_bottom_y: int, handle: str = "", source: str = "", headline_pos: str = "bottom"):
    """
    Add branding and the new 'Characteristic' Headline Card.
    headline_pos: 'top', 'center', 'bottom'
    """
    draw = ImageDraw.Draw(image, 'RGBA')
    
    # 1. Draw TOP Branding
    draw_branding(draw)

    # 1.5 Draw Source (if available) - Moved to TOP LEFT for visibility
    if source:
        font_source = get_font("arial.ttf", 26) # Slightly smaller
        source_text = f"Fuente: {source}"
        # Position: Top Left, below the red branding bar (Bar ends ~140px?)
        # Let's say x=40, y=160
        draw.text((40, 160), source_text, font=font_source, fill=(200, 200, 200, 180))
    
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
             
        words = str(text).split()
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
    
    # POSITIONING LOGIC
    if headline_pos == "top":
        card_y = 450 # Below branding
    elif headline_pos == "center":
        card_y = (REEL_HEIGHT - card_height) // 2
    else: # bottom
        # Position Card: Anchor exactly relative to the media bottom
        # Use a relaxed gap of 100px
        card_y = media_bottom_y + 100
        
        # Safety check: if card goes off screen or overlaps bottom UI
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

def generate_reel_from_image(image_path: str, headline: str, handle: str = "", output_name: str = "reel.mp4", source: str = "", headline_pos: str = "bottom") -> str:
    if image_path and os.path.exists(image_path):
        original = Image.open(image_path).convert('RGB')
        background = Image.new('RGB', (REEL_WIDTH, REEL_HEIGHT), (0,0,0)) # Pure Black background
        foreground = create_foreground_image(original, max_width=1000, max_height=950)
        fg_x, fg_y = (REEL_WIDTH - foreground.width) // 2, (REEL_HEIGHT - foreground.height) // 2
        composite = background.copy()
        composite.paste(foreground, (fg_x, fg_y))
        media_bottom = fg_y + foreground.height
    else:
        composite = Image.new('RGB', (REEL_WIDTH, REEL_HEIGHT), (15, 15, 15))
        draw = ImageDraw.Draw(composite)
        draw.rectangle([0, 0, REEL_WIDTH, 40], fill=ECONOMIKA_RED)
        draw.rectangle([0, REEL_HEIGHT-40, REEL_WIDTH, REEL_HEIGHT], fill=ECONOMIKA_RED)
        media_bottom = 400
    
    card_y = add_premium_overlay(composite, headline, media_bottom, handle, source=source, headline_pos=headline_pos)
    frame = np.array(composite)
    clip = ImageClip(frame).set_duration(REEL_DURATION)
    
    # --- BACKGROUND MUSIC FOR IMAGES ---
    music_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "music")
    audio_clip = None
    if os.path.exists(music_folder):
        import random
        try:
            from moviepy import AudioFileClip, afx
        except ImportError:
            from moviepy.editor import AudioFileClip, afx
        
        music_files = [f for f in os.listdir(music_folder) if f.lower().endswith(('.mp3', '.wav'))]
        if music_files:
            try:
                music_path = os.path.join(music_folder, random.choice(music_files))
                print(f"[GENERATOR] Adding background music: {os.path.basename(music_path)}")
                
                audio_clip = AudioFileClip(music_path)
                # Loop audio to match duration
                audio_clip = audio_clip.set_duration(REEL_DURATION).fx(afx.audio_loop, duration=REEL_DURATION)
                # Moderate volume
                audio_clip = audio_clip.volumex(0.4) 
                clip = clip.set_audio(audio_clip)
            except Exception as e:
                print(f"[GENERATOR] Failed to add audio: {e}")

    output_path = os.path.join(OUTPUT_DIR, output_name)
    print(f"[GENERATOR] Encoding image-reel to {output_name}...")
    
    clip.write_videofile(output_path, fps=30, codec='libx264', audio_codec='aac', 
                        ffmpeg_params=['-pix_fmt', 'yuv420p'], audio=True if audio_clip else False, logger=None)
    
    if audio_clip: audio_clip.close()
    clip.close()
    
    # Force delete the big numpy array to free memory
    del frame
    return output_path

def time_str_to_seconds(time_str: str) -> float:
    """Converts MM:SS or integer string to seconds. Returns 0 if invalid."""
    try:
        if not time_str or time_str == "0" or time_str == "00:00": return 0.0
        parts = time_str.split(':')
        if len(parts) == 2:
            return float(parts[0]) * 60 + float(parts[1])
        return float(time_str)
    except:
        return 0.0

def process_video_for_reel(video_path: str, headline: str, handle: str = "", output_name: str = "reel.mp4", 
                           skip_subtitles: bool = False, source: str = "", 
                           start_time_str: str = "00:00", end_time_str: str = "END", 
                           cover_path: str = None, 
                           headline_pos: str = "bottom",
                           subtitle_pos: str = "bottom") -> str:
    """Process video with PRO-TIGHT zone management and duration capping."""
    print(f"[GENERATOR] Starting video processing: {os.path.basename(video_path)}")
    
    # PRE-PROCESS: Conform to CFR to avoid desync/slow-motion
    conformed_path = conform_video_to_cfr(video_path)
    
    clip = VideoFileClip(conformed_path)
    total_duration = clip.duration
    
    start_sec = time_str_to_seconds(start_time_str)
    
    if end_time_str and end_time_str != "END":
        end_sec = time_str_to_seconds(end_time_str)
        if end_sec > 0 and end_sec < total_duration and end_sec > start_sec:
            print(f"[GENERATOR] Smart Trimming: {start_sec}s to {end_sec}s")
            clip = clip.subclip(start_sec, end_sec)
        else:
             if start_sec > 0: clip = clip.subclip(start_sec)
    elif start_sec > 0:
        print(f"[GENERATOR] Smart Trimming Start: {start_sec}s")
        clip = clip.subclip(start_sec)

    # CAP DURATION to 90 seconds
    MAX_DURATION = 90
    if clip.duration > MAX_DURATION:
        print(f"[GENERATOR] Video exceeds {MAX_DURATION}s ({clip.duration:.1f}s), capping...")
        clip = clip.subclip(0, MAX_DURATION)
    
    duration = clip.duration
    print(f"[GENERATOR] Duration: {duration:.1f}s | Resolution: {clip.w}x{clip.h}")
    
    prepend_clip = None
    if cover_path and os.path.exists(cover_path):
        print(f"[GENERATOR] Prepending Cover Image ({cover_path})...")
        try:
            cover_img = Image.open(cover_path).convert('RGB').resize((REEL_WIDTH, REEL_HEIGHT))
            prepend_clip = ImageClip(np.array(cover_img)).set_duration(0.1)
        except Exception as e:
            print(f"[GENERATOR] Failed to load cover: {e}")
    
    try:
        # Background: Pure Black
        print("[GENERATOR] Creating black background (No Blur)...")
        bg_img = Image.new('RGB', (REEL_WIDTH, REEL_HEIGHT), (0, 0, 0))
        bg_clip = ImageClip(np.array(bg_img)).set_duration(duration)
        
        # Foreground Video Positioning
        target_max_w = REEL_WIDTH
        target_max_h = 1080 
        scale = min(target_max_w / clip.w, target_max_h / clip.h)
        resized_clip = clip.resize(scale)
        resized_h = resized_clip.h
        fg_y = (REEL_HEIGHT - resized_h) // 2
        
        # Common Overlay
        print("[GENERATOR] Creating branding overlay...")
        overlay_img = Image.new('RGBA', (REEL_WIDTH, REEL_HEIGHT), (0, 0, 0, 0))
        card_y = add_premium_overlay(overlay_img, headline, fg_y + resized_h, handle, source=source, headline_pos=headline_pos)
        overlay_clip = ImageClip(np.array(overlay_img)).set_duration(duration)
        
        # Subtitles Integration: Hormozi Style
        subtitle_clips = []
        if not skip_subtitles:
            print("[GENERATOR] Transcribing and rendering Hormozi-style subtitles...")
            try:
                segments = get_subtitles(conformed_path)
                
                # --- STYLE DEFINITIONS ---
                font_size = 75
                current_font = get_font("ariblk.ttf", font_size)
                YELLOW = (255, 255, 0)
                
                for seg in segments:
                    text_content = seg['text'].strip().upper() 
                    if not text_content: continue
                    
                    sub_img = Image.new('RGBA', (REEL_WIDTH, REEL_HEIGHT), (0, 0, 0, 0))
                    sub_draw = ImageDraw.Draw(sub_img)
                    
                    # Position: Dynamic
                    text_x = REEL_WIDTH // 2
                    if subtitle_pos == "top":
                        text_y = 550 # Below branding/headline
                    elif subtitle_pos == "center":
                        text_y = REEL_HEIGHT // 2
                    else: # bottom
                        text_y = card_y - 120 # Above the white card
                    
                    # Render text with Stroke and Shadow
                    shadow_color = (0, 0, 0, 200)
                    sub_draw.text((text_x + 6, text_y + 6), text_content, font=current_font, fill=shadow_color, anchor="mm", align="center")
                    stroke_w = 6
                    stroke_color = (0, 0, 0)
                    for ox in range(-stroke_w, stroke_w + 1):
                        for oy in range(-stroke_w, stroke_w + 1):
                            if ox*ox + oy*oy <= stroke_w*stroke_w:
                                sub_draw.text((text_x + ox, text_y + oy), text_content, font=current_font, fill=stroke_color, anchor="mm", align="center")
                    
                    # Draw Main Text (Yellow)
                    sub_draw.text((text_x, text_y), text_content, font=current_font, fill=YELLOW, anchor="mm", align="center")
                    
                    sub_clip = ImageClip(np.array(sub_img)).set_start(seg['start']).set_end(min(seg['end'], duration))
                    subtitle_clips.append(sub_clip)
                    
            except Exception as e:
                print(f"[GENERATOR] Subtitles failed: {e}")
        else:
            print("[GENERATOR] Skipping subtitles as requested.")

        # Composite the final video
        final_body = CompositeVideoClip([
            bg_clip, 
            resized_clip.set_position(('center', fg_y)), 
            overlay_clip
        ] + subtitle_clips, size=(REEL_WIDTH, REEL_HEIGHT)).set_duration(duration)
        
        # Concatenate if cover exists
        if prepend_clip:
            from moviepy import concatenate_videoclips
            final = concatenate_videoclips([prepend_clip, final_body], method="compose")
        else:
            final = final_body
            
        output_path = os.path.join(OUTPUT_DIR, output_name)
        print(f"[GENERATOR] Encoding video to {output_name}...")
        
        # PERFORMANCE OPTIONS
        # We set temp_audiofile and remove_temp to be explicit and avoid race conditions
        # We also use a more stable 'p1' or 'p2' preset for NVENC
        import time, uuid
        unique_id = str(uuid.uuid4())[:8]
        temp_audio = os.path.join(OUTPUT_DIR, f"temp_audio_{unique_id}.m4a")

        common_params = {
            'fps': 30,
            'audio_codec': 'aac',
            'audio': True,
            'logger': None,
            'threads': 4,
            'temp_audiofile': temp_audio,
            'remove_temp': True
        }

        try:
            print("[GENERATOR] Attempting NVIDIA NVENC Acceleration...")
            final.write_videofile(output_path, codec='h264_nvenc', 
                                 ffmpeg_params=['-preset', 'p2', '-tune', 'hq', '-rc', 'vbr', '-cq', '24', '-pix_fmt', 'yuv420p'],
                                 **common_params)
        except Exception as e:
            print(f"[GENERATOR] NVENC failed or not available ({e}). Falling back to CPU...")
            time.sleep(1) # Small breather for OS to release files
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
