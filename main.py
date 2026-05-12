import os
import sys

from typing import Dict
import os
import shutil
import webbrowser
import time
import re
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from datetime import datetime
from core.scraper import scrape_tweet
from core.downloader import download_media, DOWNLOADS_DIR
from core.ai_handler import generate_content_ai
from core.generator import generate_reel_from_image, process_video_for_reel, OUTPUT_DIR
import cv2
import numpy as np
from PIL import Image, ImageTk, ImageDraw
try:
    from ffpyplayer.player import MediaPlayer
except ImportError:
    MediaPlayer = None

import core.publisher as publisher # New automation module
from core.youtube_uploader import upload_short
from utils.cleanup import cleanup_old_files, cleanup_temp_files
import requests # Added for cloud sync
from utils.network import check_centralai_health
from core.ai_handler import CENTRAL_AI_URL

# --- CONFIG & HELPERS ---
CLOUD_SERVER_URL = os.environ.get("ECONOMIKA_SERVER_URL", "https://economikanoticias.onrender.com").rstrip("/")
LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

class StatusManager:
    """Manages status updates for both CLI and GUI, with optional file logging."""
    def __init__(self, gui_status_var=None, gui_log_widget=None, enable_file_log=True):
        self.gui_status_var = gui_status_var
        self.gui_log_widget = gui_log_widget
        self.log_file = None
        if enable_file_log:
            log_filename = datetime.now().strftime("%Y%m%d_%H%M%S") + "_session.log"
            self.log_file = os.path.join(LOGS_DIR, log_filename)
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write(f"=== Economika Session Log - {datetime.now().isoformat()} ===\n\n")

    def update(self, message: str):
        timestamp = datetime.now().strftime('%H:%M:%S')
        full_msg = f"[{timestamp}] {message}"
        
        # Robust terminal print (prevents crash on unsupported emojis)
        try:
            print(full_msg, flush=True)
        except UnicodeEncodeError:
            try:
                # Fallback: Strip non-ascii for the terminal only
                print(full_msg.encode('ascii', 'ignore').decode('ascii'), flush=True)
            except:
                pass # If terminal is truly broken, just continue to GUI/File logs
        
        # Write to file log
        if self.log_file:
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(f"[{timestamp}] {message}\n")
            except: pass
        
        # Schedule UI updates on the main thread using a widget's .after()
        target_widget = self.gui_log_widget
        
        if target_widget:
            def _ui_update():
                try:
                    if self.gui_status_var:
                        self.gui_status_var.set(message)
                    
                    # BMP-only sanitization for Tkinter compatibility (Windows fix)
                    safe_msg = "".join(c for c in message if ord(c) <= 0xFFFF)
                    
                    self.gui_log_widget.configure(state='normal')
                    self.gui_log_widget.insert(tk.END, f"[{timestamp}] {safe_msg}\n")
                    self.gui_log_widget.see(tk.END)
                    self.gui_log_widget.configure(state='disabled')
                except: pass
            target_widget.after(0, _ui_update)
        elif self.gui_status_var:
            # Fallback if no log widget is available (mostly CLI or headless)
            self.gui_status_var.set(message)


def render_item_assets(tweet_data: Dict, status: StatusManager, feedback: str = None, 
                       headline_pos: str = "bottom", subtitle_pos: str = "bottom") -> Dict:
    """Helper to generate AI content and render video for a single item."""
    tweet_url = tweet_data.get('url', 'unknown')
    date_str = datetime.now().strftime("%Y%m%d")
    uploader_id = tweet_data.get('uploader_id', 'economika')
    is_video = tweet_data.get('is_video', False)

    # 1. Download (If not already provided from pre-filter)
    local_path = tweet_data.get('local_media_path')
    if local_path and os.path.exists(local_path):
        media_path = local_path
        status.update(f"   Using pre-downloaded media for {uploader_id}...")
    else:
        status.update(f"   Downloading media for {uploader_id}...")
        # Pass direct_url if available to bypass yt-dlp
        success, media_path = download_media(tweet_url, thumbnail_url=tweet_data.get('thumbnail'), is_video=is_video, direct_url=tweet_data.get('media_url'))
        if not success: media_path = None
    
    # 2. AI Gen - SKIP IF CONTENT ALREADY PROVIDED (e.g. reviewed in Stage 1 or from Cloud)
    # Only regenerate if explicit feedback is passed to this function (Stage 4)
    if tweet_data.get('headline') and tweet_data.get('caption') and not feedback:
        status.update("   ⚡ Using reviewed/pre-generated content...")
        headline = tweet_data['headline']
        caption = tweet_data['caption']
        slug = tweet_data.get('slug', 'noticia')
        shorts_title = tweet_data.get('shorts_title', headline[:100])
        caption_b = tweet_data.get('caption_b', caption)
        source = tweet_data.get('source', '')
    else:
        status.update("   Generando redacción final (Gemini 2.0)...")
        from core.ai_handler import generate_content_ai
        # Prioritize feedback/instructions from Stage 1
        user_instr = tweet_data.get('user_instructions', '')
        ai_feedback = feedback if feedback else user_instr
        h, c, s, st, cb, src, loc, start_t, end_t = generate_content_ai(tweet_data, media_path, ai_feedback, quality="pro")
        headline, caption, slug, shorts_title, caption_b, source = h, c, s, st, cb, src
        # Store trimming info in tweet_data for re-use if needed
        tweet_data['best_segment_start'] = start_t
        tweet_data['best_segment_end'] = end_t

    # 3. Folder Setup - Unique naming with ID to avoid [WinError 32]
    clean_slug = re.sub(r'[^a-z0-9_]', '', slug.lower().replace(" ", "_").replace("-", "_"))[:20]
    tweet_id = str(tweet_data.get('id', 'item'))
    item_folder_name = f"{date_str}_{tweet_id}_{clean_slug}"
    item_folder_path = os.path.join(OUTPUT_DIR, item_folder_name)
    os.makedirs(item_folder_path, exist_ok=True)
    base_name = f"economika_{item_folder_name}"

    # 4. Save artifacts - REMOVED .md and .html per user request
    # caption_path = os.path.join(item_folder_path, f"{base_name}.md")
    # with open(caption_path, 'w', encoding='utf-8') as f:
    #     f.write(f"# {headline}\n\n### 📹 SHORTS\n{shorts_title}\n\n### 📝 CAPTION (A)\n{caption}\n\n### 📝 CAPTION (B)\n{caption_b}\n")
    
    # html_path = os.path.join(item_folder_path, "copiar_movil.html")
    # from main import generate_mobile_html
    # generate_mobile_html(html_path, headline, shorts_title, caption)

    # 5. Render Reel
    status.update("   Rendering Video...")
    output_name = f"{base_name}.mp4"
    skip_subtitles = tweet_data.get('skip_subtitles', False)
    
    # CRITICAL FIX: Check actual file extension, as Viral Scout metadata might be outdated/wrong
    actual_is_video = is_video
    if media_path:
        ext = media_path.lower()
        if ext.endswith(('.jpg', '.jpeg', '.png', '.webp')):
            actual_is_video = False
    
    # Use the edited/detected source for rendering if available, fallback to uploader_id
    render_source = source if source else uploader_id

    if actual_is_video and media_path:
        start_t = tweet_data.get('best_segment_start', '00:00')
        end_t = tweet_data.get('best_segment_end', 'END')
        cover_path = tweet_data.get('cover_path', None) # Passed via hack for re-rendering
        
        temp_reel_path = process_video_for_reel(media_path, headline, render_source, output_name, 
                                               skip_subtitles=skip_subtitles, source=render_source, 
                                               start_time_str=start_t, end_time_str=end_t, 
                                               cover_path=cover_path,
                                               headline_pos=headline_pos,
                                               subtitle_pos=subtitle_pos)
    else:
        temp_reel_path = generate_reel_from_image(media_path, headline, render_source, output_name, source=render_source)
    
    final_reel_path = os.path.join(item_folder_path, output_name)
    if temp_reel_path and os.path.exists(temp_reel_path) and temp_reel_path != final_reel_path:
        shutil.move(temp_reel_path, final_reel_path)
    
    # NOTE: We do NOT delete media_path here anymore.
    # Cleanup happens in PostAiCurationManager._finish_close to allow RAW publishing.

    return {
        'folder': item_folder_path,
        'reel_path': final_reel_path,
        'headline': headline,
        'shorts_title': shorts_title,
        'caption': caption,
        'caption_b': caption_b,
        'source': source,
        'tweet_data': tweet_data,
        'headline_pos': headline_pos,
        'subtitle_pos': subtitle_pos
    }

def process_item_callback(item, feedback=None):
    """Callback wrapper for PostAiCurationManager UI actions."""
    # Dummy status for background re-render
    status = StatusManager(enable_file_log=False)
    
    # Extract positions from item (updated by UI before calling this)
    h_pos = item.get('headline_pos', 'bottom')
    s_pos = item.get('subtitle_pos', 'bottom')
    
    return render_item_assets(item, status, feedback=feedback, 
                              headline_pos=h_pos, subtitle_pos=s_pos)

class PostAiCurationManager:
    # Existing code here for clarity in replacement
    def __init__(self, parent, items, status_manager, process_callback):
        self.root = tk.Toplevel(parent)
        self.root.title(f"Economika Noticiero - Revisión de Lote ({len(items)} Reels)")
        self.root.geometry("1400x950")
        self.root.configure(bg="#0a0a0a")
        self.root.grab_set()
        
        self.items = items
        self.current_idx = 0
        self.status = status_manager
        self.process_callback = process_callback
        self.approved_folders = []
        
        self.cap = None
        self.player = None
        self.is_muted = False
        self.overlay_np = None # Fix AttributeError in update_frame
        
        # Platform Selection Variables
        self.use_yt = tk.BooleanVar(value=True)
        self.use_fb = tk.BooleanVar(value=True)
        self.use_ig = tk.BooleanVar(value=True)
        self.use_ig_stories = tk.BooleanVar(value=False)
        
        # Positioning Variables
        self.headline_pos = tk.StringVar(value="bottom")
        self.subtitle_pos = tk.StringVar(value="bottom")

        # --- UI LAYOUT ---
        # Left: Preview
        self.preview_frame = tk.Frame(self.root, bg="#0a0a0a", width=500)
        self.preview_frame.pack(side="left", padx=40, pady=40, fill="both", expand=True)
        
        self.canvas = tk.Canvas(self.preview_frame, width=400, height=711, bg="black", highlightthickness=1, highlightbackground="#333")
        self.canvas.pack(pady=10)
        
        self.btn_mute = tk.Button(self.preview_frame, text="🔊", bg="#222", fg="white", font=("Segoe UI", 12), width=4, command=self.toggle_mute, borderwidth=0)
        self.btn_mute.pack(pady=5)

        # Right: Editorial & Publishing Hub
        self.info_frame = tk.Frame(self.root, bg="#0a0a0a", width=600)
        self.info_frame.pack(side="right", padx=40, pady=40, fill="both")
        
        self.header_label = tk.Label(self.info_frame, text="EDITORIAL HUB", font=("Segoe UI Black", 24), fg="white", bg="#0a0a0a")
        self.header_label.pack(anchor="w", pady=(0, 20))

        # Inputs
        tk.Label(self.info_frame, text="TITULAR (HEADLINE)", font=("Segoe UI Bold", 10), fg="#888", bg="#0a0a0a").pack(anchor="w")
        self.shorts_text = tk.Text(self.info_frame, height=2, width=55, bg="#111", fg="white", font=("Segoe UI", 13), insertbackground="white", padx=15, pady=15, borderwidth=0)
        self.shorts_text.pack(fill="x", pady=(5, 20))
        
        tk.Label(self.info_frame, text="CAPCIÓN (EDITORIAL)", font=("Segoe UI Bold", 10), fg="#888", bg="#0a0a0a").pack(anchor="w")
        self.caption_text = tk.Text(self.info_frame, height=8, width=55, bg="#111", fg="white", font=("Segoe UI", 12), insertbackground="white", padx=15, pady=15, borderwidth=0)
        self.caption_text.pack(fill="x", pady=(5, 20))

        # Botonera 1: Platforms
        self.plat_frame = tk.LabelFrame(self.info_frame, text=" PLATAFORMAS DE SALIDA ", fg="#555", bg="#0a0a0a", font=("Segoe UI Bold", 9), padx=15, pady=15)
        self.plat_frame.pack(fill="x", pady=10)
        
        tk.Checkbutton(self.plat_frame, text="YouTube Shorts", variable=self.use_yt, bg="#0a0a0a", fg="#ff4444", activebackground="#0a0a0a", font=("Segoe UI Bold", 10)).pack(side="left", padx=10)
        tk.Checkbutton(self.plat_frame, text="Facebook Reels", variable=self.use_fb, bg="#0a0a0a", fg="#4444ff", activebackground="#0a0a0a", font=("Segoe UI Bold", 10)).pack(side="left", padx=10)
        tk.Checkbutton(self.plat_frame, text="Instagram Reels", variable=self.use_ig, bg="#0a0a0a", fg="#ff44ff", activebackground="#0a0a0a", font=("Segoe UI Bold", 10)).pack(side="left", padx=10)
        tk.Checkbutton(self.plat_frame, text="IG Stories", variable=self.use_ig_stories, bg="#0a0a0a", fg="#ffff44", activebackground="#0a0a0a", font=("Segoe UI Bold", 10)).pack(side="left", padx=10)

        # Botonera 2: Publishing Actions
        self.act_frame = tk.Frame(self.info_frame, bg="#0a0a0a")
        self.act_frame.pack(fill="x", pady=20)
        
        self.btn_pub_all = tk.Button(self.act_frame, text="⚡ PUBLICAR EN TODAS", bg="#E31E24", fg="white", font=("Segoe UI Black", 12), 
                                    padx=20, pady=15, borderwidth=0, command=lambda: self.publish_action(all_platforms=True))
        self.btn_pub_all.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        self.btn_pub_sel = tk.Button(self.act_frame, text="🚀 PUBLICAR SELECCIONADAS", bg="#333", fg="white", font=("Segoe UI Black", 11), 
                                    padx=20, pady=15, borderwidth=0, command=self.publish_action)
        self.btn_pub_sel.pack(side="left", fill="x", expand=True, padx=(5, 0))

        # Botonera 3: Scheduling & Batch
        self.batch_frame = tk.Frame(self.info_frame, bg="#0a0a0a")
        self.batch_frame.pack(fill="x", pady=(0, 20))
        
        self.btn_batch = tk.Button(self.batch_frame, text="📅 PROGRAMAR LOTE (GENERAL)", bg="#27ae60", fg="white", font=("Segoe UI Black", 11), 
                                  padx=20, pady=15, borderwidth=0, command=self.add_to_batch)
        self.btn_batch.pack(fill="x")

        # Botonera 4: Utilities & Positioning
        self.util_frame = tk.Frame(self.info_frame, bg="#0a0a0a")
        self.util_frame.pack(fill="x")
        
        # Regeneration & Discard
        self.btn_regen_c = tk.Button(self.util_frame, text="🔄 Regenerar Caption", bg="#222", fg="#888", font=("Segoe UI Bold", 9), padx=10, pady=10, borderwidth=0, command=lambda: self.regenerate("caption"))
        self.btn_regen_c.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        self.btn_regen_h = tk.Button(self.util_frame, text="✍️ Regenerar Título", bg="#222", fg="#888", font=("Segoe UI Bold", 9), padx=10, pady=10, borderwidth=0, command=lambda: self.regenerate("headline"))
        self.btn_regen_h.pack(side="left", fill="x", expand=True, padx=(5, 5))
        
        self.btn_discard = tk.Button(self.util_frame, text="🗑️ Descartar", bg="#3a0a0a", fg="#f44", font=("Segoe UI Bold", 9), padx=10, pady=10, borderwidth=0, command=self.discard)
        self.btn_discard.pack(side="left", fill="x", expand=True, padx=(5, 0))
        
        # Positioning (Pre-Render Level)
        self.pos_frame = tk.Frame(self.info_frame, bg="#0a0a0a")
        self.pos_frame.pack(fill="x", pady=20)
        
        tk.Label(self.pos_frame, text="Titular:", bg="#0a0a0a", fg="#555", font=("Segoe UI", 9)).grid(row=0, column=0, padx=5)
        self.cb_headline = ttk.Combobox(self.pos_frame, textvariable=self.headline_pos, values=["top", "center", "bottom"], width=10)
        self.cb_headline.grid(row=0, column=1, padx=5)
        
        tk.Label(self.pos_frame, text="Subs:", bg="#0a0a0a", fg="#555", font=("Segoe UI", 9)).grid(row=0, column=2, padx=5)
        self.cb_subtitle = ttk.Combobox(self.pos_frame, textvariable=self.subtitle_pos, values=["top", "center", "bottom"], width=10)
        self.cb_subtitle.grid(row=0, column=3, padx=5)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.load_item()
        self.update_frame()

    def load_item(self):
        """Load data and preview for the current item in the batch."""
        if not self.root.winfo_exists(): return
        if self.current_idx >= len(self.items):
            if not self.approved_folders:
                messagebox.showinfo("Fin", "No se aprobaron reels.")
                self.root.destroy()
                return
            messagebox.showinfo("Lote Completado", f"Se han procesado {len(self.approved_folders)} reels.")
            # Note: Final processing (batch publishing) happens here if needed
            self.root.destroy()
            return
            
        item = self.items[self.current_idx]
        
        # --- REGENERATION LOADING SCREEN ---
        if item.get('is_regenerating', False):
            self.header_label.config(text=f"REVISIÓN {self.current_idx + 1}/{len(self.items)}")
            self.shorts_text.delete('1.0', tk.END)
            self.caption_text.delete('1.0', tk.END)
            
            # Show Loading State
            self.canvas.delete("all")
            self.canvas.create_rectangle(0, 0, 400, 711, fill="#0a0a0a")
            self.canvas.create_text(200, 350, text="⏳ REGENERANDO...", font=("Segoe UI Bold", 16), fill="#E31E24")
            
            self._set_buttons_state("disabled")
            self.root.after(1000, self.load_item)
            return
        else:
            self._set_buttons_state("normal")

        # Standard Load Logic
        self.header_label.config(text=f"REVISIÓN {self.current_idx + 1}/{len(self.items)}")
        
        self.shorts_text.delete('1.0', tk.END)
        self.shorts_text.insert(tk.END, item.get('shorts_title', ''))
        
        self.caption_text.delete('1.0', tk.END)
        self.caption_text.insert(tk.END, item.get('caption', ''))
        
        # Positioning Defaults
        self.headline_pos.set(item.get('headline_pos', 'bottom'))
        self.subtitle_pos.set(item.get('subtitle_pos', 'bottom'))

        if self.cap: self.cap.release()
        
        try:
            self.cap = cv2.VideoCapture(item['reel_path'])
            if MediaPlayer:
                self.player = MediaPlayer(item['reel_path'], ff_opts={'pix_fmt': 'rgb24'})
            if not self.cap.isOpened():
                self.status.update(f"   ⚠️ Error de preview: {item['reel_path']}")
        except Exception as e:
            self.status.update(f"   ⚠️ Preview error: {str(e)[:40]}")
            
    def _set_buttons_state(self, state):
        """Helper to toggle buttons during regeneration wait."""
        btns = [self.btn_pub_all, self.btn_pub_sel, self.btn_batch, 
                self.btn_regen_c, self.btn_regen_h, self.btn_discard]
        for btn in btns:
            try: btn.config(state=state)
            except: pass

    def update_frame(self):
        if not self.root.winfo_exists() or self.current_idx >= len(self.items): return
        
        # Skip frame update if regenerating
        item = self.items[self.current_idx]
        if item.get('is_regenerating', False):
             self.root.after(500, self.update_frame)
             return
        
        if self.player:
            frame, val = self.player.get_frame()
            if val == 'eof':
                self.player.seek(0, relative=False)
            elif val == 'toggle':
                pass
            elif frame is not None:
                img, pts = frame
                w, h = img.get_size()
                img_data = img.to_bytearray()[0]
                
                # Convert to numpy array for CV2 and overlay processing
                # PIL -> Numpy is fast
                pil_img = Image.frombytes("RGB", (w, h), img_data)
                frame_np = np.array(pil_img)
                
                # Resize according to canvas current size or fixed 400x711 (Shorts format)
                if w != 400 or h != 711:
                    frame_np = cv2.resize(frame_np, (400, 711))
                
                if self.overlay_np is not None:
                    fg = self.overlay_np[:, :, :3]
                    alpha = self.overlay_np[:, :, 3:4]
                    bg = frame_np.astype(float) / 255.0
                    blended = (fg * alpha + bg * (1 - alpha)) * 255.0
                    final_frame = blended.astype(np.uint8)
                    img = Image.fromarray(final_frame)
                else:
                    img = Image.fromarray(frame_np)
                
                self.tk_img = ImageTk.PhotoImage(img)
                self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)
            
            self.root.after(15, self.update_frame)
            return

        # Fallback to OpenCV
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.cap.read()
                
            if ret and frame is not None:
                frame = cv2.resize(frame, (400, 711))
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                if self.overlay_np is not None:
                    fg = self.overlay_np[:, :, :3]
                    alpha = self.overlay_np[:, :, 3:4]
                    bg = frame.astype(float) / 255.0
                    blended = (fg * alpha + bg * (1 - alpha)) * 255.0
                    final_frame = blended.astype(np.uint8)
                    img = Image.fromarray(final_frame)
                else:
                    img = Image.fromarray(frame)
                
                self.tk_img = ImageTk.PhotoImage(img)
                self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)
            
        self.root.after(30, self.update_frame)

    def keep(self):
        item = self.items[self.current_idx]
        folder = item['folder']
        self.approved_folders.append(folder)
        self.status.update(f"   ⭐ Reel '{os.path.basename(folder)}' aprobado localmente.")
        self.next_item()

    def discard(self):
        """Discard current item and move to next."""
        item = self.items[self.current_idx]
        self.status.update(f"   🗑️ Reel descartado: {os.path.basename(item['folder'])}")
        try:
            shutil.rmtree(item['folder'])
        except: pass
        self.next_item()

    def publish_action(self, all_platforms=False):
        """Unified publishing action for all selected platforms."""
        item = self.items[self.current_idx]
        
        # 1. Gather Content
        shorts_title = self.shorts_text.get('1.0', tk.END).strip()
        caption = self.caption_text.get('1.0', tk.END).strip()
        video_path = item['reel_path']
        
        # 2. Determine Platforms
        platforms = []
        if all_platforms:
            platforms = ["youtube", "facebook", "instagram"]
        else:
            if self.use_yt.get(): platforms.append("youtube")
            if self.use_fb.get(): platforms.append("facebook")
            if self.use_ig.get(): platforms.append("instagram")
            if self.use_ig_stories.get(): platforms.append("instagram_story")
        
        if not platforms:
            messagebox.showwarning("Sin plataformas", "Selecciona al menos una plataforma.")
            return

        # 3. Execution
        self.btn_pub_all.config(state="disabled")
        self.btn_pub_sel.config(state="disabled")
        self.status.update(f"   🚀 Publicando en {', '.join(platforms).upper()}...")
        
        def run_publish():
            success = True
            for plat in platforms:
                self.root.after(0, lambda p=plat: self.status.update(f"   📡 Enviando a {p.upper()}..."))
                try:
                    # Delegate to publisher.py -> CentralPublishingHub
                    res = publisher.publish_video(video_path, caption, platform=plat, title=shorts_title)
                    if res and res.get('status') == 'success':
                        self.root.after(0, lambda p=plat: self.status.update(f"   ✅ {p.upper()}: Éxito"))
                    else:
                        error = res.get('error', 'Error desconocido') if res else 'Sin respuesta'
                        self.root.after(0, lambda p=plat, e=error: self.status.update(f"   ❌ {p.upper()}: {e}"))
                        success = False
                except Exception as e:
                    self.root.after(0, lambda p=plat, ex=e: self.status.update(f"   ❌ {p.upper()} Error: {ex}"))
                    success = False

            if success:
                self.root.after(0, lambda: messagebox.showinfo("Éxito", "Publicación completada en plataforma seleccionadas."))
                self.root.after(0, self.keep)
            else:
                self.root.after(0, lambda: messagebox.showwarning("Atención", "Algunas plataformas fallaron. Revisa el log."))
                self.root.after(0, lambda: self.btn_pub_all.config(state="normal"))
                self.root.after(0, lambda: self.btn_pub_sel.config(state="normal"))

        threading.Thread(target=run_publish, daemon=True).start()

    def regenerate(self, target="all"):
        """Regenerate AI content based on optional feedback or specific target."""
        item = self.items[self.current_idx]
        current_headline = self.shorts_text.get('1.0', tk.END).strip()
        current_caption = self.caption_text.get('1.0', tk.END).strip()
        
        feedback = f"REGENERATE {target.upper()}. "
        if target == "caption":
            feedback += f"Mantén el título: {current_headline}. Cambia la descripción."
        elif target == "headline":
            feedback += f"Mantén la descripción: {current_caption}. Cambia el título."
        
        self.status.update(f"⏳ Regenerando {target.upper()} para: {item.get('headline', '...')}")
        
        item['is_regenerating'] = True
        self.items.pop(self.current_idx)
        self.items.append(item)
        if self.current_idx >= len(self.items): self.current_idx = 0 
        
        self.load_item()

        def regen_task():
            try:
                # Pre-apply positions to item for the renderer
                item['headline_pos'] = self.headline_pos.get()
                item['subtitle_pos'] = self.subtitle_pos.get()
                
                new_item = self.process_callback(item, feedback)
                self.root.after(0, lambda: self._update_item_in_list(item, new_item))
            except Exception as e:
                self.root.after(0, lambda: self.status.update(f"❌ Error regenerando: {e}"))
                item['is_regenerating'] = False
        
        threading.Thread(target=regen_task, daemon=True).start()

    def _update_item_in_list(self, old_item, new_item):
        """Update the item in the list once background processing is done."""
        try:
            idx = self.items.index(old_item)
            new_item['is_regenerating'] = False
            self.items[idx] = new_item
            head = new_item.get('headline', '...')
            self.status.update(f"✨ Regeneración completada: '{head}'.")
        except ValueError:
            pass 

    def add_to_batch(self):
        """Schedule the current item for all selected platforms via CentralPublishingHub."""
        item = self.items[self.current_idx]
        shorts_title = self.shorts_text.get('1.0', tk.END).strip()
        caption = self.caption_text.get('1.0', tk.END).strip()
        video_path = item['reel_path']
        
        platforms = []
        if self.use_yt.get(): platforms.append("youtube")
        if self.use_fb.get(): platforms.append("facebook")
        if self.use_ig.get(): platforms.append("instagram")
        if self.use_ig_stories.get(): platforms.append("instagram_story")
        
        if not platforms:
            messagebox.showwarning("Sin plataformas", "Selecciona plataformas para programar.")
            return

        self.status.update(f"   📅 Programando lote para {', '.join(platforms).upper()}...")
        
        def run_schedule():
            success = True
            for plat in platforms:
                try:
                    # Delegate scheduling to publisher.py
                    res = publisher.schedule_publication(video_path, caption, platform=plat, title=shorts_title)
                    if not res or res.get('status') != 'success':
                        success = False
                except:
                    success = False
            
            if success:
                self.root.after(0, lambda: self.status.update(f"   ✅ Lote programado con éxito."))
                self.root.after(0, self.keep)
            else:
                self.root.after(0, lambda: messagebox.showwarning("Error parcial", "Algunas programaciones fallaron."))

        threading.Thread(target=run_schedule, daemon=True).start()

    def next_item(self):
        self.current_idx += 1
        self.load_item()

    def toggle_mute(self):
        self.is_muted = not self.is_muted
        if self.player:
            self.player.set_volume(0.0 if self.is_muted else 1.0)
        self.btn_mute.config(text="🔇" if self.is_muted else "🔊")

    def on_finish(self):
        """Finalize curation session and cleanup."""
        if self.cap: 
            self.cap.release()
            self.cap = None
        if hasattr(self, 'player') and self.player:
            self.player.close_player()
            self.player = None
        
        self.status.update(f"\n✨ Curación finalizada. {len(self.approved_folders)} reels guardados.")
        self._finish_close()
    
    def _finish_close(self):
        # Cleanup original media now that curation is complete
        self._cleanup_original_media()
        if self.approved_folders:
            try: os.startfile(self.approved_folders[-1])
            except: pass
        self.root.destroy()

    def on_close(self):
        if self.cap: self.cap.release()
        if hasattr(self, 'player') and self.player:
            self.player.close_player()
        self._cleanup_original_media()
        self.root.destroy()
    
    def _cleanup_original_media(self):
        """Delete original downloaded media files after curation is complete."""
        for item in self.items:
            try:
                media_path = item.get('tweet_data', {}).get('local_media_path')
                if media_path and os.path.exists(media_path):
                    os.remove(media_path)
            except: pass

class PreAiCurationManager:
    """Stage 1: Filter original tweets before using Gemini AI."""
    def __init__(self, parent, raw_items, status_manager, on_complete):
        self.root = tk.Toplevel(parent)
        self.root.title(f"Filtro Pre-IA ({len(raw_items)} Tweets)")
        self.root.geometry("1200x800") # Resized for better fit
        self.root.configure(bg="#1a1a1a")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Focus and Modal Enforcement
        self.root.lift()
        self.root.focus_force()
        self.root.grab_set()
        
        self.raw_items = raw_items
        self.current_idx = 0
        self.status = status_manager
        self.on_complete = on_complete
        self.kept_items = []
        
        # UI
        self.main_frame = tk.Frame(self.root, bg="#1a1a1a", padx=20, pady=20)
        self.main_frame.pack(fill="both", expand=True)
        
        # Two-column layout
        self.preview_frame = tk.Frame(self.main_frame, bg="#1a1a1a", width=340)
        self.preview_frame.pack(side="left", fill="both", expand=True, padx=(0, 20))
        
        self.canvas = tk.Canvas(self.preview_frame, width=340, height=500, bg="black", highlightthickness=0)
        self.canvas.pack(pady=10)
        
        self.right_frame = tk.Frame(self.main_frame, bg="#1a1a1a")
        self.right_frame.pack(side="right", fill="both", expand=True)

        self.header = tk.Label(self.right_frame, text="", font=("Segoe UI Bold", 14), fg="#E31E24", bg="#1a1a1a")
        self.header.pack(pady=(5, 10), anchor="w")
        
        # Split right frame into tweet content and AI suggestions
        self.details_frame = tk.Frame(self.right_frame, bg="#1a1a1a")
        self.details_frame.pack(fill="both", expand=True)

        self.tweet_frame = tk.LabelFrame(self.details_frame, text="ORIGINAL", bg="#1a1a1a", fg="#888", font=("Segoe UI", 9))
        self.tweet_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        self.content_text = tk.Text(self.tweet_frame, height=10, width=40, bg="#252525", fg="#bbb", font=("Segoe UI", 10), borderwidth=0, padx=10, pady=10)
        self.content_text.pack(fill="both", expand=True)

        # Merged Instructions Frame
        self.ai_frame = tk.LabelFrame(self.details_frame, text="INSTRUCCIONES PARA LA IA", bg="#1a1a1a", fg="#E31E24", font=("Segoe UI Bold", 9))
        self.ai_frame.pack(side="right", fill="both", expand=True)

        self.headline_entry = tk.Entry(self.root) # Hidden storage
        self.shorts_entry = tk.Entry(self.root)   # Hidden storage

        tk.Label(self.ai_frame, text="Instrucciones de Redacción / Contexto:", font=("Segoe UI Bold", 10), fg="#f1c40f", bg="#1a1a1a").pack(anchor="w", padx=10, pady=(10,0))
        self.caption_text = tk.Text(self.ai_frame, height=18, bg="#252525", fg="white", font=("Segoe UI", 11), borderwidth=0, padx=10, pady=10)
        self.caption_text.pack(fill="both", expand=True, padx=10, pady=10)

        # Source Section
        self.source_subframe = tk.Frame(self.ai_frame, bg="#1a1a1a")
        self.source_subframe.pack(fill="x", padx=10, pady=5)
        tk.Label(self.source_subframe, text="Fuente Detectada:", font=("Segoe UI Bold", 9), fg="#888", bg="#1a1a1a").pack(side="left")
        self.source_entry = tk.Entry(self.source_subframe, bg="#252525", fg="#27ae60", font=("Segoe UI Bold", 10), borderwidth=0, width=30, insertbackground="white")
        self.source_entry.pack(side="left", padx=10)
        self.source_entry.bind("<KeyRelease>", lambda e: self.source_entry.config(fg="#27ae60" if self.source_entry.get().strip() else "#888"))

        # Hidden Location Entry (used for AI suggestion storage)
        self.loc_entry = tk.Entry(self.root) # Hidden, just for storage to avoid AttributeError


        # Merged with caption_text above
        self.feedback_text = tk.Entry(self.root) # Hidden storage
        
        self.btn_frame = tk.Frame(self.right_frame, bg="#1a1a1a")
        self.btn_frame.pack(fill="x", pady=20)
        
        tk.Button(self.btn_frame, text="🗑️ DESCARTAR", bg="#c0392b", fg="white", font=("Segoe UI Black", 11), width=15, command=self.discard).pack(side="left")
        
        tk.Button(self.btn_frame, text="🚫 RECHAZAR", bg="#555", fg="white", font=("Segoe UI Bold", 10), width=15, command=self.permanent_reject).pack(side="left", padx=10)

        # Removed RE-GENERAR button as IA is no longer used in Stage 1

        # Mute Button
        self.btn_mute = tk.Button(self.btn_frame, text="🔊", bg="#555", fg="white", font=("Segoe UI", 11), width=3, command=self.toggle_mute)
        self.btn_mute.pack(side="left", padx=10)
        
        self.skip_subtitles_var = tk.BooleanVar(value=False)
        tk.Checkbutton(self.btn_frame, text="Sin Subs", variable=self.skip_subtitles_var, bg="#1a1a1a", fg="white", selectcolor="#333", font=("Segoe UI", 9)).pack(side="left", padx=5)
        
        tk.Button(self.btn_frame, text="✅ APROBAR Y RENDERIZAR", bg="#27ae60", fg="white", font=("Segoe UI Black", 11), width=25, command=self.keep).pack(side="right")
        
        self.cap = None
        self.player = None
        self.is_muted = False
        
        self.load_tweet()
        self.update_frame()

    def resize_contain(self, img_pil, target_w, target_h):
        """Resize image to fit into target dimensions preserving aspect ratio with black bars."""
        w, h = img_pil.size
        ratio = min(target_w / w, target_h / h)
        new_w = int(w * ratio)
        new_h = int(h * ratio)
        resized = img_pil.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        background = Image.new("RGB", (target_w, target_h), (0, 0, 0))
        offset = ((target_w - new_w) // 2, (target_h - new_h) // 2)
        background.paste(resized, offset)
        return background

    def load_tweet(self):
        if self.current_idx >= len(self.raw_items):
            self.on_close()
            return
            
        tweet = self.raw_items[self.current_idx]
        self.header.config(text=f"TWEET {self.current_idx + 1}/{len(self.raw_items)} (@{tweet.get('uploader_id', 'Unknown')})")
        
        # Original Tweet Link
        tweet_id = tweet.get('id')
        original_url = f"https://x.com/i/status/{tweet_id}"
        
        reposts = tweet.get('reposts', 0)
        likes = tweet.get('likes', 0)
        
        content = f"METRICAS: {reposts} Retweets | {likes} Likes\n"
        content += f"CONTENIDO:\n{tweet.get('description', 'Sin descripción')}\n\n"
        content += f"MEDIA: {'VÍDEO 🎥' if tweet.get('is_video') else 'IMAGEN 🖼️'}\n"
        
        self.content_text.delete('1.0', tk.END)
        self.content_text.insert(tk.END, content)
        
        # Add clickable link at the end
        self.content_text.insert(tk.END, "\nVER TUIT ORIGINAL 🔗", ("link",))
        self.content_text.tag_config("link", foreground="#3498db", underline=1)
        self.content_text.tag_bind("link", "<Button-1>", lambda e: webbrowser.open(original_url))
        self.content_text.tag_bind("link", "<Enter>", lambda e: self.content_text.config(cursor="hand2"))
        self.content_text.tag_bind("link", "<Leave>", lambda e: self.content_text.config(cursor=""))

        # Clear feedback entry
        self.feedback_text.delete(0, tk.END)

        if self.cap: self.cap.release()
        if hasattr(self, 'player') and self.player:
            self.player.close_player()
        
        self.cap = None
        self.player = None
        self.canvas.delete("all")

        # Clear AI fields
        self.headline_entry.delete(0, tk.END)
        self.shorts_entry.delete(0, tk.END)
        self.caption_text.delete('1.0', tk.END)
        self.source_entry.delete(0, tk.END)
        self.source_entry.config(fg="#888") # Default gray

        # Stage 1 is now manual only - no AI generation per user request
        
        media_path = tweet.get('local_media_path')
        if media_path and os.path.exists(media_path):
            print(f"[DEBUG] Loading media: {media_path} (Video: {tweet.get('is_video')})")
            try:
                if tweet.get('is_video'):
                    self.cap = cv2.VideoCapture(media_path)
                    print(f"[DEBUG] VideoCapture opened: {self.cap.isOpened()}")
                    if not self.cap.isOpened():
                         self.canvas.create_text(170, 250, text="ERROR OPENING VIDEO", fill="red")

                    if MediaPlayer:
                        # Request RGB24 for easy conversion to PIL
                        self.player = MediaPlayer(media_path, ff_opts={'pix_fmt': 'rgb24'})
                else:
                    print(f"[DEBUG] Loading image...")
                    img = Image.open(media_path).convert("RGB")
                    img = self.resize_contain(img, 340, 500)
                    self.tk_img = ImageTk.PhotoImage(img)
                    self.canvas.create_image(170, 250, anchor="center", image=self.tk_img)
                    print(f"[DEBUG] Image loaded successfully")
            except Exception as e:
                print(f"[UI ERROR] Failed to load media {media_path}: {e}")
                self.canvas.create_text(170, 250, text=f"⚠️ ERROR MEDIA\n{str(e)[:40]}", fill="red", font=("Segoe UI Bold", 10), justify="center")
        else:
            msg = "⌛ Descargando..." if not media_path else "⚠️ ARCHIVO ELIMINADO"
            self.canvas.create_text(170, 250, text=msg, fill="#555", font=("Segoe UI Bold", 12))
            if media_path:
                self.status.update(f"   ⚠️ Media not found at: {media_path}")

    def update_frame(self):
        if not self.root or not self.root.winfo_exists() or self.current_idx >= len(self.raw_items): return
        
        if self.player:
            # IMPORTANT: Delete old image objects to avoid memory/layer leak
            self.canvas.delete("video_frame")
            
            frame, val = self.player.get_frame()
            if val == 'eof':
                self.player.seek(0, relative=False)
            elif val == 'toggle':
                pass
            elif frame is not None:
                img, pts = frame
                # img is an ffpyplayer.pic.Image
                w, h = img.get_size()
                img_data = img.to_bytearray()[0]
                
                # Create PIL image from raw RGB bytes
                pil_img = Image.frombytes("RGB", (w, h), img_data)
                
                # Resize and center using existing helper
                background = self.resize_contain(pil_img, 340, 500)
                
                self.tk_img = ImageTk.PhotoImage(background)
                self.canvas.create_image(170, 250, anchor="center", image=self.tk_img, tags="video_frame")
            
            # Continue reading frames quickly (approx 60fps target for smooth UI)
            self.root.after(15, self.update_frame)
            return

        # Fallback to OpenCV if player is not available (e.g. static image or no ffpyplayer)
        if self.cap and self.cap.isOpened():
            self.canvas.delete("video_frame")
            
            ret, frame = self.cap.read()
            if not ret:
                # Handle end of video / looping
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.cap.read()
                
            if ret and frame is not None:
                # Fit frame to canvas without deformation
                f_h, f_w = frame.shape[:2]
                ratio = min(340 / f_w, 500 / f_h)
                new_w, new_h = int(f_w * ratio), int(f_h * ratio)
                
                frame = cv2.resize(frame, (new_w, new_h))
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Create background for letterboxing
                img = Image.fromarray(frame)
                background = Image.new("RGB", (340, 500), (0, 0, 0))
                background.paste(img, ((340 - new_w) // 2, (500 - new_h) // 2))
                
                self.tk_img = ImageTk.PhotoImage(background)
                self.canvas.create_image(170, 250, anchor="center", image=self.tk_img, tags="video_frame")

        self.root.after(30, self.update_frame)

    def on_close(self):
        if self.cap: self.cap.release()
        if hasattr(self, 'player') and self.player:
            self.player.close_player()
        self.on_complete(self.kept_items)
        self.root.destroy()

    def toggle_mute(self):
        self.is_muted = not self.is_muted
        if self.player:
            self.player.set_volume(0.0 if self.is_muted else 1.0)
        self.btn_mute.config(text="🔇" if self.is_muted else "🔊")

    def discard(self):
        """Skip this item and mark it as rejected so it doesn't appear again."""
        try:
            self.status.update(f"   🗑️ Descartando y marcando como rechazado...")
            self.permanent_reject()
        except Exception as e:
            print(f"[DISCARD ERROR] {e}")
            import traceback
            traceback.print_exc()
            self.current_idx += 1
            self.load_tweet()

    def permanent_reject(self):
        # Mark as rejected and skip
        item = self.raw_items[self.current_idx]
        tweet_id = item.get('id')
        if tweet_id:
            from core.viral_scout import ViralScout
            ViralScout().mark_as_rejected(tweet_id)
            print(f"[REJECT] Permamently rejected tweet {tweet_id}")
            
            # Cloud sync if applicable
            # if isinstance(item, dict) and item.get('url'):
            #     try:
            #         threading.Thread(target=lambda url=CLOUD_SERVER_URL, tid=tweet_id: requests.post(f"{url}/pending/{tid}/mark-rejected"), daemon=True).start()
            #     except: pass

        self.current_idx += 1
        self.load_tweet()

    def display_ai_content(self, data):
        """Populate the AI suggestion fields."""
        # Note: self.headline_entry and self.shorts_entry are now hidden
        
        self.caption_text.delete('1.0', tk.END)
        self.caption_text.insert(tk.END, data.get('caption', ''))

        source = data.get('source', '')
        self.source_entry.delete(0, tk.END)
        self.source_entry.insert(0, source)
        if source:
            self.source_entry.config(fg="#27ae60") # Green if detected
        else:
            self.source_entry.config(fg="#888")

        # Auto-fill location search if suggested
        loc_suggestion = data.get('suggested_location_query', '')
        if loc_suggestion:
             self.loc_entry.delete(0, tk.END)
             self.loc_entry.insert(0, loc_suggestion)
             # Optional: Auto-trigger search?
             # self.search_location_ui() # Maybe too aggressive, let user decide

    def run_ai_suggestion(self):
        """Run AI generation in background and update UI."""
        item = self.raw_items[self.current_idx]
        feedback = self.feedback_text.get().strip()
        
        # No overwriting entries immediately to avoid UI jitter. 
        # The status bar and presence of content in 'ORIGINAL' frame should suffice.
        
        def ai_task():
            try:
                # Use media path if available for multi-modal if supported, but here it's text-based mostly
                media_path = item.get('local_media_path')
                # Use generate_content_ai which handles the Gemini call (CHEAP mode for preview)
                from core.ai_handler import generate_content_ai
                h, c, s, st, cb, src, loc = generate_content_ai(item, media_path, feedback, quality="cheap")
                
                result = {
                    'headline': h,
                    'caption': c,
                    'slug': s,
                    'shorts_title': st,
                    'caption_b': cb,
                    'source': src,
                    'suggested_location_query': loc
                }
                
                def update_ui():
                    try:
                        # Only update if we're still on the same item and root exists
                        if self.root.winfo_exists() and self.current_idx < len(self.raw_items) and self.raw_items[self.current_idx] == item:
                            item.update(result)
                            self.display_ai_content(result)
                    except: pass
                
                if self.root.winfo_exists():
                    self.root.after(0, update_ui)
            except Exception as e:
                import traceback
                print(f"[AI TASK ERROR] {e}")
                traceback.print_exc()
                if self.root.winfo_exists():
                    self.root.after(0, lambda: self.headline_entry.delete(0, tk.END))
                    self.root.after(0, lambda: self.headline_entry.insert(0, f"❌ Error IA: {str(e)[:30]}"))

        threading.Thread(target=ai_task, daemon=True).start()

    def keep(self):
        item = self.raw_items[self.current_idx]
        
        # Capture unified instructions
        item['user_instructions'] = self.caption_text.get('1.0', tk.END).strip()
        item['source'] = self.source_entry.get().strip()
        
        item['skip_subtitles'] = self.skip_subtitles_var.get()
        item['initial_feedback'] = self.feedback_text.get().strip() # Capture feedback
        
        # Mark as processed only if approved for AI processing
        tweet_id = item.get('id')
        if tweet_id:
            from core.viral_scout import ViralScout
            ViralScout().mark_as_processed(tweet_id)
            
            # Cloud sync if applicable
            # if isinstance(item, dict) and item.get('url'):
            #     try:
            #         threading.Thread(target=lambda url=CLOUD_SERVER_URL, tid=tweet_id: requests.post(f"{url}/pending/{tid}/mark-processed"), daemon=True).start()
            #     except: pass
            
            
        # We DON'T set headline/caption here because render_item_assets checks for them to skip.
        # Let's clear them so render_item_assets DOES regenerate with pro (Kimi).
        item['headline'] = None
        item['caption'] = None
            
        self.kept_items.append(item)
        self.current_idx += 1
        self.load_tweet()



# REMOVED: generate_mobile_html is no longer needed.



# --- CORE LOGIC ---

def batch_process(urls: list, status: StatusManager):
    """Refactored 2-Stage Process: Scrape -> Filter -> Process -> Curate."""
    cleanup_old_files(DOWNLOADS_DIR, quiet=True)
    cleanup_old_files(OUTPUT_DIR, quiet=True)
    
    total = len(urls)
    status.update(f"🚀 Iniciando Batch Process ({total} items)")
    
    # --- STAGE 1: SCRAPE & DOWNLOAD ---
    scraped_data = []
    for i, item in enumerate(urls):
        # Support both URL strings and rich data dicts (from Viral Scout)
        if isinstance(item, dict):
            url = item.get('url', '').strip()
            rich_data = item  # Already has media_url, thumbnail, etc.
        else:
            url = item.strip()
            rich_data = None
        
        if not url: continue
        status.update(f"🔎 Scrapeando {i+1}/{total}: {url}")
        try:
            # If we have rich data from Viral Scout / Cloud, use it directly
            if rich_data:
                data = rich_data.copy()
                data.setdefault('title', rich_data.get('description', '')[:100])
                data.setdefault('uploader', rich_data.get('user', ''))
                data.setdefault('uploader_id', rich_data.get('user', ''))
                data.setdefault('media_url', rich_data.get('media_url'))
                status.update(f"   ✅ Usando datos de Viral Scout...")
            else:
                data = scrape_tweet(url)
            
            if data: 
                data['url'] = url # Keep 'url' as the tweet URL for compatibility
                # PRE-DOWNLOAD for filter preview
                status.update(f"   📥 Descargando media para preview...")
                # Use media_url if available, otherwise use thumbnail
                media_url = data.get('media_url')
                is_vid = data.get('is_video', True)
                success, media_path = download_media(url, thumbnail_url=data.get('thumbnail') or media_url, is_video=is_vid, direct_url=media_url)
                if success:
                    data['local_media_path'] = media_path
                    scraped_data.append(data)
                else:
                    status.update(f"   ⚠️ Salteando: Error de descarga ({media_path[:50]})")
        except Exception as e:
            status.update(f"   ❌ Error: {e}")

    if not scraped_data:
        status.update("❌ No se pudo scrapear ningún enlace.")
        return

    # --- STAGE 2: PRE-AI CURATION ---
    status.update(f"⌛ Esperando Filtro Pre-IA...")
    root = status.gui_log_widget.winfo_toplevel()
    
    kept_after_filter = []
    filter_event = threading.Event()

    def on_filter_complete(kept):
        nonlocal kept_after_filter
        kept_after_filter = kept
        filter_event.set()

    root.after(0, lambda: PreAiCurationManager(root, scraped_data, status, on_filter_complete))
    
    # Flush GUI events to ensure the window is drawn before the thread enters the wait loop
    root.update_idletasks()
    root.update()
    
    # Wait for UI to finish Stage 1
    while not filter_event.is_set():
        time.sleep(0.1)

    if not kept_after_filter:
        status.update("✨ Proceso cancelado o ningún item seleccionado.")
        return

    # --- STAGE 3: PROCESS KEPT ITEMS (PARALLEL) ---
    status.update(f"⚙️ Procesando {len(kept_after_filter)} items seleccionados (en paralelo)...")
    pending_curation = []
    
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    # Use max 2 workers to avoid crashing the PC, even with NVENC
    max_workers = 2
    
    def process_item(item_data, idx, total_items):
        try:
            status.update(f"[{idx+1}/{total_items}] Renderizando: {item_data.get('title', 'Sin título')[:30]}...")
            rendered = render_item_assets(item_data, status)
            
            # MEMORY OPTIMIZATION: Free up RAM after each render
            import gc
            gc.collect()
            return rendered
        except Exception as e:
            status.update(f"   ❌ Error en item {idx+1}: {e}")
            return None

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_item = {executor.submit(process_item, data, i, len(kept_after_filter)): data for i, data in enumerate(kept_after_filter)}
        
        for future in as_completed(future_to_item):
            result = future.result()
            if result:
                pending_curation.append(result)
            
    # Sort pending_curation to maintain original order if possible (optional)
    # For now, append order is fine as they go to a reviewer gallery anyway
            
    # --- STAGE 4: POST-AI CURATION & FEEDBACK ---
    if pending_curation:
        status.update(f"\n⌛ ABRIENDO PANTALLA DE REVISIÓN FINAL...")
        
        # Helper for regeneration
        def regenerate_callback(item, feedback):
            status.update(f"🔄 Regenerando '{item['headline']}' con feedback...")
            # Clean old folder to avoid duplicates if slug changes
            try: shutil.rmtree(item['folder'])
            except: pass
            return render_item_assets(item['tweet_data'], status, feedback)

        root.after(0, lambda: PostAiCurationManager(root, pending_curation, status, regenerate_callback))
    else:
        status.update("\n✨ Batch Complete (Nada que curar).")
        messagebox.showinfo("Finalizado", "Proceso completado. No hay vídeos para revisar.")
    cleanup_old_files(OUTPUT_DIR)
    

# --- GUI ---

def run_gui():
    root = tk.Tk()
    root.title("Economika - Reel Generator Pro")
    root.geometry("900x700")
    root.configure(bg="#0d0d0d")
    root.minsize(800, 600)

    # Modern Color Palette
    COLORS = {
        'bg_dark': '#0d0d0d',
        'bg_card': '#1a1a1a',
        'bg_input': '#252525',
        'accent': '#E31E24',
        'accent_hover': '#ff3333',
        'success': '#27ae60',
        'warning': '#f39c12',
        'text': '#ffffff',
        'text_muted': '#888888',
        'border': '#333333',
    }

    style = ttk.Style()
    style.theme_use('clam')
    style.configure("TLabel", foreground=COLORS['text'], background=COLORS['bg_dark'], font=("Segoe UI", 10))
    style.configure("TButton", font=("Segoe UI Bold", 10), padding=8)
    style.configure("TFrame", background=COLORS['bg_dark'])
    style.configure("Card.TFrame", background=COLORS['bg_card'])
    style.configure("Accent.TButton", foreground=COLORS['text'], background=COLORS['accent'])
    
    # Main container with two columns
    main_container = ttk.Frame(root, style="TFrame")
    main_container.pack(expand=True, fill="both", padx=15, pady=15)
    
    # LEFT COLUMN - Main controls
    left_frame = ttk.Frame(main_container, style="TFrame")
    left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
    
    # Header with gradient effect (simulated with label)
    header_frame = tk.Frame(left_frame, bg=COLORS['bg_dark'])
    header_frame.pack(fill="x", pady=(0, 15))
    
    tk.Label(header_frame, text="ECONÓMIKA", font=("Segoe UI Black", 28), 
             fg=COLORS['accent'], bg=COLORS['bg_dark']).pack(side="left")
    tk.Label(header_frame, text="NOTICIAS", font=("Segoe UI Light", 28), 
             fg=COLORS['text'], bg=COLORS['bg_dark']).pack(side="left", padx=(5, 0))
    
    tk.Label(left_frame, text="Reel Generator Pro", font=("Segoe UI", 11, "italic"), 
             fg=COLORS['text_muted'], bg=COLORS['bg_dark']).pack(anchor="w")
    
    # Input Card
    input_card = tk.Frame(left_frame, bg=COLORS['bg_card'], highlightbackground=COLORS['border'], 
                          highlightthickness=1, padx=15, pady=15)
    input_card.pack(fill="x", pady=(15, 10))
    
    tk.Label(input_card, text="📋 ENLACES DE TWITTER", font=("Segoe UI Bold", 11), 
             fg=COLORS['text'], bg=COLORS['bg_card']).pack(anchor="w", pady=(0, 8))
    
    input_text = scrolledtext.ScrolledText(input_card, height=6, bg=COLORS['bg_input'], 
                                           fg=COLORS['text'], font=("Consolas", 10), 
                                           borderwidth=0, relief="flat", insertbackground=COLORS['text'])
    input_text.pack(fill="x")
    
    # Button row with modern styling
    btn_row = tk.Frame(input_card, bg=COLORS['bg_card'])
    btn_row.pack(fill="x", pady=(10, 0))
    
    def create_modern_button(parent, text, command, bg_color, width=None):
        btn = tk.Button(parent, text=text, command=command, bg=bg_color, fg=COLORS['text'],
                       font=("Segoe UI Bold", 10), borderwidth=0, padx=15, pady=8, 
                       activebackground=COLORS['accent_hover'], activeforeground=COLORS['text'], cursor="hand2")
        if width: btn.config(width=width)
        return btn

    def load_file():
        file_path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
        if file_path:
            with open(file_path, 'r') as f:
                input_text.delete('1.0', tk.END)
                input_text.insert(tk.END, f.read())

    btn_load = create_modern_button(btn_row, "📁 Cargar", load_file, "#444")
    btn_load.pack(side="left", padx=(0, 5))
    
    btn_clear = create_modern_button(btn_row, "🗑️", lambda: input_text.delete('1.0', tk.END), "#444")
    btn_clear.pack(side="left", padx=5)

    # Force Process Checkbox
    force_process_var = tk.BooleanVar(value=False)
    chk_force = tk.Checkbutton(btn_row, text="⚡ Reprocesar", variable=force_process_var, 
                               bg=COLORS['bg_card'], fg="#f39c12", selectcolor=COLORS['bg_card'],
                               activebackground=COLORS['bg_card'], activeforeground="#f39c12", 
                               font=("Segoe UI Bold", 9))
    chk_force.pack(side="left", padx=10)

    # Sensitivity Scale
    tk.Label(btn_row, text="Sens:", font=("Segoe UI Bold", 9), 
             fg=COLORS['text_muted'], bg=COLORS['bg_card']).pack(side="left", padx=(5, 0))
    sensitivity_var = tk.DoubleVar(value=1.2)
    scale_sens = tk.Scale(btn_row, from_=0.1, to=5.0, resolution=0.1, orient="horizontal",
                          variable=sensitivity_var, bg=COLORS['bg_card'], fg=COLORS['text_muted'],
                          highlightthickness=0, borderwidth=0, length=80, showvalue=True,
                          troughcolor=COLORS['bg_input'], activebackground=COLORS['accent'],
                          font=("Segoe UI", 8))
    scale_sens.pack(side="left", padx=(0, 10))
    
    # Cloud server URL
    CLOUD_SERVER_URL = "https://economikanoticias.onrender.com"
    
    def fetch_from_cloud():
        """Fetch pending tweets from Render cloud server and start background pre-download."""
        nonlocal viral_scout_cache
        btn_cloud.config(state="disabled", text="⏳ Sync...")
        status_var.set("Conectando con servidor cloud...")
        
        def background_predownload(tweets):
            """Pre-download media for all tweets in the background."""
            for i, tweet in enumerate(tweets):
                if tweet.get('local_media_path') and os.path.exists(tweet.get('local_media_path', '')):
                    continue  # Already downloaded
                try:
                    download_url = tweet.get('media_url') or tweet.get('thumbnail')
                    if download_url:
                        is_video = tweet.get('is_video', True)
                        success, path = download_media(tweet.get('url', ''), thumbnail_url=download_url, is_video=is_video)
                        if success:
                            tweet['local_media_path'] = path
                except:
                    pass
            root.after(0, lambda: status_var.set(f"✅ {len(tweets)} previews listos para revisar"))
        
        def cloud_task():
            try:
                import requests
                from core.viral_scout import ViralScout
                scout = ViralScout()
                
                response = requests.get(f"{CLOUD_SERVER_URL}/pending", timeout=30)
                data = response.json()
                
                def handle_cloud_data():
                    nonlocal viral_scout_cache
                    if data.get('tweets'):
                        all_tweets = data['tweets']
                        # Filter against local history to avoid duplicates
                        tweets = [t for t in all_tweets if not scout.is_processed(t['id'])]
                        
                        if not tweets:
                            status_var.set("☁️ Todos los tweets actuales en cloud ya han sido procesados.")
                            btn_cloud.config(state="normal", text="☁️ Cloud")
                            return
                            
                        # Add to input
                        urls = "\n".join([t['url'] for t in tweets])
                        input_text.delete('1.0', tk.END)
                        input_text.insert(tk.END, urls + "\n")
                        # Cache the rich data
                        viral_scout_cache = tweets
                        status_var.set(f"☁️ {len(tweets)} nuevos tweets cargados. Descargando previews...")
                        # Start background pre-download
                        threading.Thread(target=background_predownload, args=(tweets,), daemon=True).start()
                    else:
                        status_var.set("☁️ No hay tweets pendientes en cloud")
                    btn_cloud.config(state="normal", text="☁️ Cloud")
                
                root.after(0, handle_cloud_data)
            except Exception as e:
                root.after(0, lambda: status_var.set(f"❌ Error cloud: {str(e)[:50]}"))
                root.after(0, lambda: btn_cloud.config(state="normal", text="☁️ Cloud"))
        
        threading.Thread(target=cloud_task, daemon=True).start()
    
    btn_cloud = create_modern_button(btn_row, "☁️ Cloud", fetch_from_cloud, "#3498db")
    btn_cloud.pack(side="left", padx=5)
    
    def clear_cloud():
        """Clear all pending tweets from the Render server."""
        if not messagebox.askyesno("Confirmar", "¿Vaciar toda la lista de la nube?", parent=root):
            return
            
        btn_clear_cloud.config(state="disabled", text="⏳...")
        status_var.set("Vaciando nube...")
        
        def task():
            try:
                import requests
                response = requests.post(f"{CLOUD_SERVER_URL}/pending/clear", timeout=30)
                if response.status_code == 200:
                    nonlocal viral_scout_cache
                    viral_scout_cache = None
                    root.after(0, lambda: status_var.set("✅ Nube vaciada correctamente"))
                    root.after(0, lambda: input_text.delete('1.0', tk.END))
                else:
                    root.after(0, lambda: status_var.set(f"⚠️ Error: {response.status_code}"))
            except Exception as e:
                root.after(0, lambda: status_var.set(f"❌ Error conexión: {str(e)[:40]}"))
            finally:
                root.after(0, lambda: btn_clear_cloud.config(state="normal", text="🗑️ Vaciar"))
        
        threading.Thread(target=task, daemon=True).start()

    btn_clear_cloud = create_modern_button(btn_row, "🗑️ Vaciar", clear_cloud, "#e67e22")
    btn_clear_cloud.pack(side="left", padx=(0, 5))

    def trigger_cloud_scan():
        """Trigger a manual viral scout scan on the Render server."""
        btn_scout.config(state="disabled", text="⏳ Scanning...")
        status_var.set("Solicitando escaneo al servidor cloud...")
        
        def scout_task():
            try:
                import requests
                # Send current sensitivity and default 24h (or make it configurable later if needed)
                payload = {
                    "min_ratio": sensitivity_var.get(),
                    "hours_back": 24
                }
                response = requests.post(f"{CLOUD_SERVER_URL}/scan", json=payload, timeout=60)
                if response.status_code == 200:
                    root.after(0, lambda: status_var.set("✅ Escaneo cloud completado. Pulsa 'Cloud' para cargar."))
                else:
                    root.after(0, lambda: status_var.set(f"⚠️ Error cloud: {response.status_code}"))
                root.after(0, lambda: btn_scout.config(state="normal", text="🔍 Discovery"))
            except Exception as e:
                root.after(0, lambda: status_var.set(f"❌ Error conexión cloud: {str(e)[:40]}"))
                root.after(0, lambda: btn_scout.config(state="normal", text="🔍 Discovery"))
        
        threading.Thread(target=scout_task, daemon=True).start()

    btn_scout = create_modern_button(btn_row, "🔍 Discovery", trigger_cloud_scan, "#9b59b6")
    btn_scout.pack(side="right")
    
    # Action Button (big red)
    btn_run = tk.Button(left_frame, text="▶ INICIAR PROCESO", bg=COLORS['accent'], fg=COLORS['text'],
                        font=("Segoe UI Black", 14), borderwidth=0, pady=12, cursor="hand2",
                        activebackground=COLORS['accent_hover'])
    btn_run.pack(fill="x", pady=15)
    
    # Log Card
    log_card = tk.Frame(left_frame, bg=COLORS['bg_card'], highlightbackground=COLORS['border'], 
                        highlightthickness=1, padx=15, pady=15)
    log_card.pack(fill="both", expand=True)
    
    tk.Label(log_card, text="📊 LOG DE PROGRESO", font=("Segoe UI Bold", 11), 
             fg=COLORS['text'], bg=COLORS['bg_card']).pack(anchor="w", pady=(0, 8))
    
    log_widget = scrolledtext.ScrolledText(log_card, height=10, bg="#111", fg="#0f0", 
                                           font=("Consolas", 9), state='disabled', borderwidth=0)
    log_widget.pack(fill="both", expand=True)
    
    # RIGHT COLUMN - Scheduled Posts
    right_frame = tk.Frame(main_container, bg=COLORS['bg_card'], highlightbackground=COLORS['border'],
                           highlightthickness=1, width=280)
    right_frame.pack(side="right", fill="y", padx=(10, 0))
    right_frame.pack_propagate(False)
    
    tk.Label(right_frame, text="📅 PROGRAMADOS", font=("Segoe UI Black", 12), 
             fg=COLORS['accent'], bg=COLORS['bg_card']).pack(pady=(15, 5))
    tk.Label(right_frame, text="Posts en Instagram", font=("Segoe UI", 9, "italic"), 
             fg=COLORS['text_muted'], bg=COLORS['bg_card']).pack()
    
    # Separator line
    tk.Frame(right_frame, bg=COLORS['border'], height=1).pack(fill="x", pady=10, padx=15)
    
    # Scheduled posts list
    scheduled_list = tk.Frame(right_frame, bg=COLORS['bg_card'])
    scheduled_list.pack(fill="both", expand=True, padx=15, pady=(0, 15))
    
    scheduled_label = tk.Label(scheduled_list, text="Cargando...", font=("Segoe UI", 9),
                               fg=COLORS['text_muted'], bg=COLORS['bg_card'], justify="left", anchor="w")
    scheduled_label.pack(fill="x")
    
    def refresh_scheduled():
        """Refresh the scheduled posts display from local tracking file."""
        try:
            posts = publisher.load_scheduled_posts()
            if not posts:
                scheduled_label.config(text="📭 No hay posts programados\nrecientemente.", fg=COLORS['text_muted'])
                return
            
            # Sort by time
            posts.sort(key=lambda x: x['scheduled_time'])
            
            # Filter only future or very recent posts
            from datetime import datetime
            now_iso = datetime.now().isoformat()
            
            display_text = ""
            for p in posts:
                dt = datetime.fromisoformat(p['scheduled_time'])
                time_str = dt.strftime("%H:%M (%d/%m)")
                icon = "🕒" if p['scheduled_time'] > now_iso else "✅"
                cap = p.get('caption', 'Sin descripción')
                display_text += f"{icon} {time_str}\n   {cap[:30]}...\n\n"
            
            scheduled_label.config(text=display_text.strip(), fg=COLORS['text'])
            
        except Exception as e:
            scheduled_label.config(text=f"❌ Error al cargar:\n{str(e)[:40]}", fg=COLORS['accent'])
    
    refresh_btn = tk.Button(right_frame, text="🔄 Actualizar", command=refresh_scheduled, 
                            bg="#444", fg=COLORS['text'], font=("Segoe UI", 9), borderwidth=0, pady=5, cursor="hand2")
    refresh_btn.pack(pady=(0, 15), padx=15, fill="x")
    
    # Initial refresh
    root.after(500, refresh_scheduled)
    
    # NEW: Auto-sync from cloud on startup
    # root.after(1500, fetch_from_cloud) # REMOVED: Autostart can be annoying
    
    # Status bar at bottom
    status_var = tk.StringVar(value="Listo para comenzar")
    status_bar = tk.Label(root, textvariable=status_var, font=("Segoe UI", 9), 
                          fg=COLORS['text_muted'], bg=COLORS['bg_dark'], anchor="w", padx=15)
    status_bar.pack(fill="x", side="bottom", pady=5)

    # Cache for viral scout rich data
    viral_scout_cache = None
    
    # Viral Scout function
    def run_viral_scout(hours=24, ignore_history=False, must_have_media=True):
        nonlocal viral_scout_cache
        from core.viral_scout import ViralScout
        from tkinter import simpledialog
        
        btn_scout.config(state="disabled", text="⏳ Buscando...")
        status_manager = StatusManager(status_var, log_widget)
        
        def scout_task():
            try:
                scout = ViralScout()
                status_manager.update(f"🚀 Iniciando Discovery RSS/News ({hours}h, Sens: {sensitivity_var.get()})...")
                hits = scout.scan(hours_back=hours, min_ratio=sensitivity_var.get(), ignore_history=ignore_history, 
                                 must_have_media=must_have_media, progress_callback=status_manager.update)
                
                def handle_results():
                    nonlocal viral_scout_cache
                    if hits:
                        hits.sort(key=lambda x: x.get('score', 0), reverse=True)
                        current_text = input_text.get('1.0', tk.END).strip()
                        new_urls = "\n".join([h['url'] for h in hits])
                        input_text.delete('1.0', tk.END)
                        input_text.insert(tk.END, (current_text + "\n" if current_text else "") + new_urls + "\n")
                        viral_scout_cache = hits
                        status_manager.update(f"✨ Encontrados {len(hits)} candidatos de discovery!")
                        # REMOVED: Immediate mark_as_processed. We only mark when kept or rejected.
                    else:
                        status_manager.update(f"🤷 Sin resultados en las últimas {hours}h.")
                        root.deiconify()
                        root.lift()
                        if messagebox.askyesno("Sin Resultados", f"¿Ampliar búsqueda más allá de {hours}h?", parent=root):
                            new_hours = simpledialog.askinteger("Ampliar", "¿Cuántas horas atrás?", 
                                                                initialvalue=hours+24, minvalue=1, maxvalue=720, parent=root)
                            if new_hours:
                                reprocess = messagebox.askyesno("Reprocesar", "¿Incluir tuits ya procesados?", parent=root)
                                root.after(500, lambda: run_viral_scout(hours=new_hours, ignore_history=reprocess))
                    btn_scout.config(state="normal", text="🔍 Discovery")
                
                root.after(0, handle_results)
            except Exception as e:
                root.after(0, lambda: status_manager.update(f"❌ Error: {str(e)}"))
                root.after(0, lambda: btn_scout.config(state="normal", text="🔍 Discovery"))
            
        threading.Thread(target=scout_task, daemon=True).start()
    
    # Viral Scout function

    def run_process():
        # --- PRE-FLIGHT HEALTH CHECK ---
        print("\n" + "!" * 80)
        print("🔍 EJECUTANDO PRE-FLIGHT CHECK: Verificando CentralAIService...")
        if not check_centralai_health(CENTRAL_AI_URL):
            print("\n❌ ERROR CRÍTICO: CentralAIService no está corriendo en " + CENTRAL_AI_URL)
            print("❌ Abortando proceso para no gastar recursos innecesariamente.")
            print("!" * 80 + "\n")
            messagebox.showerror("Error de Conexión", f"CentralAIService no está respondiendo en {CENTRAL_AI_URL}.\n\nPor favor, inicia el servicio antes de continuar.")
            sys.exit(1)
        print("✅ CentralAIService: ONLINE")
        print("!" * 80 + "\n")

        nonlocal viral_scout_cache
        raw_text = input_text.get('1.0', tk.END).strip()
        if not raw_text:
            messagebox.showwarning("Aviso", "La lista de enlaces está vacía.")
            return
        
        text_urls = [line.strip() for line in raw_text.split('\n') if line.strip()]
        
        # --- NEW: Immediate History Filter ---
        from core.viral_scout import ViralScout
        scout = ViralScout()
        
        final_items = []
        skipped_count = 0
        force_process = force_process_var.get()
        
        for url in text_urls:
            from core.scraper import extract_tweet_id
            tweet_id = extract_tweet_id(url)
            
            # Skip check if force process is ON
            if not force_process:
                if tweet_id and scout.is_processed(tweet_id):
                    skipped_count += 1
                    continue
            
            # Map rich data if available
            if viral_scout_cache:
                cache_map = {h['url']: h for h in viral_scout_cache}
                final_items.append(cache_map.get(url, url))
            else:
                final_items.append(url)
        
        if not final_items and skipped_count > 0:
            messagebox.showinfo("Procesado", f"Se omitieron {skipped_count} tweets porque ya han sido procesados anteriormente.\nUsa '⚡ Reprocesar' para forzar.")
            return
            
        if not final_items:
            messagebox.showwarning("Aviso", "No hay tweets válidos para procesar.")
            return

        btn_run.config(state="disabled", text="⏳ PROCESANDO...")
        status_manager = StatusManager(status_var, log_widget)
        
        if skipped_count > 0:
            status_manager.update(f"⚠️ Omitidos {skipped_count} tweets ya procesados.")
            # Update input text to show only what's being processed
            input_text.delete('1.0', tk.END)
            input_text.insert(tk.END, "\n".join([i['url'] if isinstance(i, dict) else i for i in final_items]) + "\n")

        def task():
            batch_process(final_items, status_manager)
            root.after(0, lambda: btn_run.config(state="normal", text="▶ INICIAR PROCESO"))
            root.after(0, lambda: status_var.set("✅ Proceso Finalizado"))
            root.after(0, refresh_scheduled)
            
        threading.Thread(target=task, daemon=True).start()

    btn_scout.config(command=run_viral_scout)
    btn_run.config(command=run_process)

    root.mainloop()

if __name__ == "__main__":
    import warnings
    warnings.simplefilter("ignore") # Suppress FutureWings for cleaner output
    
    # Run automated cleanup on startup (Quiet mode)
    try:
        cleanup_temp_files(os.path.dirname(os.path.abspath(__file__)))
        cleanup_old_files(os.path.join(os.path.dirname(os.path.abspath(__file__)), "output"), max_age_hours=7*24, quiet=True)
    except Exception as e:
        # print(f"[CLEANUP] Startup cleanup failed: {e}")
        pass

    if len(sys.argv) > 1:
        # CLI Mode
        urls = sys.argv[1:]
        status = StatusManager()
        batch_process(urls, status)
    else:
        try:
            run_gui()
        except BaseException as e:
            import traceback
            with open("LAST_CRASH.txt", "w", encoding="utf-8") as f:
                f.write(f"FATAL ERROR AT {datetime.now()}:\n")
                f.write(str(e) + "\n\n")
                f.write(traceback.format_exc())
            print(f"\n[FATAL] El programa ha fallado: {e}")
            print("Se ha generado LAST_CRASH.txt con los detalles.")
            sys.exit(1)
