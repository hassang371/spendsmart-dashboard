from apps.api.core.auth import get_service_client

client = get_service_client()
res = client.rpc("get_policies", {}).execute()
print(res)
