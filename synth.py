#!/usr/bin/env python3
import sys
import argparse
import os
import threading
import time
import queue
import math

from oscillators import (
    generate_wave, ADSR, SAMPLE_RATE,
    generate_fm_wave, generate_layered_wave
)
from notes import (
    note_name_to_frequency, get_note_duration,
    get_dynamics_volume, midi_to_frequency
)
from parser import (
    parse_song_file, parse_track_line, merge_tied_notes,
    NoteEvent, TrackData
)
from mixer import Track, Mixer
from effects import (
    apply_echo, apply_reverb, apply_vibrato,
    apply_lowpass, apply_highpass, apply_distortion
)
from output import write_wav, write_midi
from analyzer import (
    read_wav, ascii_waveform,
    spectrum_analysis, ascii_spectrum
)
from instruments import (
    get_instrument, list_instruments, InstrumentPreset,
    generate_fm_wave as inst_generate_fm_wave
)
from chord import (
    ChordEvent, chord_to_frequencies, chord_to_midi_notes
)
from keyboard import (
    LiveKeyboard, print_keyboard_layout,
    KEY_NOTE_MAP
)


def render_single_note(frequency, duration, volume, instrument, wave_type):
    if instrument is not None and isinstance(instrument, InstrumentPreset):
        adsr = ADSR(**instrument.get_adsr_kwargs())

        if instrument.is_fm():
            fm_params = instrument.fm_params
            samples = generate_fm_wave(
                frequency, duration,
                mod_ratio=fm_params.get('mod_ratio', 2.0),
                mod_index=fm_params.get('mod_index', 3.0),
                mod_wave=fm_params.get('mod_wave', 'sine'),
                carrier_wave=fm_params.get('carrier_wave', 'sine')
            )
        elif instrument.layer_config:
            samples = generate_layered_wave(
                frequency, duration, instrument.layer_config
            )
        else:
            wt = instrument.wave_types[0] if instrument.wave_types else wave_type
            samples = generate_wave(wt, frequency, duration)

        samples = adsr.apply(samples, duration)
        samples = [s * volume for s in samples]

        if instrument.effects:
            eff = instrument.effects
            if eff.get('distortion'):
                samples = apply_distortion(samples)
            if eff.get('vibrato'):
                v = eff['vibrato']
                samples = apply_vibrato(
                    samples,
                    v.get('freq', 5.0),
                    v.get('depth', 50)
                )
            if eff.get('lowpass'):
                samples = apply_lowpass(samples, eff['lowpass'])
            if eff.get('highpass'):
                samples = apply_highpass(samples, eff['highpass'])
    else:
        adsr = ADSR(attack=0.01, decay=0.05, sustain=0.7, release=0.1)
        samples = generate_wave(wave_type, frequency, duration)
        samples = adsr.apply(samples, duration)
        samples = [s * volume for s in samples]

    return samples


def apply_track_effects(samples, effects, instrument):
    if instrument and isinstance(instrument, InstrumentPreset) and instrument.effects:
        inst_eff = instrument.effects
        if inst_eff.get('echo'):
            e = inst_eff['echo']
            samples = apply_echo(samples, e.get('delay', 0.3), e.get('decay', 0.5))
        if inst_eff.get('reverb'):
            r = inst_eff['reverb']
            samples = apply_reverb(samples, r.get('room', 0.5), r.get('decay', 0.6))

    if effects:
        if effects.get('echo'):
            e = effects['echo']
            samples = apply_echo(samples, e.get('delay', 0.3), e.get('decay', 0.5))
        if effects.get('reverb'):
            r = effects['reverb']
            samples = apply_reverb(samples, r.get('room', 0.5), r.get('decay', 0.6))
        if effects.get('lowpass'):
            samples = apply_lowpass(samples, effects['lowpass'])
        if effects.get('highpass'):
            samples = apply_highpass(samples, effects['highpass'])
        if effects.get('vibrato'):
            v = effects['vibrato']
            samples = apply_vibrato(
                samples,
                v.get('freq', 5.0),
                v.get('depth', 50)
            )
    return samples


def render_chord_event(chord_ev, wave_type, track_instrument=None):
    duration = chord_ev.duration
    volume = chord_ev.volume

    if chord_ev.is_arpeggio():
        arp_events = chord_ev.get_arpeggio_events()
        total_dur = sum(e['duration'] for e in arp_events)
        n_total = int(total_dur * SAMPLE_RATE)
        samples = [0.0] * n_total
        current_idx = 0

        for arp_ev in arp_events:
            freq = arp_ev['frequency']
            dur = arp_ev['duration']
            note_samples = render_single_note(
                freq, dur, volume, track_instrument, wave_type
            )
            n = len(note_samples)
            for i in range(n):
                if current_idx + i < n_total:
                    samples[current_idx + i] += note_samples[i]
            current_idx += int(dur * SAMPLE_RATE)
        return samples
    else:
        n_total = int(duration * SAMPLE_RATE)
        samples = [0.0] * n_total

        for freq in chord_ev.frequencies:
            note_samples = render_single_note(
                freq, duration, volume / max(1, len(chord_ev.frequencies)),
                track_instrument, wave_type
            )
            n = len(note_samples)
            for i in range(n):
                if i < n_total:
                    samples[i] += note_samples[i]

        return samples


def render_track(track_data, adsr=None, effects=None):
    merged_events = merge_tied_notes(track_data.events)

    total_duration = 0.0
    for ev in merged_events:
        total_duration += ev.duration

    n_total = int(total_duration * SAMPLE_RATE)
    samples = [0.0] * n_total

    current_idx = 0
    current_instrument = None

    if track_data.instrument:
        current_instrument = get_instrument(track_data.instrument)

    for event in merged_events:
        if event.instrument and event.instrument != track_data.instrument:
            current_instrument = get_instrument(event.instrument)

        if event.is_rest or (not event.is_chord and event.frequency <= 0):
            current_idx += int(event.duration * SAMPLE_RATE)
            continue

        if event.is_chord and event.chord_event:
            note_samples = render_chord_event(
                event.chord_event, track_data.wave_type, current_instrument
            )
        else:
            note_samples = render_single_note(
                event.frequency, event.duration, event.volume,
                current_instrument, track_data.wave_type
            )

        if effects and not event.is_chord:
            if effects.get('vibrato'):
                v = effects['vibrato']
                note_samples = apply_vibrato(
                    note_samples,
                    v.get('freq', 5.0),
                    v.get('depth', 50)
                )

        n = len(note_samples)
        for i in range(n):
            if current_idx + i < n_total:
                samples[current_idx + i] += note_samples[i]

        current_idx += int(event.duration * SAMPLE_RATE)

    samples = apply_track_effects(samples, effects, current_instrument)
    return samples


def cmd_play(args):
    song_file = args.song
    output_file = args.output
    bpm = args.bpm
    wave = args.wave

    if not os.path.exists(song_file):
        print(f"Error: Song file '{song_file}' not found.")
        return 1

    print(f"Parsing song: {song_file}")
    track_datas = parse_song_file(song_file, default_bpm=bpm)

    if not track_datas:
        print("Error: No tracks found in song file.")
        return 1

    print(f"Found {len(track_datas)} tracks.")

    mixer = Mixer()
    midi_tracks = []

    for i, td in enumerate(track_datas):
        if wave and not td.wave_type:
            td.wave_type = wave

        inst_info = f", inst={td.instrument}" if td.instrument else ""
        print(f"  Track {i+1}: {td.name} (wave={td.wave_type}, vol={td.volume}, pan={td.pan}{inst_info})")
        print(f"    Rendering {len(td.events)} events...")

        track_samples = render_track(td)

        track = Track(
            name=td.name,
            wave_type=td.wave_type,
            volume=td.volume,
            pan=td.pan
        )
        track.set_samples(track_samples)
        mixer.add_track(track)

        midi_track = TrackData(name=td.name)
        current_time = 0.0
        for ev in td.events:
            ev_copy = NoteEvent(
                frequency=ev.frequency,
                duration=ev.duration,
                midi_note=ev.midi_note,
                volume=ev.volume,
                tied=ev.tied,
                is_rest=ev.is_rest
            )
            ev_copy.start_time = current_time
            midi_track.events.append(ev_copy)
            current_time += ev.duration
        midi_tracks.append(midi_track)

    print("Mixing...")
    left, right = mixer.mix()

    if output_file:
        if output_file.lower().endswith('.mid') or output_file.lower().endswith('.midi'):
            print(f"Writing MIDI: {output_file}")
            write_midi(output_file, midi_tracks, bpm=bpm)
        else:
            print(f"Writing WAV: {output_file}")
            write_wav(output_file, (left, right), stereo=True)

    print(f"Done! Duration: {len(left)/SAMPLE_RATE:.2f}s")
    return 0


def cmd_note(args):
    note_name = args.note
    duration = args.duration
    output_file = args.output
    wave = args.wave or "sine"
    bpm = args.bpm

    instrument = None
    if args.instrument:
        instrument = get_instrument(args.instrument)
        print(f"Using instrument: {args.instrument}")

    print(f"Generating note: {note_name} ({note_name_to_frequency(note_name):.2f} Hz)")
    freq = note_name_to_frequency(note_name)

    if freq <= 0:
        print(f"Error: Invalid note '{note_name}'")
        return 1

    samples = render_single_note(freq, duration, 0.7, instrument, wave)

    if args.vibrato:
        samples = apply_vibrato(samples)
    if args.echo:
        samples = apply_echo(samples)
    if args.reverb:
        samples = apply_reverb(samples)

    if output_file:
        print(f"Writing WAV: {output_file}")
        write_wav(output_file, samples)

    print("\nWaveform preview:")
    print(ascii_waveform(samples, width=80, height=15))

    print("\nSpectrum analysis:")
    freqs = spectrum_analysis(samples, top_n=5)
    for i, (f, m) in enumerate(freqs):
        print(f"  {i+1}. {f:.1f} Hz (mag={m:.3f})")

    return 0


def cmd_chord(args):
    chord_name = args.chord
    duration = args.duration
    output_file = args.output
    octave = args.octave

    freqs = chord_to_frequencies(chord_name, octave)
    midis = chord_to_midi_notes(chord_name, octave)

    if not freqs:
        print(f"Error: Invalid chord '{chord_name}'")
        return 1

    print(f"Chord: {chord_name} (octave {octave})")
    print(f"Notes: {midis} -> {[f'{f:.1f}Hz' for f in freqs]}")

    instrument = None
    if args.instrument:
        instrument = get_instrument(args.instrument)

    chord_ev = ChordEvent(
        frequencies=freqs,
        midi_notes=midis,
        duration=duration,
        volume=0.7,
        arpeggio=args.arpeggio,
        arpeggio_pattern=args.pattern,
        arpeggio_speed=args.speed
    )

    if args.arpeggio:
        print(f"Arpeggio pattern: {args.pattern}, speed: {args.speed}")

    samples = render_chord_event(chord_ev, args.wave or 'sine', instrument)

    if output_file:
        print(f"Writing WAV: {output_file}")
        write_wav(output_file, samples)

    print("\nWaveform preview:")
    print(ascii_waveform(samples, width=80, height=10))
    return 0


class LiveAudioPlayer:
    def __init__(self, instrument_name='piano'):
        self.active_voices = {}
        self.voice_counter = 0
        self.sample_rate = SAMPLE_RATE
        self.buffer_size = 1024
        self.running = False
        self.audio_thread = None
        self.output_module = None
        self.stream = None
        self.voices_lock = threading.Lock()
        self.instrument_name = instrument_name
        self.instrument = get_instrument(instrument_name)

    def start(self):
        try:
            import pyaudio
            self.output_module = pyaudio
            p = pyaudio.PyAudio()
            self.stream = p.open(
                format=pyaudio.paFloat32,
                channels=1,
                rate=self.sample_rate,
                output=True,
                frames_per_buffer=self.buffer_size
            )
            self.running = True
            self.audio_thread = threading.Thread(target=self._audio_loop, daemon=True)
            self.audio_thread.start()
            return True
        except ImportError:
            print("  Warning: pyaudio not installed. Live audio disabled.")
            print("  Install with: pip install pyaudio")
            self.running = False
            return False

    def stop(self):
        self.running = False
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass

    def note_on(self, midi_note, frequency, volume=0.7):
        with self.voices_lock:
            self.voice_counter += 1
            voice_id = self.voice_counter
            self.active_voices[voice_id] = {
                'midi_note': midi_note,
                'frequency': frequency,
                'volume': volume,
                'phase': 0.0,
                'mod_phase': 0.0,
                'state': 'attack',
                'env_level': 0.0,
                'adsr': ADSR(**self.instrument.get_adsr_kwargs()),
                'note_on_time': 0,
                'released': False
            }
            return voice_id

    def note_off(self, voice_id):
        with self.voices_lock:
            if voice_id in self.active_voices:
                self.active_voices[voice_id]['released'] = True

    def _generate_voice_sample(self, voice):
        freq = voice['frequency']
        vol = voice['volume']
        voice['note_on_time'] += 1

        if self.instrument.is_fm():
            fm_params = self.instrument.fm_params
            mod_ratio = fm_params.get('mod_ratio', 2.0)
            mod_index = fm_params.get('mod_index', 3.0)
            mod_wave = fm_params.get('mod_wave', 'sine')
            carrier_wave = fm_params.get('carrier_wave', 'sine')

            mod_freq = freq * mod_ratio
            mod_phase_inc = 2 * math.pi * mod_freq / self.sample_rate

            if mod_wave == 'sine':
                mod_signal = math.sin(voice['mod_phase'])
            elif mod_wave == 'square':
                mod_signal = 1.0 if (voice['mod_phase'] % (2 * math.pi)) < math.pi else -1.0
            else:
                mod_signal = math.sin(voice['mod_phase'])

            freq_deviation = mod_freq * mod_index * mod_signal
            instant_freq = freq + freq_deviation
            carrier_phase_inc = 2 * math.pi * instant_freq / self.sample_rate
            voice['phase'] += carrier_phase_inc
            voice['mod_phase'] += mod_phase_inc

            if carrier_wave == 'sine':
                sample = math.sin(voice['phase'])
            elif carrier_wave == 'square':
                sample = 1.0 if (voice['phase'] % (2 * math.pi)) < math.pi else -1.0
            else:
                sample = math.sin(voice['phase'])
        elif self.instrument.layer_config:
            sample = 0.0
            total_mix = 0.0
            for layer in self.instrument.layer_config:
                wt = layer.get('wave_type', 'sine')
                mix = layer.get('mix', 1.0)
                detune_cents = layer.get('detune', 0.0)
                octave_shift = layer.get('octave', 0)
                detune_ratio = 2.0 ** (detune_cents / 1200.0)
                octave_ratio = 2.0 ** (octave_shift / 12.0)
                layer_freq = freq * detune_ratio * octave_ratio

                phase_key = f'phase_{id(layer)}'
                if phase_key not in voice:
                    voice[phase_key] = 0.0
                phase_inc = 2 * math.pi * layer_freq / self.sample_rate
                voice[phase_key] += phase_inc

                if wt == 'sine':
                    layer_sample = math.sin(voice[phase_key])
                elif wt == 'square':
                    layer_sample = 1.0 if (voice[phase_key] % (2 * math.pi)) < math.pi else -1.0
                elif wt == 'sawtooth':
                    p = (voice[phase_key] % (2 * math.pi)) / (2 * math.pi)
                    layer_sample = p * 2.0 - 1.0
                elif wt == 'triangle':
                    p = (voice[phase_key] % (2 * math.pi)) / (2 * math.pi)
                    if p < 0.25:
                        layer_sample = p * 4.0
                    elif p < 0.75:
                        layer_sample = 2.0 - p * 4.0
                    else:
                        layer_sample = p * 4.0 - 4.0
                else:
                    layer_sample = math.sin(voice[phase_key])

                sample += layer_sample * mix
                total_mix += mix
            if total_mix > 0:
                sample /= total_mix
        else:
            phase_inc = 2 * math.pi * freq / self.sample_rate
            voice['phase'] += phase_inc
            wt = self.instrument.wave_types[0] if self.instrument.wave_types else 'sine'
            if wt == 'sine':
                sample = math.sin(voice['phase'])
            elif wt == 'square':
                sample = 1.0 if (voice['phase'] % (2 * math.pi)) < math.pi else -1.0
            elif wt == 'sawtooth':
                p = (voice['phase'] % (2 * math.pi)) / (2 * math.pi)
                sample = p * 2.0 - 1.0
            elif wt == 'triangle':
                p = (voice['phase'] % (2 * math.pi)) / (2 * math.pi)
                if p < 0.25:
                    sample = p * 4.0
                elif p < 0.75:
                    sample = 2.0 - p * 4.0
                else:
                    sample = p * 4.0 - 4.0
            else:
                sample = math.sin(voice['phase'])

        t = voice['note_on_time'] / self.sample_rate
        adsr = voice['adsr']
        attack_samples = int(adsr.attack * self.sample_rate)
        decay_samples = int(adsr.decay * self.sample_rate)
        release_samples = int(adsr.release * self.sample_rate)

        if voice['released']:
            if not hasattr(voice, 'release_start'):
                voice['release_start'] = voice['note_on_time']
                voice['release_level'] = voice['env_level']
            release_t = (voice['note_on_time'] - voice['release_start']) / self.sample_rate
            if release_t >= adsr.release:
                return None
            env = voice['release_level'] * (1.0 - release_t / adsr.release)
        else:
            idx = voice['note_on_time']
            if idx < attack_samples:
                env = idx / max(1, attack_samples)
            elif idx < attack_samples + decay_samples:
                decay_t = (idx - attack_samples) / max(1, decay_samples)
                env = 1.0 - (1.0 - adsr.sustain) * decay_t
            else:
                env = adsr.sustain
        voice['env_level'] = env

        return sample * vol * env

    def _audio_loop(self):
        import array
        while self.running:
            buffer_samples = []
            for _ in range(self.buffer_size):
                mixed = 0.0
                with self.voices_lock:
                    finished = []
                    for vid, voice in self.active_voices.items():
                        s = self._generate_voice_sample(voice)
                        if s is None:
                            finished.append(vid)
                        else:
                            mixed += s
                    for vid in finished:
                        del self.active_voices[vid]
                buffer_samples.append(max(-1.0, min(1.0, mixed)))

            try:
                if self.stream and self.output_module:
                    audio_data = array.array('f', buffer_samples).tobytes()
                    self.stream.write(audio_data)
            except Exception:
                pass


def cmd_play_live(args):
    print_keyboard_layout()
    print(f"Instrument: {args.instrument}")
    print(f"Available instruments: {', '.join(list_instruments())}")

    player = LiveAudioPlayer(instrument_name=args.instrument)
    audio_available = player.start()

    key_to_voice = {}

    def on_note_on(press):
        if audio_available:
            vid = player.note_on(press.midi_note, press.frequency, 0.7)
            key_to_voice[press.key] = vid

    def on_note_off(press):
        if audio_available and press.key in key_to_voice:
            player.note_off(key_to_voice.pop(press.key))

    kb = LiveKeyboard(on_note_on=on_note_on, on_note_off=on_note_off)
    kb.run()

    player.stop()

    if kb.recorded_notes:
        save = input("\n  Save recording? (y/n/m for MML, w for WAV): ").strip().lower()
        if save in ('y', 'm'):
            default_name = time.strftime("recording_%Y%m%d_%H%M%S.txt")
            filename = input(f"  Filename [{default_name}]: ").strip() or default_name
            kb.save_recorded_mml(filename, bpm=args.bpm)
            print(f"  Saved MML to: {filename}")
        elif save == 'w':
            default_name = time.strftime("recording_%Y%m%d_%H%M%S.wav")
            filename = input(f"  Filename [{default_name}]: ").strip() or default_name
            render_live_recording(kb, args.instrument, filename, args.bpm)
            print(f"  Saved WAV to: {filename}")

    return 0


def render_live_recording(kb, instrument_name, output_file, bpm=120):
    instrument = get_instrument(instrument_name)
    beat_duration = 60.0 / bpm

    if not kb.recorded_notes:
        return

    max_end_time = max(p.release_time or p.timestamp for p in kb.recorded_notes)
    total_duration = max_end_time + 0.5
    n_total = int(total_duration * SAMPLE_RATE)
    samples = [0.0] * n_total

    for press in kb.recorded_notes:
        if press.duration <= 0:
            continue
        start_idx = int(press.timestamp * SAMPLE_RATE)
        note_samples = render_single_note(
            press.frequency, press.duration, 0.7, instrument, 'sine'
        )
        for i, s in enumerate(note_samples):
            if start_idx + i < n_total:
                samples[start_idx + i] += s

    max_val = max(abs(max(samples)), abs(min(samples))) if samples else 1.0
    if max_val > 1.0:
        samples = [s / max_val for s in samples]

    write_wav(output_file, samples)


def cmd_analyze(args):
    input_file = args.input

    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found.")
        return 1

    print(f"Analyzing: {input_file}")
    samples, sr, channels = read_wav(input_file)

    print(f"Sample rate: {sr} Hz")
    print(f"Channels: {channels}")
    print(f"Duration: {len(samples)/sr:.2f}s")

    peak = max(abs(max(samples)), abs(min(samples)))
    print(f"Peak amplitude: {peak:.4f}")

    print("\nWaveform preview:")
    print(ascii_waveform(samples, width=80, height=15))

    print("\nSpectrum analysis (top frequencies):")
    freqs = spectrum_analysis(samples, sample_rate=sr, top_n=10)
    for i, (f, m) in enumerate(freqs):
        print(f"  {i+1}. {f:8.1f} Hz  magnitude={m:.4f}")

    print("\nSpectrum:")
    all_freqs = spectrum_analysis(samples, sample_rate=sr, top_n=200)
    print(ascii_spectrum(all_freqs, width=70, max_freq=min(4000, sr // 2)))

    return 0


def cmd_list_instruments(args):
    print("Available instruments:")
    for name in list_instruments():
        inst = get_instrument(name)
        wave_info = '/'.join(inst.wave_types)
        fm_info = " (FM)" if inst.is_fm() else ""
        print(f"  @{name:<20} waves=[{wave_info}]{fm_info}")
    print("\nFM syntax: @fm:<ratio>:<index>[:<carrier_wave>[:<mod_wave>]]")
    print("  Example: @fm:2:3.5  @fm:3.5:5:sawtooth:sine")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Terminal Audio Synthesizer")
    subparsers = parser.add_subparsers(dest="command")

    play_parser = subparsers.add_parser("play", help="Play a song file")
    play_parser.add_argument("song", help="Song text file")
    play_parser.add_argument("-o", "--output", help="Output WAV/MIDI file")
    play_parser.add_argument("--bpm", type=int, default=120, help="Tempo in BPM")
    play_parser.add_argument("--wave", help="Override wave type (sine/square/triangle/sawtooth/noise)")

    note_parser = subparsers.add_parser("note", help="Generate a single note")
    note_parser.add_argument("note", help="Note name (e.g., C4, A4)")
    note_parser.add_argument("duration", type=float, help="Duration in seconds")
    note_parser.add_argument("-o", "--output", help="Output WAV file")
    note_parser.add_argument("--wave", default="sine", help="Wave type")
    note_parser.add_argument("--bpm", type=int, default=120)
    note_parser.add_argument("--instrument", "-i", help="Instrument preset name")
    note_parser.add_argument("--vibrato", action="store_true")
    note_parser.add_argument("--echo", action="store_true")
    note_parser.add_argument("--reverb", action="store_true")

    chord_parser = subparsers.add_parser("chord", help="Generate a chord")
    chord_parser.add_argument("chord", help="Chord name (e.g., Cmaj, Am, G7, Bdim7)")
    chord_parser.add_argument("duration", type=float, help="Duration in seconds")
    chord_parser.add_argument("-o", "--output", help="Output WAV file")
    chord_parser.add_argument("--wave", default="sine", help="Wave type")
    chord_parser.add_argument("--octave", type=int, default=4, help="Root octave")
    chord_parser.add_argument("--instrument", "-i", help="Instrument preset name")
    chord_parser.add_argument("--arpeggio", "-a", action="store_true", help="Play as arpeggio")
    chord_parser.add_argument("--pattern", "-p", default="up", choices=["up", "down", "alternate"], help="Arpeggio pattern")
    chord_parser.add_argument("--speed", "-s", type=float, default=1.0, help="Arpeggio speed")

    live_parser = subparsers.add_parser("play-live", help="Live keyboard performance")
    live_parser.add_argument("--instrument", "-i", default="piano", help="Instrument preset name")
    live_parser.add_argument("--bpm", type=int, default=120, help="Recording BPM")

    analyze_parser = subparsers.add_parser("analyze", help="Analyze a WAV file")
    analyze_parser.add_argument("input", help="Input WAV file")

    inst_parser = subparsers.add_parser("instruments", help="List available instruments")

    args = parser.parse_args()

    if args.command == "play":
        return cmd_play(args)
    elif args.command == "note":
        return cmd_note(args)
    elif args.command == "chord":
        return cmd_chord(args)
    elif args.command == "play-live":
        return cmd_play_live(args)
    elif args.command == "analyze":
        return cmd_analyze(args)
    elif args.command == "instruments":
        return cmd_list_instruments(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
