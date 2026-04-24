# PyWORLD - A Python wrapper of WORLD Vocoder

WORLD Vocoder is a fast and high-quality vocoder
which parameterizes speech into three components:

  1. `f0`: Pitch contour
  2. `sp`: Harmonic spectral envelope
  3. `ap`: Aperiodic spectral envelope (relative to the harmonic spectral envelope)

It can also (re)synthesize speech using these features (see examples below).

For more information, please visit Dr. Morise's [WORLD repository](https://github.com/mmorise/World)
and the [official website of WORLD Vocoder](http://ml.cs.yamanashi.ac.jp/world/english).

This fork tracks the [performance-optimized branch](https://github.com/BeatMagic/World/tree/perf/harvest-optimization) of WORLD, which adds a runtime-dispatched AVX-512 path for the CompositeF0 analysis pipeline (DIO + Harvest + ZCR merge) plus build-time integration with [AOCL-FFTW](https://github.com/amd/amd-fftw) — AMD's fork of FFTW 3.3.10 with AVX-512 codelets tuned for Zen4 / Zen5.


## APIs

### Vocoder Functions
```python
import pyworld as pw
_f0, t = pw.dio(x, fs)    # raw pitch extractor
f0 = pw.stonemask(x, _f0, t, fs)  # pitch refinement
sp = pw.cheaptrick(x, f0, t, fs)  # extract smoothed spectrogram
ap = pw.d4c(x, f0, t, fs)         # extract aperiodicity

y = pw.synthesize(f0, sp, ap, fs) # synthesize an utterance using the parameters
```


### Utility
```python
# Convert speech into features (using default arguments)
f0, sp, ap = pw.wav2world(x, fs)
```
<br/>

You can change the default arguments of the function, too.
See more info using `help`.


## Installation

This fork uses the [BeatMagic/World](https://github.com/BeatMagic/World/tree/perf/harvest-optimization) performance-optimized branch, which includes Harvest memory pooling, recursive oscillators, and an optional FFTW3 FFT backend.

### One-Line Install
```bash
pip install git+https://github.com/BeatMagic/Python-Wrapper-for-World-Vocoder.git
```
The build process will automatically:
1. Clone the optimized World C++ source
2. Pick an FFT backend based on the host (see below)
3. Build it from source as a static library
4. Compile the Python extension with `-O3 -ffast-math` and, where supported, per-file AVX-512 flags on `simd_kernels_avx512.cpp`

### FFT backend auto-selection

| Host                                   | Backend chosen        | Notes                                                                                          |
| :------------------------------------- | :-------------------- | :--------------------------------------------------------------------------------------------- |
| **Linux x86_64, AMD Zen5** (family 26) | **AOCL-FFTW 5.2**     | Forced — pip install fails loudly if build deps are missing (no silent fallback).              |
| Linux x86_64, AMD Zen1–Zen4            | AOCL-FFTW 5.2 if deps are present, else upstream FFTW 3.3.10 | Silent fallback OK — Zen4 double-pumps AVX-512 so the codelet win is smaller. |
| Linux x86_64, Intel / non-AMD          | upstream FFTW 3.3.10  | AOCL is AMD-tuned; we don't force it.                                                          |
| Windows / macOS / non-x86_64           | upstream FFTW 3.3.10  | AOCL is Linux-only in this wrapper.                                                            |

**AVX-512 kernels** (WORLD's runtime-dispatched SIMD path) are enabled whenever the compiler accepts `-mavx512f -mavx512dq -mavx512bw -mavx512vl -mfma -mbmi2`. If not, the library still builds and falls back to scalar at runtime. Override with `PYWORLD_AVX512=0`.

### Build dependencies for the AOCL-FFTW path

AOCL-FFTW is cloned from source during `pip install` and requires the full autotools toolchain, OCaml (for the AVX-512 codelet generator), and Texinfo (for the `doc/` subdir that FFTW's top-level `make` still builds by default):

**Ubuntu / Debian:**
```bash
sudo apt-get install -y build-essential git autoconf automake libtool-bin ocaml texinfo
```
Two gotchas worth calling out:
- On Ubuntu 22.04+ the `libtool` package does **not** install the `libtool` binary — you need `libtool-bin`.
- `texinfo` is required even though we only want the library. Without `makeinfo`, `make` fails partway through `doc/fftw3.info`. Installing `texinfo` is the cheapest fix (~10 MB); alternatively use `PYWORLD_FFT_BACKEND=fftw3` to skip AOCL entirely.

**Fedora / RHEL:**
```bash
sudo dnf install -y gcc gcc-c++ make git autoconf automake libtool ocaml texinfo
```

**Arch:**
```bash
sudo pacman -S --needed base-devel git autoconf automake libtool ocaml texinfo
```

### Skipping AOCL (fast install)

AOCL-FFTW takes 3–8 minutes to compile from source the first time. If you don't need the AVX-512 FFT win (or you just want a quick smoke test), force the upstream FFTW 3.3.10 path:

```bash
PYWORLD_FFT_BACKEND=fftw3 pip install git+https://github.com/BeatMagic/Python-Wrapper-for-World-Vocoder.git
```
Upstream FFTW builds in about 30 s and still gives you AVX2/FMA codelets. The WORLD AVX-512 kernels (the `-DWORLD_HAS_AVX512` path) remain active regardless of FFT backend choice.

Other supported values for `PYWORLD_FFT_BACKEND`:

| Value    | Effect                                                                                  |
| :------- | :-------------------------------------------------------------------------------------- |
| `auto`   | Default. Follows the table above.                                                       |
| `aocl`   | Force AOCL-FFTW. Fails with a clear error if build deps are missing.                    |
| `fftw3`  | Force upstream FFTW 3.3.10. Always works as long as `cc` is present.                    |
| `ooura`  | Use the bundled Ooura FFT. No external downloads, slowest of the three, portable.       |

### Building from Source
```bash
git clone --recurse-submodules https://github.com/BeatMagic/Python-Wrapper-for-World-Vocoder.git
cd Python-Wrapper-for-World-Vocoder
pip install .
```

### Installation Validation
```bash
cd demo
python demo.py
```

### Environment/Dependencies
- Operating systems
  - Linux Ubuntu 14.04+
  - macOS (Intel / Apple Silicon)
  - Windows (thanks to [wuaalb](https://github.com/wuaalb))
  - WSL 2 (Zen5 auto-detection requires `/proc/cpuinfo`, so WSL 1 is not supported for the AOCL path)
- Python 3.7+
- A C++ compiler (Xcode CLT on macOS, `build-essential` on Linux) with AVX-512 flag support (GCC ≥ 5, Clang ≥ 3.9) for the AVX-512 kernels
- For the AOCL-FFTW backend only: `autoconf`, `automake`, `libtool-bin`, `ocaml`, `texinfo`, `make`, `git` (see the "Build dependencies for the AOCL-FFTW path" section above)



## Notice
- WORLD vocoder is designed for speech sampled ≥ 16 kHz.
  Applying WORLD to 8 kHz speech will fail.
  See a possible workaround [here](https://github.com/JeremyCCHsu/Python-Wrapper-for-World-Vocoder/issues/54).
- When the SNR is low, extracting pitch using `harvest` instead of `dio`
  is a better option.


## Troubleshooting
1. Upgrade your Cython version to 0.24.<br/>
   (I failed to build it on Cython 0.20.1post0)<br/>
   It'll require you to download Cython form http://cython.org/<br/>
   Unzip it, and `python setup.py install` it.<br/>
   (I tried `pip install Cython` but the upgrade didn't seem correct)<br/>
   (Again, add `--user` if you don't have root access.)
2. Upon executing `demo/demo.py`, the following code might be needed in some environments (e.g. when you're working on a remote Linux server):<br/>

 ```python
 import matplotlib
 matplotlib.use('Agg')
 ```
3. If you encounter `library not found: sndfile` error upon executing `demo.py`,
   you might have to install it by `apt-get install libsoundfile1`.
   You can also replace `pysoundfile` with `scipy` or `librosa`, but some modification is needed:
   - librosa:
     - load(fiilename, dtype=np.float64)
     - output.write_wav(filename, wav, fs)
     - remember to pass `dtype` argument to ensure that the method gives you a `double`.
   - scipy:
     - You'll have to write a customized utility function based on the following methods
     - scipy.io.wavfile.read (but this gives you `short`)
     - scipy.io.wavfile.write

4. If you have installation issue on Windows, I probably could not provide
   much help because my development environment is Ubuntu
   and Windows Subsystem for Linux ([read this if you are interested in installing it](https://github.com/JeremyCCHsu/wsl)).


### Other Installation Suggestions
1. For Mac users: You might need to do `MACOSX_DEPLOYMENT_TARGET=10.9 pip install .` See [issue](https://github.com/SeanNaren/warp-ctc/issues/129#issuecomment-502349652).
2. If you just want to try out some experiments, execute<br/>
  `python setup.py build_ext --inplace`<br/>
  Then you can use PyWorld from this directory.<br/>
  Alternatively you can copy/symlink the compiled files using pip, e.g. `pip install -e .`



## Acknowledgement
Thank all contributors ([tats-u](https://github.com/tats-u), [wuaalb](https://github.com/wuaalb), [r9y9](https://github.com/r9y9), [rikrd](https://github.com/rikrd), [kudan2510](https://github.com/kundan2510)) for making this repo better and [sotelo](https://github.com/sotelo) whose [world.py](https://github.com/sotelo/world.py) inspired this repo.<br/>
