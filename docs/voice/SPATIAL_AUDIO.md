# Spatial Audio

Spatial audio gives each lady a consistent place around the listener.
That matters for accessibility: when voices come from stable directions, it is easier
to tell **who** is speaking even before the sentence finishes.

## How positioning works

The spatial router uses `SpatialPosition` in `src/agentic_brain/audio/spatial_audio.py`.
Each position has:

- **azimuth**: horizontal angle around the listener
- **elevation**: vertical offset
- **distance**: relative distance for slight attenuation

Azimuth uses this model:

- `0°` = directly in front
- `90°` = right side
- `180°` = directly behind
- `270°` = left side

## Lady positions

| Lady | Azimuth | Arc |
| --- | ---: | --- |
| Karen | 0° | front center |
| Kyoko | 30° | front-right |
| Tingting | 55° | right-front |
| Yuna | 80° | right |
| Linh | 110° | right-back |
| Kanya | 140° | back-right |
| Dewi | 165° | back |
| Sari | 180° | directly behind |
| Wayan | 195° | back-left |
| Moira | 225° | left-back |
| Alice | 255° | left |
| Zosia | 285° | left-front |
| Flo | 315° | front-left |
| Shelley | 345° | front-left, near center |

## Backend options

The router automatically chooses the best backend in this order.

### 1. `native`

Used when:

- the Swift bridge is present
- Apple tooling is available
- a supported AirPods device is connected

What it gives you:

- full 3D placement
- head-tracking support
- scene configuration through `AirPodsManager`

### 2. `sox`

Used when:

- `sox`, `say`, and `afplay` are available
- native AirPods spatial audio is not active

What it gives you:

- left/right placement only
- wide headphone compatibility
- no head tracking

### 3. `mono`

Used when:

- advanced audio tooling is unavailable

What it gives you:

- plain speech
- no directional placement
- safest fallback path

## Backend selection

```python
from agentic_brain.audio.spatial_audio import SpatialAudioRouter

router = SpatialAudioRouter()              # auto-detect
router_native = SpatialAudioRouter(force_backend="native")
router_sox = SpatialAudioRouter(force_backend="sox")
router_mono = SpatialAudioRouter(force_backend="mono")
```

## AirPods Pro Max support

`src/agentic_brain/audio/airpods.py` adds support for:

- AirPods detection
- output routing
- battery reporting
- noise-control modes
- head-tracking pose data
- spatial scene configuration

Supported noise-control modes:

- `off`
- `noise_cancellation`
- `transparency`
- `adaptive`

Supported head-tracking modes:

- `off`
- `fixed`
- `follow_head`

## Status and diagnostics

```python
from agentic_brain.audio.spatial_audio import get_spatial_router

router = get_spatial_router()
print(router.status())
```

Useful fields include:

- active backend
- whether AirPods are connected
- whether the native bridge is available
- scratch directory path
- full lady position map

## Stereo panning details

`src/agentic_brain/audio/stereo_pan.py` also defines a simpler left/right map.
That map uses values from `-1.0` to `+1.0`.

Examples:

- Karen: `0.0`
- Tingting: `0.40`
- Kanya: `0.80`
- Sari: `-0.90`
- Zosia: `-0.75`

This is simpler than the 0-360° spatial ring and works with ordinary stereo output.

## Configuration

| Setting | Default | Purpose |
| --- | --- | --- |
| `AGENTIC_BRAIN_STEREO_PAN_ENABLED` | `true` | Enable stereo panning |
| `AGENTIC_BRAIN_STEREO_PAN_DIR` | repo `.cache/stereo_pan` | Panned file cache |
| `AGENTIC_BRAIN_AUDIO_SCRATCH` | `~/.cache/agentic-brain/spatial` | Spatial rendering scratch area |

## Example

```python
from agentic_brain.audio.spatial_audio import speak_spatial

speak_spatial("Tingting is reviewing the pull request.", lady="Tingting", rate=155)
```

## Troubleshooting

- If audio is centered instead of positioned, check which backend is active.
- If you expected AirPods spatial mode, confirm the Swift bridge is available and the device is connected.
- If `sox` is missing, the router falls back to mono.
- If you need stable behavior for debugging, force the backend explicitly.

See [Troubleshooting](./TROUBLESHOOTING.md) for overlap, lock, and backend issues.
