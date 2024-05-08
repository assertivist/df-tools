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

it connects to a local valkey and spams stuff there

Usage
-----

    enable dfdb
    disable dfdb
]====]
local ns = "dfdb"
local script = require('gui.script')
local eventful = require('plugins.eventful')
local valkey = require('redis')
local serpent = require('serpent')
local sluggify = require('sluggify')
local client = nil
local dumper = require('dumper')
local machine = require('statemachine')

local world = df.global.world
local wslug = world.cur_savegame.save_dir

local df2utf = dfhack.df2utf
local TranslateName = dfhack.TranslateName

local CBID = ns
local YIELD_TIMEOUT_MS = 10
local RECURSION_DEPTH_LIMIT = 10

local YIELD_COUNT = 0
local TOTAL_RUN = 0

enabled = enabled or false
started_ms = dfhack.getTickCount()
last_update_ms = 0

state = machine.create({
    events = {
        { name = 'connect', from = 'none',      to = 'connected' },
        { name = 'sync',    from = 'connected', to = 'ready' },

        { name = 'fail',    from = 'none',      to = 'failure' },
        { name = 'fail',    from = 'connected', to = 'failure' },
        { name = 'fail',    from = 'ready',     to = 'failure' }
}})



function isEnabled()
    -- this function is for the enabled API, the script won't show up on the
    -- control panel without it
    return enabled
end

local function db_connect()
    if client == nil then
        client = valkey.connect({host="127.0.0.1", port=6379, scheme="tcp"})
        if not client then 
            dfhack.println("Could not connect to valkey")
            state:fail()
            return
        end
        dfhack.println("valkey connected")
    end
end

local function ns_log(level, text)
    if client then
        client:xadd(wslug .. "." .. ns .. ".log", "*", level, text)
    end
    dfhack.println(text)
end

local function ns_info(text) ns_log("info", text) end
local function ns_error(text) ns_log("error", text) end
local function ns_debug(text) ns_log("debug", text) end


local function yield_if_timeout()
    local now_ms = dfhack.getTickCount()
    if now_ms - last_update_ms > YIELD_TIMEOUT_MS then
        script.sleep(1, 'frames')
        YIELD_COUNT = YIELD_COUNT + 1
        last_update_ms = dfhack.getTickCount()
    end
end

dfhack.onStateChange[ns] = function(sc)
    if sc == SC_MAP_UNLOADED then
        dfhack.run_command('disable', ns)

        -- ensure our mod doesn't try to enable itself when a different
        -- world is loaded where we are *not* active
        dfhack.onStateChange[ns] = nil

        return
    end

    if sc ~= SC_MAP_LOADED or df.global.gamemode ~= df.game_mode.DWARF then
        return
    end

    dfhack.run_command('enable', ns)
end

if dfhack_flags.module then
    return
end

if not dfhack_flags.enable then
    print(dfhack.script_help())
    print()
    print((ns .. " is currently "):format(
            enabled and 'enabled' or 'disabled'))
    return
end


local function world_basic(w)
    return df2utf(dfhack.TranslateName(str))
end
-- calls elem_cb(k, v) for each element of the table
-- returns true if we iterated successfully, false if not
-- this differs from safe_pairs() above in that it only calls pcall() once per
-- full iteration and it returns whether iteration succeeded or failed.
local function safe_iterate(table, iterator_fn, elem_cb)
    local function iterate()
        for k,v in iterator_fn(table) do elem_cb(k, v) end
    end
    return pcall(iterate)
end

-- Get the date of the world as a string
-- Format: "YYYYY-MM-DD"
local function get_world_date_str()
    local month = dfhack.world.ReadCurrentMonth() + 1 --days and months are 1-indexed
    local day = dfhack.world.ReadCurrentDay()
    local date_str = string.format('%05d-%02d-%02d', df.global.cur_year, month, day)
    return date_str
end

local allowlist = {}
local denylist = {}

local dontcollapse = {
    -- not useful, pull from raw files
    ".*_raw.*",
    -- crashes the game ??
    ".*connected_.*"
}

local function collapser(thing, path, depth)
    for _, p in pairs(dontcollapse) do
        if string.find(path, p) then
            ns_info("Skipping " .. path .. " because it is dontcollapse")
            return "skipped"
        end
    end
    ns_info("Collapsing " .. path)
    if thing == nil then return nil end
    if type(thing) == "string" or 
       type(thing) == "boolean" or 
       type(thing) == "number" or
       type(thing) == "function" then
        return tostring(thing)
    end
    if not (type(thing) == "table" or 
       type(thing) == "userdata") or
       depth > RECURSION_DEPTH_LIMIT then
        return "ERROR: Unhandled type or recursion level too deep"
    end
    local collapsed = {}
    local girth = 0
    ns_debug("starting iteration on " .. path)
    for k, v in pairs(thing) do
        local sub_path = path .. "." .. k
        ns_debug("now going to either access or collapse " .. sub_path)
        yield_if_timeout()
        if type(v) == "table" or type(v) == "userdata" then
            ns_debug("collapsing " .. sub_path .. " k: " .. k)
            collapsed[k] = collapser(v, sub_path, depth + 1)
            ns_debug("result: " .. tostring(collapsed[k]))
        else
            ns_debug("accessing" .. sub_path .. " k: " .. tostring(k) .. " v: " .. tostring(v))
            collapsed[k] = v
        end
        ns_debug(sub_path .. " was saved successfully")
        girth = girth + 1
        if girth > 2500 then
            ns_error("Bailing on " .. sub_path .. " because of its immense Girth.")
            goto collapser_bail
        end
    end
    ::collapser_bail::
    return collapsed
end

local function descender(table, root, depth)
    if not client then return end
    print(string.format("%s (%d) %d", root, depth, dfhack.getTickCount() - started_ms))
    yield_if_timeout()
    if depth > RECURSION_DEPTH_LIMIT then
        ns_error(string.format("too deep: %s", root))
        goto descender_bail
    end
    for k, v in pairs(table) do
        yield_if_timeout()
        local path = root .. "." .. k
        if type(k) == "number" then
            -- make a set for # indexed tables
            local t = collapser(v, path, 0)
            if next(t) == nil then
                goto descender_next_pair
            end
            local st = serpent.dump(t)
            client:zadd(root, k, path)
            client:set(path, st)
            goto descender_next_pair
        else
            client:zadd(root, 0, path)
        end
        if type(v) == "table" or type(v) == "userdata" then
            descender(v, path, depth + 1)
        elseif type (v) == "string" or type(v) == "boolean" or type(v) == "number" then
            --dfhack.println(string.format("%-23s\t = %s", tostring(key), tostring(v)))
            client:set(tostring(path), v)
            TOTAL_RUN = TOTAL_RUN + 1
        else
            client:set(tostring(path), tostring(v))
        end
        ::descender_next_pair::
    end
    ::descender_bail::
end


local function legends_exp()
    --local wname = df2utf(TranslateName(world.world_data.name))
    --local waltname = df2utf(TranslateName(world.world_data.name, 1))
    ns_info("Legends mode detected, starting " .. wslug .. " export")
    yield_if_timeout()
    descender(world, wslug, 0)
    ns_info("Finished export of " .. wslug)
    ns_info(TOTAL_RUN .. " keys updated")
    ns_info(YIELD_COUNT .. " total yields")
end

if dfhack_flags.enable_state then
    if state.current == "none" then
        db_connect()
        state:connect()
    end
    
    if dfhack.world.isLegends() and state.current == "connected" then
        script.start(legends_exp)
        --legends_exp()
        ns_info("asdf")
    end
end
