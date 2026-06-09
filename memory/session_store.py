print("\nSESSION_STORE MODULE LOADED\n")
import uuid
import logging

logger = logging.getLogger(__name__)

class SessionStore:

    

    def __init__(self, session_id: str):
        
        self.session_id = session_id
        self.history = []

    def get_history(self):
        print("GET_HISTORY CALLED")
        return self.history

    def append_history(self, query: str, response: str):
        print("APPEND_HISTORY CALLED")
        logger.info(
       "APPENDING TO SESSION=%s | QUERY=%s",
    self.session_id,
    query,
)
        
        
        self.history.append(
            {
                "query": query,
                "response": response,
            }
        )

        logger.info(
    "NEW HISTORY SIZE=%d",
    len(self.history),
)

        print("APPEND HISTORY CALLED")
        print(self.history)

    def clear_history(self):
        self.history.clear()


class SessionManager:
    def __init__(self):
        self.sessions: dict[str, SessionStore] = {}

    def get_or_create_session(self, session_id: str | None = None) -> SessionStore:
        session_id = session_id or str(uuid.uuid4())

        if session_id not in self.sessions:
            self.sessions[session_id] = SessionStore(session_id)

        return self.sessions[session_id]

    def get_history(self, session_id: str):
        session = self.get_or_create_session(session_id)
        return session.get_history()

    def append(self, session_id: str, query: str, response: str):
        session = self.get_or_create_session(session_id)
        session.append_history(query, response)

    def clear(self, session_id: str):
        if session_id in self.sessions:
            self.sessions[session_id].clear_history()


session_manager = SessionManager()