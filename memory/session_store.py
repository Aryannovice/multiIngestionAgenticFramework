import uuid
import logging

from database.models import Session, Message

logger = logging.getLogger(__name__)


class SessionStore:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.history = []

    def get_history(self):
        return self.history

    def append_history(self, query: str, response: str):
        logger.info(
            "APPENDING TO SESSION=%s | QUERY=%s", self.session_id, query
            )

        turn_index = len(self.history)
        Message.insert(
            self.session_id, f"Q: {query} | A: {response}", turn_index
            )

        self.history.append({
            "query": query, "response": response
            })
        logger.info(
            "NEW HISTORY SIZE=%d", len(self.history)
            )

    def clear_history(self):
        self.history.clear()


class SessionManager:
    def __init__(self):
        self.sessions: dict[str, SessionStore] = {}

    def get_or_create_session(self, session_id: str | None = None, user_id: str = None) -> SessionStore:
        session_id = session_id or str(uuid.uuid4())

        if session_id not in self.sessions:
            # check DB first before creating
            existing = Session.get_by_id(session_id)
            if not existing:
                Session.create(session_id, user_id)
            
            store = SessionStore(session_id)

            # load history from DB into memory
            rows = Message.get_by_session(session_id)
            if rows:
                for row in rows:
                    raw = row[3]  # content column
                    # stored as "Q: ... | A: ..."
                    if "| A: " in raw:
                        q, a = raw.split("| A: ", 1)
                        store.history.append({"query": q[3:], "response": a})

            self.sessions[session_id] = store

        Session.update_last_active(session_id)
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