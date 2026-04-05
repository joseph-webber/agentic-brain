# Voice emotions

Voice personas can now add simple emotional expression to serialized speech.

## Supported emotions

- `neutral` - default calm baseline
- `happy` - positive news
- `concerned` - warnings and issues
- `excited` - celebrations and achievements
- `calm` - meditation and wellness moments
- `professional` - work mode default
- `friendly` - casual conversation
- `urgent` - critical alerts

## How it works

`agentic_brain.voice.emotions` defines the core `VoiceEmotion` enum, the default
emotion prosody parameters, and `apply_emotion()` for adjusting a `VoiceConfig`.

`agentic_brain.voice.expression.ExpressionEngine` adds context:

- keyword-based emotion detection
- work mode bias toward `professional`
- per-voice styling such as Kanya staying calm and Yuna sounding more excited

## Serializer support

`speak_serialized()` now accepts `emotion=None`.

- If `emotion` is omitted, the expression engine auto-detects it.
- The serializer adjusts speaking rate directly.
- On macOS `say`, pitch and volume are applied with inline prosody tags such as
  `[[pbas +2]]` and `[[volm 90]]`.

## Example

```python
from agentic_brain.voice.emotions import VoiceEmotion
from agentic_brain.voice.serializer import speak_serialized

speak_serialized("Great news, deployment succeeded!", voice="Karen")
speak_serialized(
    "Critical alert. Production needs attention immediately.",
    voice="Karen",
    emotion=VoiceEmotion.URGENT,
)
```
