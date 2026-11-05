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

-- With region_lock (slot data), the regions open from the Great Plateau
-- outward, the Paraglider to leave it: one is in logic once its map is received
-- and it borders one already in logic, across the seed's open borders (slot
-- data region_borders); a region inside another's area with that one. With
-- map_travel_points (slot data), a map's travel point is warped to from
-- anywhere: its region is in logic once its map is received.
local function reached_regions()
    local reached = {["Great Plateau"] = true}
    if Tracker:ProviderCountForCode("paraglider") > 0 then
        local opened = {}
        for region, code in pairs(REGION_MAPS) do
            opened[region] = Tracker:ProviderCountForCode(code) > 0
            if opened[region] and enabled(SLOT_DATA.map_travel_points) then
                reached[region] = true
            end
        end
        -- pairs, not ipairs: the slot data's lists, whatever their first index.
        local borders = {}
        for _, border in pairs(SLOT_DATA.region_borders or {}) do
            local ends = {}
            for _, name in pairs(border) do
                ends[#ends + 1] = name
            end
            borders[#borders + 1] = ends
        end
        local grown = true
        while grown do
            grown = false
            for _, ends in ipairs(borders) do
                for i = 1, 2 do
                    local from, to = ends[i], ends[3 - i]
                    if reached[from] and not reached[to] and opened[to] then
                        reached[to] = true
                        grown = true
                    end
                end
            end
        end
    end
    for inner, outer in pairs(INNER_REGIONS) do
        reached[inner] = reached[outer]
    end
    return reached
end

local function region_locked()
    return tonumber(SLOT_DATA.tower_maps) == 2 and enabled(SLOT_DATA.region_lock)
end

-- With region_lock, a location is out of reach until the regions it asks for
-- are reached (REGION_KEYS): the client sends Link back from a closed region.
function botw_regions(id)
    if not region_locked() then
        return true
    end
    local reached = reached_regions()
    for _, region in ipairs(REGION_KEYS[tonumber(id)] or {}) do
        if not reached[region] then
            return false
        end
    end
    return true
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

-- The regions panel: a region's "reached" toggle, which its tile and its piece
-- of the mini-map combine with its map, is on once the map is received and,
-- with region_lock, the region reached (scripts/init.lua watches the maps, the
-- Paraglider and these toggles: a click on one is undone).
--
-- Never from inside an item's change: a toggle written there reaches its
-- composite before the map does, and the composite, from its stage, writes the
-- map back off (PopTracker's tracker.cpp). The watches mark the panel stale,
-- and botw_regions_frame updates it at the next frame.
local regions_stale = false

function botw_regions_changed()
    regions_stale = true
end

function botw_regions_frame()
    if regions_stale then
        regions_stale = false
        botw_update_regions()
    end
end

-- A region's marker on the big map (locations/regions.json) is checked, grey
-- as a location done, once the region is open: green would read as a location
-- in logic.
local function open_marker(region, open)
    local section = Tracker:FindObjectForCode("@" .. region .. " Region/Region")
    local left = open and 0 or 1
    if section and section.AvailableChestCount ~= left then
        section.AvailableChestCount = left
    end
end

function botw_update_regions()
    local lock = region_locked()
    local reached = lock and reached_regions() or {}
    for region, code in pairs(REGION_MAPS) do
        local item = Tracker:FindObjectForCode(code .. "_reached")
        local value = Tracker:ProviderCountForCode(code) > 0 and (not lock or reached[region] == true)
        if item and item.Active ~= value then
            item.Active = value
        end
        open_marker(region, value)
    end
    open_marker("Great Plateau", true)
end

-- The regions' markers on the big map: hidden when the towers reveal the maps
-- (tower_maps vanilla), their maps then never received.
function botw_regions_shown()
    return tonumber(SLOT_DATA.tower_maps) ~= 0
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
