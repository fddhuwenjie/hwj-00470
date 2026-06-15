import sys
import termios
import tty
import time
import threading
from notes import midi_to_frequency


KEY_NOTE_MAP = {
    'a': 0,
    'w': 1,
    's': 2,
    'e': 3,
    'd': 4,
    'f': 5,
    't': 6,
    'g': 7,
    'y': 8,
    'h': 9,
    'u': 10,
    'j': 11,
    'k': 12,
}

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def get_key_note_midi(key, octave=4):
    if key not in KEY_NOTE_MAP:
        return None
    semitone_offset = KEY_NOTE_MAP[key]
    base_midi = (octave + 1) * 12
    return base_midi + semitone_offset


def get_key_note_name(key, octave=4):
    if key not in KEY_NOTE_MAP:
        return None
    semitone_offset = KEY_NOTE_MAP[key]
    note_idx = semitone_offset % 12
    note_octave = octave + semitone_offset // 12
    return NOTE_NAMES[note_idx] + str(note_octave)


def get_key_note_frequency(key, octave=4):
    midi = get_key_note_midi(key, octave)
    if midi is None:
        return 0.0
    return midi_to_frequency(midi)


class KeyPress:
    def __init__(self, key, midi_note, frequency, timestamp):
        self.key = key
        self.midi_note = midi_note
        self.frequency = frequency
        self.timestamp = timestamp
        self.release_time = None
        self.note_name = get_key_note_name(key, midi_to_octave(midi_note))

    @property
    def duration(self):
        if self.release_time is None:
            return 0.0
        return self.release_time - self.timestamp

    def release(self, timestamp):
        self.release_time = timestamp


def midi_to_octave(midi_note):
    return midi_note // 12 - 1


class RawKeyboardInput:
    def __init__(self):
        self.old_settings = None
        self.fd = sys.stdin.fileno()

    def __enter__(self):
        self.old_settings = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.old_settings is not None:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)
        return False

    def read_key(self, timeout=0.01):
        import select
        r, _, _ = select.select([sys.stdin], [], [], timeout)
        if r:
            try:
                ch = sys.stdin.read(1)
                return ch
            except IOError:
                return None
        return None


class LiveKeyboard:
    def __init__(self, on_note_on=None, on_note_off=None, on_quit=None):
        self.octave = 4
        self.active_notes = {}
        self.recorded_notes = []
        self.recording = True
        self.start_time = time.time()
        self.running = False
        self.on_note_on = on_note_on
        self.on_note_off = on_note_off
        self.on_quit = on_quit
        self._lock = threading.Lock()

    def shift_octave_up(self):
        if self.octave < 8:
            self.octave += 1
            print(f"\n  Octave: {self.octave}  ", end='', flush=True)

    def shift_octave_down(self):
        if self.octave > 0:
            self.octave -= 1
            print(f"\n  Octave: {self.octave}  ", end='', flush=True)

    def handle_key_press(self, key):
        current_time = time.time() - self.start_time
        key_lower = key.lower()

        if key == 'x' or key == 'X':
            self.shift_octave_up()
            return

        if key == 'z' or key == 'Z':
            self.shift_octave_down()
            return

        if key == 'q' or key == 'Q' or key == '\x1b':
            if self.on_quit:
                self.on_quit()
            self.stop()
            return

        if key_lower in KEY_NOTE_MAP:
            with self._lock:
                if key_lower not in self.active_notes:
                    midi = get_key_note_midi(key_lower, self.octave)
                    freq = midi_to_frequency(midi)
                    press = KeyPress(key_lower, midi, freq, current_time)
                    self.active_notes[key_lower] = press
                    if self.recording:
                        self.recorded_notes.append(press)
                    if self.on_note_on:
                        self.on_note_on(press)
                    note_name = get_key_note_name(key_lower, self.octave)
                    print(f"\r  Playing: {note_name:<4} (key={key_lower}, octave={self.octave})  ", end='', flush=True)

    def handle_key_release(self, key):
        current_time = time.time() - self.start_time
        key_lower = key.lower()
        with self._lock:
            if key_lower in self.active_notes:
                press = self.active_notes.pop(key_lower)
                press.release(current_time)
                if self.on_note_off:
                    self.on_note_off(press)
                if not self.active_notes:
                    print("\r                                                         ", end='', flush=True)

    def stop(self):
        self.running = False
        current_time = time.time() - self.start_time
        with self._lock:
            for press in self.active_notes.values():
                press.release(current_time)
                if self.on_note_off:
                    self.on_note_off(press)
            self.active_notes.clear()

    def get_recorded_mml(self, bpm=120):
        beat_duration = 60.0 / bpm
        lines = []

        for press in self.recorded_notes:
            if press.duration <= 0:
                continue

            beats = press.duration / beat_duration
            if beats >= 3.5:
                dur_str = '1'
            elif beats >= 1.75:
                dur_str = '2'
            elif beats >= 0.875:
                dur_str = '4'
            elif beats >= 0.4375:
                dur_str = '8'
            else:
                dur_str = '16'

            dotted = (beats % 1.0) > 0.5
            if dotted:
                dur_str += '.'

            note_idx = press.midi_note % 12
            octave = press.midi_note // 12 - 1
            note_name = NOTE_NAMES[note_idx]
            note_name = note_name.replace('#', '#')
            mml_note = note_name + str(octave) + dur_str
            lines.append(mml_note)

        return ' '.join(lines)

    def save_recorded_mml(self, filepath, bpm=120):
        mml = self.get_recorded_mml(bpm)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# Recorded live performance\n")
            f.write(f"# BPM: {bpm}\n")
            f.write(f"name=Recorded,wave=sine,vol=0.8,pan=0.0 | bpm={bpm} {mml}\n")
        return filepath

    def run(self):
        self.running = True
        self.start_time = time.time()

        print("\n" + "=" * 60)
        print("  Live Keyboard Mode")
        print("=" * 60)
        print("  Keys:")
        print("    White: A S D F G H J K  (C4 D4 E4 F4 G4 A4 B4 C5)")
        print("    Black: W   E   T Y   U  (C#4 D#4 F#4 G#4 A#4)")
        print("  Octave: Z (down)  X (up)")
        print("  Quit: Q or ESC")
        print("=" * 60)
        print(f"  Current Octave: {self.octave}")
        print("  Ready. Press keys to play...\n")

        try:
            with RawKeyboardInput() as kb:
                pressed_keys = set()
                while self.running:
                    ch = kb.read_key(timeout=0.005)
                    if ch:
                        if ord(ch) == 27:
                            ch2 = kb.read_key(timeout=0.005)
                            if ch2 == '[':
                                kb.read_key(timeout=0.005)
                                continue
                            elif ch2 is None:
                                self.handle_key_press('\x1b')
                                break
                            continue

                        ch_lower = ch.lower()
                        if ch_lower in KEY_NOTE_MAP or ch_lower in ('z', 'x', 'q'):
                            self.handle_key_press(ch)

                            pressed_keys.add(ch_lower)

                    released = set()
                    for k in pressed_keys:
                        still_pressed = self._check_key_held(kb, k)
                        if not still_pressed and k in self.active_notes:
                            self.handle_key_release(k)
                            released.add(k)
                    pressed_keys -= released

                    time.sleep(0.001)

        except Exception as e:
            print(f"\nError: {e}")
        finally:
            self.stop()
            print("\n\n  Performance stopped.")
            print(f"  Recorded {len(self.recorded_notes)} notes.")

    def _check_key_held(self, kb, key):
        import select
        r, _, _ = select.select([sys.stdin], [], [], 0)
        if r:
            try:
                ch = sys.stdin.read(1)
                if ch.lower() == key:
                    return True
            except IOError:
                pass
        return key in self.active_notes


def print_keyboard_layout():
    layout = """
  Keyboard Layout (Octave 4):

  W   E   T Y   U      <- Black keys (C# D# F# G# A#)
  A S D F G H J K      <- White keys (C D E F G A B C)
  4 4 4 4 4 4 4 5      <- Octaves

  Z = Octave Down    X = Octave Up    Q/ESC = Quit
"""
    print(layout)
