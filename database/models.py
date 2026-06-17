from database.db import db_obj


class Session:
    @staticmethod
    def create(username: str):
        query = """
            INSERT INTO sessions (username)
            VALUES (%s)
            RETURNING session_id, username, created_at, last_active;
        """
        return db_obj.execute(query, (username,), fetch="one", commit=True)

    @staticmethod
    def get_by_id(session_id: str):
        query = "SELECT session_id, username, created_at, last_active FROM sessions WHERE session_id = %s;"
        return db_obj.execute(query, (session_id,), fetch="one")

    @staticmethod
    def get_by_username(username: str):
        query = "SELECT session_id, username, created_at, last_active FROM sessions WHERE username = %s;"
        return db_obj.execute(query, (username,), fetch="one")

    @staticmethod
    def get_all():
        query = "SELECT session_id, username, created_at, last_active FROM sessions ORDER BY last_active DESC;"
        return db_obj.execute(query, fetch="all")

    @staticmethod
    def update_last_active(session_id: str):
        query = "UPDATE sessions SET last_active = NOW() WHERE session_id = %s RETURNING session_id;"
        return db_obj.execute(query, (session_id,), fetch="one", commit=True)

    @staticmethod
    def delete(session_id: str):
        query = "DELETE FROM sessions WHERE session_id = %s RETURNING session_id;"
        return db_obj.execute(query, (session_id,), fetch="one", commit=True)


class Message:
    @staticmethod
    def insert(session_id: str, content: str, turn_index: int = 0):
        query = """
            INSERT INTO messages (session_id, content, turn_index)
            VALUES (%s, %s, %s)
            RETURNING message_id, session_id, turn_index, created_at;
        """
        return db_obj.execute(query, (session_id, content, turn_index), fetch="one", commit=True)

    @staticmethod
    def get_by_session(session_id: str):
        query = """
            SELECT message_id, session_id, turn_index, content, created_at
            FROM messages
            WHERE session_id = %s
            ORDER BY turn_index ASC;
        """
        return db_obj.execute(query, (session_id,), fetch="all")

    @staticmethod
    def delete_by_session(session_id: str):
        query = "DELETE FROM messages WHERE session_id = %s;"
        return db_obj.execute(query, (session_id,), commit=True)


class RetrievalLog:
    @staticmethod
    def insert(session_id: str, retrieval_info: str):
        query = """
            INSERT INTO retrieval_logs (session_id, retrieval_info)
            VALUES (%s, %s)
            RETURNING log_id, created_at;
        """
        return db_obj.execute(query, (session_id, retrieval_info), fetch="one", commit=True)

    @staticmethod
    def get_by_session(session_id: str):
        query = """
            SELECT log_id, session_id, retrieval_info, created_at
            FROM retrieval_logs
            WHERE session_id = %s
            ORDER BY created_at DESC;
        """
        return db_obj.execute(query, (session_id,), fetch="all")