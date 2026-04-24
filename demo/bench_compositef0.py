#!/usr/bin/env python3
"""
CompositeF0 bench for pyworld: measures the end-to-end F0 extraction time
from the Python side (so any binding / GIL-release cost is captured).

Usage:
    python demo/bench_compositef0.py [--audio PATH] [--runs N] [--warmup K]
    python demo/bench_compositef0.py --compare  # toggle AVX-512 off via env var

Runs AOCL-FFTW / AVX-512 tiers implicitly based on how the wheel was built.
Set WORLD_FORCE_SIMD_TIER=scalar to force scalar for a side-by-side comparison
(requires exporting it BEFORE Python imports pyworld, since WORLD reads the env
var once at library init time).
"""
from __future__ import print_function

import argparse
import os
import platform
import sys
import time

import numpy as np
import soundfile as sf

import pyworld as pw


def _print_env():
    print('[env]')
    print('  python:        {}'.format(sys.version.split()[0]))
    print('  numpy:         {}'.format(np.__version__))
    print('  platform:      {} {}'.format(platform.system(), platform.machine()))
    print('  pyworld:       {}'.format(getattr(pw, '__version__', '?')))
    for key in ('WORLD_FORCE_SIMD_TIER', 'WORLD_AVX512_DISABLE',
                'PYWORLD_FFT_BACKEND', 'PYWORLD_AVX512'):
        v = os.environ.get(key)
        if v:
            print('  {}={}'.format(key, v))


def _cpu_brand():
    if platform.system() == 'Linux':
        try:
            with open('/proc/cpuinfo') as f:
                for line in f:
                    if line.startswith('model name'):
                        return line.split(':', 1)[1].strip()
        except OSError:
            pass
    return platform.processor() or 'unknown'


def bench(audio_path, runs, warmup, frame_period, f0_floor, f0_ceil):
    x, fs = sf.read(audio_path)
    if x.ndim > 1:
        x = x.mean(axis=1)
    x = np.ascontiguousarray(x.astype(np.float64))

    print('[input]')
    print('  audio:         {}'.format(audio_path))
    print('  fs:            {} Hz  duration: {:.3f} s  samples: {}'.format(
        fs, len(x) / fs, len(x)))
    print('  frame_period:  {} ms'.format(frame_period))
    print('  CPU:           {}'.format(_cpu_brand()))
    _print_env()

    for _ in range(warmup):
        pw.compositef0(x, fs, f0_floor=f0_floor, f0_ceil=f0_ceil,
                       frame_period=frame_period)

    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        f0, tpos = pw.compositef0(x, fs, f0_floor=f0_floor, f0_ceil=f0_ceil,
                                  frame_period=frame_period)
        times.append(time.perf_counter() - t0)

    best = min(times) * 1000.0
    avg = (sum(times) / len(times)) * 1000.0
    worst = max(times) * 1000.0
    voiced = int((f0 > 0).sum())
    print('\n[bench]')
    print('  runs:          {} (best-of)   warmup: {}'.format(runs, warmup))
    print('  total_ms best: {:.3f}'.format(best))
    print('  total_ms avg:  {:.3f}'.format(avg))
    print('  total_ms worst:{:.3f}'.format(worst))
    print('  frames:        {}  voiced: {}'.format(len(f0), voiced))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--audio', default='demo/utterance/vaiueo2d.wav')
    ap.add_argument('--runs', type=int, default=10)
    ap.add_argument('--warmup', type=int, default=3)
    ap.add_argument('--frame-period', type=float, default=5.0)
    ap.add_argument('--f0-floor', type=float, default=50.0)
    ap.add_argument('--f0-ceil', type=float, default=1100.0)
    args = ap.parse_args()
    bench(args.audio, args.runs, args.warmup, args.frame_period,
          args.f0_floor, args.f0_ceil)


if __name__ == '__main__':
    main()
