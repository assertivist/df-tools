local dfdb = {
    _VERSION = 'dfdb 0.0.1-dev',
    _DESCRIPTION = 'A connection from DFHack to Redis',
    _COPYRIGHT = 'Zlib'
}

local YIELD_TIMEOUT_MS = 10

local redis = require('redis')
local client = redis.connect({host="127.0.0.1",port=6379,scheme="tcp"})

--client.set('foo', 'bar')
--local value = c:get('foo')
--dfhack.println(value)

dfdb.client = client



return dfdb
