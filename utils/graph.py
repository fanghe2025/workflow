from config import env
from core.graph_api_client import GraphAPIClient


def get_authenticated_api_client() -> GraphAPIClient:
    """Authenticate API client"""

    client_id = env.GRAPH_CLIENT_ID
    client_secret = env.GRAPH_CLIENT_SECRET
    tenant_id = env.GRAPH_TENANT_ID
    user_email = env.GRAPH_USER_EMAIL

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
