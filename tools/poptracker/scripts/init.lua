-- Breath of the Wild for Archipelago: PopTracker pack (built by tools/build_poptracker.py).

ScriptHost:LoadScript("scripts/data.lua")
ScriptHost:LoadScript("scripts/logic.lua")

Tracker:AddItems("items/items.json")
Tracker:AddMaps("maps/maps.json")
Tracker:AddLocations("locations/locations.json")
Tracker:AddLayouts("layouts/tracker.json")

ScriptHost:AddOnLocationSectionChangedHandler("botw events", botw_update_events)
for _, code in pairs(REGION_MAPS) do
    ScriptHost:AddWatchForCode("botw regions " .. code, code, botw_update_regions)
    ScriptHost:AddWatchForCode("botw regions " .. code .. "_reached", code .. "_reached", botw_update_regions)
end
ScriptHost:AddWatchForCode("botw regions paraglider", "paraglider", botw_update_regions)

if PopVersion and Archipelago then
    ScriptHost:LoadScript("scripts/autotracking/archipelago.lua")
end
