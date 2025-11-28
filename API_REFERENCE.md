# Higgsfield API Reference

This document provides details about the Higgsfield API endpoints discovered from network analysis.

## Authentication

All API requests require authentication using a Bearer token:

```
Authorization: Bearer {your-auth-token}
```

---

## Media Upload

Before using images for img2img or video generation, they must be uploaded.

### Step 1: Get Upload URL
```
POST https://fnf.higgsfield.ai/media
```

**Response:**
```json
{
  "id": "media-uuid",
  "upload_url": "https://s3-presigned-url...",
  "url": "https://cdn-url-for-media...",
  "content_type": "image/jpeg"
}
```

### Step 2: Upload File
```
PUT {upload_url}
Content-Type: {content_type}

<binary file content>
```

### Step 3: Confirm Upload
```
POST https://fnf.higgsfield.ai/media/{media-id}/upload
```

---

## Image Generation

### Endpoint
```
POST https://fnf.higgsfield.ai/jobs/{model-name}
```

### Standard Models Request Body

For models like `nano-banana-2`, `flux-2`, `seedream`:

```json
{
  "params": {
    "prompt": "string",
    "input_images": [],
    "width": 1024,
    "height": 1024,
    "batch_size": 1,
    "aspect_ratio": "1:1",
    "use_unlim": true,
    "resolution": "2k",
    "enhance_prompt": true,
    "seed": 123456
  },
  "use_unlim": true
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `prompt` | string | Yes | Text prompt for image generation |
| `input_images` | array | No | Array of uploaded images for img2img |
| `width` | integer | Yes | Image width in pixels |
| `height` | integer | Yes | Image height in pixels |
| `batch_size` | integer | No | Number of images (default: 1) |
| `aspect_ratio` | string | Yes | "1:1", "3:4", "4:3", "16:9", "9:16" |
| `use_unlim` | boolean | No | Use unlimited credits (default: true) |
| `resolution` | string | No | "2k" (default) |
| `seed` | integer | **Yes for flux-2** | 1-1000000 (required for some models) |

### Input Images Format

When using img2img, format uploaded images as:

```json
"input_images": [
  {
    "id": "media-uuid",
    "url": "https://cdn-url...",
    "type": "media_input"
  }
]
```

### Soul Model Request Body

The `text2image-soul` model has additional parameters:

```json
{
  "params": {
    "prompt": "string",
    "quality": "720p",
    "aspect_ratio": "4:3",
    "enhance_prompt": true,
    "style_id": "uuid",
    "style_strength": 1.0,
    "seed": 123456,
    "width": 1536,
    "height": 1152,
    "steps": 50,
    "batch_size": 1,
    "sample_shift": 4.0,
    "sample_guide_scale": 4.0,
    "negative_prompt": "",
    "version": 3,
    "use_unlim": true,
    "fashion_factory_id": null,
    "custom_reference_strength": 0.9
  },
  "use_unlim": true
}
```

#### Soul-Specific Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `quality` | enum | "720p" | "720p" or "1080p" |
| `aspect_ratio` | enum | "4:3" | "9:16", "16:9", "4:3", "3:4", "1:1", "2:3", "3:2" |
| `batch_size` | integer | 1 | 1 or 4 |
| `style_id` | uuid | null | Soul style preset UUID |
| `style_strength` | float | 1.0 | 0.0 to 1.0 |
| `seed` | integer | random | 1-1000000 |
| `sample_shift` | float | 4.0 | Sampling parameter |
| `sample_guide_scale` | float | 4.0 | Guidance scale |
| `negative_prompt` | string | "" | Elements to avoid |
| `version` | integer | 3 | API version |

#### Soul Dimension Mapping

| Quality | Aspect | Width | Height |
|---------|--------|-------|--------|
| 720p | 1:1 | 1152 | 1152 |
| 720p | 3:4 | 1152 | 1536 |
| 720p | 4:3 | 1536 | 1152 |
| 720p | 2:3 | 1024 | 1536 |
| 720p | 3:2 | 1536 | 1024 |
| 720p | 9:16 | 864 | 1536 |
| 720p | 16:9 | 1536 | 864 |
| 1080p | 1:1 | 1536 | 1536 |
| 1080p | 3:4 | 1536 | 2048 |
| 1080p | 4:3 | 2048 | 1536 |
| 1080p | 2:3 | 1365 | 2048 |
| 1080p | 3:2 | 2048 | 1365 |
| 1080p | 9:16 | 1152 | 2048 |
| 1080p | 16:9 | 2048 | 1152 |

### Available Models

| Model | Endpoint | Notes |
|-------|----------|-------|
| `nano_banana_2` | `nano-banana-2` | Fast, good quality |
| `flux_2` | `flux-2` | **Requires seed** |
| `seedream` | `seedream` | High quality |
| `text2image_soul` | `text2image-soul` | Style presets, see above |
| `reve` | `reve` | |
| `text2image` | `text2image` | |
| `text2image_gpt` | `text2image-gpt` | |
| `flux_kontext` | `flux-kontext` | |
| `canvas` | `canvas` | |
| `canvas_soul` | `canvas-soul` | |
| `wan2_2_image` | `wan2-2-image` | |
| `nano_banana` | `nano-banana` | |
| `nano_banana_animal` | `nano-banana-animal` | |
| `keyframes_faceswap` | `keyframes-faceswap` | |
| `qwen_camera_control` | `qwen-camera-control` | |
| `viral_transform_image` | `viral-transform-image` | |
| `game_dump` | `game-dump` | |

---

## Video Generation (Image to Video)

### Endpoint
```
POST https://fnf.higgsfield.ai/jobs/image2video
```

### Request Body

```json
{
  "params": {
    "prompt": "A cinematic push-in shot",
    "enhance_prompt": true,
    "model": "lite",
    "frames": 85,
    "input_image": {
      "id": "media-uuid",
      "url": "https://cdn-url...",
      "type": "media_input"
    },
    "motion_id": "motion-uuid",
    "width": 1024,
    "height": 1024,
    "seed": 123456,
    "steps": 30,
    "use_unlim": true
  },
  "use_unlim": true
}
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `prompt` | string | Text prompt for video |
| `model` | string | "lite", "standard", or "turbo" |
| `frames` | integer | Frame count (85 for 3s, 145 for 5s) |
| `input_image` | object | Uploaded image reference |
| `motion_id` | uuid | Motion preset UUID |
| `width`, `height` | integer | From uploaded image |
| `seed` | integer | 1-1000000 |
| `steps` | integer | Inference steps (default: 30) |

### Available Motion Presets

| Name | UUID | Description |
|------|------|-------------|
| GENERAL | `d2389a9a-91c2-4276-bc9c-c9e35e8fb85a` | General purpose |
| DISINTEGRATION | `4e981984-1cdc-4b96-a2b1-1a7c1ecb822d` | Particle disintegration |
| EARTH_ZOOM_OUT | `70e490b9-26b7-4572-8d9c-2ac8dcc9adc0` | Earth zoom out |
| EYES_IN | `0ab33462-481e-4c78-8ffc-086bebd84187` | Zoom to eyes |
| FACE_PUNCH | `cd5bfd11-5a1a-46e0-9294-b22b0b733b1e` | Face punch effect |
| ARC_RIGHT | `0bdbf318-f918-4f9b-829a-74cab681d806` | Arc right |
| HANDHELD | `36e6e450-52d9-484f-bfbe-f069e06a1530` | Handheld camera |
| BUILDING_EXPLOSION | `e974bca9-c9eb-4cc8-9318-5676cc110f17` | Building explosion |
| STATIC | `aab8440c-0d65-4554-b88a-7a9a5e084b6e` | Minimal movement |
| TURNING_METAL | `46e23a6b-1047-40f1-9cf5-33f5f55ddf2e` | Metallic rotation |
| 3D_ROTATION | `6f06f47e-922e-4660-9fe9-754e4be69696` | 3D rotation |
| SNORRICAM | `893cb65f-c528-40aa-83d8-c5aeb2bfe59f` | Body-mounted camera |

### Duration to Frames Mapping

| Duration | Frames |
|----------|--------|
| 3 seconds | 85 |
| 5 seconds | 145 |

---

## Job Status Tracking

### Endpoint
```
GET https://fnf.higgsfield.ai/job-sets/{job-set-id}
```

### Response

```json
{
  "jobs": [
    {
      "id": "job-uuid",
      "status": "queued|processing|completed|failed",
      "result": {
        "url": "https://output-url..."
      },
      "results": {
        "raw": {"type": "image", "url": "..."},
        "min": {"type": "image", "url": "..._min.webp"}
      },
      "error": null
    }
  ]
}
```

**Job Statuses:**
- `queued` - Waiting to start
- `processing` - Generation in progress
- `completed` - Done, results available
- `failed` - Error occurred

---

## User Information

### Endpoint
```
GET https://fnf.higgsfield.ai/user
```

Returns user account information including credits, plan details, etc.

---

## Projects/Listings

### Endpoint
```
GET https://fnf.higgsfield.ai/project?job_set_type={type1}&job_set_type={type2}&...&size=12
```

Retrieves user projects filtered by job types.

---

## Notes

- All endpoints use `https://fnf.higgsfield.ai` as the base URL
- Authentication is required for all endpoints
- The API uses JSON for request/response bodies
- CORS is configured to allow requests from `https://higgsfield.ai`
- Responses may include Cloudflare-specific headers

## Error Handling

Common HTTP status codes:
- `200`: Success
- `401`: Invalid or expired token
- `422`: Unprocessable Content (check required fields)
- `429`: Rate limited
- `500`: Server error

## Rate Limiting

The API implements rate limiting. Monitor `x-ratelimit-*` headers in responses if present.
