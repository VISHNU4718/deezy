import asyncio
from deezy.interface.web.api import app
from deezy.auth import get_auth_manager, init_auth
from deezy.metrics import get_metrics_collector, init_metrics
import httpx

async def test_ws():
    init_auth()
    init_metrics()
    auth = get_auth_manager()
    user = auth.create_user('wstest', 'ws@example.com', 'password123', 'WS Test User')
    access_token = auth.create_access_token(user.id, user.username)
    print('Created user:', user.id)
    print('Token created')

    headers = {'Authorization': f'Bearer {access_token}'}
    transport = httpx.ASGITransport(app=app)
    
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        # Test metrics WebSocket
        ws_url = f'/ws/metrics/test123?token={access_token}'
        print('Connecting to:', ws_url)
        async with client.websocket_connect(ws_url) as ws:
            print('WebSocket connected')
            # Wait for initial snapshot
            msg = await ws.receive_text()
            print('Received snapshot:', msg[:200])
            # Test ping
            await ws.send_text('{"type": "ping"}')
            pong = await ws.receive_text()
            print('Pong:', pong)
            # Test subscribe
            await ws.send_text('{"type": "subscribe_metrics"}')
            sub = await ws.receive_text()
            print('Subscribed:', sub)
            # Test get_snapshot
            await ws.send_text('{"type": "get_snapshot"}')
            snapshot = await ws.receive_text()
            print('Snapshot:', snapshot[:200])

    print('WebSocket tests passed!')

if __name__ == '__main__':
    import asyncio
    asyncio.run(test_ws())