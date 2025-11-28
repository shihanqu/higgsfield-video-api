from typing import Optional

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
from tortoise.exceptions import DoesNotExist

from ...repository.models.client import Client

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
"""
APIKeyHeader instance for extracting the API key (token) from
the X-API-Key header in incoming requests.
auto_error=False allows endpoints to work without auth when desired.
"""


async def validate_client_by_token(token: Optional[str] = Security(api_key_header)) -> Client:
    """
    Validate the provided API key and ensure the client has a webhook URL.

    If no token is provided, returns a default "local" client for local API usage.

    :param token: The API key, automatically extracted from the "X-API-Key" header.
    :type token: str

    :raises HTTPException 401: If the token is provided but invalid.
    :raises HTTPException 400: If the retrieved client does not have a webhook URL set.

    :return: The validated Client object.
    :rtype: Client
    """
    # Allow unauthenticated access for local use - get or create default client
    if not token:
        client, _ = await Client.get_or_create(
            username="local",
            defaults={"password": "not-used", "is_admin": False}
        )
        return client

    if len(token) != 32:
        raise HTTPException(status_code=401, detail="Invalid API key")
    try:
        client = await Client.get(token=token)
    except DoesNotExist:
        raise HTTPException(status_code=401, detail="The API key is incorrect")

    if not client.url:
        raise HTTPException(
            status_code=400,
            detail="To deliver the results, you need to send a POST request with the field webhook_url.",
        )
    return client


async def validate_client_by_token_only(
    token: Optional[str] = Security(api_key_header),
) -> Client:
    """
    Validate the provided API key and return the corresponding client.

    If no token is provided, returns a default "local" client for local API usage.

    :param token: The API key, automatically extracted from the "X-API-Key" header.
    :type token: str

    :raises HTTPException 401: If the token is provided but invalid.

    :return: The validated Client object.
    :rtype: Client
    """
    # Allow unauthenticated access for local use - get or create default client
    if not token:
        client, _ = await Client.get_or_create(
            username="local",
            defaults={"password": "not-used", "is_admin": False}
        )
        return client

    if len(token) != 32:
        raise HTTPException(status_code=401, detail="Invalid API key")
    try:
        client = await Client.get(token=token)
    except DoesNotExist:
        raise HTTPException(status_code=401, detail="The API key is incorrect")

    return client


async def validate_admin_by_token(token: Optional[str] = Security(api_key_header)) -> Client:
    """
    Validate the provided API key for an admin client.

    Admin endpoints always require authentication - no default client.

    :param token: The API key, automatically extracted from the "X-API-Key" header.
    :type token: str

    :raises HTTPException 401: If the token is not exactly 32 characters or no admin
                               client is found with the given token.

    :return: The validated admin Client object.
    :rtype: Client
    """
    if not token or len(token) != 32:
        raise HTTPException(status_code=401, detail="Invalid API key")
    try:
        sysadmin = await Client.get(token=token, is_admin=True)
    except DoesNotExist:
        raise HTTPException(status_code=401, detail="The API key is incorrect")

    return sysadmin
