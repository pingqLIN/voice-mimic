from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(slots=True)
class AudioDeviceInfo:
    index: int
    name: str
    max_input_channels: int
    max_output_channels: int
    default_samplerate: float


def list_audio_devices() -> list[AudioDeviceInfo]:
    sounddevice = _load_sounddevice()
    devices = sounddevice.query_devices()
    return [
        AudioDeviceInfo(
            index=index,
            name=str(device["name"]),
            max_input_channels=int(device["max_input_channels"]),
            max_output_channels=int(device["max_output_channels"]),
            default_samplerate=float(device["default_samplerate"]),
        )
        for index, device in enumerate(devices)
    ]


def generate_log_sweep(
    sample_rate: int,
    duration_seconds: int,
    *,
    start_hz: float = 20.0,
    end_hz: float = 20_000.0,
    amplitude: float = 0.5,
    leading_silence_seconds: float = 0.25,
    trailing_silence_seconds: float = 0.75,
) -> np.ndarray:
    sweep_samples = int(sample_rate * duration_seconds)
    time_axis = np.linspace(0.0, duration_seconds, sweep_samples, endpoint=False)
    sweep = amplitude * np.sin(
        2.0
        * np.pi
        * start_hz
        * duration_seconds
        / np.log(end_hz / start_hz)
        * (np.exp(time_axis * np.log(end_hz / start_hz) / duration_seconds) - 1.0)
    )
    leading = np.zeros(int(sample_rate * leading_silence_seconds), dtype=np.float32)
    trailing = np.zeros(int(sample_rate * trailing_silence_seconds), dtype=np.float32)
    return np.concatenate([leading, sweep.astype(np.float32), trailing]).astype(np.float32)


def record_room_noise(
    sample_rate: int,
    duration_seconds: float,
    *,
    input_device: int | str | None = None,
    channels: int = 1,
) -> np.ndarray:
    sounddevice = _load_sounddevice()
    frames = int(sample_rate * duration_seconds)
    recording = sounddevice.rec(
        frames=frames,
        samplerate=sample_rate,
        channels=channels,
        dtype="float32",
        device=input_device,
    )
    sounddevice.wait()
    return _to_mono(np.asarray(recording))


def play_and_record(
    playback_signal: np.ndarray,
    sample_rate: int,
    *,
    input_device: int | str | None = None,
    output_device: int | str | None = None,
    input_channels: int = 1,
) -> np.ndarray:
    sounddevice = _load_sounddevice()
    mono_signal = _to_mono(np.asarray(playback_signal, dtype=np.float32))
    playback_buffer = mono_signal.reshape(-1, 1)
    device: int | str | tuple[int | str | None, int | str | None] | None = None
    if input_device is not None or output_device is not None:
        device = (input_device, output_device)
    recording = sounddevice.playrec(
        playback_buffer,
        samplerate=sample_rate,
        channels=input_channels,
        dtype="float32",
        device=device,
        input_mapping=None,
        output_mapping=None,
    )
    sounddevice.wait()
    return _to_mono(np.asarray(recording))


def write_wav(path: Path, samples: np.ndarray, sample_rate: int) -> None:
    soundfile = _load_soundfile()
    path.parent.mkdir(parents=True, exist_ok=True)
    soundfile.write(str(path), _to_mono(np.asarray(samples, dtype=np.float32)), sample_rate)


def estimate_latency_ms(playback_signal: np.ndarray, captured_signal: np.ndarray, sample_rate: int) -> float:
    playback = _to_mono(np.asarray(playback_signal, dtype=np.float32))
    captured = _to_mono(np.asarray(captured_signal, dtype=np.float32))
    correlation = np.correlate(captured, playback, mode="full")
    lag = int(np.argmax(correlation) - (len(playback) - 1))
    return max(0.0, lag * 1000.0 / sample_rate)


def estimate_noise_floor_dbfs(noise_signal: np.ndarray) -> float:
    noise = _to_mono(np.asarray(noise_signal, dtype=np.float32))
    rms = float(np.sqrt(np.mean(np.square(noise))) + 1e-12)
    return float(20.0 * np.log10(rms))


def estimate_frequency_tilt_db(playback_signal: np.ndarray, captured_signal: np.ndarray, sample_rate: int) -> float:
    playback = _to_mono(np.asarray(playback_signal, dtype=np.float32))
    captured = _to_mono(np.asarray(captured_signal, dtype=np.float32))
    aligned = _align_capture_to_playback(playback, captured, sample_rate)
    playback_fft = np.fft.rfft(playback)
    aligned_fft = np.fft.rfft(aligned)
    freqs = np.fft.rfftfreq(len(playback), d=1.0 / sample_rate)

    low_mask = (freqs >= 100.0) & (freqs <= 500.0)
    high_mask = (freqs >= 2_000.0) & (freqs <= 8_000.0)
    playback_low = _safe_band_energy(playback_fft, low_mask)
    playback_high = _safe_band_energy(playback_fft, high_mask)
    capture_low = _safe_band_energy(aligned_fft, low_mask)
    capture_high = _safe_band_energy(aligned_fft, high_mask)

    low_ratio_db = 20.0 * np.log10((capture_low / playback_low) + 1e-12)
    high_ratio_db = 20.0 * np.log10((capture_high / playback_high) + 1e-12)
    return float(high_ratio_db - low_ratio_db)


def derive_eq_profile(
    frequency_tilt_db: float,
    *,
    max_boost_db: float,
    max_cut_db: float,
) -> dict[str, float]:
    low_shelf = float(np.clip(-frequency_tilt_db * 0.5, -max_cut_db, max_boost_db))
    presence = float(np.clip(frequency_tilt_db * 0.35, -max_cut_db, max_boost_db))
    return {"low_shelf_db": low_shelf, "presence_db": presence}


def simulate_room_capture(
    playback_signal: np.ndarray,
    sample_rate: int,
    *,
    latency_ms: float = 48.0,
    frequency_tilt_db: float = 2.0,
    noise_floor: float = 0.003,
) -> np.ndarray:
    playback = _to_mono(np.asarray(playback_signal, dtype=np.float32))
    lag = int(sample_rate * latency_ms / 1000.0)
    kernel = _simple_room_kernel(sample_rate, frequency_tilt_db)
    shaped = np.convolve(playback, kernel, mode="full")[: len(playback)]
    padded = np.concatenate([np.zeros(lag, dtype=np.float32), shaped]).astype(np.float32)
    padded = padded[: len(playback)] if len(padded) >= len(playback) else np.pad(
        padded, (0, len(playback) - len(padded))
    )
    noise = np.random.default_rng(7).normal(0.0, noise_floor, size=len(playback)).astype(np.float32)
    return (padded + noise).astype(np.float32)


def _align_capture_to_playback(
    playback_signal: np.ndarray, captured_signal: np.ndarray, sample_rate: int
) -> np.ndarray:
    lag_ms = estimate_latency_ms(playback_signal, captured_signal, sample_rate=sample_rate)
    lag = int(sample_rate * lag_ms / 1000.0)
    if lag <= 0:
        aligned = captured_signal[: len(playback_signal)]
    else:
        aligned = captured_signal[lag : lag + len(playback_signal)]
    if len(aligned) < len(playback_signal):
        aligned = np.pad(aligned, (0, len(playback_signal) - len(aligned)))
    return aligned.astype(np.float32)


def _safe_band_energy(spectrum: np.ndarray, mask: np.ndarray) -> float:
    values = np.abs(spectrum[mask])
    return float(np.mean(values) + 1e-12)


def _simple_room_kernel(sample_rate: int, frequency_tilt_db: float) -> np.ndarray:
    taps = np.array([1.0, 0.25, 0.1], dtype=np.float32)
    high_boost = np.clip(frequency_tilt_db / 12.0, -0.5, 0.5)
    taps[1] += high_boost * 0.15
    taps[2] += high_boost * 0.1
    return taps / np.sum(np.abs(taps))


def _to_mono(signal: np.ndarray) -> np.ndarray:
    if signal.ndim == 1:
        return signal.astype(np.float32)
    return np.mean(signal, axis=1, dtype=np.float32)


def _load_sounddevice() -> Any:
    try:
        import sounddevice
    except ImportError as exc:
        raise RuntimeError(
            "sounddevice is required for the live audio backend. "
            "Install project dependencies with `uv sync` first."
        ) from exc
    return sounddevice


def _load_soundfile() -> Any:
    try:
        import soundfile
    except ImportError as exc:
        raise RuntimeError(
            "soundfile is required for the live audio backend. "
            "Install project dependencies with `uv sync` first."
        ) from exc
    return soundfile
