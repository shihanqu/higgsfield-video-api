# Higgsfield API Service

A FastAPI-based proxy service for the Higgsfield AI image and video generation platform. This service provides a REST API for text-to-image, Soul model image generation, and image-to-video tasks with automatic account rotation and task queue management.

## Technologies

* **Python 3.10+**
* **FastAPI**: Modern web framework for building APIs
* **Uvicorn**: ASGI server for running FastAPI
* **Tortoise ORM**: Asynchronous ORM for SQLite database
* **APScheduler**: Task scheduler for background processing
* **Playwright**: Browser automation for authentication
* **Pytest**: Automated testing

## Project Structure

```text
├── higgsfield-api/              # Main application directory
│   ├── src/                     # Source code
│   │   ├── main.py              # FastAPI application entry point
│   │   ├── app_factory.py       # Application factory
│   │   ├── config.py            # Configuration and settings
│   │   ├── endpoints/           # API endpoints
│   │   │   ├── auth/            # Authentication (login, registration)
│   │   │   ├── higgsfield/      # Generation endpoints (t2i, soul, i2v)
│   │   │   ├── results.py       # Task status and cancellation
│   │   │   └── routes.py        # Route registration
│   │   ├── repository/          # Database models and access
│   │   ├── services/            # Higgsfield API integration
│   │   ├── schedulers/          # Background task processing
│   │   └── utils/               # Utilities
│   ├── scripts/                 # CLI tools
│   │   ├── generate_sample_image.py   # Test image generation
│   │   ├── generate_sample_video.py   # Test video generation
│   │   ├── manage_accounts.py         # Account management (login, add, list)
│   │   └── tools/                     # Additional utilities
│   ├── tests/                   # Automated tests
│   └── requirements/            # Dependencies
├── API_REFERENCE.md             # Higgsfield API documentation
└── README.md                    # This file
```

## Quick Start

### 1. Setup Environment

```powershell
cd "higgsfield-video-api\higgsfield-api"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements/base.txt
```

### 2. Configure Environment

Create `.env` file in the `higgsfield-api/src/` directory:

```env
UUID_TEST_CHECK=your-secret-uuid-for-health-check
```

Create `.env.credentials` file in `higgsfield-api/` for Higgsfield login:

```env
HIGGSFIELD_LOGIN_EMAIL=your@email.com
HIGGSFIELD_LOGIN_PASSWORD=YourPassword
```

### 3. Add Higgsfield Account

```powershell
python scripts/manage_accounts.py login
```

This opens a browser, logs in automatically, and stores the session.

### 4. Run the Server

```powershell
uvicorn src.main:app --host 0.0.0.0 --port 8018 --reload
```

The API will be available at:
- **Local**: `http://localhost:8018`
- **Network**: `http://<your-ip>:8018` (accessible from other machines)

### 5. Quick Test

Generate an image:
```powershell
curl.exe --% -X POST http://localhost:8018/api/higgsfield/t2i/ -H "Content-Type: application/json" -d "{\"prompt\": \"A sunset over mountains\"}"
```

Check task status (use the `request_id` from the response):
```powershell
curl.exe http://localhost:8018/api/task/<request_id>/status
```

---

## API Endpoints

**For local use, no API key is required.** The service uses the Higgsfield account credentials from `auth.json` (captured via `manage_accounts.py login`).

For multi-client setups with webhooks, clients can register and authenticate via the `/api/auth/` endpoints.

### Authentication (Optional)

#### Login
```
POST /api/auth/login
```
Authenticate with username/password (HTTP Basic Auth) and receive an API token.

#### Registration
```
POST /api/auth/registration
```
Register a new client (requires admin token).

#### Get Current User
```
GET /api/auth/user/whoami
```
Returns the authenticated user's info.

#### Set Webhook URL
```
POST /api/auth/user/webhook
```
Set a webhook URL to receive task completion notifications.

---

### Image Generation

#### Text-to-Image
```
POST /api/higgsfield/t2i/
Content-Type: application/json
```

**Request Body:**
```json
{
  "prompt": "A sunset landscape with mountains",
  "model": "nano-banana-2",
  "aspect_ratio": "16:9",
  "seed": 12345,
  "guidance_scale": 7.5,
  "use_unlim": true,
  "resolution": "2k",
  "num_images": 1
}
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt` | string | **required** | Text prompt for generation |
| `model` | enum | `nano-banana-2` | Model: nano-banana-2, flux-2, seedream, etc. |
| `aspect_ratio` | enum | `4:3` | 1:1, 3:4, 4:3, 16:9, 9:16 |
| `seed` | int | random | Deterministic seed (1-1000000) |
| `guidance_scale` | float | 7.5 | Guidance scale (1-20) |
| `resolution` | enum | `2k` | Output resolution: 1k, 2k |
| `num_images` | int | 1 | Number of images (1-4) |

**Response:**
```json
{
  "request_id": "uuid",
  "status": "queued",
  "status_url": "/api/task/{id}/status",
  "cancel_url": "/api/task/{id}/cancel"
}
```

---

#### Soul Model (Style Presets)
```
POST /api/higgsfield/soul/
Content-Type: application/json
```

**Request Body:**
```json
{
  "prompt": "A portrait in cinematic lighting",
  "style": "realistic",
  "aspect_ratio": "3:4",
  "resolution": "1080p",
  "style_strength": 1.0,
  "batch_size": 1,
  "enhance_prompt": true,
  "negative_prompt": "",
  "seed": 12345,
  "steps": 50
}
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt` | string | **required** | Text prompt |
| `style` | string | `general` | Style name (see `/styles/` endpoint) |
| `style_id` | uuid | null | Style UUID (overrides style name) |
| `style_strength` | float | 1.0 | Style influence (0.0-1.0) |
| `resolution` | enum | `720p` | 720p or 1080p |
| `aspect_ratio` | enum | `4:3` | 1:1, 3:4, 4:3, 2:3, 3:2, 16:9, 9:16 |
| `batch_size` | enum | 1 | Number of images: 1 or 4 |
| `enhance_prompt` | bool | true | Auto-enhance prompt |
| `negative_prompt` | string | "" | Elements to avoid |
| `steps` | int | 50 | Inference steps (10-100) |

---

#### List Soul Styles
```
GET /api/higgsfield/styles/
```
**No authentication required.**

Returns all available Soul style presets with IDs, names, descriptions, and preview images.

---

### Video Generation

#### Image-to-Video
```
POST /api/higgsfield/i2v/
Content-Type: multipart/form-data
```

**Form Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `image` | file | **required** | Source image file |
| `prompt` | string | "A cinematic push-in shot" | Motion prompt |
| `motion` | enum | `GENERAL` | Motion preset (see below) |
| `model` | enum | `lite` | lite, standard, turbo |
| `duration` | enum | `3` | Video duration: 3 or 5 seconds |
| `seed` | int | random | Deterministic seed |
| `use_unlim` | bool | true | Use unlimited credits |

**Motion Presets:**
GENERAL, DISINTEGRATION, EARTH_ZOOM_OUT, EYES_IN, FACE_PUNCH, ARC_RIGHT, HANDHELD, BUILDING_EXPLOSION, STATIC, TURNING_METAL, 3D_ROTATION, SNORRICAM

---

### Task Management

#### Get Task Status
```
GET /api/task/{task_id}/status
```

**Response:**
```json
{
  "request_id": "uuid",
  "status": "completed",
  "status_url": "/api/task/{id}/status",
  "cancel_url": "/api/task/{id}/cancel",
  "result": ["https://cdn.higgsfield.ai/..."],
  "created_at": "2025-01-01T00:00:00Z",
  "finished_at": "2025-01-01T00:01:00Z",
  "task_type": "t2i"
}
```

**Status Values:** `queued`, `in_progress`, `completed`, `failed`, `canceled`

#### Cancel Task
```
POST /api/task/{task_id}/cancel
```
Cancels a pending or in-progress task.

---

### Health Check
```
GET /health/{uuid}
```
Returns 200 if the UUID matches `UUID_TEST_CHECK` from `.env`.

---

## CLI Scripts

### Generate Sample Image
```powershell
cd higgsfield-video-api/higgsfield-api

# Basic text-to-image
python scripts/generate_sample_image.py --prompt "A dreamy watercolor landscape"

# Soul model with style
python scripts/generate_sample_image.py --model soul --prompt "Portrait" --style realistic

# List available Soul styles
python scripts/generate_sample_image.py --list-styles
```

### Generate Sample Video
```powershell
# Basic video from image
python scripts/generate_sample_video.py --image path/to/photo.png

# With motion preset
python scripts/generate_sample_video.py --image photo.png --motion DISINTEGRATION --duration 5

# List available motions
python scripts/generate_sample_video.py --list-motions
```

### Account Management
```powershell
# Full login flow (opens browser, saves to database)
python scripts/manage_accounts.py login

# Force re-login even if session is valid
python scripts/manage_accounts.py login --force

# List all stored accounts
python scripts/manage_accounts.py list

# List with cookie details
python scripts/manage_accounts.py list --verbose
```

---

## Testing

```powershell
cd higgsfield-video-api/higgsfield-api
pytest -v
```

---

## Architecture

1. **Local-First Design**: No API key required for local use; just run and go
2. **Auto-Authentication**: If no valid account is in the database, the service automatically loads from `auth.json`
3. **Task Queue**: Generation requests create tasks stored in SQLite
4. **Background Scheduler**: Processes pending tasks using Higgsfield accounts
5. **Account Rotation**: Multiple Higgsfield accounts can be added; scheduler rotates through them
6. **Optional Webhooks**: For multi-client setups, clients can register and set webhook URLs for delivery

---

## Troubleshooting

### "No auth.json found" or "credentials are invalid"
Run `python scripts/manage_accounts.py login` to authenticate. This opens a browser, logs in using your `.env.credentials`, and saves the session to `auth.json`.

### Session expired
Run `python scripts/manage_accounts.py login --force` to re-authenticate and refresh the session.

### Port already in use
Change the port: `uvicorn src.main:app --port 8019`

### PowerShell JSON in curl
Use the stop-parsing token when sending JSON:
```powershell
curl.exe --% -X POST http://localhost:8018/api/higgsfield/t2i/ -H "Content-Type: application/json" -d "{\"prompt\": \"A sunset\"}"
```
