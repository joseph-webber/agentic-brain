# Kokoro-82M voice personas map

This document maps the 14 voice personas onto the best available Kokoro-82M voices.

## Research summary

- Runtime research was done against `kokoro==0.9.4` in a local Python 3.12 virtual environment.
- The package exposes `KPipeline` but does **not** currently expose a public `list_voices()` helper.
- Because of that, the authoritative voice inventory comes from the upstream Kokoro voice catalogue: `hexgrad/Kokoro-82M/VOICES.md`.
- Official Kokoro languages relevant here are:
  - `en-us`
  - `en-gb`
  - `ja`
  - `zh`
  - `fr`
  - `it`

For Vietnamese, Korean, Thai, Indonesian, Javanese, Balinese, Polish, and Irish accents, Kokoro does not yet ship dedicated native voices, so the mapping uses the closest high-quality English proxy plus a fallback chain.

## Voice selection table

| Voice Persona | Primary Kokoro voice | Language | Style | Rate | Why this works |
| --- | --- | --- | --- | --- | --- |
| Karen | `bf_emma` | `en-gb` | Confident, direct, polished host | `0.98` | Strong Commonwealth feel; closest fit for Australian lead-host energy |
| Kyoko | `jf_alpha` | `ja` | Precise, calm, meticulous | `0.94` | Best Japanese female base in the official set |
| Tingting | `zf_xiaoxiao` | `zh` | Fast, analytical, solution-focused | `1.06` | Reads cleanly at speed for dashboards and summaries |
| Yuna | `af_bella` | `en-us` | Energetic, social, bright tech voice | `1.08` | Highest-quality upbeat proxy for Korean-accented English |
| Linh | `bf_alice` | `en-gb` | Clear, practical, grounded | `1.00` | Crisp guidance voice for GitHub walkthroughs |
| Kanya | `af_nicole` | `en-us` | Calm, caring, wellness-first | `0.92` | Soft and steady long-form delivery |
| Dewi | `af_sarah` | `en-us` | Modern, organised, polished | `1.01` | Good fit for project-management updates |
| Sari | `af_kore` | `en-us` | Reflective, cultural, measured | `0.95` | Neutral base voice suited to documentation |
| Wayan | `af_heart` | `en-us` | Spiritual, airy, meditative | `0.90` | Warmest voice in the catalogue for reflective speech |
| Moira | `bf_isabella` | `en-gb` | Warm, artistic, thoughtful | `0.97` | Melodic British proxy for Irish warmth |
| Alice | `if_sara` | `it` | Expressive, lively, warm | `1.03` | Native Italian voice, ideal for food and travel |
| Zosia | `af_aoede` | `en-us` | Thoughtful, analytical, security-minded | `0.96` | Serious tone works for security reviews |
| Flo | `ff_siwis` | `fr` | Elegant, refined, articulate | `0.99` | The official French female voice fits her perfectly |
| Shelley | `bf_lily` | `en-gb` | Friendly, supportive, dependable | `1.00` | Balanced tone for deployment guidance |

## Blend guidance

These blends are metadata for blend-capable backends or future Kokoro post-processing. They are not required for basic synthesis.

| Voice Persona | Blend | Intent |
| --- | --- | --- |
| Karen | `bf_emma 70% + af_bella 30%` | Commonwealth authority plus extra drive |
| Kyoko | `jf_alpha 80% + jf_tebukuro 20%` | Precision with a softer finish |
| Tingting | `zf_xiaoxiao 75% + zf_xiaoyi 25%` | Sharp analytics with more brightness |
| Yuna | `af_bella 65% + af_nova 35%` | Youthful, high-energy tech personality |
| Linh | `bf_alice 70% + af_nicole 30%` | Clear guidance with warmth |
| Kanya | `af_nicole 75% + af_heart 25%` | Wellness and reassurance |
| Dewi | `af_sarah 60% + bf_emma 40%` | Modern PM voice with executive polish |
| Sari | `af_kore 65% + bf_isabella 35%` | Documentary calm with a literary edge |
| Wayan | `af_heart 80% + af_sarah 20%` | Spiritual softness with slightly clearer articulation |
| Moira | `bf_isabella 70% + af_heart 30%` | Warm debugging companion |
| Alice | `if_sara 80% + bf_isabella 20%` | Native Italian core with extra flourish |
| Zosia | `af_aoede 75% + bf_emma 25%` | Analytical authority |
| Flo | `ff_siwis 80% + bf_alice 20%` | Elegant review voice with extra clarity |
| Shelley | `bf_lily 70% + bf_emma 30%` | Supportive release manager |

## Ethnicity and accent guidance

Kokoro should not be treated as a perfect ethnicity simulator. The best result comes from mapping **persona and speech function** first, then accent proximity second.

- **Japanese**: `jf_alpha` is the safest primary female choice.
- **Mandarin Chinese**: `zf_xiaoxiao` is the best fast-speaking female analytic option.
- **Italian**: `if_sara` is the clear native match.
- **French**: `ff_siwis` is the only official female French voice and works very well.
- **Australian / Irish / Korean / Vietnamese / Thai / Indonesian / Polish**: use the closest high-quality English proxy voice, then fall back to a platform-native voice if authentic native pronunciation is required.

## Sample synthesis commands

### Python: use the mapping helper

```python
from kokoro import KPipeline
from agentic_brain.voice.lady_voices import get_lady_voice

config = get_lady_voice("Kyoko")
pipeline = KPipeline(lang_code="j")

for _, _, audio in pipeline(
    "品質チェックを始めます。",
    voice=config["voice_id"],
    speed=config["rate_adjustment"],
):
    # write audio to your playback pipeline
    pass
```

### Python: inspect a fallback chain

```python
from agentic_brain.voice.lady_voices import get_fallback_chain

print(get_fallback_chain("Karen"))
# ['bf_emma', 'af_bella', 'bf_lily', 'af_heart']
```

### Shell: quick local test from this repo

```bash
cd /Users/joe/brain/agentic-brain
. .venv312/bin/activate
python - <<'PY'
from kokoro import KPipeline
from agentic_brain.voice.lady_voices import get_lady_voice

config = get_lady_voice("Flo")
pipeline = KPipeline(lang_code="f")
for _, _, audio in pipeline("Bonjour, je relis la pull request.", voice=config["voice_id"], speed=config["rate_adjustment"]):
    print(type(audio), len(audio))
    break
PY
```

## Notes

- `kokoro-tts-tool` was attempted first, but package resolution in this environment was not reliable enough to use as the implementation base.
- The mapping module therefore targets the official `kokoro` package and the upstream Kokoro voice catalogue.
