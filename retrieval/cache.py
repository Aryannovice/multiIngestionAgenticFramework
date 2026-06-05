# from urllib import response

# import redis
# import json 
# import hashlib


# class RedisCache:
#     def __init__(self, host = 'localhost', port =  6379, db = 0,  ttl = 3300):
#         self.client = redis.Redis(host = host, port = port, db = db, decode_responses = True)
#         self.ttl = ttl

#     def _make_key(self, prefix: str, value: str) -> str:
#         return f"{prefix}:{hashlib.sha256(value.encode()).hexdigest()}"
    
#     def get(self, prefix: str, value: str):
#         key = self._make_key(prefix, value)
#         cached_set = self.client.get(key)
#         return json.loads(cached_set) if cached_set else None
    
#     def set(self, prefix: str, value: str, results: dict):
#         key = self._make_key(prefix, value)
#         self.client.setex(key, self.ttl, json.dumps(results))

