-- Breath of the Wild for Archipelago: PopTracker pack (built by tools/build_poptracker.py).

ScriptHost:LoadScript("scripts/data.lua")
ScriptHost:LoadScript("scripts/logic.lua")

Tracker:AddItems("items/items.json")
Tracker:AddMaps("maps/maps.json")
Tracker:AddLocations("locations/locations.json")
Tracker:AddLayouts("layouts/tracker.json")

ScriptHost:AddOnLocationSectionChangedHandler("botw events", botw_update_events)

if PopVersion and Archipelago then
    ScriptHost:LoadScript("scripts/autotracking/archipelago.lua")
end
