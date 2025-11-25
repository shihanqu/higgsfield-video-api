import hashlib
import hmac


def create_hmac_sha256_signature(key: str, data: str, message: str = "MusicAPI") -> str:
    """
    Create an HMAC SHA-256 signature for given data using a key and an optional message.

    First, a temporary hash of the key plus ``message`` is created. Then,
    that hash is used to sign the ``data``.

    :param key: Secret key used to generate the signature.
    :type key: str
    :param data: The message or payload to sign.
    :type data: str
    :param message: (optional) A prefix message used to further derive the key.
    :type message: str, optional

    :return: Hex-encoded SHA-256 signature.
    :rtype: str
    """
    key = hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()
    return hmac.new(key.encode(), data.encode(), hashlib.sha256).hexdigest()
