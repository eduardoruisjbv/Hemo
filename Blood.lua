-- Low-health blood, drawn as four full-screen layers that arrive one after
-- another as health falls and are deliberately asymmetric (each favours
-- different corners). Health is read ONLY through UnitHealthPercent with a
-- ColorCurve: in combat the value can be secret, which may be passed to
-- textures but never calculated on. Each curve turns health straight into an
-- alpha that SetVertexColor consumes, so this file does no health math.
local _, ns = ...

-- Stage order is the order the blood arrives. points = { health, alpha }
-- ascending in health; pulse is the heartbeat half-period (seconds), different
-- per layer so the layers never beat in lockstep.
local LAYERS = {
  { file = "blood_edge", pulse = 0.90, points = { { 0.00, 0.95 }, { 0.15, 0.72 }, { 0.35, 0.38 }, { 0.55, 0.12 }, { 0.75, 0.00 } } },
  { file = "blood_left", pulse = 1.30, points = { { 0.00, 1.00 }, { 0.10, 0.90 }, { 0.28, 0.50 }, { 0.40, 0.00 } } },
  { file = "blood_right", pulse = 1.10, points = { { 0.00, 1.00 }, { 0.08, 0.90 }, { 0.20, 0.50 }, { 0.30, 0.00 } } },
  { file = "blood_veins", pulse = 0.70, points = { { 0.00, 1.00 }, { 0.12, 0.60 }, { 0.25, 0.00 } } },
}

local master = CreateFrame("Frame", "HemoBloodFrame", UIParent)
master:SetAllPoints(UIParent)
master:SetFrameStrata("BACKGROUND") -- under the whole UI: blood on the world, not on the panels
master:EnableMouse(false)

local flipped = false
local hasCurves = C_CurveUtil and C_CurveUtil.CreateColorCurve and true or false

for _, layer in ipairs(LAYERS) do
  local frame = CreateFrame("Frame", nil, master)
  frame:SetAllPoints(master)
  frame:EnableMouse(false)

  local texture = frame:CreateTexture(nil, "BACKGROUND")
  texture:SetAllPoints(frame)
  texture:SetTexture(ns.TEXTURE_PATH .. layer.file .. ".png")
  texture:SetVertexColor(1, 1, 1, 0)
  layer.texture = texture

  -- Heartbeat: a slow alpha swell on the frame itself. Frame alpha is never
  -- secret, so it multiplies freely with the secret vertex alpha.
  local group = frame:CreateAnimationGroup()
  group:SetLooping("BOUNCE")
  local beat = group:CreateAnimation("Alpha")
  beat:SetFromAlpha(1)
  beat:SetToAlpha(0.72)
  beat:SetDuration(layer.pulse)
  beat:SetSmoothing("IN_OUT")
  group:Play()

  if hasCurves then
    local curve = C_CurveUtil.CreateColorCurve()
    curve:SetType(Enum.LuaCurveType.Linear)
    for _, point in ipairs(layer.points) do
      curve:AddPoint(point[1], CreateColor(1, 1, 1, point[2]))
    end
    -- Always close the curve at full health with zero alpha: never rely on
    -- the engine holding the last point's value past the end of the curve.
    if layer.points[#layer.points][1] < 1 then
      curve:AddPoint(1.0, CreateColor(1, 1, 1, 0))
    end
    layer.curve = curve
  end
end

local function ApplyFlip()
  for _, layer in ipairs(LAYERS) do
    if flipped then
      layer.texture:SetTexCoord(1, 0, 0, 1)
    else
      layer.texture:SetTexCoord(0, 1, 0, 1)
    end
  end
end

local function HideAll()
  for _, layer in ipairs(LAYERS) do layer.texture:SetVertexColor(1, 1, 1, 0) end
end

-- Plan B when UnitHealthPercent is unavailable or fails: the plain health
-- fraction, which is only readable when the game does not mark it secret.
local function ReadFraction()
  local current, maximum = UnitHealth("player"), UnitHealthMax("player")
  if issecretvalue and (issecretvalue(current) or issecretvalue(maximum)) then return nil end
  if type(current) ~= "number" or type(maximum) ~= "number" or maximum <= 0 then return nil end
  return current / maximum
end

local warned = false

local function ApplyLayer(layer)
  local ok, color = pcall(UnitHealthPercent, "player", true, layer.curve)
  if ok and color and color.GetRGBA then
    layer.texture:SetVertexColor(color:GetRGBA())
    return true
  end
  if not ok and not warned then
    warned = true
    print("|cffc0392bHemo|r: UnitHealthPercent falhou (" .. tostring(color) .. "); usando plano B.")
  end
  local fraction = ReadFraction()
  if fraction then
    layer.texture:SetVertexColor(layer.curve:Evaluate(fraction):GetRGBA())
    return true
  end
  layer.texture:SetVertexColor(1, 1, 1, 0)
  return false
end

local function Update()
  if not hasCurves or not ns.db.enabled or UnitIsDeadOrGhost("player") then
    HideAll()
    return
  end
  for _, layer in ipairs(LAYERS) do ApplyLayer(layer) end
  ns.Fire("HEALTH_CHANGED")
end

function ns.RefreshBlood()
  master:SetAlpha((ns.db.intensity or 100) / 100)
  ApplyFlip()
  Update()
end

local events = CreateFrame("Frame")
events:RegisterUnitEvent("UNIT_HEALTH", "player")
events:RegisterUnitEvent("UNIT_MAXHEALTH", "player")
events:RegisterEvent("PLAYER_ALIVE")
events:RegisterEvent("PLAYER_DEAD")
events:RegisterEvent("PLAYER_UNGHOST")
events:RegisterEvent("PLAYER_ENTERING_WORLD")
events:RegisterEvent("PLAYER_REGEN_DISABLED")
events:SetScript("OnEvent", function(_, event)
  if event == "PLAYER_REGEN_DISABLED" and math.random() < 0.5 then
    -- Each fight can mirror the blood, so it never settles into one pattern.
    -- Done on combat entry, when the effect is normally invisible.
    flipped = not flipped
    ApplyFlip()
  end
  if ns.db.enabled ~= nil then Update() end
end)

ns.Register("SETTINGS_READY", ns.RefreshBlood)

-- /hemo test <0-100>: preview the layers at a given health percent.
-- /hemo crit: preview a critical hit. /hemo: open the options.
SLASH_HEMO1 = "/hemo"
SlashCmdList.HEMO = function(message)
  local arg = (message or ""):lower():match("^%s*(.-)%s*$")
  local percent = tonumber(arg:match("^test%s+(%d+)%s*$"))
  if percent and hasCurves then
    local previewPercent = math.min(100, percent)
    local fraction = previewPercent / 100
    for _, layer in ipairs(LAYERS) do
      layer.texture:SetVertexColor(layer.curve:Evaluate(fraction):GetRGBA())
    end
    print(string.format("|cffc0392bHemo|r: prévia a %d%% de vida (volta ao normal em 6 s).", previewPercent))
    -- A preview must never outlive itself: nothing else refreshes at full health.
    C_Timer.After(6, Update)
  elseif arg == "debug" then
    local layer = LAYERS[1]
    print("|cffc0392bHemo|r debug:")
    print("  curvas:", tostring(hasCurves), " UnitHealthPercent:", type(UnitHealthPercent))
    local ok, color = pcall(UnitHealthPercent, "player", true, layer.curve)
    if ok and color and color.GetRGBA then
      print("  UnitHealthPercent -> RGBA:", color:GetRGBA())
    else
      print("  UnitHealthPercent erro/vazio:", tostring(color))
    end
    local current, maximum = UnitHealth("player"), UnitHealthMax("player")
    print("  vida secreta?", tostring(issecretvalue and issecretvalue(current)),
      " fração legível:", tostring(ReadFraction()))
    print("  alpha real da camada 1:", select(4, layer.texture:GetVertexColor()))
  elseif arg:match("^crit") and ns.FlashCrit then
    local name = arg:match("^crit%s+(%S+)")
    if name == "demo" then
      ns.FlashAllSchools()
    else
      -- accepts the school id (fire) or its Portuguese name (fogo)
      local ALIASES = { fisico = "physical", fogo = "fire", gelo = "frost", sombra = "shadow",
        arcano = "arcane", natureza = "nature", sagrado = "holy", caos = "chaos" }
      ns.FlashCrit(name and (ALIASES[name] or name) or "physical")
    end
  else
    Update()
    if ns.OpenOptions then ns.OpenOptions() end
  end
end
