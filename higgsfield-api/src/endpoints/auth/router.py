import logging
import secrets

import bcrypt
from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.security import HTTPBasicCredentials
from pydantic import HttpUrl

from ...repository.models.client import Client
from .security import validate_admin_by_token, validate_client_by_token_only

router = APIRouter()
logger = logging.getLogger("runway")


def get_response(data: dict, message: str, status_code: int = 200):
    return {"data": data, "message": message, "status_code": status_code}


@router.post("/login", status_code=200)
async def login(credentials: HTTPBasicCredentials):
    """
    Authenticate an existing client and return a new API token upon success.

    This endpoint checks whether the client (user) exists and verifies the
    provided password. If valid, a new token is generated and stored in the
    database. The token is returned to the client for subsequent requests.

    :param credentials: The HTTP Basic credentials (username and password).
    :type credentials: HTTPBasicCredentials

    :raises HTTPException 404: If the user does not exist.
    :raises HTTPException 401: If the provided password is incorrect.

    :return: A JSON response containing the new token.
    :rtype: dict
    """
    client = await Client.filter(username=credentials.username).first()
    if not client:
        raise HTTPException(status_code=404, detail="User not found")

    if not bcrypt.checkpw(
        credentials.password.encode("utf-8"), client.password.encode("utf-8")
    ):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
        )

    client.token = secrets.token_hex(16)
    await client.save()

    logger.info(f"***   Client Logged In ({client.username})   ***")
    return get_response(data={"X-API-KEY": client.token}, message="success")


@router.post("/registration", status_code=200)
async def registration(
    credentials: HTTPBasicCredentials,
    sysadmin: Client = Depends(validate_admin_by_token),
):
    """
    Register a new client (user) in the system.

    This endpoint can only be accessed by an existing admin client. It creates
    a new client record with the given username and a hashed password.

    :param credentials: The HTTP Basic credentials (username and password)
        for the new client.
    :type credentials: HTTPBasicCredentials
    :param sysadmin: The authorized admin client, automatically injected via
        dependency injection.
    :type sysadmin: Client

    :raises HTTPException 400: If a client with the provided username already exists.

    :return: A JSON response containing the new client's token.
    :rtype: dict
    """
    cli = await Client.filter(username=credentials.username)
    if cli:
        raise HTTPException(status_code=400, detail="User already exists")

    hashed_password = bcrypt.hashpw(
        credentials.password.encode("utf-8"), bcrypt.gensalt()
    )

    new_client = Client(
        username=credentials.username,
        password=hashed_password.decode("utf-8"),
    )
    await new_client.save()

    logger.info(f"***   New Client Registred({new_client.token})   ***")
    return get_response(data={"X-API-KEY": new_client.token}, message="success")


@router.get("/user/whoami", status_code=200)
async def whoami(client: Client = Depends(validate_client_by_token_only)):
    """
    Return the current client's basic information.

    This endpoint requires a valid token in the header. It retrieves the client's
    username and token, and optionally includes the webhook URL if set.

    :param client: The authorized client, automatically injected via dependency.
    :type client: Client

    :return: A JSON response containing the client's username, token, and webhook URL.
    :rtype: dict
    """
    response = {"username": client.username, "token": client.token}
    if client.url:
        response["webhook_url"] = client.url
    return get_response(data=response, message="success")


@router.post("/user/webhook", status_code=200)
async def update_webhook(
    webhook_url: HttpUrl = Body(embed=True),
    client: Client = Depends(validate_client_by_token_only),
):
    """
    Update the client's webhook URL.

    This endpoint sets a new webhook URL for the authenticated client. The URL
    must be a valid HTTP or HTTPS address (as enforced by the HttpUrl type).

    :param webhook_url: The new webhook URL to be stored.
    :type webhook_url: HttpUrl
    :param client: The authorized client, automatically injected via dependency.
    :type client: Client

    :return: A JSON response containing the updated webhook URL.
    :rtype: dict
    """
    client.url = webhook_url
    await client.save()
    return get_response(data={"webhook_url": str(webhook_url)}, message="success")
