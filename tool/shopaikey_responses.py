"""Single-attempt native Responses transport, avoiding the gateway's Chat route."""
import json
from urllib.request import Request, build_opener
from urllib.error import HTTPError, URLError
from approve_tool import encoded
from api_providers import ProviderFatal
from compatible_chat import NoRedirect


def responses_request(key, payload):
    req = Request('https://api.shopaikey.com/v1/responses', data=encoded(payload),
                  headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json',
                           'User-Agent': 'Mozilla/5.0'})
    try:
        with build_opener(NoRedirect()).open(req, timeout=90) as response:
            return json.load(response)
    except HTTPError as error:
        code = error.code
        error.close()
        # Preserve scheduler handling of global authentication/quota failures.
        raise ProviderFatal(f'CHAT_HTTP_{code}') from None
    except (URLError, TimeoutError, OSError):
        raise ProviderFatal('API_NETWORK_ERROR') from None
