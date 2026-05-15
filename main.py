from __future__ import annotations

import ctypes
import logging
import os
import socket
import sys
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from typing import Iterable

from flask import Flask, jsonify, render_template_string, request, send_file
from PIL import Image, ImageTk
import pyautogui
import pyperclip
import pystray
import qrcode

__version__ = "1.0"

APP_NAME = "PawSync_miao"
APP_HOST = "0.0.0.0"
APP_PORT = 5000
MAX_TEXT_LENGTH = 10_000
CLIPBOARD_SETTLE_SECONDS = 0.08
PASTE_SETTLE_SECONDS = 0.05

BACKGROUND_IMAGE_NAMES = (
    "background.png",
    "background.jpg",
    "background.jpeg",
    "background.webp",
    "anime-bg.png",
    "anime-bg.jpg",
    "anime-bg.webp",
)

MASCOT_IMAGE_NAMES = ("miao.png",)
APP_ICON_NAME = "miao.ico"
SINGLE_INSTANCE_MUTEX_NAME = "Global\\PawSyncMiaoSingleInstanceMutex"
ERROR_ALREADY_EXISTS = 183

PROFILE_LINKS = {
    "github_label": "GitHub",
    "github_url": "https://github.com/xiaofeiji7/PawSync_miao",
    "gitee_label": "Gitee",
    "gitee_url": "https://gitee.com/cold-nine/PawSync_miao",
    "bilibili_label": "Bilibili @是伊兹啊",
    "bilibili_url": "https://space.bilibili.com/432322151",
}

app = Flask(__name__)


def app_base_dir() -> Path:
    """Return source directory in development and bundled resource directory in PyInstaller."""
    bundled_dir = getattr(sys, "_MEIPASS", None)
    if bundled_dir:
        return Path(bundled_dir)
    return Path(__file__).resolve().parent


def find_image_file(names: Iterable[str]) -> Path | None:
    base_dir = app_base_dir()
    for name in names:
        image_path = base_dir / name
        if image_path.is_file():
            return image_path
    return None


def no_cache(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def paste_text(text: str) -> None:
    """Paste text into the current focused desktop control through the clipboard."""
    original_clipboard = pyperclip.paste()
    try:
        pyperclip.copy(text)
        time.sleep(CLIPBOARD_SETTLE_SECONDS)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(PASTE_SETTLE_SECONDS)
    finally:
        pyperclip.copy(original_clipboard)


def get_local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        sock.close()


def generate_qr_image(url: str, size: int = 200) -> Image.Image:
    """Generate a QR code as a PIL Image."""
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img = img.resize((size, size), Image.NEAREST)
    return img


def create_tray_icon_image() -> Image.Image:
    mascot_path = find_image_file(MASCOT_IMAGE_NAMES)
    if mascot_path:
        try:
            icon_img = Image.open(mascot_path).convert("RGBA")
            icon_img.thumbnail((64, 64), Image.LANCZOS)
            canvas = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            canvas.alpha_composite(icon_img, ((64 - icon_img.width) // 2, (64 - icon_img.height) // 2))
            return canvas
        except Exception:
            pass
    return Image.new("RGB", (64, 64), "#ff78bd")


def app_icon_path() -> Path | None:
    icon_path = app_base_dir() / APP_ICON_NAME
    return icon_path if icon_path.is_file() else None


def acquire_single_instance_mutex() -> object | None:
    if os.name != "nt":
        return object()
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, SINGLE_INSTANCE_MUTEX_NAME)
    if not mutex:
        return None
    if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        ctypes.windll.user32.MessageBoxW(None, f"{APP_NAME} 已经在运行了。", APP_NAME, 0x40)
        ctypes.windll.kernel32.CloseHandle(mutex)
        return None
    return mutex


# ==================== HTML Template ====================

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>{{ app_name }}</title>
    <style>
        * { box-sizing: border-box; }
        :root {
            color-scheme: light;
            --accent: #ff78bd;
            --text: #3b2948;
            --muted: #8f769c;
            --border: rgba(255, 135, 194, 0.5);
            --glass: rgba(255, 255, 255, 0.72);
        }
        body {
            min-height: 100vh; margin: 0;
            padding: clamp(12px, 3.5vw, 22px);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
            background: linear-gradient(145deg, #fff1f8 0%, #f9f1ff 52%, #eef8ff 100%);
            color: var(--text);
        }
        .app-card { position: relative; z-index: 1; width: min(100%, 540px); margin: 0 auto; padding-top: clamp(4px, 2vh, 16px); }
        #input-box {
            width: 100%; min-height: clamp(128px, 26vh, 200px);
            padding: clamp(14px, 4vw, 18px); border: 1.5px solid var(--border);
            border-radius: 22px; resize: none; outline: none; font: inherit;
            font-size: clamp(1.08rem, 4.4vw, 1.48rem); line-height: 1.5;
            color: var(--text); background: var(--glass);
            box-shadow: 0 12px 34px rgba(111, 76, 130, 0.12);
            backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
            transition: border-color 0.18s ease, box-shadow 0.18s ease;
        }
        #input-box:focus {
            border-color: rgba(255, 120, 189, 0.88);
            box-shadow: 0 14px 38px rgba(255, 120, 189, 0.18), 0 0 0 4px rgba(255, 120, 189, 0.15);
        }
        #send-device-btn {
            width: 100%; margin-top: clamp(9px, 2.6vw, 12px);
            min-height: clamp(54px, 12vw, 64px); border: none; border-radius: 999px;
            color: white; background: linear-gradient(135deg, #ff78bd 0%, #ff9acb 42%, #9b7cff 100%);
            font-size: clamp(1.12rem, 4.6vw, 1.48rem); font-weight: 800;
            cursor: pointer; box-shadow: 0 14px 30px rgba(155, 124, 255, 0.28);
            transition: transform 0.16s ease, opacity 0.16s ease;
        }
        #send-device-btn:active { transform: translateY(1px) scale(0.99); }
        #send-device-btn:disabled { cursor: wait; opacity: 0.72; }
        .hint { margin: 9px 0 0; text-align: center; color: var(--muted); font-size: clamp(0.8rem, 3.1vw, 0.92rem); }
        .hint.error { color: #c93b73; }
        .hint.success { color: #6a5acd; }
        .mascot-wrap { display: flex; justify-content: center; margin-top: clamp(12px, 3.5vw, 18px); pointer-events: none; }
        .mascot-img { width: min(58vw, 260px); max-height: min(34vh, 260px); object-fit: contain; opacity: 0.92; filter: drop-shadow(0 18px 28px rgba(111, 76, 130, 0.18)); }
        .profile-links {
            display: flex; justify-content: center; gap: 22px;
            margin-top: clamp(18px, 5vw, 26px);
        }
        .profile-link {
            width: 48px; height: 48px; border-radius: 16px;
            display: inline-flex; align-items: center; justify-content: center;
            text-decoration: none; color: white;
            box-shadow: 0 10px 22px rgba(111, 76, 130, 0.16);
            transition: transform 0.16s ease, box-shadow 0.16s ease;
        }
        .profile-link svg { width: 25px; height: 25px; fill: currentColor; }
        .profile-link:active { transform: translateY(1px) scale(0.98); }
        .profile-link.github { background: #24292f; }
        .profile-link.gitee { background: #c71d23; }
        .profile-link.bilibili { background: #00aeec; }
    </style>
</head>
<body>
    <main class="app-card">
        <textarea id="input-box" autofocus maxlength="{{ max_text_length }}" placeholder="在这里输入要发送到电脑的内容"></textarea>
        <button id="send-device-btn" type="button">发送到设备</button>
        <p id="status-hint" class="hint">发送成功后输入框会自动重置</p>
        <div class="mascot-wrap" aria-hidden="true">
            <img class="mascot-img" src="/mascot-image" alt="">
        </div>
        <nav class="profile-links" aria-label="外部链接">
            <a class="profile-link github" href="{{ github_url }}" target="_blank" rel="noopener noreferrer" aria-label="GitHub"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.92.58.1.79-.25.79-.56v-2.15c-3.2.7-3.87-1.36-3.87-1.36-.52-1.32-1.28-1.68-1.28-1.68-1.04-.71.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.76 2.7 1.25 3.36.96.1-.75.4-1.25.73-1.54-2.56-.29-5.25-1.28-5.25-5.7 0-1.26.45-2.29 1.19-3.1-.12-.29-.52-1.47.11-3.06 0 0 .97-.31 3.17 1.18A11.1 11.1 0 0 1 12 6.02c.98 0 1.96.13 2.88.38 2.2-1.49 3.16-1.18 3.16-1.18.63 1.59.23 2.77.11 3.06.74.81 1.19 1.84 1.19 3.1 0 4.43-2.7 5.4-5.27 5.69.42.36.79 1.06.79 2.14v3.15c0 .31.21.67.8.56A11.51 11.51 0 0 0 23.5 12C23.5 5.65 18.35.5 12 .5Z"/></svg></a>
            <a class="profile-link gitee" href="{{ gitee_url }}" target="_blank" rel="noopener noreferrer" aria-label="Gitee"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2a10 10 0 1 0 0 20h5.2A4.8 4.8 0 0 0 22 17.2V12A10 10 0 0 0 12 2Zm5.4 8.8c0 .35-.28.62-.62.62h-6.2c-.35 0-.63.29-.63.63v.8c0 .35.28.63.63.63h4.3c.35 0 .63.28.63.62v.8c0 .35-.28.63-.63.63h-4.3a2.63 2.63 0 0 1-2.63-2.63v-2.7a2.63 2.63 0 0 1 2.63-2.63h6.2c.34 0 .62.28.62.63v2.6Z"/></svg></a>
            <a class="profile-link bilibili" href="{{ bilibili_url }}" target="_blank" rel="noopener noreferrer" aria-label="Bilibili"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8.5 3.2a1 1 0 0 1 1.4.1L12 5.7l2.1-2.4a1 1 0 1 1 1.5 1.3L14.4 6h2.4A4.2 4.2 0 0 1 21 10.2v5.6a4.2 4.2 0 0 1-4.2 4.2H7.2A4.2 4.2 0 0 1 3 15.8v-5.6A4.2 4.2 0 0 1 7.2 6h2.4L8.4 4.6a1 1 0 0 1 .1-1.4ZM7.2 8A2.2 2.2 0 0 0 5 10.2v5.6A2.2 2.2 0 0 0 7.2 18h9.6a2.2 2.2 0 0 0 2.2-2.2v-5.6A2.2 2.2 0 0 0 16.8 8H7.2Zm1.5 3.2c.55 0 1 .45 1 1v1.4a1 1 0 1 1-2 0v-1.4c0-.55.45-1 1-1Zm6.6 0c.55 0 1 .45 1 1v1.4a1 1 0 1 1-2 0v-1.4c0-.55.45-1 1-1Z"/></svg></a>
        </nav>
    </main>
    <script>
        const inputBox = document.getElementById('input-box');
        const sendButton = document.getElementById('send-device-btn');
        const statusHint = document.getElementById('status-hint');
        let isSending = false;
        function setStatus(msg, type='') { statusHint.textContent = msg; statusHint.className = type ? 'hint '+type : 'hint'; }
        async function sendToDevice() {
            const text = inputBox.value.trim();
            if (!text || isSending) return;
            isSending = true; sendButton.disabled = true; setStatus('正在发送...');
            try {
                const r = await fetch('/send', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({text}) });
                const result = await r.json().catch(()=>({}));
                if (!r.ok) throw new Error(result.message || '发送失败');
                inputBox.value = ''; setStatus('已发送到电脑', 'success');
            } catch(e) { setStatus(e.message || '发送失败', 'error'); }
            finally { isSending = false; sendButton.disabled = false; inputBox.focus(); }
        }
        sendButton.addEventListener('click', sendToDevice);
        inputBox.addEventListener('keydown', function(e) { if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); sendToDevice(); } });
        window.addEventListener('load', ()=> setTimeout(()=>inputBox.focus(), 150));
    </script>
</body>
</html>
'''


# ==================== Flask Routes ====================

@app.route("/")
def index():
    response = app.make_response(
        render_template_string(HTML_TEMPLATE, app_name=APP_NAME, **PROFILE_LINKS, max_text_length=MAX_TEXT_LENGTH)
    )
    return no_cache(response)


@app.route("/background-image")
def background_image():
    image_path = find_image_file(BACKGROUND_IMAGE_NAMES)
    if not image_path:
        return "", 204
    return no_cache(send_file(image_path))


@app.route("/mascot-image")
def mascot_image():
    image_path = find_image_file(MASCOT_IMAGE_NAMES)
    if not image_path:
        return "", 204
    return no_cache(send_file(image_path))


@app.route("/send", methods=["POST"])
def send_text():
    if not request.is_json:
        return jsonify({"status": "error", "message": "请求必须是 JSON 格式"}), 400
    data = request.get_json(silent=True) or {}
    raw_text = data.get("text")
    if not isinstance(raw_text, str):
        return jsonify({"status": "error", "message": "缺少 text 字段"}), 400
    text = raw_text.strip()
    if not text:
        return jsonify({"status": "error", "message": "发送内容不能为空"}), 400
    if len(text) > MAX_TEXT_LENGTH:
        return jsonify({"status": "error", "message": f"发送内容不能超过 {MAX_TEXT_LENGTH} 字"}), 413
    try:
        paste_text(text)
    except Exception as exc:
        return jsonify({"status": "error", "message": f"粘贴失败：{exc}"}), 500
    return jsonify({"status": "success", "message": "已发送"})


# ==================== GUI Application ====================

class PawSyncMiaoApp:
    def __init__(self):
        self.local_ip = get_local_ip()
        self.access_url = f"http://{self.local_ip}:{APP_PORT}"
        self.tray_icon = None
        self.minimize_to_tray = True

        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} v{__version__}")
        self.root.resizable(False, False)
        self.root.configure(bg="#fff1f8")
        icon_path = app_icon_path()
        if icon_path:
            self.root.iconbitmap(str(icon_path))
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._start_flask()

    def _build_ui(self):
        frame = tk.Frame(self.root, bg="#fff1f8", padx=20, pady=15)
        frame.pack()

        title_label = tk.Label(frame, text=APP_NAME, font=("Segoe UI", 16, "bold"), bg="#fff1f8", fg="#3b2948")
        title_label.pack(pady=(0, 8))

        qr_img = generate_qr_image(self.access_url, size=200)
        self._qr_photo = ImageTk.PhotoImage(qr_img)
        qr_label = tk.Label(frame, image=self._qr_photo, bg="#fff1f8")
        qr_label.pack(pady=(0, 8))

        url_frame = tk.Frame(frame, bg="#fff1f8")
        url_frame.pack(pady=(0, 4))

        url_label = tk.Label(url_frame, text=self.access_url, font=("Consolas", 11), bg="#fff1f8", fg="#9b7cff")
        url_label.pack(side=tk.LEFT, padx=(0, 8))

        copy_button = tk.Button(
            url_frame,
            text="复制",
            command=self._copy_access_url,
            bg="#9b7cff",
            fg="white",
            activebackground="#8a6cff",
            activeforeground="white",
            relief=tk.FLAT,
            padx=10,
            pady=2,
            font=("Microsoft YaHei", 9),
        )
        copy_button.pack(side=tk.LEFT)

        hint_label = tk.Label(frame, text="手机扫码或输入地址访问\n手机和电脑需在同一局域网", font=("Microsoft YaHei", 9), bg="#fff1f8", fg="#8f769c")
        hint_label.pack(pady=(0, 10))

        links_frame = tk.Frame(frame, bg="#fff1f8")
        links_frame.pack(pady=(0, 10))
        for index, (label_key, url_key) in enumerate((
            ("github_label", "github_url"),
            ("gitee_label", "gitee_url"),
            ("bilibili_label", "bilibili_url"),
        )):
            link = tk.Label(
                links_frame,
                text=PROFILE_LINKS[label_key],
                font=("Microsoft YaHei", 9, "underline"),
                bg="#fff1f8",
                fg="#9b7cff",
                cursor="hand2",
            )
            link.pack(side=tk.LEFT, padx=(0 if index == 0 else 12, 0))
            link.bind("<Button-1>", lambda _event, url=PROFILE_LINKS[url_key]: webbrowser.open(url))

        self.tray_var = tk.BooleanVar(value=True)
        tray_check = tk.Checkbutton(
            frame, text="关闭时最小化到系统托盘", variable=self.tray_var,
            bg="#fff1f8", fg="#3b2948", activebackground="#fff1f8",
            font=("Microsoft YaHei", 9), command=self._on_tray_toggle
        )
        tray_check.pack(pady=(0, 5))

    def _copy_access_url(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.access_url)
        self.root.update()
        self._show_copy_notice()

    def _show_copy_notice(self):
        notice = tk.Toplevel(self.root)
        notice.title(APP_NAME)
        notice.resizable(False, False)
        notice.configure(bg="#fff1f8")
        notice.transient(self.root)
        notice.grab_set()
        icon_path = app_icon_path()
        if icon_path:
            notice.iconbitmap(str(icon_path))

        box = tk.Frame(notice, bg="#fff1f8", padx=26, pady=18)
        box.pack()
        tk.Label(box, text="局域网地址已复制", font=("Microsoft YaHei", 11), bg="#fff1f8", fg="#3b2948").pack(pady=(0, 12))
        tk.Button(
            box,
            text="知道了",
            command=notice.destroy,
            bg="#9b7cff",
            fg="white",
            activebackground="#8a6cff",
            activeforeground="white",
            relief=tk.FLAT,
            padx=18,
            pady=4,
            font=("Microsoft YaHei", 9),
        ).pack()
        notice.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - notice.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - notice.winfo_height()) // 2
        notice.geometry(f"+{x}+{y}")
        notice.after(1200, notice.destroy)

    def _show_port_error(self):
        error_dialog = tk.Toplevel(self.root)
        error_dialog.title(APP_NAME)
        error_dialog.resizable(False, False)
        error_dialog.configure(bg="#fff1f8")
        error_dialog.transient(self.root)
        error_dialog.grab_set()
        icon_path = app_icon_path()
        if icon_path:
            error_dialog.iconbitmap(str(icon_path))

        box = tk.Frame(error_dialog, bg="#fff1f8", padx=26, pady=18)
        box.pack()
        tk.Label(
            box,
            text=f"端口 {APP_PORT} 已被占用\n请关闭其他占用该端口的程序后重试",
            font=("Microsoft YaHei", 11),
            bg="#fff1f8",
            fg="#3b2948",
            justify=tk.CENTER
        ).pack(pady=(0, 12))
        tk.Button(
            box,
            text="退出程序",
            command=self._quit,
            bg="#9b7cff",
            fg="white",
            activebackground="#8a6cff",
            activeforeground="white",
            relief=tk.FLAT,
            padx=18,
            pady=4,
            font=("Microsoft YaHei", 9),
        ).pack()
        error_dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - error_dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - error_dialog.winfo_height()) // 2
        error_dialog.geometry(f"+{x}+{y}")

    def _on_tray_toggle(self):
        self.minimize_to_tray = self.tray_var.get()

    def _on_close(self):
        if self.minimize_to_tray:
            self.root.withdraw()
            self._create_tray()
        else:
            self._quit()

    def _create_tray(self):
        if self.tray_icon is not None:
            return
        icon_image = create_tray_icon_image()
        menu = pystray.Menu(
            pystray.MenuItem("显示窗口", self._show_window, default=True),
            pystray.MenuItem("退出", self._quit_from_tray),
        )
        self.tray_icon = pystray.Icon(APP_NAME, icon_image, APP_NAME, menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _show_window(self, icon=None, item=None):
        self.root.after(0, self.root.deiconify)

    def _quit_from_tray(self, icon=None, item=None):
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        self.root.after(0, self._quit)

    def _quit(self):
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        self.root.destroy()
        os._exit(0)

    def _start_flask(self):
        logging.getLogger("werkzeug").setLevel(logging.ERROR)
        
        def run_flask():
            try:
                app.run(host=APP_HOST, port=APP_PORT, debug=False, threaded=True, use_reloader=False)
            except OSError as e:
                if "address already in use" in str(e).lower() or e.errno == 10048:
                    self.root.after(0, self._show_port_error)
        
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()

    def run(self):
        self.root.mainloop()


def main() -> None:
    mutex = acquire_single_instance_mutex()
    if mutex is None:
        return
    gui_app = PawSyncMiaoApp()
    gui_app.run()


if __name__ == "__main__":
    main()