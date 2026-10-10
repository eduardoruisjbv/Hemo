-- Hemo core: shared namespace, settings and a tiny internal event bus.
-- Modules talk through the bus so a future audio module can listen to the
-- same events without touching the visual code.
local _, ns = ...

ns.TEXTURE_PATH = "Interface\\AddOns\\Hemo\\Textures\\"

ns.DEFAULTS = {
  enabled = true, -- low-health blood
  intensity = 100, -- percent, multiplies the whole low-health effect
  critTaken = true, -- blood flash + number when a critical hit lands on you
  critDealt = true, -- blood number when your own critical hit lands
  critIntensity = 100, -- percent, strength of the screen flash
  critNumbers = true, -- draw styled crit numbers
  critSchools = true, -- reserved for a future per-school look; every crit is red blood for now
  critNumberSize = 100, -- percent
}

ns.db = {}

local listeners = {}

function ns.Register(event, callback)
  listeners[event] = listeners[event] or {}
  table.insert(listeners[event], callback)
end

function ns.Fire(event, ...)
  local list = listeners[event]
  if not list then return end
  for i = 1, #list do list[i](...) end
end

local loader = CreateFrame("Frame")
loader:RegisterEvent("ADDON_LOADED")
loader:SetScript("OnEvent", function(_, _, addon)
  if addon ~= "Hemo" then return end
  loader:UnregisterEvent("ADDON_LOADED")

  HemoDB = HemoDB or {}
  for key, value in pairs(ns.DEFAULTS) do
    if type(HemoDB[key]) ~= type(value) then HemoDB[key] = value end
  end
  ns.db = HemoDB
  ns.Fire("SETTINGS_READY")
end)
