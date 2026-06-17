from database.db import db_obj

result = db_obj.execute("SELECT 1;", fetch="one")
print(result)