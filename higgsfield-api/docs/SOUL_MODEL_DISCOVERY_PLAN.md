# Soul Model Parameter Discovery Plan

This document outlines the action plan for discovering all available options for the Higgsfield Soul model (`text2image-soul` endpoint).

## Status: ✅ COMPLETE

All Soul model parameters and styles have been documented.

---

## Discovered Parameters

| Name | Type | Default | Required | Description |
|------|------|---------|----------|-------------|
| `prompt` | string | - | **Yes** | The text prompt for the image |
| `aspect_ratio` | enum | `4:3` | No | `9:16`, `16:9`, `4:3`, `3:4`, `1:1`, `2:3`, `3:2` |
| `batch_size` | integer | `1` | No | Number of images to generate (`1` or `4`) |
| `enhance_prompt` | boolean | `true` | No | Automatically enhance the prompt |
| `resolution` | enum | `720p` | No | `720p`, `1080p` (affects output dimensions) |
| `seed` | integer | null | No | Min: 1, Max: 1000000 |
| `style_id` | uuid | null | No | The ID of the specific Soul Style to use |
| `style_strength` | float | `1` | No | Min: 0, Max: 1 |

### Internal Parameters (set automatically)

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `width` | integer | varies | Calculated from resolution + aspect_ratio |
| `height` | integer | varies | Calculated from resolution + aspect_ratio |
| `steps` | integer | `50` | Inference steps |
| `sample_shift` | float | `4.0` | Sampling parameter |
| `sample_guide_scale` | float | `4.0` | Guidance scale |
| `version` | integer | `3` | API version |
| `negative_prompt` | string | `""` | Elements to avoid |
| `fashion_factory_id` | uuid | null | Unknown purpose |
| `custom_reference_strength` | float | `0.9` | For custom references |
| `use_unlim` | boolean | varies | Unlimited credits mode |

---

## Resolution to Dimension Mapping

### 720p
| Aspect Ratio | Width | Height |
|--------------|-------|--------|
| 1:1 | 1152 | 1152 |
| 3:4 | 1152 | 1536 |
| 4:3 | 1536 | 1152 |
| 2:3 | 1024 | 1536 |
| 3:2 | 1536 | 1024 |
| 9:16 | 864 | 1536 |
| 16:9 | 1536 | 864 |

### 1080p
| Aspect Ratio | Width | Height |
|--------------|-------|--------|
| 1:1 | 1536 | 1536 |
| 3:4 | 1536 | 2048 |
| 4:3 | 2048 | 1536 |
| 2:3 | 1365 | 2048 |
| 3:2 | 2048 | 1365 |
| 9:16 | 1152 | 2048 |
| 16:9 | 2048 | 1152 |

---

## Soul Styles

**98 styles available** in `scripts/reference_input/soul_styles.json`

### Sample Styles

| Name | ID | Description |
|------|-----|-------------|
| General | `464ea177-8d40-4940-8d9d-b438bab269c7` | Clean, balanced, natural |
| Realistic | `1cb4b936-77bf-4f9a-9039-f3d349a4cdbe` | No filters, flawless clarity |
| Y2K | `6b9e6b4d-325a-4a78-a0fb-a00ddf612380` | Gloss, glitter, early 2000s |
| Grunge | `ad9de607-3941-4540-81ea-ba978ef1550b` | Distressed, moody, messy |
| Fairycore | `7f21e7bd-4df6-4cef-a9a9-9746bceaea1d` | Glittery woodland fantasy |
| 90s Grain | `f5c094c7-4671-4d86-90d2-369c8fdbd7a5` | Warm tones, film texture |

Run `python generate_sample_image_soul.py --list-styles` to see all available styles.

---

## Usage Examples

```bash
# Standard model (nano-banana-2)
python generate_sample_image.py --prompt "A sunset landscape"
python generate_sample_image.py --model flux-2 --aspect-ratio 16:9

# Soul model - basic
python generate_sample_image.py --model soul --prompt "A portrait in dramatic lighting"

# Soul model - with style
python generate_sample_image.py --model soul --style realistic --resolution 1080p

# Soul model - by style UUID
python generate_sample_image.py --model soul --style-id 464ea177-8d40-4940-8d9d-b438bab269c7

# Soul model - batch generation
python generate_sample_image.py --model soul --batch-size 4 --prompt "Abstract art"

# List all available Soul styles
python generate_sample_image.py --list-styles
```

---

## Related Files

- `scripts/generate_sample_image.py` - Unified generation script (supports both standard and Soul models)
- `scripts/reference_input/soul_styles.json` - Complete list of 98 Soul styles
- `scripts/playwright_session_logger.py` - Network traffic capture tool

---

## Discovery History

- **2025-11-27**: Initial capture of Soul model API structure
- **2025-11-27**: Captured 2 styles via network logs (General, Style 7)
- **2025-11-27**: User provided complete parameter documentation and 98 styles
- **2025-11-27**: Updated script with all parameters and style loading from JSON
