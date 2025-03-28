id = 1

import jwt
import datetime

secret_key = "secret_key"

payload = {
    "user_id": id,
    "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
}

token = jwt.encode(payload, secret_key, algorithm='HS256')
print(token)