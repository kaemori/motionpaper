import tkinter as tk
import os
import subprocess
import sys
import threading
import json

from PIL import Image, ImageTk, ImageSequence
from rapidfuzz import fuzz
from motionpaper.config_store import load_config, load_themes, save_config
from motionpaper.constants import PROJECT_ROOT, VERSION
from motionpaper.constants import CONFIG_DIR
from motionpaper.daemon_control import (
    is_daemon_running,
    kill_daemon,
    launch_daemon,
    restart_daemon,
)
from motionpaper.gui_helpers import ease_out_quad, hex_to_rgb, round_rectangle
from motionpaper.wallpaper_library import load_wallpapers

VER = VERSION
THEMES = load_themes()


class WallpaperTile(tk.Canvas):
    def __init__(
        self,
        parent,
        wallpaper_data,
        on_click,
        theme,
        is_active=False,
        is_previewed=False,
    ):
        super().__init__(
            parent, bg=theme["main_bg"], highlightthickness=0, width=110, height=140
        )
        self.theme = theme
        self.wallpaper_data = wallpaper_data
        self.on_click = on_click
        self.gif_frames = []
        self.current_frame = 0
        self.animating = False
        self.anim_id = None
        self.static_image = None
        self.is_active = is_active
        self.is_previewed = is_previewed
        bg_color = self._get_bg_color()
        self.bg_rect = round_rectangle(
            self, 0, 0, 110, 140, radius=10, fill=bg_color, outline=""
        )
        self.load_thumbnail()
        if self.static_image:
            self.image_id = self.create_image(55, 60, image=self.static_image)
        else:
            self.image_id = self.create_image(55, 60)
        title_text = wallpaper_data["title"][:28] + (
            "..." if len(wallpaper_data["title"]) > 28 else ""
        )
        font_weight = "bold" if is_active else "normal"
        self.title_id = self.create_text(
            55,
            125,
            text=title_text,
            fill=self.theme["text_on_dark"],
            font=("Arial", 8, font_weight),
            width=100,
            justify="center",
        )
        self.bind("<Enter>", self.on_hover)
        self.bind("<Leave>", self.on_leave)
        self.bind("<Button-1>", self.on_tile_click)

    def _get_bg_color(self):
        if self.is_active:
            return self.theme["tile_active"]
        elif self.is_previewed:
            return self.theme["tile_preview"]
        else:
            return self.theme["tile_idle"]

    def set_active(self, active, previewed=False):
        self.is_active = active
        self.is_previewed = previewed
        bg_color = self._get_bg_color()
        font_weight = "bold" if active else "normal"
        self.itemconfig(self.bg_rect, fill=bg_color)
        self.itemconfig(self.title_id, font=("Arial", 8, font_weight))

    def load_thumbnail(self):
        try:
            img = Image.open(self.wallpaper_data["preview_path"])
            img.thumbnail((100, 100), Image.Resampling.LANCZOS)
            self.static_image = ImageTk.PhotoImage(img)
            if self.wallpaper_data["is_gif"]:
                threading.Thread(target=self.preload_gif, daemon=True).start()
        except Exception as e:
            print(f"error loading thumbnail: {e}")

    def preload_gif(self):
        try:
            img = Image.open(self.wallpaper_data["preview_path"])
            for frame in ImageSequence.Iterator(img):
                frame_copy = frame.copy()
                frame_copy.thumbnail((100, 100), Image.Resampling.LANCZOS)
                self.gif_frames.append(ImageTk.PhotoImage(frame_copy))
        except Exception as e:
            print(f"error preloading gif: {e}")

    def on_hover(self, event):
        if self.wallpaper_data["is_gif"] and self.gif_frames and not self.animating:
            self.animating = True
            self.animate_gif()

    def on_leave(self, event):
        self.animating = False
        if self.anim_id:
            try:
                self.after_cancel(self.anim_id)
            except:
                pass
            self.anim_id = None
        if self.static_image:
            self.itemconfig(self.image_id, image=self.static_image)

    def animate_gif(self):
        if not self.animating or not self.gif_frames:
            return
        self.itemconfig(self.image_id, image=self.gif_frames[self.current_frame])
        self.current_frame = (self.current_frame + 1) % len(self.gif_frames)
        self.anim_id = self.after(100, self.animate_gif)

    def on_tile_click(self, event):
        self.on_click(self.wallpaper_data["id"])


class CustomSwitch(tk.Canvas):
    def __init__(
        self,
        parent,
        variable,
        command=None,
        bg_color="#ffffff",
        active_color="#7a62bd",
        *args,
        **kwargs,
    ):
        super().__init__(
            parent,
            *args,
            width=44,
            height=24,
            bg=bg_color,
            highlightthickness=0,
            **kwargs,
        )
        self.variable = variable
        self.command = command
        self.bind("<Button-1>", self.toggle)
        self.bg_off = "#e0e0e0"
        self.bg_on = active_color
        self.thumb_color = "#ffffff"
        self.draw()

    def draw(self):
        self.delete("all")
        is_on = self.variable.get()
        bg = self.bg_on if is_on else self.bg_off
        self.create_oval(2, 2, 22, 22, fill=bg, outline="")
        self.create_oval(22, 2, 42, 22, fill=bg, outline="")
        self.create_rectangle(12, 2, 32, 22, fill=bg, outline="")
        if is_on:
            self.create_oval(24, 4, 40, 20, fill=self.thumb_color, outline="")
        else:
            self.create_oval(4, 4, 20, 20, fill=self.thumb_color, outline="")

    def toggle(self, event=None):
        self.variable.set(not self.variable.get())
        self.draw()
        if self.command:
            self.command()


class CustomSpinbox(tk.Frame):
    def __init__(
        self,
        parent,
        variable,
        from_,
        to,
        step=1,
        bg_color="#ffffff",
        input_bg="#f9f8fc",
        input_border="#e2dbe9",
        text_color="#32274f",
        accent_color="#7a62bd",
        disabled=False,
        *args,
        **kwargs,
    ):
        super().__init__(parent, *args, bg=bg_color, **kwargs)
        self.variable = variable
        self.from_ = from_
        self.to = to
        self.step = step
        self.disabled = disabled
        self.input_bg = input_bg
        self.input_border = input_border
        self.text_color = text_color
        self.accent_color = accent_color
        self.editing = False
        self.canvas = tk.Canvas(
            self, width=90, height=26, bg=bg_color, highlightthickness=0
        )
        self.canvas.pack()
        self.entry = tk.Entry(
            self,
            bg=self.input_bg,
            fg=self.text_color,
            insertbackground=self.text_color,
            relief="flat",
            bd=0,
            font=("Helvetica", 11, "bold"),
            highlightthickness=0,
            justify="center",
        )
        self.entry_window = None
        self.draw()
        self.variable.trace_add("write", self.update_display)

    def draw(self):
        self.canvas.delete("all")
        color = self.input_bg if not self.disabled else "#f3f4f6"
        outline = self.input_border if not self.disabled else "#e5e7eb"
        text_col = self.text_color if not self.disabled else "#9ca3af"
        btn_col = self.accent_color if not self.disabled else "#9ca3af"
        round_rectangle(
            self.canvas, 2, 2, 88, 24, radius=10, fill=color, outline=outline, width=1
        )
        self.canvas.create_text(
            15, 13, text="−", fill=btn_col, font=("Helvetica", 16, "bold"), tags="minus"
        )
        self.val_text = self.canvas.create_text(
            45,
            13,
            text=str(self.variable.get()),
            fill=text_col,
            font=("Helvetica", 11, "bold"),
            tags="value",
        )
        self.canvas.create_text(
            75, 13, text="+", fill=btn_col, font=("Helvetica", 14, "bold"), tags="plus"
        )
        if not self.disabled:
            self.canvas.tag_bind("minus", "<Button-1>", self.decrement)
            self.canvas.tag_bind("plus", "<Button-1>", self.increment)
            self.canvas.tag_bind("value", "<Button-1>", self.start_edit)

    def start_edit(self, event=None):
        if self.disabled or self.editing:
            return
        self.editing = True
        self.canvas.itemconfig(self.val_text, state="hidden")
        if self.entry_window is None:
            self.entry_window = self.canvas.create_window(
                45, 13, window=self.entry, width=40
            )
        else:
            self.canvas.itemconfig(self.entry_window, state="normal")
        self.entry.delete(0, tk.END)
        self.entry.insert(0, str(self.variable.get()))
        self.entry.focus_set()
        self.entry.select_range(0, tk.END)
        self.entry.bind("<Return>", self.finish_edit)
        self.entry.bind("<Escape>", self.cancel_edit)
        self.entry.bind("<FocusOut>", self.finish_edit)

    def finish_edit(self, event=None):
        if not self.editing:
            return
        try:
            val = int(self.entry.get())
            val = max(self.from_, min(self.to, val))
            self.variable.set(val)
        except ValueError:
            pass
        self.end_edit()

    def cancel_edit(self, event=None):
        self.end_edit()

    def end_edit(self):
        if not self.editing:
            return
        self.editing = False
        if self.entry_window is not None:
            self.canvas.itemconfig(self.entry_window, state="hidden")
        self.canvas.itemconfig(self.val_text, state="normal")
        self.entry.unbind("<Return>")
        self.entry.unbind("<Escape>")
        self.entry.unbind("<FocusOut>")

    def config_state(self, state):
        self.disabled = state == "disabled"
        if self.disabled and self.editing:
            self.end_edit()
        self.draw()

    def decrement(self, event=None):
        if self.disabled:
            return
        val = self.variable.get()
        if val > self.from_:
            self.variable.set(val - self.step)

    def increment(self, event=None):
        if self.disabled:
            return
        val = self.variable.get()
        if val < self.to:
            self.variable.set(val + self.step)

    def update_display(self, *args):
        try:
            self.canvas.itemconfig(self.val_text, text=str(self.variable.get()))
        except:
            pass


class CustomCombobox(tk.Frame):
    def __init__(
        self,
        parent,
        variable,
        values,
        bg_color="#ffffff",
        input_bg="#f9f8fc",
        input_border="#e2dbe9",
        text_color="#32274f",
        accent_color="#7a62bd",
        *args,
        **kwargs,
    ):
        super().__init__(parent, *args, bg=bg_color, **kwargs)
        self.variable = variable
        self.values = values
        self.input_bg = input_bg
        self.input_border = input_border
        self.text_color = text_color
        self.accent_color = accent_color
        self.canvas = tk.Canvas(
            self, width=146, height=26, bg=bg_color, highlightthickness=0
        )
        self.canvas.pack()
        round_rectangle(
            self.canvas,
            2,
            2,
            85,
            24,
            radius=10,
            fill=self.input_bg,
            outline=self.input_border,
            width=1,
        )
        self.val_text = self.canvas.create_text(
            15,
            13,
            text=self.variable.get(),
            fill=self.text_color,
            font=("Helvetica", 10),
            anchor="w",
        )
        self.canvas.create_text(
            75, 13, text="▼", fill=self.accent_color, font=("Arial", 8)
        )
        self.canvas.bind("<Button-1>", self.open_menu)
        self.menu_window = None

    def open_menu(self, event):
        if self.menu_window:
            try:
                self.menu_window.destroy()
            except:
                pass
        menu = tk.Menu(
            self,
            tearoff=0,
            bg=self.input_bg,
            fg=self.text_color,
            activebackground=self.input_border,
            activeforeground=self.text_color,
            relief="flat",
            bd=1,
        )
        self.menu_window = menu
        for val in self.values:
            menu.add_command(label=val, command=lambda v=val: self.set_val(v))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def set_val(self, val):
        self.variable.set(val)
        self.canvas.itemconfig(self.val_text, text=val)


class SettingsScreen(tk.Frame):
    def __init__(
        self,
        parent,
        config,
        on_save,
        theme,
        theme_names,
        on_theme_change=None,
    ):
        self.theme = theme
        self.theme_names = theme_names
        self.on_theme_change = on_theme_change
        bg_main = self.theme["settings_main"]
        bg_side = self.theme["settings_side"]
        super().__init__(parent, bg=bg_main)
        self.config = config.copy()
        self.on_save = on_save
        main_container = tk.Frame(self, bg=bg_main)
        main_container.pack(fill="both", expand=True)
        sidebar = tk.Frame(main_container, bg=bg_side, width=180)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        title = tk.Label(
            sidebar,
            text="Settings",
            bg=bg_side,
            fg=self.theme["text_primary"],
            font=("Helvetica", 16, "bold"),
        )
        title.pack(pady=25)
        self.content_area = tk.Frame(main_container, bg=bg_main)
        self.content_area.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        self._create_variables()
        self.nav_buttons = []
        self.create_nav_btn(sidebar, "Display", self.show_display)
        self.create_nav_btn(sidebar, "Performance", self.show_perf)
        self.create_nav_btn(sidebar, "Audio", self.show_audio)
        self.create_nav_btn(sidebar, "Effects", self.show_effects)
        self.create_nav_btn(sidebar, "Theme", self.show_theme)
        save_btn_frame = tk.Frame(sidebar, bg=bg_side)
        save_btn_frame.pack(side="bottom", pady=25, padx=20, fill="x")
        self.save_button_canvas = tk.Canvas(
            save_btn_frame,
            height=40,
            bg=bg_side,
            highlightthickness=0,
            cursor="hand2",
        )
        self.save_button_canvas.pack(fill="x")

        def draw_save_btn(color=None):
            color = color or self.theme["accent"]
            self.save_button_canvas.delete("all")
            w = (
                self.save_button_canvas.winfo_width()
                if self.save_button_canvas.winfo_width() > 1
                else 140
            )
            round_rectangle(
                self.save_button_canvas, 0, 0, w, 40, radius=20, fill=color, outline=""
            )
            self.save_button_canvas.create_text(
                w / 2,
                20,
                text="Save Changes ✨",
                fill=self.theme["text_on_dark"],
                font=("Helvetica", 11, "bold"),
            )

        self.save_button_canvas.bind("<Configure>", lambda e: draw_save_btn())
        self.save_button_canvas.bind(
            "<Enter>", lambda e: draw_save_btn(self.theme["accent_hover"])
        )
        self.save_button_canvas.bind(
            "<Leave>", lambda e: draw_save_btn(self.theme["accent"])
        )
        self.save_button_canvas.bind(
            "<ButtonPress-1>", lambda e: draw_save_btn(self.theme["accent_press"])
        )
        self.save_button_canvas.bind(
            "<ButtonRelease-1>",
            lambda e: (draw_save_btn(self.theme["accent_hover"]), self.save_settings()),
        )
        draw_save_btn()
        self.nav_buttons[0].set_active(True)
        self.show_display()

    def _create_variables(self):
        self.scaling_var = tk.StringVar(value=self.config.get("scaling", "fit"))
        self.fps_var = tk.IntVar(value=self.config.get("fps", 60))
        self.fullscreen_pause_var = tk.BooleanVar(
            value=self.config.get("fullscreen_pause", True)
        )
        self.mute_var = tk.BooleanVar(value=self.config.get("mute", False))
        self.volume_var = tk.IntVar(value=self.config.get("volume", 100))
        self.automute_var = tk.BooleanVar(value=self.config.get("automute", False))
        self.audio_processing_var = tk.BooleanVar(
            value=self.config.get("audio_processing", True)
        )
        self.particles_var = tk.BooleanVar(value=self.config.get("particles", True))
        self.track_mouse_var = tk.BooleanVar(value=self.config.get("track_mouse", True))
        self.parallax_var = tk.BooleanVar(value=self.config.get("parallax", True))
        self.theme_var = tk.StringVar(value=self.config.get("theme", "purple"))
        self.theme_var.trace_add("write", self._on_theme_var_changed)

    def _on_theme_var_changed(self, *_):
        new_theme = self.theme_var.get()
        self.config["theme"] = new_theme
        if self.on_theme_change:
            self.on_theme_change(new_theme)

    def create_nav_btn(self, parent, text, command):
        bg_side = self.theme["settings_side"]
        bg_active = self.theme["entry_border"]
        bg_hover = self.theme["entry_bg"]
        fg_col = self.theme["text_primary"]
        btn_canvas = tk.Canvas(parent, bg=bg_side, height=36, highlightthickness=0)
        btn_canvas.pack(fill="x", pady=2, padx=10)

        def draw_bg(color):
            btn_canvas.delete("bg")
            w = btn_canvas.winfo_width() if btn_canvas.winfo_width() > 1 else 160
            h = btn_canvas.winfo_height() if btn_canvas.winfo_height() > 1 else 36
            round_rectangle(
                btn_canvas, 0, 0, w, h, radius=10, fill=color, outline="", tags="bg"
            )
            btn_canvas.tag_lower("bg")

        btn_canvas.current_bg = bg_side
        btn_canvas.is_active = False
        text_id = btn_canvas.create_text(
            20, 18, text=text, fill=fg_col, font=("Helvetica", 11), anchor="w"
        )
        btn_canvas.bind("<Configure>", lambda e: draw_bg(btn_canvas.current_bg))

        def set_active(active):
            btn_canvas.is_active = active
            btn_canvas.current_bg = bg_active if active else bg_side
            font_weight = "bold" if active else "normal"
            btn_canvas.itemconfig(text_id, font=("Helvetica", 11, font_weight))
            draw_bg(btn_canvas.current_bg)

        def on_enter(e):
            if not btn_canvas.is_active:
                btn_canvas.current_bg = bg_hover
                draw_bg(btn_canvas.current_bg)

        def on_leave(e):
            if not btn_canvas.is_active:
                btn_canvas.current_bg = bg_side
                draw_bg(btn_canvas.current_bg)

        def cmd(e=None):
            for b in self.nav_buttons:
                b.set_active(False)
            set_active(True)
            command()

        btn_canvas.bind("<Enter>", on_enter)
        btn_canvas.bind("<Leave>", on_leave)
        btn_canvas.bind("<Button-1>", cmd)
        btn_canvas.tag_bind(text_id, "<Button-1>", cmd)
        btn_canvas.set_active = set_active
        self.nav_buttons.append(btn_canvas)
        return btn_canvas

    def clear_content(self):
        for widget in self.content_area.winfo_children():
            widget.destroy()

    def show_display(self):
        self.clear_content()
        self.add_header("Display")
        card = self.create_card("Scaling Mode", "How the wallpaper fits")
        dropdown = CustomCombobox(
            card,
            self.scaling_var,
            ["stretch", "fit", "fill", "default"],
            bg_color=self.theme["settings_card"],
            input_bg=self.theme["entry_bg"],
            input_border=self.theme["entry_border"],
            text_color=self.theme["text_primary"],
            accent_color=self.theme["accent"],
        )
        dropdown.pack(side="right", padx=15)

    def show_perf(self):
        self.clear_content()
        self.add_header("Performance")
        card1 = self.create_card("Framerate", "Target FPS")
        spinbox = CustomSpinbox(
            card1,
            self.fps_var,
            1,
            144,
            bg_color=self.theme["settings_card"],
            input_bg=self.theme["entry_bg"],
            input_border=self.theme["entry_border"],
            text_color=self.theme["text_primary"],
            accent_color=self.theme["accent"],
        )
        spinbox.pack(side="right", padx=15)
        card2 = self.create_card("Pause when fullscreen", "Save resources")
        cb1 = CustomSwitch(
            card2,
            self.fullscreen_pause_var,
            bg_color=self.theme["settings_card"],
            active_color=self.theme["accent"],
        )
        cb1.pack(side="right", padx=15)

    def show_audio(self):
        self.clear_content()
        self.add_header("Audio")
        card1 = self.create_card("Mute Wallpaper", "Silence audio")
        mute_cb = CustomSwitch(
            card1,
            self.mute_var,
            command=self.on_mute_toggle,
            bg_color=self.theme["settings_card"],
            active_color=self.theme["accent"],
        )
        mute_cb.pack(side="right", padx=15)
        card2 = self.create_card("Volume", "0-100")
        self.volume_widget = CustomSpinbox(
            card2,
            self.volume_var,
            0,
            100,
            step=5,
            bg_color=self.theme["settings_card"],
            input_bg=self.theme["entry_bg"],
            input_border=self.theme["entry_border"],
            text_color=self.theme["text_primary"],
            accent_color=self.theme["accent"],
        )
        self.volume_widget.pack(side="right", padx=15)
        card3 = self.create_card("Auto-mute", "Mute when other audio plays")
        cb2 = CustomSwitch(
            card3,
            self.automute_var,
            bg_color=self.theme["settings_card"],
            active_color=self.theme["accent"],
        )
        cb2.pack(side="right", padx=15)
        card4 = self.create_card("Audio Processing", "Reactivity etc")
        cb3 = CustomSwitch(
            card4,
            self.audio_processing_var,
            bg_color=self.theme["settings_card"],
            active_color=self.theme["accent"],
        )
        cb3.pack(side="right", padx=15)
        self.on_mute_toggle()

    def show_effects(self):
        self.clear_content()
        self.add_header("Effects")
        card1 = self.create_card("Particles", "Enable particles")
        cb1 = CustomSwitch(
            card1,
            self.particles_var,
            bg_color=self.theme["settings_card"],
            active_color=self.theme["accent"],
        )
        cb1.pack(side="right", padx=15)
        card2 = self.create_card("Mouse Tracking", "Cursor movement")
        cb2 = CustomSwitch(
            card2,
            self.track_mouse_var,
            bg_color=self.theme["settings_card"],
            active_color=self.theme["accent"],
        )
        cb2.pack(side="right", padx=15)
        card3 = self.create_card("Parallax Effect", "Depth-based movement")
        cb3 = CustomSwitch(
            card3,
            self.parallax_var,
            bg_color=self.theme["settings_card"],
            active_color=self.theme["accent"],
        )
        cb3.pack(side="right", padx=15)

    def show_theme(self):
        self.clear_content()
        self.add_header("Theme")
        card = self.create_card("Color Scheme", "Choose the GUI palette")
        dropdown = CustomCombobox(
            card,
            self.theme_var,
            self.theme_names,
            bg_color=self.theme["settings_card"],
            input_bg=self.theme["entry_bg"],
            input_border=self.theme["entry_border"],
            text_color=self.theme["text_primary"],
            accent_color=self.theme["accent"],
        )
        dropdown.pack(side="right", padx=15)

    def add_header(self, text):
        lbl = tk.Label(
            self.content_area,
            text=text,
            bg=self.theme["settings_main"],
            fg=self.theme["text_primary"],
            font=("Helvetica", 15, "bold"),
        )
        lbl.pack(anchor="nw", padx=15, pady=(20, 15))

    def create_card(self, title, desc):
        card_bg = self.theme["settings_card"]
        card = tk.Frame(self.content_area, bg=self.theme["settings_main"])
        card.pack(fill="x", padx=15, pady=8)
        bg_canvas = tk.Canvas(
            card, bg=self.theme["settings_main"], highlightthickness=0
        )
        bg_canvas.place(relx=0, rely=0, relwidth=1.0, relheight=1.0)

        def on_resize(event):
            bg_canvas.delete("bg")
            if event.width > 2 and event.height > 2:
                round_rectangle(
                    bg_canvas,
                    1,
                    1,
                    event.width - 2,
                    event.height - 2,
                    radius=10,
                    fill=card_bg,
                    outline="",
                    tags="bg",
                )

        card.bind("<Configure>", on_resize)
        info = tk.Frame(card, bg=card_bg)
        info.pack(side="left", padx=15, pady=12)
        tk.Label(
            info,
            text=title,
            bg=card_bg,
            fg=self.theme["text_primary"],
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w")
        if desc:
            tk.Label(
                info,
                text=desc,
                bg=card_bg,
                fg=self.theme["accent"],
                font=("Helvetica", 9),
            ).pack(anchor="w", pady=(2, 0))
        return card

    def on_mute_toggle(self):
        if hasattr(self, "volume_widget"):
            if self.mute_var.get():
                self.volume_widget.config_state("disabled")
            else:
                self.volume_widget.config_state("normal")

    def save_settings(self):
        self.config["scaling"] = self.scaling_var.get()
        self.config["fps"] = self.fps_var.get()
        self.config["fullscreen_pause"] = self.fullscreen_pause_var.get()
        self.config["mute"] = self.mute_var.get()
        self.config["volume"] = self.volume_var.get()
        self.config["automute"] = self.automute_var.get()
        self.config["audio_processing"] = self.audio_processing_var.get()
        self.config["particles"] = self.particles_var.get()
        self.config["track_mouse"] = self.track_mouse_var.get()
        self.config["parallax"] = self.parallax_var.get()
        self.on_save(self.config)


class App(tk.Tk):
    def __init__(self):
        width, height = 900, 600
        super().__init__()
        self.title("motionpaper")
        self.geometry(f"{width}x{height}")
        self.config = load_config()
        self.config.setdefault("show_mature", True)
        self.theme_name = self.config.get("theme", "purple")
        if self.theme_name not in THEMES:
            self.theme_name = "purple"
        self.theme = THEMES[self.theme_name]
        self.all_wallpapers = []
        self.filtered_wallpapers = []
        self.search_debounce_id = None
        self.tile_cache = {}
        self.current_screen = "wallpapers"
        self.search_expanded = False
        self.button_states = {}
        self.active_toasts = []
        self.toast_fade_jobs = {}
        self._last_toast_ts = 0
        self.previewed_wpid = None
        self.applied_wpid = self.config.get("wpid")
        self.refreshing_wallpapers = False
        self.show_mature_var = tk.BooleanVar(value=self.config.get("show_mature", True))
        self.sidebar_gif_frames = []
        self.sidebar_current_frame = 0
        self.sidebar_animating = False
        self.sidebar_anim_id = None
        self.configure(bg=self.theme["main_bg"])
        self._create_top_bar()
        self._create_main_content()
        self._create_side_panel()
        self.wallpaper_screen = self.create_wallpaper_screen()
        self.settings_screen = None
        self.show_screen("wallpapers")
        self.loading_label = tk.Label(
            self.scrollable_frame,
            text="loading wallpapers...",
            bg=self.theme["main_bg"],
            fg=self.theme["text_on_dark"],
            font=("Arial", 12),
        )
        self.loading_label.pack(pady=50)
        threading.Thread(target=self.load_wallpapers_async, daemon=True).start()
        # start polling for daemon-to-gui toasts (written to CONFIG_DIR/toast.json)
        self.after(1000, self._poll_daemon_toasts)

    def _poll_daemon_toasts(self):
        try:
            toast_file = CONFIG_DIR / "toast.json"
            if toast_file.exists():
                try:
                    with open(toast_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    ts = float(data.get("ts") or 0)
                    shown = bool(data.get("shown"))
                    # if already shown, just update last ts and skip
                    if shown:
                        if ts and ts > (self._last_toast_ts or 0):
                            self._last_toast_ts = ts
                    else:
                        # only show if newer than last
                        if ts and ts > (self._last_toast_ts or 0):
                            msg = data.get("message") or data.get("title") or ""
                            if msg:
                                try:
                                    self.show_toast(msg)
                                    self._last_toast_ts = ts
                                except Exception:
                                    pass
                            # mark as shown so GUI restarts won't re-show
                            try:
                                data["shown"] = True
                                tmp = toast_file.with_suffix(".tmp")
                                with open(tmp, "w", encoding="utf-8") as tf:
                                    json.dump(data, tf)
                                try:
                                    tmp.replace(toast_file)
                                except Exception:
                                    os.replace(str(tmp), str(toast_file))
                            except Exception:
                                pass
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            # poll again
            try:
                self.after(1000, self._poll_daemon_toasts)
            except Exception:
                pass

    def _create_top_bar(self):
        width = 900
        self.top_canvas = tk.Canvas(
            self,
            width=width,
            bg=self.theme["main_bg"],
            height=36,
            highlightthickness=0,
            bd=0,
        )
        self.top_canvas.pack(fill="x")
        self.top_bar_bg_id = self.top_canvas.create_rectangle(
            -1, 0, width, 36, fill=self.theme["top_bar"], outline=""
        )
        self.top_bar_title_id = self.top_canvas.create_text(
            15,
            18,
            text=f"MotionPaper v{VER}",
            fill=self.theme["text_on_dark"],
            anchor="w",
            font=("Arial", 11, "bold"),
        )
        self._create_search_bar()
        self._create_left_refresh_button()
        self.create_control_buttons()

    def _create_left_refresh_button(self):
        refresh_x = self.search_x1 - 25
        self._create_button(
            "refresh",
            refresh_x,
            "↻",
            13,
            self.refresh_wallpapers_click,
            shape="circle",
        )

    def _create_search_bar(self):
        self.search_x1 = 210
        self.search_collapsed_x2 = 310
        self.search_expanded_x2 = 430
        self.search_y1 = 6
        self.search_y2 = 30
        self.search_background = round_rectangle(
            self.top_canvas,
            self.search_x1,
            self.search_y1,
            self.search_collapsed_x2,
            self.search_y2,
            radius=22,
            fill=self.theme["surface"],
            outline="",
        )
        self.search_placeholder = self.top_canvas.create_text(
            (self.search_x1 + self.search_collapsed_x2) / 2,
            18,
            text="   search...",
            fill=self.theme["search_placeholder"],
            font=("Arial", 10),
        )
        self.search_entry = tk.Entry(
            self.top_canvas,
            bg=self.theme["surface"],
            fg=self.theme["text_on_dark"],
            insertbackground=self.theme["text_on_dark"],
            relief="flat",
            bd=0,
            font=("Arial", 10),
            highlightthickness=0,
        )
        self.search_entry_window = None
        self.top_canvas.tag_bind(self.search_background, "<Button-1>", self.open_search)
        self.top_canvas.tag_bind(
            self.search_placeholder, "<Button-1>", self.open_search
        )

    def _create_main_content(self):
        self.main_container = tk.Frame(self, bg=self.theme["main_bg"])
        self.main_container.pack(fill="both", expand=True)
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(1, weight=0)
        self.screen_container = tk.Frame(self.main_container, bg=self.theme["main_bg"])
        self.screen_container.grid(row=0, column=0, sticky="nsew")

    def _create_side_panel(self):
        self.side_panel = tk.Frame(
            self.main_container, bg=self.theme["panel_bg"], width=260
        )
        self.side_panel.grid(row=0, column=1, sticky="ns")
        self.side_panel.grid_propagate(False)
        self.side_panel.pack_propagate(False)
        self.side_preview_label = tk.Label(self.side_panel, bg=self.theme["panel_bg"])
        self.side_preview_label.pack(pady=(20, 10))
        self.side_name_label = tk.Label(
            self.side_panel,
            text="No Wallpaper",
            bg=self.theme["panel_bg"],
            fg=self.theme["text_on_dark"],
            font=("Arial", 12, "bold"),
            wraplength=240,
            justify="center",
        )
        self.side_name_label.pack(pady=(0, 5))
        self.side_rating_label = tk.Label(
            self.side_panel,
            text="",
            bg=self.theme["panel_bg"],
            fg=self.theme["text_muted"],
            font=("Arial", 9),
        )
        self.side_rating_label.pack(pady=2)
        self.side_tags_label = tk.Label(
            self.side_panel,
            text="",
            bg=self.theme["panel_bg"],
            fg=self.theme["text_secondary"],
            font=("Arial", 9),
            wraplength=240,
        )
        self.side_tags_label.pack(pady=2)
        self.side_file_label = tk.Label(
            self.side_panel,
            text="",
            bg=self.theme["panel_bg"],
            fg=self.theme["text_secondary"],
            font=("Arial", 8),
            wraplength=240,
        )
        self.side_file_label.pack(pady=(10, 4))
        self.side_workshop_label = tk.Label(
            self.side_panel,
            text="",
            bg=self.theme["panel_bg"],
            fg=self.theme["text_secondary"],
            font=("Arial", 8),
            wraplength=240,
            justify="center",
            cursor="hand2",
        )
        self.side_workshop_label.pack(pady=(2, 2))
        self.side_workshop_label.bind("<Button-1>", self.copy_workshop_url)
        self.side_type_label = tk.Label(
            self.side_panel,
            text="",
            bg=self.theme["panel_bg"],
            fg=self.theme["text_secondary"],
            font=("Arial", 8),
            wraplength=240,
        )
        self.side_type_label.pack(pady=2)
        self.side_version_label = tk.Label(
            self.side_panel,
            text="",
            bg=self.theme["panel_bg"],
            fg=self.theme["text_secondary"],
            font=("Arial", 8),
            wraplength=240,
        )
        self.side_version_label.pack(pady=2)
        self._create_apply_button()

    def copy_workshop_url(self, event=None):
        if not hasattr(self, "current_workshop_url") or not self.current_workshop_url:
            self.show_toast("no workshop url to copy")
            return
        self.clipboard_clear()
        self.clipboard_append(self.current_workshop_url)
        self.update_idletasks()
        self.show_toast("workshop url copied ✨")

    def _create_apply_button(self):
        if hasattr(self, "apply_btn_frame") and self.apply_btn_frame.winfo_exists():
            self.apply_btn_frame.destroy()
        apply_btn_frame = tk.Frame(self.side_panel, bg=self.theme["panel_bg"])
        self.apply_btn_frame = apply_btn_frame
        apply_btn_frame.pack(side="bottom", pady=20, padx=20, fill="x")

        self.static_button_canvas = tk.Canvas(
            apply_btn_frame,
            height=36,
            bg=self.theme["panel_bg"],
            highlightthickness=0,
            cursor="hand2",
        )
        self.static_button_canvas.pack(fill="x", pady=(0, 8))

        def draw_static_btn(color=None):
            color = color or self.theme["surface"]
            self.static_button_canvas.delete("all")
            w = (
                self.static_button_canvas.winfo_width()
                if self.static_button_canvas.winfo_width() > 1
                else 220
            )
            round_rectangle(
                self.static_button_canvas,
                0,
                0,
                w,
                36,
                radius=15,
                fill=color,
                outline="",
            )
            self.static_button_canvas.create_text(
                w / 2,
                18,
                text="Set as Static Wallpaper",
                fill=self.theme["text_on_dark"],
                font=("Helvetica", 10, "bold"),
            )

        self.static_button_canvas.bind("<Configure>", lambda e: draw_static_btn())
        self.static_button_canvas.bind(
            "<Enter>", lambda e: draw_static_btn(self.theme["surface_hover"])
        )
        self.static_button_canvas.bind(
            "<Leave>", lambda e: draw_static_btn(self.theme["surface"])
        )
        self.static_button_canvas.bind(
            "<ButtonPress-1>", lambda e: draw_static_btn(self.theme["surface_press"])
        )
        self.static_button_canvas.bind(
            "<ButtonRelease-1>",
            lambda e: (
                draw_static_btn(self.theme["surface_hover"]),
                self.set_static_wallpaper(),
            ),
        )
        draw_static_btn()

        self.apply_button_canvas = tk.Canvas(
            apply_btn_frame,
            height=36,
            bg=self.theme["panel_bg"],
            highlightthickness=0,
            cursor="hand2",
        )
        self.apply_button_canvas.pack(fill="x")

        def draw_apply_btn(color=None):
            color = color or self.theme["accent"]
            self.apply_button_canvas.delete("all")
            w = (
                self.apply_button_canvas.winfo_width()
                if self.apply_button_canvas.winfo_width() > 1
                else 220
            )
            round_rectangle(
                self.apply_button_canvas, 0, 0, w, 36, radius=15, fill=color, outline=""
            )
            self.apply_button_canvas.create_text(
                w / 2,
                18,
                text="Apply ✨",
                fill=self.theme["text_on_dark"],
                font=("Helvetica", 11, "bold"),
            )

        self.apply_button_canvas.bind("<Configure>", lambda e: draw_apply_btn())
        self.apply_button_canvas.bind(
            "<Enter>", lambda e: draw_apply_btn(self.theme["accent_hover"])
        )
        self.apply_button_canvas.bind(
            "<Leave>", lambda e: draw_apply_btn(self.theme["accent"])
        )
        self.apply_button_canvas.bind(
            "<ButtonPress-1>", lambda e: draw_apply_btn(self.theme["accent_press"])
        )
        self.apply_button_canvas.bind(
            "<ButtonRelease-1>",
            lambda e: (
                draw_apply_btn(self.theme["accent_hover"]),
                self.apply_wallpaper(),
            ),
        )
        draw_apply_btn()

    def show_toast(self, message, duration=2000):
        MAX_TOASTS = 5
        if len(self.active_toasts) >= MAX_TOASTS:
            oldest = self.active_toasts[0]
            toast_id = id(oldest)
            if toast_id in self.toast_fade_jobs:
                try:
                    self.after_cancel(self.toast_fade_jobs[toast_id])
                except:
                    pass
                del self.toast_fade_jobs[toast_id]
            self.active_toasts.pop(0)
            try:
                oldest.destroy()
            except:
                pass
        toast_canvas = tk.Canvas(
            self, bg=self.theme["top_bar"], highlightthickness=0, bd=0
        )
        temp_label = tk.Label(toast_canvas, text=message, font=("Arial", 10, "bold"))
        temp_label.update_idletasks()
        text_width = temp_label.winfo_reqwidth()
        text_height = temp_label.winfo_reqheight()
        temp_label.destroy()
        canvas_width = text_width + 40
        canvas_height = text_height + 20
        round_rectangle(
            toast_canvas,
            0,
            0,
            canvas_width,
            canvas_height,
            radius=15,
            fill=self.theme["top_bar"],
            outline="",
        )
        toast_canvas.create_text(
            canvas_width / 2,
            canvas_height / 2,
            text=message,
            fill=self.theme["text_on_dark"],
            font=("Arial", 10, "bold"),
        )
        toast_canvas.config(width=canvas_width, height=canvas_height)
        self.active_toasts.append(toast_canvas)
        self.reposition_toasts()
        start_y = -canvas_height
        toast_canvas.place(relx=0.5, y=start_y, anchor="n")
        target_y = 30 + (len(self.active_toasts) - 1) * (canvas_height + 10)

        def slide_down(progress=0):
            steps = 15
            if progress <= steps:
                if toast_canvas not in self.active_toasts:
                    return
                t = progress / steps
                eased = ease_out_quad(t)
                current_y = start_y + (target_y - start_y) * eased
                try:
                    toast_canvas.place(relx=0.5, y=current_y, anchor="n")
                except:
                    return
                self.after(16, lambda: slide_down(progress + 1))
            else:
                fade_job = self.after(duration, lambda: self.fade_toast(toast_canvas))
                self.toast_fade_jobs[id(toast_canvas)] = fade_job

        slide_down()

    def reposition_toasts(self):
        for i, toast in enumerate(self.active_toasts):
            try:
                if not toast.winfo_exists():
                    continue
            except:
                continue
            canvas_height = (
                toast.winfo_reqheight() if toast.winfo_reqheight() > 1 else 40
            )
            target_y = 30 + i * (canvas_height + 10)

            def animate_move(toast_widget, target, progress=0):
                steps = 10
                if progress <= steps:
                    if toast_widget not in self.active_toasts:
                        return
                    try:
                        if not toast_widget.winfo_exists():
                            return
                        current_info = toast_widget.place_info()
                    except:
                        return
                    if current_info:
                        try:
                            current_y = float(current_info["y"])
                            t = progress / steps
                            eased = ease_out_quad(t)
                            new_y = current_y + (target - current_y) * eased
                            toast_widget.place(relx=0.5, y=new_y, anchor="n")
                            self.after(
                                16,
                                lambda: animate_move(
                                    toast_widget, target, progress + 1
                                ),
                            )
                        except:
                            pass

            try:
                if toast.place_info():
                    animate_move(toast, target_y)
            except:
                pass

    def fade_toast(self, toast_canvas):
        if toast_canvas not in self.active_toasts:
            return
        try:
            if not toast_canvas.winfo_exists():
                self.active_toasts.remove(toast_canvas)
                toast_id = id(toast_canvas)
                if toast_id in self.toast_fade_jobs:
                    del self.toast_fade_jobs[toast_id]
                return
        except:
            self.active_toasts.remove(toast_canvas)
            return
        self.active_toasts.remove(toast_canvas)
        toast_id = id(toast_canvas)
        if toast_id in self.toast_fade_jobs:
            del self.toast_fade_jobs[toast_id]
        try:
            all_items = toast_canvas.find_all()
        except:
            try:
                toast_canvas.destroy()
            except:
                pass
            self.reposition_toasts()
            return
        start_color = hex_to_rgb(self.theme["top_bar"])
        end_color = hex_to_rgb(self.theme["main_bg"])

        def fade_out(progress=0):
            steps = 15
            if progress <= steps:
                try:
                    if not toast_canvas.winfo_exists():
                        self.reposition_toasts()
                        return
                except:
                    self.reposition_toasts()
                    return
                t = progress / steps
                for item in all_items:
                    try:
                        item_type = toast_canvas.type(item)
                        if item_type == "polygon":
                            r = int(
                                start_color[0] + (end_color[0] - start_color[0]) * t
                            )
                            g = int(
                                start_color[1] + (end_color[1] - start_color[1]) * t
                            )
                            b = int(
                                start_color[2] + (end_color[2] - start_color[2]) * t
                            )
                            new_color = f"#{r:02x}{g:02x}{b:02x}"
                            toast_canvas.itemconfig(item, fill=new_color)
                        elif item_type == "text":
                            alpha = int(255 * (1 - t))
                            text_color = f"#{alpha:02x}{alpha:02x}{alpha:02x}"
                            toast_canvas.itemconfig(item, fill=text_color)
                    except:
                        pass
                self.after(16, lambda: fade_out(progress + 1))
            else:
                try:
                    toast_canvas.destroy()
                except:
                    pass
                self.reposition_toasts()

        fade_out()

    def create_control_buttons(self):
        btn_size = 24
        spacing = 6
        right_margin = 12
        menu_x = 900 - right_margin - btn_size / 2
        self._create_button("menu", menu_x, "☰", 15, self.toggle_screen)
        restart_x = menu_x - btn_size - spacing
        self._create_button("restart", restart_x, "⟳", 13, self.restart_button_click)
        kill_x = restart_x - btn_size - spacing
        self._create_button("kill", kill_x, "✕", 16, self.kill_button_click)
        mature_right_x = kill_x - btn_size / 2 - 14
        self._create_mature_toggle(mature_right_x)

    def _create_mature_toggle(self, right_x):
        self.mature_toggle_right_x = right_x
        self.mature_toggle_y1 = 8
        self.mature_toggle_y2 = 28
        switch_width = 34
        self.mature_toggle_x1 = right_x - switch_width
        self.mature_toggle_x2 = right_x

        self.mature_toggle_label = self.top_canvas.create_text(
            self.mature_toggle_x1 - 8,
            18,
            text="Mature",
            fill=self.theme["text_on_dark"],
            anchor="e",
            font=("Arial", 9),
        )
        self.mature_toggle_track = round_rectangle(
            self.top_canvas,
            self.mature_toggle_x1,
            self.mature_toggle_y1,
            self.mature_toggle_x2,
            self.mature_toggle_y2,
            radius=10,
            fill=self.theme["surface_press"],
            outline="",
        )
        self.mature_toggle_thumb = self.top_canvas.create_oval(
            0,
            0,
            0,
            0,
            fill=self.theme["text_on_dark"],
            outline="",
        )

        for item in (
            self.mature_toggle_label,
            self.mature_toggle_track,
            self.mature_toggle_thumb,
        ):
            self.top_canvas.tag_bind(item, "<Button-1>", self.toggle_mature_content)

        self._redraw_mature_toggle()

    def _redraw_mature_toggle(self):
        is_on = self.show_mature_var.get()
        track_color = self.theme["accent"] if is_on else self.theme["surface_press"]
        label_color = self.theme["text_on_dark"] if is_on else self.theme["text_muted"]
        self.top_canvas.itemconfig(self.mature_toggle_track, fill=track_color)
        self.top_canvas.itemconfig(self.mature_toggle_label, fill=label_color)

        thumb_size = 14
        y1 = self.mature_toggle_y1 + 3
        y2 = y1 + thumb_size
        if is_on:
            x1 = self.mature_toggle_x2 - thumb_size - 3
        else:
            x1 = self.mature_toggle_x1 + 3
        x2 = x1 + thumb_size
        self.top_canvas.coords(self.mature_toggle_thumb, x1, y1, x2, y2)

    def toggle_mature_content(self, event=None):
        self.show_mature_var.set(not self.show_mature_var.get())
        self.config["show_mature"] = self.show_mature_var.get()
        save_config(self.config)
        self._redraw_mature_toggle()
        self.apply_filters()

    def _create_button(self, name, x, icon, icon_size, callback, shape="rounded"):
        btn_size = 24
        if shape == "circle":
            bg = self.top_canvas.create_oval(
                x - btn_size / 2,
                6,
                x + btn_size / 2,
                6 + btn_size,
                fill=self.theme["surface"],
                outline="",
            )
        else:
            bg = round_rectangle(
                self.top_canvas,
                x - btn_size / 2,
                6,
                x + btn_size / 2,
                6 + btn_size,
                radius=12,
                fill=self.theme["surface"],
                outline="",
            )
        icon_elem = self.top_canvas.create_text(
            x, 18, text=icon, fill=self.theme["text_on_dark"], font=("Arial", icon_size)
        )
        items = [bg, icon_elem]
        self.button_states[name] = {"items": items, "default": self.theme["surface"]}
        for item in items:
            self.top_canvas.tag_bind(
                item, "<Enter>", lambda e, btn=name: self.on_button_hover(btn)
            )
            self.top_canvas.tag_bind(
                item, "<Leave>", lambda e, btn=name: self.on_button_leave(btn)
            )
            self.top_canvas.tag_bind(
                item, "<ButtonPress-1>", lambda e, btn=name: self.on_button_press(btn)
            )
            self.top_canvas.tag_bind(
                item,
                "<ButtonRelease-1>",
                lambda e, btn=name: self.on_button_release(btn, callback),
            )

    def on_button_hover(self, button_name):
        state = self.button_states.get(button_name)
        if state and "items" in state:
            for item in state["items"]:
                if self.top_canvas.type(item) in ("polygon", "oval"):
                    self.top_canvas.itemconfig(item, fill=self.theme["surface_hover"])
                    break

    def on_button_leave(self, button_name):
        state = self.button_states.get(button_name)
        if state and "items" in state:
            for item in state["items"]:
                if self.top_canvas.type(item) in ("polygon", "oval"):
                    self.top_canvas.itemconfig(item, fill=state["default"])
                    break

    def on_button_press(self, button_name):
        state = self.button_states.get(button_name)
        if state and "items" in state:
            for item in state["items"]:
                if self.top_canvas.type(item) in ("polygon", "oval"):
                    self.top_canvas.itemconfig(item, fill=self.theme["surface_press"])
                    break

    def on_button_release(self, button_name, callback):
        state = self.button_states.get(button_name)
        if state and "items" in state:
            for item in state["items"]:
                if self.top_canvas.type(item) in ("polygon", "oval"):
                    self.top_canvas.itemconfig(item, fill=self.theme["surface_hover"])
                    break
        callback()

    def kill_button_click(self):
        def _do():
            self.show_toast("killing daemon...")
            success = kill_daemon()
            self.after(
                0,
                lambda: self.show_toast(
                    "killed! >:3c" if success else "nothing to kill ¯\\_(ツ)_/¯"
                ),
            )

        threading.Thread(target=_do, daemon=True).start()

    def restart_button_click(self):
        def _do():
            kill_daemon()
            result = launch_daemon()
            if result == "incompatible":
                msg = "oof this wallpaper is incompatible :c"
            elif result:
                msg = "restarted! ✨"
            else:
                msg = "couldn't start daemon :("
            self.after(0, lambda: self.show_toast(msg))

        threading.Thread(target=_do, daemon=True).start()

    def refresh_wallpapers_click(self):
        if self.refreshing_wallpapers:
            self.show_toast("already refreshing...")
            return
        self.show_toast("refreshing wallpapers...")
        threading.Thread(target=self.refresh_wallpapers_async, daemon=True).start()

    def refresh_wallpapers_async(self):
        self.refreshing_wallpapers = True
        try:
            new_wallpapers = load_wallpapers()
            self.after(0, lambda: self.on_wallpapers_refreshed(new_wallpapers))
        finally:
            self.refreshing_wallpapers = False

    def on_wallpapers_refreshed(self, new_wallpapers):
        old_ids = {wp["id"] for wp in self.all_wallpapers}
        new_ids = {wp["id"] for wp in new_wallpapers}
        added_count = len(new_ids - old_ids)
        removed_count = len(old_ids - new_ids)

        self.all_wallpapers = new_wallpapers

        if self.applied_wpid and self.applied_wpid not in new_ids:
            self.applied_wpid = None
            self.config["wpid"] = None
            save_config(self.config)

        if self.previewed_wpid and self.previewed_wpid not in new_ids:
            self.previewed_wpid = None

        self.apply_filters()

        if added_count or removed_count:
            self.show_toast(f"refreshed! +{added_count} / -{removed_count}")
        else:
            self.show_toast("refreshed, no changes found")

    def create_wallpaper_screen(self):
        scroll_frame = tk.Frame(self.screen_container, bg=self.theme["main_bg"])
        self.canvas = tk.Canvas(
            scroll_frame, bg=self.theme["main_bg"], highlightthickness=0
        )
        self.scrollable_frame = tk.Frame(self.canvas, bg=self.theme["main_bg"])
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.scrollable_frame, anchor="nw"
        )

        def on_canvas_resize(event):
            self.canvas.itemconfig(self.canvas_window, width=event.width)

        self.canvas.bind("<Configure>", on_canvas_resize)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)
        return scroll_frame

    def show_screen(self, screen_name):
        self.current_screen = screen_name
        if hasattr(self, "wallpaper_screen"):
            self.wallpaper_screen.pack_forget()
        if self.settings_screen:
            self.settings_screen.pack_forget()
        if screen_name == "wallpapers":
            self.wallpaper_screen.pack(fill="both", expand=True)
        else:
            if not self.settings_screen:
                self.settings_screen = SettingsScreen(
                    self.screen_container,
                    self.config,
                    self.on_settings_save,
                    self.theme,
                    list(THEMES.keys()),
                    self.on_theme_change,
                )
            self.settings_screen.pack(fill="both", expand=True)

    def toggle_screen(self):
        if self.current_screen == "wallpapers":
            self.show_screen("settings")
        else:
            self.show_screen("wallpapers")

    def on_settings_save(self, new_config):
        self.config = new_config
        save_config(new_config)
        self.show_toast("settings saved! ✨")
        self.show_screen("wallpapers")

    def on_theme_change(self, theme_name):
        self.config["theme"] = theme_name
        self.apply_theme(theme_name)
        save_config(self.config)

    def apply_theme(self, theme_name):
        if theme_name not in THEMES:
            theme_name = "purple"
        self.theme_name = theme_name
        self.theme = THEMES[theme_name]
        self.config["theme"] = theme_name
        self.configure(bg=self.theme["main_bg"])

        if hasattr(self, "main_container"):
            self.main_container.configure(bg=self.theme["main_bg"])
        if hasattr(self, "screen_container"):
            self.screen_container.configure(bg=self.theme["main_bg"])
        if hasattr(self, "canvas"):
            self.canvas.configure(bg=self.theme["main_bg"])
        if hasattr(self, "scrollable_frame"):
            self.scrollable_frame.configure(bg=self.theme["main_bg"])
        if hasattr(self, "loading_label") and self.loading_label.winfo_exists():
            self.loading_label.configure(
                bg=self.theme["main_bg"], fg=self.theme["text_on_dark"]
            )

        if hasattr(self, "top_canvas"):
            self.top_canvas.configure(bg=self.theme["main_bg"])
            self.top_canvas.itemconfig(self.top_bar_bg_id, fill=self.theme["top_bar"])
            self.top_canvas.itemconfig(
                self.top_bar_title_id, fill=self.theme["text_on_dark"]
            )
            self.top_canvas.itemconfig(
                self.search_background,
                fill=self.theme["surface"],
            )
            self.top_canvas.itemconfig(
                self.search_placeholder,
                fill=self.theme["search_placeholder"],
            )
            self.search_entry.configure(
                bg=self.theme["surface"],
                fg=self.theme["text_on_dark"],
                insertbackground=self.theme["text_on_dark"],
            )
            self._redraw_mature_toggle()

        for state in self.button_states.values():
            state["default"] = self.theme["surface"]
            for item in state["items"]:
                if self.top_canvas.type(item) in ("polygon", "oval"):
                    self.top_canvas.itemconfig(item, fill=self.theme["surface"])
                elif self.top_canvas.type(item) == "text":
                    self.top_canvas.itemconfig(item, fill=self.theme["text_on_dark"])

        if hasattr(self, "side_panel"):
            self.side_panel.configure(bg=self.theme["panel_bg"])
            self.side_preview_label.configure(bg=self.theme["panel_bg"])
            self.side_name_label.configure(
                bg=self.theme["panel_bg"], fg=self.theme["text_on_dark"]
            )
            self.side_rating_label.configure(
                bg=self.theme["panel_bg"], fg=self.theme["text_muted"]
            )
            self.side_tags_label.configure(
                bg=self.theme["panel_bg"], fg=self.theme["text_secondary"]
            )
            self.side_file_label.configure(
                bg=self.theme["panel_bg"], fg=self.theme["text_secondary"]
            )
            self.side_workshop_label.configure(
                bg=self.theme["panel_bg"], fg=self.theme["text_secondary"]
            )
            self.side_type_label.configure(
                bg=self.theme["panel_bg"], fg=self.theme["text_secondary"]
            )
            self.side_version_label.configure(
                bg=self.theme["panel_bg"], fg=self.theme["text_secondary"]
            )
            self._create_apply_button()

        for tile in self.tile_cache.values():
            try:
                tile.destroy()
            except:
                pass
        self.tile_cache = {}
        self.display_wallpapers()
        self.update_side_panel()

        if self.settings_screen:
            self.settings_screen.destroy()
            self.settings_screen = None

    def _on_mousewheel(self, event):
        scroll_amount = 2
        if event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-scroll_amount, "units")
        elif event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(scroll_amount, "units")

    def load_wallpapers_async(self):
        self.all_wallpapers = load_wallpapers()
        self.after(0, self.apply_filters)

    def is_mature_wallpaper(self, wallpaper):
        return str(wallpaper.get("contentrating", "")).strip().lower() == "mature"

    def apply_filters(self):
        query = (
            self.search_entry.get().strip().lower()
            if hasattr(self, "search_entry")
            else ""
        )
        show_mature = self.show_mature_var.get()
        self.filtered_wallpapers = []

        for wp in self.all_wallpapers:
            if not show_mature and self.is_mature_wallpaper(wp):
                continue

            if query:
                score1 = fuzz.partial_ratio(query, wp["title"].lower())
                score2 = fuzz.partial_ratio(query, wp["romanized"].lower())
                if max(score1, score2) <= 60:
                    continue

            self.filtered_wallpapers.append(wp)

        self.display_wallpapers()

    def display_wallpapers(self):
        for widget in self.scrollable_frame.winfo_children():
            if isinstance(widget, tk.Label):
                widget.destroy()
            elif (
                isinstance(widget, tk.Frame) and widget not in self.tile_cache.values()
            ):
                widget.destroy()
        for tile in self.tile_cache.values():
            tile.grid_forget()
        if not self.filtered_wallpapers:
            no_results = tk.Label(
                self.scrollable_frame,
                text="no wallpapers found :(",
                bg=self.theme["main_bg"],
                fg=self.theme["text_on_dark"],
                font=("Arial", 12),
            )
            no_results.grid(row=0, column=0, pady=50, padx=50)
            return
        for i in range(5):
            self.scrollable_frame.grid_columnconfigure(i, weight=1, uniform="tile")
        for i, wp in enumerate(self.filtered_wallpapers):
            wp_id = wp["id"]
            is_active = wp_id == self.applied_wpid
            is_previewed = wp_id == self.previewed_wpid
            if wp_id not in self.tile_cache:
                self.tile_cache[wp_id] = WallpaperTile(
                    self.scrollable_frame,
                    wp,
                    self.on_wallpaper_select,
                    self.theme,
                    is_active,
                    is_previewed,
                )
            else:
                self.tile_cache[wp_id].set_active(is_active, is_previewed)
            self.tile_cache[wp_id].grid(row=i // 5, column=i % 5, padx=5, pady=5)
        self.update_side_panel()

    def animate_sidebar_gif(self):
        if not self.sidebar_animating or not self.sidebar_gif_frames:
            return
        self.side_preview_label.config(
            image=self.sidebar_gif_frames[self.sidebar_current_frame]
        )
        self.sidebar_current_frame = (self.sidebar_current_frame + 1) % len(
            self.sidebar_gif_frames
        )
        self.sidebar_anim_id = self.after(100, self.animate_sidebar_gif)

    def update_side_panel(self):
        self.sidebar_animating = False
        if hasattr(self, "sidebar_anim_id") and self.sidebar_anim_id:
            try:
                self.after_cancel(self.sidebar_anim_id)
            except:
                pass
            self.sidebar_anim_id = None
        self.sidebar_gif_frames = []
        self.sidebar_current_frame = 0
        display_wpid = self.previewed_wpid if self.previewed_wpid else self.applied_wpid
        if not display_wpid:
            self.side_name_label.config(text="No Wallpaper Selected")
            self.side_preview_label.config(image="")
            self.side_rating_label.config(text="")
            self.side_tags_label.config(text="")
            self.side_file_label.config(text="")
            self.side_workshop_label.config(text="")
            self.side_type_label.config(text="")
            self.side_version_label.config(text="")
            self.current_workshop_url = ""
            return
        wp_data = None
        for wp in self.all_wallpapers:
            if wp["id"] == display_wpid:
                wp_data = wp
                break
        if not wp_data:
            self.side_name_label.config(text="Wallpaper Data Missing TwT")
            self.side_workshop_label.config(text="")
            self.side_type_label.config(text="")
            self.side_version_label.config(text="")
            self.current_workshop_url = ""
            return
        title = wp_data.get("title", "Unknown Title")
        tags = wp_data.get("tags", [])
        content_rating = wp_data.get("contentrating", "Unrated")
        file_path = wp_data.get("file", "Unknown file")
        workshop_id = wp_data.get("workshopid", "")
        workshop_url = wp_data.get("workshopurl", "")
        wallpaper_type = wp_data.get("type", "Unknown")
        version = wp_data.get("version", "Unknown")
        self.current_workshop_url = workshop_url
        self.side_name_label.config(text=f"Name: {title}")
        self.side_rating_label.config(text=f"Rating: {content_rating}")
        tags_str = ", ".join(tags) if tags else "No tags"
        self.side_tags_label.config(text=f"Tags: {tags_str}")
        self.side_file_label.config(text=f"File: {file_path}")
        self.side_workshop_label.config(
            text=(
                f"Workshop ID: {workshop_id}" if workshop_id else "Workshop ID: Unknown"
            )
        )
        self.side_workshop_label.config(cursor="hand2" if workshop_url else "")
        self.side_type_label.config(text=f"Type: {wallpaper_type}")
        self.side_version_label.config(text=f"Version: {version}")
        preview_path = wp_data.get("preview_path")
        if preview_path and os.path.exists(preview_path):
            try:
                img = Image.open(preview_path)
                is_gif = wp_data.get("is_gif", False)
                if is_gif:
                    panel_rgb = hex_to_rgb(self.theme["panel_bg"])
                    for frame in ImageSequence.Iterator(img):
                        frame_copy = frame.copy()
                        frame_copy.thumbnail((180, 180), Image.Resampling.LANCZOS)
                        canvas = Image.new(
                            "RGBA",
                            (180, 180),
                            (panel_rgb[0], panel_rgb[1], panel_rgb[2], 255),
                        )
                        offset = (180 - frame_copy.width) // 2, (
                            180 - frame_copy.height
                        ) // 2
                        canvas.paste(frame_copy, offset)
                        self.sidebar_gif_frames.append(ImageTk.PhotoImage(canvas))
                    if self.sidebar_gif_frames:
                        self.sidebar_animating = True
                        self.animate_sidebar_gif()
                else:
                    img.thumbnail((180, 180), Image.Resampling.LANCZOS)
                    panel_rgb = hex_to_rgb(self.theme["panel_bg"])
                    canvas = Image.new(
                        "RGBA",
                        (180, 180),
                        (panel_rgb[0], panel_rgb[1], panel_rgb[2], 255),
                    )
                    offset = (180 - img.width) // 2, (180 - img.height) // 2
                    canvas.paste(img, offset)
                    self._side_preview_img = ImageTk.PhotoImage(canvas)
                    self.side_preview_label.config(image=self._side_preview_img)
            except Exception as e:
                print(f"couldn't load large preview: {e}")
                self.side_preview_label.config(image="")
        else:
            self.side_preview_label.config(image="")

    def on_wallpaper_select(self, wpid):
        if wpid == self.previewed_wpid:
            self.apply_wallpaper()
        else:
            old_previewed = self.previewed_wpid
            self.previewed_wpid = wpid
            if old_previewed and old_previewed in self.tile_cache:
                is_active = old_previewed == self.applied_wpid
                self.tile_cache[old_previewed].set_active(is_active, False)
            if wpid in self.tile_cache:
                is_active = wpid == self.applied_wpid
                self.tile_cache[wpid].set_active(is_active, True)
            self.update_side_panel()

    def apply_wallpaper(self):
        if not self.previewed_wpid:
            if not self.applied_wpid:
                self.show_toast("no wallpaper selected! pick one first uwu")
                return
            wpid_to_apply = self.applied_wpid
        else:
            wpid_to_apply = self.previewed_wpid
        self.config["wpid"] = wpid_to_apply
        self.show_toast("applying wallpaper...don't close the app!")
        save_config(self.config)
        old_applied = self.applied_wpid
        self.applied_wpid = wpid_to_apply
        self.previewed_wpid = None
        if old_applied and old_applied in self.tile_cache:
            self.tile_cache[old_applied].set_active(False, False)
        if wpid_to_apply in self.tile_cache:
            self.tile_cache[wpid_to_apply].set_active(True, False)
        self.update_side_panel()

        # then thread the daemon stuff
        def _do():
            if not is_daemon_running():
                result = launch_daemon()
                if result == "incompatible":
                    msg = "oof this wallpaper is incompatible :c"
                elif result:
                    msg = "started daemon! :3"
                else:
                    msg = "couldn't start daemon :("
                self.after(0, lambda: self.show_toast(msg))
            else:
                result = restart_daemon()
                if not result:
                    self.after(0, lambda: self.show_toast("couldn't restart daemon :("))
                    return

            self.after(6500, lambda: self.show_toast("wallpaper applied! :3c"))

        threading.Thread(target=_do, daemon=True).start()

    def set_static_wallpaper(self):
        if not self.previewed_wpid:
            if not self.applied_wpid:
                self.show_toast("no wallpaper selected! pick one first uwu")
                return
            wpid_to_apply = self.applied_wpid
        else:
            wpid_to_apply = self.previewed_wpid

        self.config["wpid"] = wpid_to_apply
        self.show_toast("setting static wallpaper...don't close the app!")
        save_config(self.config)
        old_applied = self.applied_wpid
        self.applied_wpid = wpid_to_apply
        self.previewed_wpid = None
        if old_applied and old_applied in self.tile_cache:
            self.tile_cache[old_applied].set_active(False, False)
        if wpid_to_apply in self.tile_cache:
            self.tile_cache[wpid_to_apply].set_active(True, False)
        self.update_side_panel()

        def _do():
            kill_daemon()
            main_path = PROJECT_ROOT / "main.py"
            try:
                result = subprocess.run(
                    [
                        sys.executable,
                        str(main_path),
                        "--set-static",
                        "--wpid",
                        wpid_to_apply,
                    ],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    msg = "static wallpaper set! :3"
                else:
                    msg = "failed to set static wallpaper :("
                    if result.stderr:
                        print(result.stderr.strip())
            except Exception as e:
                msg = f"failed to set static wallpaper: {e}"
            self.after(0, lambda: self.show_toast(msg))

        threading.Thread(target=_do, daemon=True).start()

    def open_search(self, event=None):
        if self.search_expanded:
            return
        if self.search_entry_window is None:
            self.search_entry_window = self.top_canvas.create_window(
                self.search_x1 + 10, 18, anchor="w", window=self.search_entry, width=90
            )
            self.search_entry.bind("<KeyRelease>", self.on_search_input)
            self.search_entry.bind("<Return>", self.on_search_submit)
            self.search_entry.bind("<Escape>", self.close_search)
            self.search_entry.bind("<FocusIn>", self.open_search)
        else:
            self.top_canvas.itemconfig(self.search_entry_window, state="normal")
        self.bind("<Button-1>", self.on_click_outside)
        self.search_entry.focus_set()
        self.search_expanded = True
        self.animate_expand(
            self.search_x1,
            self.search_collapsed_x2,
            self.search_expanded_x2,
            0,
        )
        if not bool(self.search_entry.get().strip()):
            self.top_canvas.itemconfig(self.search_placeholder, state="normal")
            self.animate_fade(255, 0)

    def close_search(self, event=None):
        if not self.search_expanded:
            return
        has_text = bool(self.search_entry.get().strip())
        if not has_text:
            self.search_entry.delete(0, tk.END)
            self.top_canvas.itemconfig(
                self.search_placeholder,
                state="normal",
                fill=self.theme["search_placeholder"],
            )
            if self.search_entry_window is not None:
                self.top_canvas.itemconfig(self.search_entry_window, state="hidden")
            self.perform_search()
        self.animate_expand(
            self.search_x1,
            self.search_expanded_x2,
            self.search_collapsed_x2,
            0,
        )
        self.search_expanded = False
        self.focus_set()
        try:
            self.unbind("<Button-1>")
        except:
            pass
        return "break"

    def on_click_outside(self, event):
        widget = event.widget
        if widget == self.search_entry:
            return
        if widget == self.top_canvas:
            canvas_x = event.x
            canvas_y = event.y
            if (
                self.search_x1 <= canvas_x <= self.search_expanded_x2
                and self.search_y1 <= canvas_y <= self.search_y2
            ):
                return
        self.close_search()

    def on_search_submit(self, event):
        self.perform_search()
        return "break"

    def on_search_input(self, event):
        if event.keysym in ("Return", "Escape"):
            return
        self.top_canvas.itemconfigure(self.search_placeholder, state="hidden")
        if self.search_debounce_id:
            self.after_cancel(self.search_debounce_id)
        self.search_debounce_id = self.after(150, self.perform_search)

    def perform_search(self):
        self.apply_filters()

    def animate_expand(self, x1, start_x, target_x, progress):
        duration = 20
        if progress <= duration:
            t = progress / duration
            eased = ease_out_quad(t)
            eased_x = start_x + (target_x - start_x) * eased
            text_content = self.search_entry.get()
            if text_content:
                text_width = len(text_content) * 7 + 30
                current_x = max(text_width + x1, eased_x)
            else:
                current_x = eased_x
            radius = 22
            y1, y2 = 6, 30
            points = [
                x1 + radius,
                y1,
                current_x - radius,
                y1,
                current_x,
                y1,
                current_x,
                y1 + radius,
                current_x,
                y2 - radius,
                current_x,
                y2,
                current_x - radius,
                y2,
                x1 + radius,
                y2,
                x1,
                y2,
                x1,
                y2 - radius,
                x1,
                y1 + radius,
                x1,
                y1,
            ]
            self.top_canvas.coords(self.search_background, *points)
            entry_width = current_x - x1 - 15
            if self.search_entry_window is not None:
                self.top_canvas.itemconfig(self.search_entry_window, width=entry_width)
            self.after(
                16, lambda: self.animate_expand(x1, start_x, target_x, progress + 1)
            )

    def animate_fade(self, current_alpha, target_alpha):
        if current_alpha > target_alpha:
            current_alpha = max(current_alpha - 15, target_alpha)
            hex_alpha = f"#{current_alpha:02x}{current_alpha:02x}{current_alpha:02x}"
            self.top_canvas.itemconfig(self.search_placeholder, fill=hex_alpha)
            if current_alpha <= 0:
                self.top_canvas.itemconfig(self.search_placeholder, state="hidden")
            self.after(16, lambda: self.animate_fade(current_alpha, target_alpha))


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
