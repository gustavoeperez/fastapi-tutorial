import redis

# this will erase all testing data in Redis
redis_client = redis.StrictRedis(host='127.0.0.1', port=6379, db=0, decode_responses=True)
redis_client.flushdb()