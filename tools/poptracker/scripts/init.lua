-- Breath of the Wild for Archipelago: PopTracker pack (built by tools/build_poptracker.py).

ScriptHost:LoadScript("scripts/data.lua")
ScriptHost:LoadScript("scripts/logic.lua")

Tracker:AddItems("items/items.json")
Tracker:AddMaps("maps/maps.json")
Tracker:AddLocations("locations/locations.json")
Tracker:AddLayouts("layouts/tracker.json")

ScriptHost:AddOnLocationSectionChangedHandler("botw events", botw_update_events)
for _, code in pairs(REGION_MAPS) do
    ScriptHost:AddWatchForCode("botw regions " .. code, code, botw_regions_changed)
    ScriptHost:AddWatchForCode("botw regions " .. code .. "_reached", code .. "_reached", botw_regions_changed)
end
ScriptHost:AddWatchForCode("botw regions paraglider", "paraglider", botw_regions_changed)
ScriptHost:AddOnFrameHandler("botw regions", botw_regions_frame)

if PopVersion and Archipelago then
    ScriptHost:LoadScript("scripts/autotracking/archipelago.lua")
end
