-- Link on the map, told by the client (botw_client/uat.py) through UAT, on this computer:
-- "region", the region he stands in, and "x", "z", his position in the MainField, whole
-- world units (kept from the MainField in a shrine). His mark shows in the cell he stands in
-- (locations/link.json); with the "Follow" toggle, the view frames the region he enters.
ScriptHost:LoadScript("scripts/view.lua")

local region = nil

-- The view of Link's region (REGION_VIEWS: zoom, then its centre in pixels), on a change of
-- region or when the toggle is turned on; never on a move inside it.
local function follow()
    local view = REGION_VIEWS[region or ""]
    local toggle = Tracker:FindObjectForCode(FOLLOW_REGION)
    if view == nil or toggle == nil or not toggle.Active or Tracker.UiHint == nil then
        return
    end
    Tracker:UiHint("Zoom " .. MAP_NAME, tostring(view[1]))
    Tracker:UiHint("Pan " .. MAP_NAME, view[2] .. "," .. view[3])
end

local function set_count(code, value)
    local item = Tracker:FindObjectForCode(code)
    if item and item.AcquiredCount ~= value then
        item.AcquiredCount = value
    end
end

-- His cell, from 1 (0, 0: off the map shown): the counters the spots' rules read.
local function place(store)
    local x, z = store:ReadVariable("x"), store:ReadVariable("z")
    if type(x) ~= "number" or type(z) ~= "number" then
        return
    end
    local grid = LINK_GRID
    local col = math.floor(((x - grid.origin_x) * grid.scale - grid.left) / grid.cell) + 1
    local row = math.floor(((z - grid.origin_z) * grid.scale - grid.top) / grid.cell) + 1
    if col < 1 or row < 1 or col > grid.cols or row > grid.rows then
        row, col = 0, 0
    end
    set_count(LINK_ROW, row)
    set_count(LINK_COL, col)
    -- A click on the mark checks it: back as it was.
    local section = Tracker:FindObjectForCode("@Link/Link")
    if section and section.AvailableChestCount == 0 then
        section.AvailableChestCount = 1
    end
end

-- A white glow around the mark (PopTracker 0.32 or later).
local mark = Tracker:FindObjectForCode("@Link/Link")
if mark and Highlight and Highlight.Unspecified then
    mark.Highlight = Highlight.Unspecified
end

local function entered(store)
    local value = store:ReadVariable("region")
    if type(value) == "string" and value ~= "" and value ~= region then
        region = value
        follow()
    end
end

ScriptHost:AddVariableWatch("botw link", {"x", "z"}, place)
ScriptHost:AddVariableWatch("botw region", {"region"}, entered)
ScriptHost:AddWatchForCode("botw follow", FOLLOW_REGION, follow)
