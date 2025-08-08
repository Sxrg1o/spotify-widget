import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk
import subprocess
import json
import os

def run_playerctl_command(*args):
    try:
        command = ['playerctl', '-p', 'spotify', *args]
        return subprocess.check_output(command, text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    
def play_pause():
    run_playerctl_command('play-pause')

def next_song():
    run_playerctl_command('next')

def previous_song():
    run_playerctl_command('previous')

def set_volume(level):
    run_playerctl_command('volume', str(level))

def get_metadata():
    metadata_json = run_playerctl_command('metadata', '--format', '{{toJson(metadata)}}')
    if metadata_json:
        return json.loads(metadata_json)
    return {}

def get_current_song_info():
    metadata_str = run_playerctl_command('metadata', '--format', '{{xesam:title}}¦{{xesam:artist}}¦{{mpris:length}}')

    if not metadata_str:
        return "Spotify not active", "---", 0, 1
    
    position_str = run_playerctl_command('position')

    try:
        title, artist, duration_str = metadata_str.split('¦', 2)
        position = float(position_str) if position_str else 0
        duration = float(duration_str) / 1000000 if duration_str else 1
        
        if not artist:
            artist = "Unknown Artist"

        return title, artist, position, duration
    except ValueError:
        return "Error", "---", 0, 1

def get_playback_status():
    return run_playerctl_command('status')

def get_position():
    pos = run_playerctl_command('position')
    duration_str = run_playerctl_command('metadata', '--format', '{{mpris:length}}')
    
    if pos and duration_str:
        return float(pos), float(duration_str) / 1000000
    return 0, 1 

class SpotifyWidget(Gtk.Window):
    def __init__(self):
        super().__init__(title="Spotify Widget")
        self.move(0,0)
        self.load_css()
        self.set_name("main-window")
        self.set_keep_above(True)
        self.stick()
        self.set_accept_focus(False)

        self.set_border_width(15)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.connect("destroy", Gtk.main_quit)
        self.connect("key-press-event", lambda w, e: Gtk.main_quit() if e.keyval == Gdk.KEY_Escape else None)

        self.is_seeking = False
        self.is_volume_changing = False

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(vbox)

        self.song_label = Gtk.Label(label="Loading...")
        self.song_label.get_style_context().add_class("title-1")
        vbox.pack_start(self.song_label, True, True, 0)
        
        progress_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.time_label_start = Gtk.Label(label="0:00")
        self.progress_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=Gtk.Adjustment(value=0, lower=0, upper=100, step_increment=1, page_increment=10))
        self.progress_scale.set_draw_value(False) 
        self.progress_scale.connect("value-changed", self.on_seek_changed)
        self.progress_scale.connect("button-press-event", lambda w, e: self.set_seeking(True))
        self.progress_scale.connect("button-release-event", lambda w, e: self.set_seeking(False))
        self.time_label_end = Gtk.Label(label="0:00")
        progress_box.pack_start(self.time_label_start, False, False, 0)
        progress_box.pack_start(self.progress_scale, True, True, 0)
        progress_box.pack_start(self.time_label_end, False, False, 0)
        vbox.pack_start(progress_box, True, True, 5)

        controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.pack_start(controls_box, True, True, 0)
        
        button_box = Gtk.Box(spacing=6)
        controls_box.pack_start(button_box, True, True, 0)

        prev_button = Gtk.Button.new_from_icon_name("media-skip-backward-symbolic", Gtk.IconSize.BUTTON)
        prev_button.connect("clicked", self.on_prev_clicked)
        button_box.pack_start(prev_button, True, True, 0)
        
        self.play_pause_button = Gtk.Button()
        self.play_pause_button.connect("clicked", lambda w: run_playerctl_command('play-pause'))
        button_box.pack_start(self.play_pause_button, True, True, 0)

        next_button = Gtk.Button.new_from_icon_name("media-skip-forward-symbolic", Gtk.IconSize.BUTTON)
        next_button.connect("clicked", self.on_next_clicked)
        button_box.pack_start(next_button, True, True, 0)

        volume_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        volume_box.set_size_request(120, -1) 
        volume_icon = Gtk.Image.new_from_icon_name("audio-volume-high-symbolic", Gtk.IconSize.BUTTON)
        self.volume_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=Gtk.Adjustment(value=0, lower=0, upper=1, step_increment=0.01, page_increment=0.1))
        self.volume_scale.set_draw_value(False)
        self.volume_scale.connect("value-changed", self.on_volume_changed)
        volume_box.pack_start(volume_icon, False, False, 0)
        volume_box.pack_start(self.volume_scale, True, True, 0)
        controls_box.pack_end(volume_box, False, False, 0) 

        self.update_ui()
        GLib.timeout_add_seconds(1, self.update_ui)

    def update_ui(self):
        title, artist, position, duration = get_current_song_info()
        self.song_label.set_markup(f"<b>{GLib.markup_escape_text(title)}</b>\n<span size='xx-small'>{GLib.markup_escape_text(artist)}</span>")
        
        if not self.is_seeking:
            self.progress_scale.get_adjustment().set_upper(duration)
            self.progress_scale.set_value(position)

        start_time = f"{int(position//60)}:{int(position%60):02d}"
        end_time = f"{int(duration//60)}:{int(duration%60):02d}"

        self.time_label_start.set_markup(f"<small>{start_time}</small>")
        self.time_label_end.set_markup(f"<small>{end_time}</small>")
        
        vol_str = run_playerctl_command('volume')
        if vol_str:
            self.volume_scale.handler_block_by_func(self.on_volume_changed)
            self.volume_scale.set_value(float(vol_str))
            self.volume_scale.handler_unblock_by_func(self.on_volume_changed)

        status = run_playerctl_command('status')
        
        if status == "Playing":
            icon_image = Gtk.Image.new_from_icon_name("media-playback-pause-symbolic", Gtk.IconSize.BUTTON)
            self.play_pause_button.set_image(icon_image)
        else:
            icon_image = Gtk.Image.new_from_icon_name("media-playback-start-symbolic", Gtk.IconSize.BUTTON)
            self.play_pause_button.set_image(icon_image)
        
        return True

    def set_seeking(self, seeking):
        self.is_seeking = seeking

    def on_seek_changed(self, scale):
        if self.is_seeking:
            new_position = scale.get_value()
            run_playerctl_command('position', str(new_position))

    def on_volume_changed(self, scale):
        new_volume = scale.get_value()
        run_playerctl_command('volume', f"{new_volume:.2f}")

    def on_next_clicked(self, widget):
        run_playerctl_command('next')

    def on_prev_clicked(self, widget):
        run_playerctl_command('previous')

    def load_css(self):
        css_provider = Gtk.CssProvider()
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        css_path = os.path.join(script_dir, 'style.css')
        
        try:
            css_provider.load_from_path(css_path)
            screen = Gdk.Screen.get_default()
            style_context = self.get_style_context()
            style_context.add_provider_for_screen(screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        except GLib.Error as e:
            print(f"Error cargando el archivo CSS desde '{css_path}': {e}")


if __name__ == "__main__":
    win = SpotifyWidget()
    win.show_all()
    Gtk.main()