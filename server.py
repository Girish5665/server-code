import asyncio
import logging
import websockets
from urllib.parse import urlparse, parse_qs
from ocpp.v201 import ChargePoint as cp
from ocpp.v201 import call_result
from ocpp.v201.enums import RegistrationStatusType
from ocpp.routing import on
from datetime import datetime
import json

# Setup basic logging
logging.basicConfig(level=logging.INFO)

# Simulated token validation method (replace it with actual logic)
VALID_TOKENS = {"TOKEN1", "token456", "Giri"}  # Modify as needed

# Store active WebSocket connections
connected_clients = set()

# OCPP ChargePoint class
class ChargePoint(cp):
    @on('BootNotification')
    async def on_boot_notification(self, charging_station, reason, **kwargs):
        logging.info(f"BootNotification received: {charging_station}")
        return call_result.BootNotificationPayload(
            current_time=datetime.utcnow().isoformat(),
            interval=10,
            status=RegistrationStatusType.accepted
        )

    async def on_message(self, message):
        logging.info(f"Received message from client: {message}")
        if message == "charge":
            # Simulate charging details
            response = {
                "voltage": "240V",
                "battery_health": "90%",
                "status": "Charging"
            }
            await self._send(json.dumps(response))
        else:
            response = f"Server received: {message}"
            await self._send(response)

# Handling client connections
async def on_connect(websocket, path):
    query_params = parse_qs(urlparse(path).query)
    token = query_params.get('token', [None])[0]

    # Token validation
    if not token or token not in VALID_TOKENS:
        logging.warning(f"Authentication failed for client. Token: {token}")
        await websocket.close(reason="Invalid or missing authentication token.")
        return

    # Track connected client
    connected_clients.add(websocket)
    logging.info(f"Client authenticated with token: {token}. Total clients: {len(connected_clients)}")
    await websocket.send("Welcome! You are authenticated.")

    charge_point_id = path.strip('/')
    cp = ChargePoint(charge_point_id, websocket)

    try:
        # WebSocket Ping Task
        asyncio.create_task(ping(websocket))

        # Handle messages from the client
        async for message in websocket:
            await cp.on_message(message)

    except websockets.ConnectionClosed:
        logging.info(f"Client disconnected. Token: {token}")
    finally:
        connected_clients.remove(websocket)
        logging.info(f"Client disconnected. Total clients: {len(connected_clients)}")

# Ping WebSocket to prevent idle timeouts
async def ping(websocket):
    while True:
        try:
            await websocket.ping()
            await asyncio.sleep(30)  # Ping every 30 seconds
        except websockets.ConnectionClosed:
            logging.info("WebSocket connection closed.")
            break

# Main function to start the WebSocket server
async def main():
    while True:  # Keep the server running continuously
        try:
            server = await websockets.serve(on_connect, '0.0.0.0', 9000, subprotocols=['ocpp2.0.1'])
            logging.info("WebSocket Server started at ws://0.0.0.0:9000")
            await server.wait_closed()
        except Exception as e:
            logging.error(f"Server encountered an error: {e}")
        finally:
            logging.info("Restarting server...")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Server stopped by user.")
