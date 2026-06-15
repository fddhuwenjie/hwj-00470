import re
from notes import (
    note_name_to_frequency, note_name_to_midi,
    jianpu_to_frequency, jianpu_to_midi,
    get_note_duration, parse_duration_suffix,
    get_dynamics_volume
)


class NoteEvent:
    def __init__(self, frequency=0.0, duration=1.0, midi_note=None, volume=0.7, tied=False, is_rest=False):
        self.frequency = frequency
        self.duration = duration
        self.midi_note = midi_note
        self.volume = volume
        self.tied = tied
        self.is_rest = is_rest


class TrackData:
    def __init__(self, name="Track", wave_type="sine", volume=0.8, pan=0.0):
        self.name = name
        self.wave_type = wave_type
        self.volume = volume
        self.pan = pan
        self.events = []


def _expand_loops(tokens):
    result = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == '[:' :
            j = i + 1
            loop_content = []
            depth = 1
            while j < len(tokens) and depth > 0:
                if tokens[j] == '[:' :
                    depth += 1
                    loop_content.append(tokens[j])
                elif tokens[j] == ':]' :
                    depth -= 1
                    if depth > 0:
                        loop_content.append(tokens[j])
                else:
                    loop_content.append(tokens[j])
                j += 1

            repeat_count = 2
            if j < len(tokens):
                m = re.match(r'×(\d+)', tokens[j])
                if m:
                    repeat_count = int(m.group(1))
                    j += 1
                else:
                    m2 = re.match(r'\*(\d+)', tokens[j])
                    if m2:
                        repeat_count = int(m2.group(1))
                        j += 1

            expanded = _expand_loops(loop_content)
            for _ in range(repeat_count):
                result.extend(expanded)
            i = j
        else:
            result.append(tok)
            i += 1
    return result


def _tokenize(text):
    text = text.strip()
    if not text:
        return []

    pattern = r'\[\:|\:\]|×\d+|\*\d+|[^\s]+'
    tokens = re.findall(pattern, text)
    return tokens


def parse_track_line(line, default_bpm=120):
    parts = line.split('|', 1)
    if len(parts) == 2:
        header = parts[0].strip()
        content = parts[1].strip()
    else:
        header = ""
        content = parts[0].strip()

    track = TrackData()

    if header:
        hparts = [p.strip() for p in header.split(',')]
        for hp in hparts:
            hp_lower = hp.lower()
            if hp_lower.startswith('name=') or hp_lower.startswith('n='):
                track.name = hp.split('=', 1)[1].strip()
            elif hp_lower.startswith('wave=') or hp_lower.startswith('w='):
                track.wave_type = hp.split('=', 1)[1].strip()
            elif hp_lower.startswith('vol=') or hp_lower.startswith('v='):
                try:
                    track.volume = float(hp.split('=', 1)[1])
                except ValueError:
                    pass
            elif hp_lower.startswith('pan=') or hp_lower.startswith('p='):
                try:
                    track.pan = float(hp.split('=', 1)[1])
                except ValueError:
                    pass

    bpm = default_bpm
    current_volume = 0.7
    current_octave = 4
    current_duration = 'quarter'

    tokens = _tokenize(content)
    tokens = _expand_loops(tokens)

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        tok_lower = tok.lower()

        if tok_lower in ('p', 'pp', 'ppp', 'mp', 'mf', 'f', 'ff', 'fff'):
            current_volume = get_dynamics_volume(tok_lower)
            i += 1
            continue

        if tok_lower.startswith('bpm'):
            m = re.match(r'bpm[=:](\d+)', tok_lower)
            if m:
                bpm = int(m.group(1))
            i += 1
            continue

        if tok_lower.startswith('o'):
            m = re.match(r'o(\d)', tok_lower)
            if m:
                current_octave = int(m.group(1))
            i += 1
            continue

        m = re.match(r'^(?:l|len)(\d+\.?)$', tok_lower)
        if m:
            current_duration = parse_duration_suffix(m.group(1))
            i += 1
            continue

        is_rest = False
        frequency = 0.0
        midi_note = None
        duration = current_duration
        tied = False

        if tok_lower == 'r' or tok == '0':
            is_rest = True
        elif tok[0].isdigit():
            m = re.match(r'^([1-7])([.,#b]*)(\d*\.?)(-?)$', tok)
            if m:
                jianpu_note = m.group(1)
                modifiers = m.group(2)
                dur_suffix = m.group(3)
                tie_marker = m.group(4)

                jianpu_str = jianpu_note + modifiers
                frequency = jianpu_to_frequency(jianpu_str, current_octave)
                midi_note = jianpu_to_midi(jianpu_str, current_octave)

                if dur_suffix:
                    duration = parse_duration_suffix(dur_suffix)
                if tie_marker == '-':
                    tied = True
            else:
                i += 1
                continue
        elif tok[0].isalpha():
            m = re.match(r'^([A-Ga-g])([#b]?)(\d?)(\d*\.?)(-?)$', tok)
            if m:
                note_letter = m.group(1).upper()
                accidental = m.group(2)
                octave_suffix = m.group(3)
                dur_suffix = m.group(4)
                tie_marker = m.group(5)

                note_str = note_letter + accidental
                if octave_suffix:
                    note_str += octave_suffix
                else:
                    note_str += str(current_octave)

                frequency = note_name_to_frequency(note_str)
                midi_note = note_name_to_midi(note_str)

                if dur_suffix:
                    duration = parse_duration_suffix(dur_suffix)
                if tie_marker == '-':
                    tied = True
            else:
                i += 1
                continue
        else:
            i += 1
            continue

        dur_seconds = get_note_duration(duration, bpm)

        event = NoteEvent(
            frequency=frequency,
            duration=dur_seconds,
            midi_note=midi_note,
            volume=current_volume,
            tied=tied,
            is_rest=is_rest
        )
        track.events.append(event)
        i += 1

    return track


def parse_song_file(filepath, default_bpm=120):
    tracks = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('//'):
                continue
            track = parse_track_line(line, default_bpm)
            tracks.append(track)
    return tracks


def merge_tied_notes(events):
    if not events:
        return []

    result = []
    i = 0
    while i < len(events):
        ev = events[i]
        if ev.tied and not ev.is_rest and i + 1 < len(events):
            next_ev = events[i + 1]
            if next_ev.midi_note == ev.midi_note:
                merged = NoteEvent(
                    frequency=ev.frequency,
                    duration=ev.duration + next_ev.duration,
                    midi_note=ev.midi_note,
                    volume=ev.volume,
                    tied=False,
                    is_rest=False
                )
                result.append(merged)
                i += 2
                continue
        result.append(ev)
        i += 1
    return result
