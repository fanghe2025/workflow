from utils.common import load_config
from core.graph_api_client import GraphAPIClient


def get_authenticated_api_client() -> GraphAPIClient:
    """Authenticate API client"""

    # Get credentials from config
    config = load_config("config/graph_config.json")
    client_id = config.get("client_id")
    client_secret = config.get("client_secret")
    tenant_id = config.get("tenant_id")
    user_email = config.get("user_email")

    if not client_id or not client_secret or not tenant_id:
        print("Credentials are required. Provide via config file")
        return None

    # Initialize tagger
    api_client = GraphAPIClient(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
        user_email=user_email,
    )

    # Authenticate
    if not api_client.authenticate():
        return None

    return api_client
