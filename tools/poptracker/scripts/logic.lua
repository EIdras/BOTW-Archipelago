-- The world's logic (botw_world/catalog.requirements), read from scripts/data.lua:
-- a location is reachable when each of its groups is met by one of its items.

SLOT_DATA = {}
-- The AP location ids of the connected seed (shops and stalls are optional);
-- nil before a connection: everything is shown.
SEED_LOCATIONS = nil

local function met(groups)
    for _, group in ipairs(groups) do
        local found = false
        for _, code in ipairs(group[1]) do
            if Tracker:ProviderCountForCode(code) >= group[2] then
                found = true
                break
            end
        end
        if not found then
            return false
        end
    end
    return true
end

local function enabled(value)
    return value == true or (type(value) == "number" and value ~= 0)
end

function botw_access(id)
    local groups = REQUIREMENTS[tonumber(id)]
    return groups == nil or met(groups)
end

-- The maps as region keys (slot data tower_maps 2, region_keys): a location
-- is in logic once its maps are received; without them, its rule's bracket
-- makes it a sequence break, possible but out of logic.
function botw_maps(id)
    if tonumber(SLOT_DATA.tower_maps) ~= 2 then
        return true
    end
    local maps = MAP_KEYS[tonumber(id)]
    if maps == nil then
        return true
    end
    for _, code in ipairs(maps) do
        if Tracker:ProviderCountForCode(code) < 1 then
            return false
        end
    end
    return true
end

function botw_in_seed(id)
    return SEED_LOCATIONS == nil or SEED_LOCATIONS[tonumber(id)] == true
end

-- Hyrule Castle's sanctum stays sealed until the seed's requirements are met
-- (botw_patch/ganon_gate.py, slot data "sanctum_*").
function botw_ganon()
    if not met(GOAL_REQUIREMENTS) then
        return false
    end
    if enabled(SLOT_DATA.sanctum_master_sword) and Tracker:ProviderCountForCode("master_sword") < 1 then
        return false
    end
    if enabled(SLOT_DATA.sanctum_runes) then
        for _, code in ipairs(RUNES) do
            if Tracker:ProviderCountForCode(code) < 1 then
                return false
            end
        end
    end
    local beasts = 0
    for _, code in pairs(BEAST_EVENTS) do
        beasts = beasts + Tracker:ProviderCountForCode(code)
    end
    if beasts < (tonumber(SLOT_DATA.sanctum_divine_beasts) or 0) then
        return false
    end
    return Tracker:ProviderCountForCode("shrines_cleared") >= (tonumber(SLOT_DATA.sanctum_shrines) or 0)
end

local function cleared(id)
    local section = Tracker:FindObjectForCode(LOCATION_SECTIONS[id])
    return section ~= nil and section.AvailableChestCount == 0
end

-- What the sanctum's gate counts, as the game does: the Divine Beasts freed
-- and the shrines cleared, from their sections (checked by Archipelago or by
-- hand). The locations' own rules need a beast reachable, not freed (data.lua).
function botw_update_events()
    for id, code in pairs(BEAST_EVENTS) do
        local item = Tracker:FindObjectForCode(code)
        local done = cleared(id)
        if item and item.Active ~= done then
            item.Active = done
        end
    end
    local count = 0
    for _, id in ipairs(SHRINES) do
        if cleared(id) then
            count = count + 1
        end
    end
    local shrines = Tracker:FindObjectForCode("shrines_cleared")
    if shrines and shrines.AcquiredCount ~= count then
        shrines.AcquiredCount = count
    end
end
