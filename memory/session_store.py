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
        self.sessions: dict[tuple, SessionStore] = {}

    def get_or_create_session(
    self,
    session_id: str | None = None,
    user_id: str | None = None,
) -> SessionStore:
        
    
    
        session_id = session_id or str(uuid.uuid4())
        cache_key = (session_id, user_id)

        if cache_key not in self.sessions:
        # scope the DB check to this user
            existing = Session.get_by_id_and_user(session_id, user_id) 
            if not existing:
                anyone_owns_it = Session.get_by_id(session_id)
                if anyone_owns_it:
                    session_id = str(uuid.uuid4())
                    cache_key = (session_id, user_id)
                    Session.create(session_id, user_id)

                else:
                    Session.create(session_id, user_id)

            store = SessionStore(session_id)
        # only load messages if session belongs to this user
            if existing:
                rows = Message.get_by_session(session_id)
            else:
                rows = []
                if rows:
                    for row in rows:
                        raw = row[3]
                        if "| A: " in raw:

                            q, a = raw.split("| A: ", 1)
                            store.history.append({"query": q[3:], "response": a})

            self.sessions[cache_key] = store

        Session.update_last_active(session_id)
        return self.sessions[cache_key]

    def get_history(self, session_id: str, user_id: str = None):
        session = self.get_or_create_session(session_id, user_id)
        return session.get_history()

    def append(self, session_id: str, query: str, response: str, user_id: str = None):
        session = self.get_or_create_session(session_id, user_id)
        session.append_history(query, response)

    def clear(self, session_id: str, user_id: str = None):
        cache_key = (session_id, user_id)
        if cache_key in self.sessions:
            self.sessions[cache_key].clear_history()


session_manager = SessionManager()