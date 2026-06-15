#!/usr/bin/env python3
import sys
import argparse
import os

from oscillators import generate_wave, ADSR, SAMPLE_RATE
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
    apply_lowpass, apply_highpass
)
from output import write_wav, write_midi
from analyzer import (
    read_wav, ascii_waveform,
    spectrum_analysis, ascii_spectrum
)


def render_track(track_data, adsr=None, effects=None):
    if adsr is None:
        adsr = ADSR(attack=0.01, decay=0.05, sustain=0.7, release=0.1)

    merged_events = merge_tied_notes(track_data.events)

    total_duration = 0.0
    for ev in merged_events:
        total_duration += ev.duration

    n_total = int(total_duration * SAMPLE_RATE)
    samples = [0.0] * n_total

    current_idx = 0

    for event in merged_events:
        if event.is_rest or event.frequency <= 0:
            current_idx += int(event.duration * SAMPLE_RATE)
            continue

        note_samples = generate_wave(track_data.wave_type, event.frequency, event.duration)
        note_samples = adsr.apply(note_samples, event.duration)

        vol = event.volume
        note_samples = [s * vol for s in note_samples]

        if effects:
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

        print(f"  Track {i+1}: {td.name} (wave={td.wave_type}, vol={td.volume}, pan={td.pan})")
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

    print(f"Generating note: {note_name} ({note_name_to_frequency(note_name):.2f} Hz)")
    freq = note_name_to_frequency(note_name)

    if freq <= 0:
        print(f"Error: Invalid note '{note_name}'")
        return 1

    adsr = ADSR()
    samples = generate_wave(wave, freq, duration)
    samples = adsr.apply(samples, duration)

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
    note_parser.add_argument("--vibrato", action="store_true")
    note_parser.add_argument("--echo", action="store_true")
    note_parser.add_argument("--reverb", action="store_true")

    analyze_parser = subparsers.add_parser("analyze", help="Analyze a WAV file")
    analyze_parser.add_argument("input", help="Input WAV file")

    args = parser.parse_args()

    if args.command == "play":
        return cmd_play(args)
    elif args.command == "note":
        return cmd_note(args)
    elif args.command == "analyze":
        return cmd_analyze(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
