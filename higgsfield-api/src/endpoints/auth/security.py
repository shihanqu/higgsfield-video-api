from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
from tortoise.exceptions import DoesNotExist

from ...repository.models.client import Client

api_key_header = APIKeyHeader(name="X-API-Key")
"""
APIKeyHeader instance for extracting the API key (token) from
the X-API-Key header in incoming requests.
"""


async def validate_client_by_token(token: str = Security(api_key_header)) -> Client:
    """
    Validate the provided API key and ensure the client has a webhook URL.

    This function checks the length of the given token, then attempts to
    retrieve a `Client` object based on that token. It raises an HTTP 401
    error if the token is invalid or the client does not exist, and a 400
    error if the client has no webhook URL configured.

    :param token: The API key, automatically extracted from the "X-API-Key" header.
    :type token: str

    :raises HTTPException 401: If the token is not exactly 32 characters or no client
                               is found with the given token.
    :raises HTTPException 400: If the retrieved client does not have a webhook URL set.

    :return: The validated Client object.
    :rtype: Client
    """
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
    token: str = Security(api_key_header),
) -> Client:
    """
    Validate the provided API key and return the corresponding client.

    Similar to `validate_client_by_token`, but does not enforce the presence
    of a webhook URL. Useful for endpoints that do not require a webhook URL.

    :param token: The API key, automatically extracted from the "X-API-Key" header.
    :type token: str

    :raises HTTPException 401: If the token is not exactly 32 characters or no client
                               is found with the given token.

    :return: The validated Client object.
    :rtype: Client
    """
    if len(token) != 32:
        raise HTTPException(status_code=401, detail="Invalid API key")
    try:
        client = await Client.get(token=token)
    except DoesNotExist:
        raise HTTPException(status_code=401, detail="The API key is incorrect")

    return client


async def validate_admin_by_token(token: str = Security(api_key_header)) -> Client:
    """
    Validate the provided API key for an admin client.

    Checks the length of the given token, then attempts to retrieve a
    `Client` object that has `is_admin=True`. Raises an HTTP 401 error
    if the token is invalid or if an admin client cannot be found for
    the given token.

    :param token: The API key, automatically extracted from the "X-API-Key" header.
    :type token: str

    :raises HTTPException 401: If the token is not exactly 32 characters or no admin
                               client is found with the given token.

    :return: The validated admin Client object.
    :rtype: Client
    """
    if len(token) != 32:
        raise HTTPException(status_code=401, detail="Invalid API key")
    try:
        sysadmin = await Client.get(token=token, is_admin=True)
    except DoesNotExist:
        raise HTTPException(status_code=401, detail="The API key is incorrect")

    return sysadmin
