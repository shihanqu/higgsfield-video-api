# Higgsfield API Service

This project is a web service for working with the Higgsfield API, providing functionality for creating and managing video generation tasks from images.

## Technologies

* **Python 3**
* **FastAPI**: Modern web framework for building APIs.
* **Uvicorn**: ASGI server for running FastAPI.
* **Tortoise ORM**: Asynchronous ORM for working with the database.
* **APScheduler**: Task scheduler for asynchronous processing.
* **Docker & Docker Compose**: For containerization and service orchestration.
* **Pytest**: For automated testing.

## Project structure

```text
.
├── docker-compose.yaml      # File for service orchestration
├── post-merge               # Git hook for automatic testing
├── higgsfield-api/          # Main application directory
│   ├── Dockerfile             # Dockerfile for building the image
│   ├── pytest.ini             # Pytest configuration
│   ├── requirements/          # Project dependencies
│   │   └── base.txt
│   ├── src/                   # Source code
│   │   ├── main.py            # FastAPI application entry point
│   │   ├── app_factory.py     # Application factory
│   │   ├── config.py          # Configuration and settings
│   │   ├── endpoints/         # API endpoints
│   │   │   ├── auth/          # Authentication
│   │   │   ├── higgsfield/    # Higgsfield endpoints
│   │   │   └── routes.py      # Routing
│   │   ├── repository/        # Database access
│   │   │   ├── models/        # Data models
│   │   │   └── core.py        # DB initialization
│   │   ├── services/          # Business logic
│   │   ├── schedulers/        # Task schedulers
│   │   └── utils/             # Utilities
│   └── tests/                 # Automated tests
└── README.md                # This file
```

## How to run

The project is designed to run in Docker containers.

1. **Clone the repository:**

   ```bash
   git clone <repository URL>
   cd hf
   ```

2. **Create a `.env` file** in the project root:

   ```env
   DB_HOST=localhost
   DB_SOCKET=/path/to/socket
   DB_USER=your_db_user
   DB_PASSWORD=your_db_password
   DB_NAME=your_db_name
   UUID_TEST_CHECK=your-secret-uuid
   ```

3. **Start the services with Docker Compose:**
   This command will build the Docker image and start the containers in the background.

   ```bash
   docker-compose up -d --build
   ```

   If the image is already built, you can use:

   ```bash
   docker-compose up -d
   ```

4. The service will be available at `http://localhost:8018`.

## API

### Authentication

#### Registration

* **URL**: `/api/auth/registration`
* **Method**: `POST`
* **Description**: Registers a new client (requires an admin token).

#### Login

* **URL**: `/api/auth/login`
* **Method**: `POST`
* **Description**: Authenticates an existing client and returns a token.

### Video generation

#### Create a video generation task

* **URL**: `/api/higgsfield/i2v/`
* **Method**: `POST`
* **Description**: Creates a task to generate a video from an image.
* **Headers**:

  * `X-API-KEY`: Client API token
* **Form parameters**:

  * `image`: Image file
  * `prompt`: Optional prompt for the video
  * `motion`: Motion type (GENERAL, DISINTEGRATION, etc.)
  * `model`: Model (lite, standard, turbo)
  * `duration`: Video duration (3 or 5 seconds)
  * `metadata`: Additional metadata in JSON format

### Service health check

* **URL**: `/health/{uuid}`
* **Method**: `GET`
* **Description**: Checks whether the service is running.
* **Path parameters**:

  * `uuid` (string): Secret UUID specified in the `.env` file (`UUID_TEST_CHECK`).

## Testing

To run the tests, execute:

```bash
docker-compose run --rm test
```

This command will start a separate container, run the tests with `pytest`, and then remove the container.
