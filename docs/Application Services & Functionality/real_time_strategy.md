# Real-Time Communication Strategy (WebSockets & Video PaaS with FastAPI)

## 1. Overview

- **Purpose**: To define the strategy for implementing real-time communication features within the ERP system, specifically:
  1.  A **chat application** (one-to-one and group chats) using FastAPI's native WebSocket capabilities.
  2.  **Video meetings** by integrating with an external API-First Video Platform as a Service (PaaS).
- **Scope**: Covers WebSocket endpoint design, connection management, message broadcasting for chat, integration patterns for the Video PaaS, authentication for real-time services, and scalability considerations.
- **Chosen Technologies**:
  - **Chat**: FastAPI native WebSockets, **`broadcaster`** library with a **Redis** backend for multi-process message distribution.
  - **Video Meetings**: Integration with an external API-First Video PaaS (e.g., Daily.co, Twilio Video, Vonage Video API - specific provider TBD).
  - **Database**: PostgreSQL (via SQLAlchemy) for chat message history and room metadata.

## 2. Core Principles

- **Scalability**: Design for handling multiple concurrent WebSocket connections and distributing messages efficiently.
- **Security**: Ensure proper authentication and authorization for accessing chat rooms and initiating video sessions.
- **Reliability**: Strive for reliable message delivery for chat. Video reliability will depend on the chosen PaaS.
- **Decoupling**: Video meeting media processing is offloaded to the external PaaS. The backend orchestrates.
- **User Experience**: Aim for a responsive real-time experience for chat. Video UX will be a mix of embedded PaaS components and application control.

## 3. Chat Application (FastAPI WebSockets + Broadcaster)

    ### 3.1. Strategic Overview
    *   FastAPI will manage WebSocket connections for chat clients.
    *   A `ConnectionManager` class (per process) will track active connections.
    *   The `broadcaster` library (with Redis backend) will handle message distribution across multiple FastAPI application instances/workers, enabling users connected to different server processes to communicate within the same chat room.
    *   Chat messages and room metadata stored in PostgreSQL.

    ### 3.2. General Setup Implementation Details (Chat)

    *   **3.2.1. Library Installation (`requirements/base.txt`):**
        ```txt
        # websockets (usually a dependency of uvicorn[standard], but good to ensure)
        # websockets>=10.0,<12.0
        broadcaster[redis]>=0.2.0,<0.3.0 # For Redis-backed broadcasting
        # redis (already listed for caching/Celery)
        ```
    *   **3.2.2. Pydantic Settings (`app/core/config.py`):**
        *   Redis URL for `broadcaster` (can reuse general Redis or a specific DB number).
            ```python
            # In Settings class:
            # REDIS_BROADCASTER_URL: Optional[RedisDsn] = None # e.g., redis://localhost:6379/4
            # If not set, broadcaster might default or need explicit init with components.
            # For simplicity, assume broadcaster uses a Redis URL like REDIS_CACHE_URL but with a different DB.
            # Let's define a specific one:
            # REDIS_CHAT_BROADCAST_DB: int = 4
            # @property
            # def REDIS_CHAT_BROADCAST_URL(self) -> str:
            #     auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
            #     return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_CHAT_BROADCAST_DB}"
            ```
    *   **3.2.3. Broadcaster Initialization (`app/core/broadcast_manager.py` or in `app/main.py`):**
        ```python
        # app/core/broadcast_manager.py (Example)
        from broadcaster import Broadcast
        from app.core.config import settings
        import logging

        logger = logging.getLogger(__name__)
        broadcast_instance: Optional[Broadcast] = None

        async def init_broadcaster():
            global broadcast_instance
            if broadcast_instance is None:
                # Ensure REDIS_CHAT_BROADCAST_URL is correctly defined in settings
                # or construct it here if using individual host/port/db settings
                if hasattr(settings, 'REDIS_CHAT_BROADCAST_URL') and settings.REDIS_CHAT_BROADCAST_URL:
                    broadcast_url = str(settings.REDIS_CHAT_BROADCAST_URL)
                    broadcast_instance = Broadcast(broadcast_url)
                    try:
                        await broadcast_instance.connect()
                        logger.info("Broadcaster connected to Redis.")
                    except Exception as e:
                        logger.error(f"Failed to connect broadcaster to Redis: {e}", exc_info=True)
                        broadcast_instance = None # Ensure it's None if connection fails
                else:
                    logger.warning("REDIS_CHAT_BROADCAST_URL not configured. Broadcaster not initialized.")
            return broadcast_instance

        async def get_broadcast_client() -> Optional[Broadcast]:
            if broadcast_instance is None or not broadcast_instance.is_connected: # Check if connected
                await init_broadcaster() # Attempt to initialize/reconnect
            return broadcast_instance

        async def close_broadcaster():
            if broadcast_instance and broadcast_instance.is_connected:
                await broadcast_instance.disconnect()
                logger.info("Broadcaster disconnected.")

        # In app/main.py:
        # @app.on_event("startup")
        # async def on_startup():
        #     await init_broadcaster()
        # @app.on_event("shutdown")
        # async def on_shutdown():
        #     await close_broadcaster()
        ```
    *   **3.2.4. Connection Manager (`app/features/chat/connection_manager.py`):**
        *   Manages active WebSocket connections *within a single process*. It maps users/clients to their WebSocket objects and potentially to the rooms they are subscribed to.
            ```python
            # app/features/chat/connection_manager.py
            from fastapi import WebSocket
            from typing import Dict, List, Set

            class ChatConnectionManager:
                def __init__(self):
                    # user_id -> WebSocket object (for direct messages or user's primary connection)
                    self.active_user_connections: Dict[str, WebSocket] = {}
                    # room_id -> Set of WebSockets (or user_ids if broadcast targets users)
                    self.room_connections: Dict[str, Set[WebSocket]] = {}

                async def connect(self, websocket: WebSocket, user_id: str, room_id: Optional[str] = None):
                    await websocket.accept()
                    self.active_user_connections[user_id] = websocket
                    if room_id:
                        if room_id not in self.room_connections:
                            self.room_connections[room_id] = set()
                        self.room_connections[room_id].add(websocket)

                def disconnect(self, websocket: WebSocket, user_id: str, room_id: Optional[str] = None):
                    if user_id in self.active_user_connections and self.active_user_connections[user_id] == websocket:
                        del self.active_user_connections[user_id]
                    if room_id and room_id in self.room_connections:
                        self.room_connections[room_id].discard(websocket)
                        if not self.room_connections[room_id]: # Remove empty room set
                            del self.room_connections[room_id]

                async def send_personal_message(self, message: str, websocket: WebSocket):
                    try:
                        await websocket.send_text(message)
                    except RuntimeError: # Handle client abruptly disconnected
                        pass # Disconnect logic will handle removal

                async def broadcast_to_room_locally(self, message: str, room_id: str, exclude_sender: Optional[WebSocket] = None):
                    """Broadcasts to WebSockets connected to this specific server instance's room."""
                    if room_id in self.room_connections:
                        for connection in list(self.room_connections[room_id]): # list() for safe iteration
                            if connection != exclude_sender:
                                await self.send_personal_message(message, connection)

            chat_manager = ChatConnectionManager() # Singleton for this process
            ```
    *   **3.2.5. SQLAlchemy Models (`app/features/chat/models.py`):**
        *   `ChatRoom`: `id`, `name`, `room_type` ('direct', 'group'), `created_at`. Links to other entities (e.g., `project_id`, `organization_id`).
        *   `ChatMessage`: `id`, `room_id` (FK), `sender_user_id` (FK), `content` (Text), `timestamp`, `message_type` (e.g., 'text', 'file_attachment').
        *   `ChatRoomParticipant`: `room_id` (FK), `user_id` (FK), `joined_at`, `last_read_timestamp`.
    *   **3.2.6. Alembic Migration:** For chat models.

    ### 3.3. Integration & Usage Patterns (Chat)

    *   **3.3.1. WebSocket Authentication:**
        *   Pass JWT or session token as a query parameter during WebSocket handshake (`ws://.../?token=xxx`).
        *   The WebSocket endpoint (`@app.websocket(...)`) verifies this token to authenticate the user before accepting the connection.
    *   **3.3.2. Chat WebSocket Endpoint (`app/features/chat/router.py`):**
        ```python
        # app/features/chat/router.py
        # from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, Path
        # from .connection_manager import chat_manager
        # from .services import chat_service # For saving messages, getting history, etc.
        # from app.core.auth_dependencies import get_user_from_websocket_token # Custom dep for WS auth
        # from app.core.broadcast_manager import get_broadcast_client
        # from app.users.schemas import UserRead
        # from app.core.db import get_db_session, AsyncSession
        # import json

        # router = APIRouter(prefix="/ws/chat", tags=["Chat WebSockets"])

        # @router.websocket("/{room_id}")
        # async def chat_websocket_endpoint(
        #     websocket: WebSocket,
        #     room_id: str, # Can be a specific ID or a convention like "user_{user_id}" for direct
        #     current_user: UserRead = Depends(get_user_from_websocket_token), # Authenticates user
        #     db: AsyncSession = Depends(get_db_session),
        #     broadcast_client = Depends(get_broadcast_client) # Injected broadcaster
        # ):
        #     # Authorize user access to room_id
        #     # if not await chat_service.can_user_access_room(db, current_user.id, room_id):
        #     #     await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        #     #     return

        #     await chat_manager.connect(websocket, str(current_user.id), room_id)
        #     # Optionally subscribe this WebSocket to a broadcaster channel for this room
        #     if broadcast_client:
        #         channel_name = f"chat_room_{room_id}"
        #         async with broadcast_client.subscribe(channel=channel_name) as subscriber:
        #             # Send recent history or welcome message
        #             # recent_messages = await chat_service.get_recent_messages(db, room_id)
        #             # await websocket.send_text(json.dumps({"type": "history", "messages": [m.dict() for m in recent_messages]}))

        #             try:
        #                 # Listen for messages from this client AND from broadcaster
        #                 # This part needs careful async handling (e.g., asyncio.gather or trio.Nursery)
        #                 # to concurrently listen to websocket.receive_text() and subscriber.iter_events()

        #                 while True: # Simplified loop, real one needs concurrent listening
        #                     data_str = await websocket.receive_text()
        #                     data = json.loads(data_str) # Expecting JSON messages

        #                     if data.get("type") == "new_message":
        #                         # message_content = data.get("content")
        #                         # saved_message = await chat_service.save_message(
        #                         #    db, room_id, current_user.id, message_content
        #                         # )
        #                         # message_to_broadcast = {"type": "message", "data": saved_message.dict()}
        #                         # if broadcast_client:
        #                         #    await broadcast_client.publish(channel=channel_name, message=json.dumps(message_to_broadcast))
        #                         # else: # Local broadcast only if no global broadcaster
        #                         #    await chat_manager.broadcast_to_room_locally(json.dumps(message_to_broadcast), room_id, exclude_sender=websocket)
        #                         pass # Placeholder for message handling

        #             except WebSocketDisconnect:
        #                 pass # Already handled by finally or manager will clean up
        #             except json.JSONDecodeError:
        #                 await websocket.send_text(json.dumps({"type": "error", "detail": "Invalid JSON message"}))
        #             except Exception as e:
        #                 # logger.error(f"Chat WebSocket error for room {room_id}, user {current_user.id}: {e}", exc_info=True)
        #                 # Optionally send an error to client before closing
        #                 await websocket.send_text(json.dumps({"type": "error", "detail": "An unexpected error occurred."}))
        #             finally:
        #                 chat_manager.disconnect(websocket, str(current_user.id), room_id)
        #                 # Broadcast presence update if implementing presence
        #                 # if broadcast_client:
        #                 #     await broadcast_client.publish(channel=f"presence_room_{room_id}", message=json.dumps({"user_id": current_user.id, "status": "offline"}))
        ```
        *The concurrent listening to client WebSocket and broadcaster subscriber is the most complex part of the endpoint.*

    *   **3.3.3. Sending Chat Messages (via HTTP API to trigger WebSocket broadcast):**
        *   While clients can send messages via WebSocket, sometimes an HTTP API endpoint is useful for the system or other services to send messages into a chat room.
        *   `POST /api/v1/chat/rooms/{room_id}/messages`
        *   This endpoint saves the message to PostgreSQL and then uses the `broadcast_client.publish(...)` to send it to the room's channel. Connected WebSocket endpoints subscribed to this channel (via `broadcaster`) will then receive it and forward to their clients.

    *   **3.3.4. Fetching Chat History (Paginated HTTP API):**
        *   `GET /api/v1/chat/rooms/{room_id}/messages/` (standard paginated REST endpoint).

## 4. Video Meeting Integration (External API-First Video PaaS)

    ### 4.1. Strategic Overview
    *   The ERP backend orchestrates video meetings by interacting with a chosen external Video PaaS provider's API (e.g., Daily.co, Twilio Video, Vonage Video API).
    *   The backend handles creating rooms/sessions on the PaaS and generating access tokens for clients to join.
    *   The frontend uses the PaaS provider's client SDKs to embed the video experience.
    *   **No self-hosted STUN/TURN/SFU servers.**

    ### 4.2. General Setup Implementation Details (Video PaaS)

    *   **4.2.1. PaaS Provider Selection & Account Setup:**
        *   **[DECISION REQUIRED]: Select a Video PaaS provider.** (e.g., Daily.co, Twilio Video, Vonage Video API).
        *   Sign up for an account and obtain API Key and API Secret.
    *   **4.2.2. Library Installation (`requirements/base.txt`):**
        *   Add the chosen PaaS provider's Python server-side SDK.
            *   Example for Daily.co: `daily-python>=0.10.0,<0.11.0`
            *   Example for Twilio: `twilio>=7.0,<8.0`
    *   **4.2.3. Pydantic Settings (`app/core/config.py`):**
        *   Store PaaS API Key, API Secret, and any other relevant configuration.
            ```python
            # In Settings class:
            # VIDEO_PAAS_PROVIDER: str = "daily" # "daily", "twilio", "vonage"
            # VIDEO_PAAS_API_KEY: Optional[str] = None # From secrets manager
            # VIDEO_PAAS_API_SECRET: Optional[str] = None # From secrets manager
            # VIDEO_PAAS_DEFAULT_ROOM_DURATION_MINUTES: int = 60
            ```
    *   **4.2.4. Video PaaS Client/Service (`app/features/video_meetings/paas_client.py`):**
        *   Create a wrapper service to interact with the PaaS SDK.
            ```python
            # app/features/video_meetings/paas_clients/daily_co_client.py (Example)
            # from daily import Daily # If using Daily.co SDK
            # from app.core.config import settings

            # class DailyCoClient:
            #     def __init__(self):
            #         if not (settings.VIDEO_PAAS_API_KEY): # Ensure key is loaded
            #             raise ValueError("Daily.co API key not configured.")
            #         Daily.init(settings.VIDEO_PAAS_API_KEY) # Initialize SDK

            #     async def create_room(self, room_name: Optional[str] = None, expiry_minutes: Optional[int] = None) -> dict:
            #         # properties = {"exp": time.time() + (expiry_minutes or settings.VIDEO_PAAS_DEFAULT_ROOM_DURATION_MINUTES) * 60}
            #         # if room_name: properties["name"] = room_name
            #         # response = Daily.create_room(properties=properties)
            #         # return {"id": response.get("id"), "name": response.get("name"), "url": response.get("url")}
            #         pass # Replace with actual SDK calls

            #     async def get_meeting_token(self, room_name: str, user_id: str, is_owner: bool = False) -> str:
            #         # properties = {"room_name": room_name, "user_id": user_id, "is_owner": is_owner}
            #         # token_response = Daily.create_meeting_token(properties=properties)
            #         # return token_response.get("token")
            #         pass # Replace with actual SDK calls

            # video_paas_client = None # Singleton instance
            # def get_video_paas_client(): # Factory/DI
            #    global video_paas_client
            #    if video_paas_client is None:
            #        if settings.VIDEO_PAAS_PROVIDER == "daily":
            #            video_paas_client = DailyCoClient()
            #        # else if ... for other providers
            #        else: raise ValueError("Unsupported Video PaaS provider")
            #    return video_paas_client
            ```

    ### 4.3. Integration & Usage Patterns (Video PaaS)

    *   **4.3.1. API Endpoints for Managing Video Meetings (`app/features/video_meetings/router.py`):**
        *   `POST /api/v1/video-meetings/rooms/`: Create a new meeting room via the PaaS API.
            *   Takes room name (optional), expiry settings.
            *   Calls `video_paas_client.create_room()`.
            *   Stores basic room metadata (PaaS room ID, ERP internal meeting ID, associated ERP entity like project/event) in your PostgreSQL DB.
            *   Returns room URL and ERP internal meeting ID.
        *   `POST /api/v1/video-meetings/rooms/{erp_meeting_id}/join-token/`: Generate a client token to join a PaaS room.
            *   Takes `erp_meeting_id`. Looks up PaaS room ID/name.
            *   Calls `video_paas_client.get_meeting_token(paas_room_name, current_user.id, is_owner=...)`.
            *   Returns the token for the client SDK.
        *   `GET /api/v1/video-meetings/rooms/{erp_meeting_id}/`: Get details of a meeting (link, status from PaaS if available).
    *   **4.3.2. Frontend Integration:**
        *   Frontend calls "create room" API.
        *   Then calls "join token" API.
        *   Uses the PaaS provider's JavaScript (or mobile) SDK with the obtained token and room URL/name to embed and join the video call.

## 5. Scalability and Reliability

- **Chat WebSockets:**
  - Horizontal scaling of FastAPI instances requires `broadcaster` with Redis.
  - Monitor Redis Pub/Sub performance.
  - Optimize WebSocket connection management and OS limits for concurrent connections.
- **Video PaaS:** Scalability and reliability are primarily handled by the chosen PaaS provider. Monitor API call rates to the PaaS.

## 6. Security

- **WebSocket Authentication:** Crucial. Token-based (e.g., JWT in query param) is common.
- **Chat Authorization:** Ensure users can only join/send messages to rooms they are authorized for.
- **Video PaaS API Keys:** Store securely (Secrets Manager), use with least privilege.
- **Video Meeting Access Tokens:** Generate short-lived tokens for clients to join PaaS rooms. Ensure only authorized ERP users can obtain these tokens for specific meetings.
