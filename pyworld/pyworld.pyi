import numpy as np
from numpy.typing import NDArray

default_frame_period: float
default_f0_floor: float
default_f0_ceil: float

def dio(
    x: NDArray[np.float64],
    fs: int,
    f0_floor: float = ...,
    f0_ceil: float = ...,
    channels_in_octave: float = ...,
    frame_period: float = ...,
    speed: int = ...,
    allowed_range: float = ...,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]: ...

def harvest(
    x: NDArray[np.float64],
    fs: int,
    f0_floor: float = ...,
    f0_ceil: float = ...,
    frame_period: float = ...,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]: ...

def compositef0(
    x: NDArray[np.float64],
    fs: int,
    f0_floor: float = ...,
    f0_ceil: float = ...,
    frame_period: float = ...,
    zcr_frame_length: int = ...,
    zcr_threshold: float = ...,
    gaussian_sigma: float = ...,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]: ...

def stonemask(
    x: NDArray[np.float64],
    f0: NDArray[np.float64],
    temporal_positions: NDArray[np.float64],
    fs: int,
) -> NDArray[np.float64]: ...

def get_cheaptrick_fft_size(
    fs: int,
    f0_floor: float = ...,
) -> int: ...

def get_cheaptrick_f0_floor(
    fs: int,
    fft_size: int,
) -> float: ...

def cheaptrick(
    x: NDArray[np.float64],
    f0: NDArray[np.float64],
    temporal_positions: NDArray[np.float64],
    fs: int,
    q1: float = ...,
    f0_floor: float = ...,
    fft_size: int | None = ...,
) -> NDArray[np.float64]: ...

def d4c(
    x: NDArray[np.float64],
    f0: NDArray[np.float64],
    temporal_positions: NDArray[np.float64],
    fs: int,
    threshold: float = ...,
    fft_size: int | None = ...,
) -> NDArray[np.float64]: ...

def synthesize(
    f0: NDArray[np.float64],
    spectrogram: NDArray[np.float64],
    aperiodicity: NDArray[np.float64],
    fs: int,
    frame_period: float = ...,
) -> NDArray[np.float64]: ...

def get_num_aperiodicities(fs: int) -> int: ...

def code_aperiodicity(
    aperiodicity: NDArray[np.float64],
    fs: int,
) -> NDArray[np.float64]: ...

def decode_aperiodicity(
    coded_aperiodicity: NDArray[np.float64],
    fs: int,
    fft_size: int,
) -> NDArray[np.float64]: ...

def code_spectral_envelope(
    spectrogram: NDArray[np.float64],
    fs: int,
    number_of_dimensions: int,
) -> NDArray[np.float64]: ...

def decode_spectral_envelope(
    coded_spectral_envelope: NDArray[np.float64],
    fs: int,
    fft_size: int,
) -> NDArray[np.float64]: ...

def wav2world(
    x: NDArray[np.float64],
    fs: int,
    fft_size: int | None = ...,
    frame_period: float = ...,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]: ...
