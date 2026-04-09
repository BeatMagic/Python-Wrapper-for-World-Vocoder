# PyWORLD - A Python wrapper of WORLD Vocoder

WORLD Vocoder is a fast and high-quality vocoder
which parameterizes speech into three components:

  1. `f0`: Pitch contour
  2. `sp`: Harmonic spectral envelope
  3. `ap`: Aperiodic spectral envelope (relative to the harmonic spectral envelope)

It can also (re)synthesize speech using these features (see examples below).

For more information, please visit Dr. Morise's [WORLD repository](https://github.com/mmorise/World)
and the [official website of WORLD Vocoder](http://ml.cs.yamanashi.ac.jp/world/english).

This fork uses the [performance-optimized branch](https://github.com/BeatMagic/World/tree/perf/harvest-optimization) with FFTW3 support and Harvest optimizations.


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
2. Download and compile [FFTW3](https://www.fftw.org/) from source as a static library
3. Build the Python extension with `-O3 -ffast-math` optimization flags

### FFT Backend Selection
By default the FFTW3 backend is used. To use the built-in Ooura FFT instead (no external dependencies):
```bash
PYWORLD_FFT_BACKEND=ooura pip install git+https://github.com/BeatMagic/Python-Wrapper-for-World-Vocoder.git
```

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
  - WSL
- Python 3.7+
- A C++ compiler (Xcode CLT on macOS, `build-essential` on Linux)



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
