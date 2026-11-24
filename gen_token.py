import jwt
import datetime

secret = '741me-7nVMIguTOdXDvZqHIT_xiUD7g0d5WRqIulIJiysg7GrxqrYrVTLKrlRcxI'

payload = {
    'iss': 'supabase-demo',
    'role': 'anon',
    'exp': int((datetime.datetime.now() + datetime.timedelta(hours=1)).timestamp()),
    'iat': int(datetime.datetime.now().timestamp()),
    'email': 'ysegovia@corpocentro.gob.ve'
}

token = jwt.encode(payload, secret, algorithm='HS256')
with open('/tmp/anon_key.txt', 'w') as f:
    f.write(token)
print('Token saved to /tmp/anon_key.txt')