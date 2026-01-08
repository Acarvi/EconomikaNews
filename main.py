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
from scraper import scrape_tweet
from downloader import download_media, DOWNLOADS_DIR
from ai_handler import generate_content_ai
from generator import generate_reel_from_image, process_video_for_reel, OUTPUT_DIR
import cv2
import numpy as np
from PIL import Image, ImageTk, ImageDraw
try:
    from ffpyplayer.player import MediaPlayer
except ImportError:
    MediaPlayer = None

import publisher # New automation module

# --- CONFIG & HELPERS ---

class StatusManager:
    """Manages status updates for both CLI and GUI."""
    def __init__(self, gui_status_var=None, gui_log_widget=None):
        self.gui_status_var = gui_status_var
        self.gui_log_widget = gui_log_widget

    def update(self, message: str):
        print(message)  # Always print to console
        
        # Schedule UI updates on the main thread using a widget's .after()
        # We prefer gui_log_widget as it's a real widget, gui_status_var is just data.
        
        target_widget = self.gui_log_widget
        
        if target_widget:
            def _ui_update():
                try:
                    if self.gui_status_var:
                        self.gui_status_var.set(message)
                    
                    self.gui_log_widget.configure(state='normal')
                    self.gui_log_widget.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
                    self.gui_log_widget.see(tk.END)
                    self.gui_log_widget.configure(state='disabled')
                except: pass
            target_widget.after(0, _ui_update)
        elif self.gui_status_var:
            # Fallback if no log widget is available (mostly CLI or headless)
            # Setting StringVar directly is often thread-safe, but we lack .after() here
            self.gui_status_var.set(message)

def render_item_assets(tweet_data: Dict, status: StatusManager, feedback: str = None) -> Dict:
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
        success, media_path = download_media(tweet_url, thumbnail_url=tweet_data.get('thumbnail'))
        if not success: media_path = None
    
    # 2. AI Gen (with feedback support)
    status.update("   Generating AI content...")
    from ai_handler import generate_content_ai # Ensure import
    headline, caption, slug, shorts_title = generate_content_ai(tweet_data, media_path, feedback)

    # 3. Folder Setup
    clean_slug = re.sub(r'[^a-z0-9_]', '', slug.lower().replace(" ", "_").replace("-", "_"))
    item_folder_name = f"{date_str}_{clean_slug}"
    item_folder_path = os.path.join(OUTPUT_DIR, item_folder_name)
    os.makedirs(item_folder_path, exist_ok=True)
    base_name = f"economika_{item_folder_name}"

    # 4. Save artifacts
    caption_path = os.path.join(item_folder_path, f"{base_name}.md")
    with open(caption_path, 'w', encoding='utf-8') as f:
        f.write(f"# {headline}\n\n### 📹 SHORTS\n{shorts_title}\n\n### 📝 CAPTION\n{caption}\n")
    
    html_path = os.path.join(item_folder_path, "copiar_movil.html")
    from main import generate_mobile_html
    generate_mobile_html(html_path, headline, shorts_title, caption)

    # 5. Render Reel
    status.update("   Rendering Video...")
    output_name = f"{base_name}.mp4"
    skip_subtitles = tweet_data.get('skip_subtitles', False)
    if is_video and media_path:
        temp_reel_path = process_video_for_reel(media_path, headline, uploader_id, output_name, skip_subtitles=skip_subtitles)
    else:
        temp_reel_path = generate_reel_from_image(media_path, headline, uploader_id, output_name)
    
    final_reel_path = os.path.join(item_folder_path, output_name)
    if temp_reel_path and os.path.exists(temp_reel_path) and temp_reel_path != final_reel_path:
        shutil.move(temp_reel_path, final_reel_path)
    
    # Cleanup temp media
    try:
        if media_path and os.path.exists(media_path): os.remove(media_path)
    except: pass

    return {
        'folder': item_folder_path,
        'reel_path': final_reel_path,
        'headline': headline,
        'shorts_title': shorts_title,
        'caption': caption,
        'tweet_data': tweet_data
    }

class PostAiCurationManager:
    # Existing code here for clarity in replacement
    def __init__(self, parent, items, status_manager, process_callback):
        self.root = tk.Toplevel(parent)
        self.root.title(f"Revisión de Lote ({len(items)} Reels) - Economika")
        self.root.geometry("1100x900")
        self.root.configure(bg="#121212")
        self.root.grab_set()
        
        self.items = items
        self.current_idx = 0
        self.status = status_manager
        self.process_callback = process_callback # To call for regeneration
        self.approved_folders = []
        
        self.cap = None
        self.player = None
        self.is_muted = False
        self.scheduled_posts = []  # For batch scheduling
        
        # --- UI LAYOUT (Persistent) ---
        self.preview_frame = tk.Frame(self.root, bg="#121212", width=400, height=711)
        self.preview_frame.pack(side="left", padx=30, pady=30, fill="both", expand=True)
        self.canvas = tk.Canvas(self.preview_frame, width=400, height=711, bg="black", highlightthickness=0)
        self.canvas.pack(expand=True)
        
        self.info_frame = tk.Frame(self.root, bg="#121212")
        self.info_frame.pack(side="right", padx=30, pady=30, fill="both")
        
        self.header_label = tk.Label(self.info_frame, text="", font=("Segoe UI Black", 16), fg="#E31E24", bg="#121212")
        self.header_label.pack(anchor="w")
        
        tk.Label(self.info_frame, text="YouTube Shorts Title:", font=("Segoe UI Bold", 10), fg="#888", bg="#121212").pack(anchor="w", pady=(20, 5))
        self.shorts_text = tk.Text(self.info_frame, height=2, width=45, bg="#1e1e1e", fg="white", font=("Segoe UI", 11), borderwidth=0, padx=10, pady=10)
        self.shorts_text.pack(fill="x")
        
        tk.Label(self.info_frame, text="Instagram Caption:", font=("Segoe UI Bold", 10), fg="#888", bg="#121212").pack(anchor="w", pady=(20, 5))
        self.caption_text = tk.Text(self.info_frame, height=10, width=45, bg="#1e1e1e", fg="white", font=("Segoe UI", 11), borderwidth=0, padx=10, pady=10)
        self.caption_text.pack(fill="x")
        
        # Feedback Section
        tk.Label(self.info_frame, text="Instrucciones para la IA (Feedback):", font=("Segoe UI Bold", 10), fg="#f1c40f", bg="#121212").pack(anchor="w", pady=(20, 5))
        self.feedback_text = tk.Text(self.info_frame, height=3, width=45, bg="#2c3e50", fg="white", font=("Segoe UI Italic", 10), borderwidth=0, padx=10, pady=10)
        self.feedback_text.pack(fill="x")
        self.feedback_text.insert(tk.END, "Ej: Hazlo más dramático, menciona el impacto en el ahorro...")

        self.btn_sub_frame = tk.Frame(self.info_frame, bg="#121212")
        self.btn_sub_frame.pack(fill="x", pady=20)
        
        self.btn_regen = tk.Button(self.btn_sub_frame, text="🔄 REGENERAR IA", bg="#f39c12", fg="#121212", font=("Segoe UI Black", 10), 
                                  padx=8, pady=8, borderwidth=0, command=self.regenerate)
        self.btn_regen.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        self.btn_remove_subs = tk.Button(self.btn_sub_frame, text="🚫 QUITAR SUBS", bg="#e74c3c", fg="white", font=("Segoe UI Black", 10), 
                                        padx=8, pady=8, borderwidth=0, command=self.remove_subtitles)
        self.btn_remove_subs.pack(side="right", fill="x", expand=True, padx=(5, 0))

        self.action_btn_frame = tk.Frame(self.info_frame, bg="#121212")
        self.action_btn_frame.pack(fill="x", pady=20)
        
        self.btn_discard = tk.Button(self.action_btn_frame, text="⬅ DESCARTAR", bg="#c0392b", fg="white", font=("Segoe UI Black", 12), 
                                    padx=20, pady=15, borderwidth=0, command=self.discard)
        self.btn_discard.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.btn_publish = tk.Button(self.action_btn_frame, text="📸 PUBLICAR EN INSTAGRAM", bg="#3498db", fg="white", font=("Segoe UI Black", 12), 
                                    padx=20, pady=15, borderwidth=0, command=self.publish_ig)
        self.btn_publish.pack(side="left", fill="x", expand=True, padx=(5, 5))

        self.btn_keep = tk.Button(self.action_btn_frame, text="APROBAR ➡", bg="#27ae60", fg="white", font=("Segoe UI Black", 12), 
                                 padx=20, pady=15, borderwidth=0, command=self.keep)
        self.btn_keep.pack(side="right", fill="x", expand=True, padx=(10, 0))
        
        # Second row for mute and batch
        self.action_btn_frame2 = tk.Frame(self.info_frame, bg="#121212")
        self.action_btn_frame2.pack(fill="x", pady=(0, 10))
        
        self.btn_mute = tk.Button(self.action_btn_frame2, text="🔊", bg="#555", fg="white", font=("Segoe UI", 12), width=4, command=self.toggle_mute)
        self.btn_mute.pack(side="left", padx=(0, 10))
        
        self.btn_batch = tk.Button(self.action_btn_frame2, text="📅 PROGRAMAR", bg="#9b59b6", fg="white", font=("Segoe UI Black", 10),
                                   padx=10, pady=6, borderwidth=0, command=self.add_to_batch)
        self.btn_batch.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        self.btn_raw = tk.Button(self.action_btn_frame2, text="🎬 RAW", bg="#2c3e50", fg="white", font=("Segoe UI Black", 10),
                                 padx=10, pady=6, borderwidth=0, command=self.publish_raw)
        self.btn_raw.pack(side="right", fill="x", expand=True, padx=(5, 0))
        
        # Asset Loading
        self.overlay_np = None
        overlay_path = os.path.join(os.path.dirname(__file__), "assets", "instagram_mock.png")
        if os.path.exists(overlay_path):
            ov_img = Image.open(overlay_path).convert("RGBA").resize((400, 711))
            self.overlay_np = np.array(ov_img).astype(float) / 255.0
            
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.load_item()
        self.update_frame()

    def load_item(self):
        if self.current_idx >= len(self.items):
            self.on_finish()
            return
            
        item = self.items[self.current_idx]
        self.header_label.config(text=f"REVISIÓN {self.current_idx + 1}/{len(self.items)}")
        
        self.shorts_text.delete('1.0', tk.END)
        self.shorts_text.insert(tk.END, item.get('shorts_title', ''))
        
        self.caption_text.delete('1.0', tk.END)
        self.caption_text.insert(tk.END, item.get('caption', ''))
        
        self.feedback_text.delete('1.0', tk.END)
        self.feedback_text.insert(tk.END, "") # Clear each time

        if self.cap: self.cap.release()
        try:
            self.cap = cv2.VideoCapture(item['reel_path'])
            if MediaPlayer:
                self.player = MediaPlayer(item['reel_path'])
            
            if not self.cap.isOpened():
                self.status.update(f"   ⚠️ Error al abrir vídeo para preview: {item['reel_path']}")
        except Exception as e:
            print(f"[UI ERROR] Failed to load reel preview: {e}")
            self.status.update(f"   ⚠️ Error de preview: {str(e)[:40]}")

    def update_frame(self):
        if not self.root.winfo_exists() or self.current_idx >= len(self.items): return
        
        ret, frame = False, None
        
        if self.cap and self.cap.isOpened():
            # Sync with ffpyplayer if available
            if self.player:
                audio_frame, val = self.player.get_frame()
                if val == 'eof':
                    self.player.seek(0, relative=False)
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = self.cap.read()
                elif val != 'toggle' and audio_frame is not None:
                    # audio_frame is (img, pts)
                    img_data, pts = audio_frame
                    # We still use cv2 for the main frame to keep alpha blending logic simple
                    ret, frame = self.cap.read()
                else:
                    # Just keep showing
                    ret, frame = self.cap.read()
            else:
                ret, frame = self.cap.read()

            if not ret:
                if self.cap: self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                if self.player: self.player.seek(0, relative=False)
                ret, frame = self.cap.read()
                
            if ret and frame is not None:
                # Resize according to canvas current size or fixed 400x711
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
        new_shorts = self.shorts_text.get('1.0', tk.END).strip()
        new_caption = self.caption_text.get('1.0', tk.END).strip()
        
        try:
            base_name = os.path.basename(item['reel_path']).replace(".mp4", "")
            md_path = os.path.join(folder, f"{base_name}.md")
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(f"# {item.get('headline', 'NOTICIA')}\n\n### 📹 SHORTS\n{new_shorts}\n\n### 📝 CAPTION\n{new_caption}\n")
            
            html_path = os.path.join(folder, "copiar_movil.html")
            generate_mobile_html(html_path, item.get('headline', 'NOTICIA'), new_shorts, new_caption)
            self.approved_folders.append(folder)
            self.status.update(f"   ⭐ Reel '{os.path.basename(folder)}' aprobado.")
        except Exception as e:
            self.status.update(f"   ⚠️ Error actualizando archivos: {e}")
            self.approved_folders.append(folder)
            
        self.next_item()

    def publish_ig(self):
        item = self.items[self.current_idx]
        config = publisher.load_config()
        if not config:
            messagebox.showerror("Error de API", "No se encontró configuración de API. Asegura que el token sea correcto.")
            return
            
        caption = self.caption_text.get('1.0', tk.END).strip()
        video_path = item['reel_path']
        
        self.btn_publish.config(state="disabled", text="⏳ SUBIENDO...")
        self.status.update(f"   🚀 Iniciando publicación en Instagram para '{os.path.basename(video_path)}'...")
        
        def run_publish():
            try:
                # 1. Upload to temp host
                temp_url = publisher.upload_to_temporary_host(video_path)
                if not temp_url:
                    self.root.after(0, lambda: messagebox.showerror("Error", "No se pudo generar una URL pública para el vídeo."))
                    return
                
                # 2. Upload to Instagram
                res = publisher.upload_reel(temp_url, caption, config['access_token'], config['ig_user_id'])
                
                if res and "id" in res:
                    self.root.after(0, lambda: messagebox.showinfo("Éxito", f"¡Vídeo publicado con éxito!\nID: {res['id']}"))
                    self.root.after(0, self.keep) # Move to next and save locally
                else:
                    self.root.after(0, lambda: messagebox.showerror("Error", f"Fallo en la publicación de Instagram: {res}"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Error inesperado: {str(e)}"))
            finally:
                self.root.after(0, lambda: self.btn_publish.config(state="normal", text="📸 PUBLICAR EN INSTAGRAM"))

        threading.Thread(target=run_publish, daemon=True).start()

    def discard(self):
        item = self.items[self.current_idx]
        self.status.update(f"   🗑️ Reel '{os.path.basename(item['folder'])}' descartado.")
        try: shutil.rmtree(item['folder'])
        except: pass
        self.next_item()

    def regenerate(self):
        item = self.items[self.current_idx]
        feedback = self.feedback_text.get('1.0', tk.END).strip()
        if not feedback or "Ej:" in feedback:
            messagebox.showwarning("Feedback necesario", "Por favor escribe qué quieres cambiar en el campo de feedback.")
            return

        self.btn_regen.config(state="disabled", text="⏳ REGENERANDO CON IA...")
        self.items[self.current_idx] = self.process_callback(item, feedback)
        self.btn_regen.config(state="normal", text="🔄 REGENERAR IA")
        self.load_item() # Refresh current item

    def remove_subtitles(self):
        """Re-render the current video without subtitles."""
        item = self.items[self.current_idx]
        self.btn_remove_subs.config(state="disabled", text="⏳ RE-RENDERIZANDO...")
        self.status.update(f"   🔄 Re-renderizando sin subtítulos...")
        
        # Force skip_subtitles and re-render
        tweet_data = item.get('tweet_data', {})
        tweet_data['skip_subtitles'] = True
        
        # Re-render using callback
        self.items[self.current_idx] = self.process_callback(item, None)
        self.btn_remove_subs.config(state="normal", text="🚫 QUITAR SUBS")
        self.status.update(f"   ✅ Vídeo re-renderizado sin subtítulos.")
        self.load_item()

    def next_item(self):
        self.current_idx += 1
        self.load_item()

    def toggle_mute(self):
        self.is_muted = not self.is_muted
        if self.player:
            self.player.set_volume(0.0 if self.is_muted else 1.0)
        self.btn_mute.config(text="🔇" if self.is_muted else "🔊")

    def add_to_batch(self):
        """Add current item to the scheduled batch and move to next."""
        item = self.items[self.current_idx]
        caption = self.caption_text.get('1.0', tk.END).strip()
        self.scheduled_posts.append({
            'reel_path': item['reel_path'],
            'caption': caption,
            'folder': item['folder']
        })
        self.status.update(f"   📅 Reel añadido al batch de programación ({len(self.scheduled_posts)} en cola).")
        self.approved_folders.append(item['folder'])
        self.next_item()

    def publish_raw(self):
        """Publish the original/raw video without Economika branding."""
        item = self.items[self.current_idx]
        tweet_data = item.get('tweet_data', {})
        
        # Get the original media path
        raw_video_path = tweet_data.get('local_media_path')
        
        if not raw_video_path or not os.path.exists(raw_video_path):
            messagebox.showerror("Error", "No se encontró el vídeo original. Puede que ya se haya eliminado.")
            return
        
        config = publisher.load_config()
        if not config:
            messagebox.showerror("Error de API", "No se encontró configuración de API.")
            return
            
        caption = self.caption_text.get('1.0', tk.END).strip()
        
        self.btn_raw.config(state="disabled", text="⏳ SUBIENDO RAW...")
        self.status.update(f"   🎬 Publicando vídeo RAW en Instagram...")
        
        def run_raw_publish():
            try:
                # Upload original video directly
                temp_url = publisher.upload_to_temporary_host(raw_video_path)
                if not temp_url:
                    self.root.after(0, lambda: messagebox.showerror("Error", "No se pudo subir el vídeo."))
                    return
                
                res = publisher.upload_reel(temp_url, caption, config['access_token'], config['ig_user_id'])
                
                if res and "id" in res:
                    self.root.after(0, lambda: messagebox.showinfo("Éxito", f"¡Vídeo RAW publicado!\\nID: {res['id']}"))
                    self.root.after(0, self.keep)
                else:
                    self.root.after(0, lambda: messagebox.showerror("Error", f"Fallo: {res}"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Error: {str(e)}"))
            finally:
                self.root.after(0, lambda: self.btn_raw.config(state="normal", text="🎬 RAW"))
        
        threading.Thread(target=run_raw_publish, daemon=True).start()

    def on_finish(self):
        self.status.update(f"\n✨ Curación finalizada. {len(self.approved_folders)} reels guardados.")
        
        # Trigger batch scheduling if any posts were queued
        if self.scheduled_posts:
            self.status.update(f"📅 Programando {len(self.scheduled_posts)} posts para Instagram...")
            try:
                scheduled_times = publisher.schedule_batch(self.scheduled_posts)
                for i, t in enumerate(scheduled_times):
                    self.status.update(f"   ⏰ Post {i+1} programado para {t}")
            except Exception as e:
                self.status.update(f"   ❌ Error programando: {e}")
        
        if self.approved_folders:
            try: os.startfile(self.approved_folders[-1])
            except: pass
        self.on_close()

    def on_close(self):
        if self.cap: self.cap.release()
        if hasattr(self, 'player') and self.player:
            self.player.close_player()
        self.root.destroy()

class PreAiCurationManager:
    """Stage 1: Filter original tweets before using Gemini AI."""
    def __init__(self, parent, raw_items, on_complete):
        self.root = tk.Toplevel(parent)
        self.root.title(f"Filtro Pre-IA ({len(raw_items)} Tweets)")
        self.root.geometry("1000x650")
        self.root.configure(bg="#1a1a1a")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self.raw_items = raw_items
        self.current_idx = 0
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
        self.header.pack(pady=(10, 20), anchor="w")
        
        self.content_text = tk.Text(self.right_frame, height=15, bg="#252525", fg="white", font=("Segoe UI", 11), borderwidth=0, padx=10, pady=10)
        self.content_text.pack(fill="both", expand=True)
        
        self.btn_frame = tk.Frame(self.right_frame, bg="#1a1a1a")
        self.btn_frame.pack(fill="x", pady=20)
        
        tk.Button(self.btn_frame, text="🗑️ DESCARTAR", bg="#c0392b", fg="white", font=("Segoe UI Black", 11), width=15, command=self.discard).pack(side="left")
        
        # Mute Button
        self.btn_mute = tk.Button(self.btn_frame, text="🔊", bg="#555", fg="white", font=("Segoe UI", 11), width=3, command=self.toggle_mute)
        self.btn_mute.pack(side="left", padx=10)
        
        # Skip Subtitles Checkbox
        self.skip_subtitles_var = tk.BooleanVar(value=False)
        tk.Checkbutton(self.btn_frame, text="Sin Subs", variable=self.skip_subtitles_var, bg="#1a1a1a", fg="white", selectcolor="#333", font=("Segoe UI", 10), activebackground="#1a1a1a", activeforeground="white").pack(side="left", padx=5)
        
        tk.Button(self.btn_frame, text="✅ PROCESAR CON IA", bg="#27ae60", fg="white", font=("Segoe UI Black", 11), width=18, command=self.keep).pack(side="right")
        
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

        if self.cap: self.cap.release()
        if hasattr(self, 'player') and self.player:
            self.player.close_player()
        
        self.cap = None
        self.player = None
        self.canvas.delete("all")
        
        media_path = tweet.get('local_media_path')
        if media_path and os.path.exists(media_path):
            try:
                if tweet.get('is_video'):
                    self.cap = cv2.VideoCapture(media_path)
                    if MediaPlayer:
                        # Sync with 30fps roughly
                        self.player = MediaPlayer(media_path)
                else:
                    # Still image
                    img = Image.open(media_path).convert("RGB")
                    img = self.resize_contain(img, 340, 500)
                    self.tk_img = ImageTk.PhotoImage(img)
                    self.canvas.create_image(170, 250, anchor="center", image=self.tk_img)
            except Exception as e:
                print(f"[UI ERROR] Failed to load media {media_path}: {e}")
                self.canvas.create_text(170, 250, text=f"⚠️ ERROR MEDIA\n{str(e)[:40]}", fill="red", font=("Segoe UI Bold", 10), justify="center")

    def update_frame(self):
        if not self.root.winfo_exists() or self.current_idx >= len(self.raw_items): return
        
        ret, frame = False, None
        
        if self.cap and self.cap.isOpened():
            if hasattr(self, 'player') and self.player:
                audio_frame, val = self.player.get_frame()
                if val == 'eof':
                    self.player.seek(0, relative=False)
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = self.cap.read()
                elif val != 'toggle' and audio_frame is not None:
                    ret, frame = self.cap.read()
                else:
                    # If no audio frame yet, still read video to keep it moving
                    ret, frame = self.cap.read()
            else:
                ret, frame = self.cap.read()

            if not ret:
                # Handle end of video if val=='eof' missed it
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                if hasattr(self, 'player') and self.player:
                    self.player.seek(0, relative=False)
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
                self.canvas.create_image(170, 250, anchor="center", image=self.tk_img)
        
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

    def keep(self):
        item = self.raw_items[self.current_idx]
        item['skip_subtitles'] = self.skip_subtitles_var.get()
        self.kept_items.append(item)
        self.current_idx += 1
        self.load_tweet()

    def discard(self):
        self.current_idx += 1
        self.load_tweet()

def cleanup_old_files(directory: str, max_age_hours: int = 24):
    """Delete files and folders older than max_age_hours."""
    now = time.time()
    count = 0
    if not os.path.exists(directory): return
    for f in os.listdir(directory):
        path = os.path.join(directory, f)
        try:
            if os.stat(path).st_mtime < now - (max_age_hours * 3600):
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                count += 1
        except Exception as e:
            print(f"Error cleaning {f}: {e}")
    if count > 0:
        print(f"🧹 Cleaned {count} old items from {os.path.basename(directory)}")

def generate_mobile_html(output_path, headline, shorts_title, caption):
    """Creates a mobile-friendly HTML with reliable copy functionality."""
    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Copy Tool - Economika</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #121212; color: #fff; padding: 15px; }}
        .header {{ text-align: center; border-bottom: 2px solid #E31E24; padding-bottom: 10px; margin-bottom: 20px; }}
        h1 {{ color: #E31E24; margin: 0; font-size: 22px; }}
        .card {{ background: #1e1e1e; padding: 15px; border-radius: 12px; margin-bottom: 25px; border: 1px solid #333; }}
        .label {{ font-size: 11px; color: #aaa; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; font-weight: bold; }}
        
        /* Textarea for reliable copying */
        textarea.copy-source {{
            width: 100%;
            background: #252525;
            color: #ddd;
            border: 1px solid #444;
            border-radius: 6px;
            padding: 10px;
            font-size: 14px;
            resize: none;
            height: 120px;
            box-sizing: border-box;
            font-family: inherit;
        }}
        textarea.short {{ height: 60px; }}

        .btn {{ 
            display: block; width: 100%; background: #E31E24; color: white; border: none; 
            padding: 14px; border-radius: 8px; font-weight: bold; margin-top: 10px; cursor: pointer;
            font-size: 16px; user-select: none; -webkit-user-select: none;
        }}
        .btn:active {{ transform: scale(0.98); background: #c01a20; }}
        .success {{ background: #27ae60 !important; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>ECONÓMIKA TOOLS</h1>
    </div>

    <div class="card">
        <div class="label">YouTube Shorts Title</div>
        <textarea id="shorts" class="copy-source short" readonly onclick="this.select()">{shorts_title}</textarea>
        <button class="btn" onclick="copyToClipboard('shorts', this)">COPIAR TÍTULO</button>
    </div>

    <div class="card">
        <div class="label">Instagram Caption</div>
        <textarea id="caption" class="copy-source" readonly onclick="this.select()">{caption}</textarea>
        <button class="btn" onclick="copyToClipboard('caption', this)">COPIAR CAPTION</button>
    </div>

    <script>
        function copyToClipboard(elementId, btn) {{
            const textarea = document.getElementById(elementId);
            
            // Method 1: Select and ExecCommand (Better for mobile webviews)
            textarea.select();
            textarea.setSelectionRange(0, 99999); // For mobile devices
            
            try {{
                const successful = document.execCommand('copy');
                if(successful) {{
                    showSuccess(btn);
                }} else {{
                    // Method 2: Navigator Clipboard API
                    navigator.clipboard.writeText(textarea.value).then(() => {{
                        showSuccess(btn);
                    }}).catch(err => {{
                        btn.innerText = "COPIA MANUALMENTE (Selecciona el texto arriba)";
                        btn.style.background = "#555";
                    }});
                }}
            }} catch (err) {{
                btn.innerText = "ERROR - Usa copiado manual";
            }}
        }}

        function showSuccess(btn) {{
            const originalText = "COPIAR";
            btn.innerText = "¡COPIADO!";
            btn.classList.add('success');
            setTimeout(() => {{
                if (btn.innerText === "¡COPIADO!") {{
                    btn.classList.remove('success');
                    // Restaurar texto original basado en el contexto si fuera dinámico, pero aquí es simple button
                    // Simplemente quitamos la clase, el texto puede quedarse o volver
                    btn.style.background = "#E31E24";
                }}
            }}, 2000);
        }}
    </script>
</body>
</html>"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

# --- CORE LOGIC ---

def batch_process(urls: list, status: StatusManager):
    """Refactored 2-Stage Process: Scrape -> Filter -> Process -> Curate."""
    cleanup_old_files(DOWNLOADS_DIR)
    cleanup_old_files(OUTPUT_DIR)
    
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
            # If we have rich data from Viral Scout, use it directly
            if rich_data and rich_data.get('media_url'):
                data = {
                    'id': rich_data.get('id'),
                    'title': rich_data.get('description', '')[:100],
                    'description': rich_data.get('description', ''),
                    'uploader': rich_data.get('user', ''),
                    'uploader_id': rich_data.get('user', ''),
                    'thumbnail': rich_data.get('thumbnail'),
                    'url': rich_data.get('media_url'),
                    'media_url': rich_data.get('media_url'),
                    'is_video': rich_data.get('is_video', False),
                    'reposts': rich_data.get('reposts', 0),
                    'likes': rich_data.get('likes', 0),
                }
                status.update(f"   ✅ Usando datos de Viral Scout...")
            else:
                data = scrape_tweet(url)
            
            if data: 
                data['url'] = url
                # PRE-DOWNLOAD for filter preview
                status.update(f"   📥 Descargando media para preview...")
                # Use media_url if available, otherwise use thumbnail
                download_url = data.get('media_url') or data.get('url')
                success, media_path = download_media(url, thumbnail_url=data.get('thumbnail') or download_url)
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

    root.after(0, lambda: PreAiCurationManager(root, scraped_data, on_filter_complete))
    
    # Wait for UI to finish Stage 1
    while not filter_event.is_set():
        time.sleep(0.1)

    if not kept_after_filter:
        status.update("✨ Proceso cancelado o ningún item seleccionado.")
        return

    # --- STAGE 3: PROCESS KEPT ITEMS ---
    status.update(f"⚙️ Procesando {len(kept_after_filter)} items seleccionados...")
    pending_curation = []
    
    for i, item_data in enumerate(kept_after_filter):
        if i > 0: time.sleep(5) # RPM Safety
        status.update(f"\n[{i+1}/{len(kept_after_filter)}] Redactando y Renderizando...")
        try:
            rendered = render_item_assets(item_data, status)
            pending_curation.append(rendered)
        except Exception as e:
            status.update(f"   ❌ Error procesando: {e}")
            
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
    
    # Cloud server URL
    CLOUD_SERVER_URL = "https://economikanoticias.onrender.com"
    
    def fetch_from_cloud():
        """Fetch pending tweets from Render cloud server."""
        nonlocal viral_scout_cache
        btn_cloud.config(state="disabled", text="⏳ Sync...")
        status_var.set("Conectando con servidor cloud...")
        
        def cloud_task():
            try:
                import requests
                response = requests.get(f"{CLOUD_SERVER_URL}/pending", timeout=30)
                data = response.json()
                
                def handle_cloud_data():
                    nonlocal viral_scout_cache
                    if data.get('tweets'):
                        tweets = data['tweets']
                        # Add to input
                        urls = "\n".join([t['url'] for t in tweets])
                        input_text.delete('1.0', tk.END)
                        input_text.insert(tk.END, urls + "\n")
                        # Cache the rich data
                        viral_scout_cache = tweets
                        status_var.set(f"☁️ {len(tweets)} tweets cargados desde cloud")
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
    
    btn_scout = create_modern_button(btn_row, "🔍 Scout", lambda: None, "#9b59b6")  # Will be configured later
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
        from viral_scout import ViralScout
        from tkinter import simpledialog
        
        btn_scout.config(state="disabled", text="⏳ Buscando...")
        status_manager = StatusManager(status_var, log_widget)
        
        def scout_task():
            try:
                scout = ViralScout()
                status_manager.update(f"🚀 Iniciando Viral Scout ({hours}h)...")
                hits = scout.scan(hours_back=hours, ignore_history=ignore_history, 
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
                        status_manager.update(f"✨ Encontrados {len(hits)} tweets virales!")
                        for h in hits:
                            scout.mark_as_processed(h['id'])
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
                    btn_scout.config(state="normal", text="🔍 Viral Scout")
                
                root.after(0, handle_results)
            except Exception as e:
                root.after(0, lambda: status_manager.update(f"❌ Error: {str(e)}"))
                root.after(0, lambda: btn_scout.config(state="normal", text="🔍 Viral Scout"))
            
        threading.Thread(target=scout_task, daemon=True).start()
    
    btn_scout.config(command=run_viral_scout)
    
    def run_process():
        nonlocal viral_scout_cache
        raw_text = input_text.get('1.0', tk.END).strip()
        if not raw_text:
            messagebox.showwarning("Aviso", "La lista de enlaces está vacía.")
            return
        
        text_urls = [line.strip() for line in raw_text.split('\n') if line.strip()]
        
        if viral_scout_cache:
            cache_map = {h['url']: h for h in viral_scout_cache}
            items = [cache_map.get(url, url) for url in text_urls]
        else:
            items = text_urls
        
        btn_run.config(state="disabled", text="⏳ PROCESANDO...")
        status_manager = StatusManager(status_var, log_widget)
        
        def task():
            batch_process(items, status_manager)
            root.after(0, lambda: btn_run.config(state="normal", text="▶ INICIAR PROCESO"))
            root.after(0, lambda: status_var.set("✅ Proceso Finalizado"))
            root.after(0, refresh_scheduled)
            
        threading.Thread(target=task, daemon=True).start()

    btn_run.config(command=run_process)

    root.mainloop()

if __name__ == "__main__":
    import warnings
    warnings.simplefilter("ignore") # Suppress FutureWings for cleaner output
    
    if len(sys.argv) > 1:
        # CLI Mode
        urls = sys.argv[1:]
        status = StatusManager()
        batch_process(urls, status)
    else:
        run_gui()
