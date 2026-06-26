from database.db import db_obj


class User:
    @staticmethod
    def create(username: str, email: str, hashed_password: str, role: str = "user"):
        query = """
            INSERT INTO users (username, email, hashed_password, role)
            VALUES (%s, %s, %s, %s)
            RETURNING user_id, username, email, is_active, created_at;
        """
        return db_obj.execute(query, (username, email, hashed_password, role), fetch="one", commit=True)
    
    

    @staticmethod
    def get_by_username(username: str):
        query = """
            SELECT user_id, username, email, hashed_password, is_active, role
            FROM users
            WHERE username = %s;
        """
        return db_obj.execute(query, (username,), fetch="one")

    @staticmethod
    def get_by_email(email: str):
        query = "SELECT user_id FROM users WHERE email = %s;"
        return db_obj.execute(query, (email,), fetch="one")

    @staticmethod
    def get_by_id(user_id: str):
        query = "SELECT user_id, username, email, is_active, role FROM users WHERE user_id = %s;"
        return db_obj.execute(query, (user_id,), fetch="one")

    @staticmethod
    def update_last_login(user_id: str):
        query = "UPDATE users SET last_login = NOW() WHERE user_id = %s;"
        return db_obj.execute(query, (user_id,), commit=True)

    @staticmethod
    def deactivate(user_id: str):
        query = "UPDATE users SET is_active = FALSE WHERE user_id = %s RETURNING user_id;"
        return db_obj.execute(query, (user_id,), fetch="one", commit=True)


class Session:

    @staticmethod
    def get_all():
        query = """
            SELECT session_id, user_id, name, created_at, last_active
            FROM sessions
            ORDER BY last_active DESC;
        """
        return db_obj.execute(query, fetch="all")

    @staticmethod
    def create(session_id: str, user_id: str, name: str = None):
        query = """
            INSERT INTO sessions (session_id, user_id, name)
            VALUES (%s, %s, %s)
            ON CONFLICT (session_id) DO NOTHING
            RETURNING session_id, user_id, name, created_at, last_active;
        """
        return db_obj.execute(query, (session_id, user_id, name), fetch="one", commit=True)

    @staticmethod
    def get_by_id(session_id: str):
        query = """
            SELECT session_id, user_id, name, created_at, last_active
            FROM sessions
            WHERE session_id = %s;
        """
        return db_obj.execute(query, (session_id,), fetch="one")

    @staticmethod
    def get_by_user(user_id: str):
        query = """
            SELECT session_id, user_id, name, created_at, last_active
            FROM sessions
            WHERE user_id = %s
            ORDER BY last_active DESC;
        """
        return db_obj.execute(query, (user_id,), fetch="all")
    

    @staticmethod
    def get_by_id_and_user(session_id: str, user_id: str):
        query = """
        SELECT session_id, user_id, name, created_at, last_active
        FROM sessions
        WHERE session_id = %s AND user_id = %s;
    """
        return db_obj.execute(query, (session_id, user_id), fetch="one")
    

    @staticmethod
    def update_last_active(session_id: str):
        query = """
            UPDATE sessions
            SET last_active = NOW()
            WHERE session_id = %s
            RETURNING session_id;
        """
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
            ON CONFLICT (session_id, turn_index) DO NOTHING
            RETURNING message_id, session_id, turn_index, content, created_at;
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