-- Archipelago auto-tracking (PopTracker's "AP" button): items received and
-- locations checked, from the multiworld server.

local current_index = -1
local GOAL_STATUS = 30

local function set_goal(reached)
    local section = Tracker:FindObjectForCode(GOAL_SECTION)
    if section then
        section.AvailableChestCount = reached and 0 or section.ChestCount
    end
end

local function on_status(key, value)
    if key == STATUS_KEY then
        set_goal(value == GOAL_STATUS)
    end
end

local function reset_item(item)
    if item.Type == "toggle" then
        item.Active = false
    elseif item.Type == "progressive" then
        item.CurrentStage = 0
        item.Active = false
    elseif item.Type == "consumable" then
        item.AcquiredCount = 0
    end
end

local function on_clear(slot_data)
    SLOT_DATA = slot_data or {}
    current_index = -1
    for _, code in pairs(ITEM_CODES) do
        local item = Tracker:FindObjectForCode(code)
        if item then
            reset_item(item)
        end
    end
    for _, path in pairs(LOCATION_SECTIONS) do
        local section = Tracker:FindObjectForCode(path)
        if section then
            section.AvailableChestCount = section.ChestCount
        end
    end
    set_goal(false)
    -- The goal is no AP location: the server keeps the slot's status, 30 once
    -- the goal is reached.
    STATUS_KEY = "_read_client_status_" .. (Archipelago.TeamNumber or 0) .. "_" .. Archipelago.PlayerNumber
    Archipelago:SetNotify({STATUS_KEY})
    Archipelago:Get({STATUS_KEY})
    -- The seed's own locations: shops and stalls exist only by its options.
    local seed = {}
    local any = false
    for _, list in ipairs({Archipelago.MissingLocations or {}, Archipelago.CheckedLocations or {}}) do
        for _, id in ipairs(list) do
            seed[id] = true
            any = true
        end
    end
    SEED_LOCATIONS = any and seed or nil
    -- Rules are evaluated again when an item changes.
    local refresh = Tracker:FindObjectForCode("seed_loaded")
    if refresh then
        refresh.Active = not refresh.Active
    end
    botw_update_events()
end

local function on_item(index, item_id, item_name, player_number)
    if index <= current_index then
        return
    end
    current_index = index
    local code = ITEM_CODES[item_id]
    if not code then
        return
    end
    local item = Tracker:FindObjectForCode(code)
    if not item then
        return
    end
    if item.Type == "toggle" then
        item.Active = true
    elseif item.Type == "progressive" then
        if item.Active then
            item.CurrentStage = item.CurrentStage + 1
        else
            item.Active = true
        end
    elseif item.Type == "consumable" then
        item.AcquiredCount = item.AcquiredCount + item.Increment
    end
end

local function on_location(location_id, location_name)
    local path = LOCATION_SECTIONS[location_id]
    if not path then
        return
    end
    local section = Tracker:FindObjectForCode(path)
    if section then
        section.AvailableChestCount = 0
    end
end

Archipelago:AddClearHandler("botw clear", on_clear)
Archipelago:AddItemHandler("botw item", on_item)
Archipelago:AddLocationHandler("botw location", on_location)
Archipelago:AddRetrievedHandler("botw goal", on_status)
Archipelago:AddSetReplyHandler("botw goal", on_status)
