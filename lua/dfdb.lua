-- main file for dfdb
--@module = true
--@enable = true

-- this is the help text that will appear in `help` and
-- `gui/launcher`. see possible tags here:
-- https://docs.dfhack.org/en/latest/docs/Tags.html
--[====[
dfdb
===========

Tags: fort | legends | introspection | productivity

Dwarf fortress database

it connects to a local redis and spams stuff there

Usage
-----

    enable dfdb
    disable dfdb
]====]
local CBID = "dfdb"
local YIELD_TIMEOUT_MS = 10

enabled = enabled or false
last_update_ms = 0

function isEnabled()
    -- this function is for the enabled API, the script won't show up on the
    -- control panel without it
    return enabled
end

local function yield_if_timeout()
    local now_ms = dfhack.getTickCount()
    if now_ms - last_update_ms > YIELD_TIMEOUT_MS then
        script.sleep(1, 'frames')
        last_update_ms = dfhack.getTickCount()
    end
end



local eventful = require('plugins.eventful')
local redis = require('redis')
--local client = nil

--client.set('foo', 'bar')
--local value = c:get('foo')
--dfhack.println(value)

dfhack.onStateChange[CBID] = function(sc)
    if sc == SC_MAP_UNLOADED then
        dfhack.run_command('disable', 'dfdb')

        -- ensure our mod doesn't try to enable itself when a different
        -- world is loaded where we are *not* active
        dfhack.onStateChange[CBID] = nil

        return
    end

    if sc ~= SC_MAP_LOADED or df.global.gamemode ~= df.game_mode.DWARF then
        return
    end

    dfhack.run_command('enable', 'dfdb')
end

if dfhack_flags.module then
    return
end

if not dfhack_flags.enable then
    print(dfhack.script_help())
    print()
    print(('dfdb is currently '):format(
            enabled and 'enabled' or 'disabled'))
    return
end

if dfhack_flags.enable_state then
    local client = redis.connect({host="127.0.0.1", port=6379, scheme="tcp"})
    if not client then 
        dfhack.println("Could not connect to Redis")
        return
    end
    dfhack.println("Redis connected")

    client:set('foo', 'bar')
    local value = client:get('foo')
    dfhack.println(value)
end
