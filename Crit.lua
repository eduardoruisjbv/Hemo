-- Critical hits: a school-coloured floating number plus, for hits on you, a
-- screen flash. Blood is the only texture: Physical keeps it red, every magic
-- school (see Schools.lua) tints it with its colour, and Shadow turns it
-- black with smoke and skulls.
--
-- Numbers: Blizzard's own floating text is drawn by the engine and cannot be
-- restyled per number, so crits get a number of Hemo's own (the normal
-- Blizzard numbers are left alone). The amount can be a secret value in
-- restricted content: it is only ever passed straight to SetText, never
-- calculated on.
-- UNIT_COMBAT carries the hit flag and the school as values that may also be
-- secret (bosses, Mythic+). A secret flag cannot be compared, so then nothing
-- is shown rather than guessing; a secret school falls back to blood.
-- The API gives no hit direction: a hit on you flashes a random side.
local _, ns = ...

local COOLDOWN = 0.30 -- minimum seconds between crit effects
local OWN_CAST_WINDOW = 1.0 -- a target crit counts as yours within this long after your cast

-- Total life of a crit effect: burst in, hold a moment, fade by 1.5 s.
local EFFECT_TIME = 1.5

local function StyleFor(schoolId)
  if not ns.db.critSchools then return ns.SCHOOLS.physical end
  return ns.SCHOOLS[schoolId] or ns.SCHOOLS.physical
end

-- Screen flash -------------------------------------------------------------

local flashFrame = CreateFrame("Frame", "HemoCritFrame", UIParent)
flashFrame:SetAllPoints(UIParent)
flashFrame:SetFrameStrata("BACKGROUND")
flashFrame:SetFrameLevel(5)
flashFrame:EnableMouse(false)
flashFrame:SetAlpha(0)

local flashTexture = flashFrame:CreateTexture(nil, "BACKGROUND")
flashTexture:SetAllPoints(flashFrame)

-- Optional layer over the blood (Shadow's smoke and skulls); same animation.
local overlayTexture = flashFrame:CreateTexture(nil, "ARTWORK")
overlayTexture:SetAllPoints(flashFrame)
overlayTexture:Hide()

local WHITE = { 1, 1, 1 }

-- The flash motion lives here, isolated, so an accessibility option
-- (reduce motion, softer palette) can replace it later. Durations, scale and
-- drift are set per school in Flash().
local flashGroup = flashFrame:CreateAnimationGroup()

-- The effect sprays in from the edge it hits: the layer starts small,
-- anchored at that edge, and expands fast to full size.
local burst = flashGroup:CreateAnimation("Scale")
burst:SetOrder(1)
burst:SetSmoothing("OUT")

local rise = flashGroup:CreateAnimation("Alpha")
rise:SetOrder(1)
rise:SetSmoothing("OUT")

-- Then it fades while slowly drifting.
local fall = flashGroup:CreateAnimation("Alpha")
fall:SetOrder(2)
fall:SetSmoothing("IN_OUT")

local drift = flashGroup:CreateAnimation("Translation")
drift:SetOrder(2)
drift:SetSmoothing("IN")

flashGroup:SetScript("OnFinished", function() flashFrame:SetAlpha(0) end)

local function SetScaleRange(animation, from, to)
  -- Scale animation API changed in 10.0; support both spellings.
  if animation.SetScaleFrom then
    animation:SetScaleFrom(from, from)
    animation:SetScaleTo(to, to)
  else
    animation:SetFromScale(from, from)
    animation:SetToScale(to, to)
  end
end

local function Flash(style)
  local strength = style.peak * (ns.db.critIntensity or 100) / 100
  local fallTime = EFFECT_TIME - style.inTime

  -- A random layer of the school, randomly mirrored: never the same twice in
  -- a row. Layers are heavy on the left except blood_right (heavy on the
  -- right); mirroring swaps the side, and the burst starts from that edge.
  local file = style.layers[math.random(#style.layers)]
  local mirrored = math.random() < 0.5
  local heavyOnLeft = (not file:find("blood_right", 1, true)) ~= mirrored
  flashTexture:SetTexture(ns.TEXTURE_PATH .. file .. ".png")
  flashTexture:SetTexCoord(mirrored and 1 or 0, mirrored and 0 or 1, 0, 1)
  flashTexture:SetBlendMode(style.blend)
  local tint = style.tint or WHITE
  flashTexture:SetVertexColor(tint[1], tint[2], tint[3])
  if style.overlay then
    -- The overlay is heavy on the left like the blood: follow the same side.
    overlayTexture:SetTexture(ns.TEXTURE_PATH .. style.overlay .. ".png")
    overlayTexture:SetTexCoord(heavyOnLeft and 0 or 1, heavyOnLeft and 1 or 0, 0, 1)
    overlayTexture:SetBlendMode("BLEND")
    overlayTexture:Show()
  else
    overlayTexture:Hide()
  end

  flashGroup:Stop()
  burst:SetOrigin(heavyOnLeft and "LEFT" or "RIGHT", 0, 0)
  burst:SetDuration(style.inTime)
  SetScaleRange(burst, style.burstFrom, 1.0)
  rise:SetDuration(style.inTime)
  rise:SetFromAlpha(0)
  rise:SetToAlpha(strength)
  fall:SetDuration(fallTime)
  fall:SetFromAlpha(strength)
  fall:SetToAlpha(0)
  drift:SetDuration(fallTime)
  -- Drift is authored for the left edge; flip x when the layer is mirrored.
  drift:SetOffset(heavyOnLeft and style.drift[1] or -style.drift[1], style.drift[2])
  flashFrame:SetAlpha(0)
  flashGroup:Play()
end

-- Floating numbers ---------------------------------------------------------

local DURATION = EFFECT_TIME
local POP_TIME = 0.14
local RISE_PIXELS = 70
local POOL_SIZE = 8
local BASE_FONT_SIZE = 30

local pool, active = {}, {}

local driver = CreateFrame("Frame")
driver:Hide()

local function CreateEntry()
  local frame = CreateFrame("Frame", nil, UIParent)
  frame:SetFrameStrata("HIGH")
  frame:SetSize(1, 1)
  frame:EnableMouse(false)
  frame:Hide()

  local splat = frame:CreateTexture(nil, "BACKGROUND")
  splat:SetSize(120, 120)
  splat:SetPoint("CENTER", frame, "CENTER", 0, 0)

  local text = frame:CreateFontString(nil, "OVERLAY")
  text:SetPoint("CENTER", frame, "CENTER", 0, 0)
  text:SetShadowColor(0, 0, 0, 0.9)
  text:SetShadowOffset(2, -2)

  return { frame = frame, splat = splat, text = text }
end

for i = 1, POOL_SIZE do pool[i] = CreateEntry() end

local function EaseOutQuad(t) return 1 - (1 - t) * (1 - t) end

local function Release(entry)
  entry.frame:Hide()
  entry.frame:ClearAllPoints()
  for i = #active, 1, -1 do
    if active[i] == entry then table.remove(active, i) end
  end
  pool[#pool + 1] = entry
  if #active == 0 then driver:Hide() end
end

local function Place(entry, rise)
  entry.frame:ClearAllPoints()
  if entry.plate and entry.plate:IsShown() then
    entry.frame:SetPoint("BOTTOM", entry.plate, "TOP", entry.dx, 24 + rise)
  else
    entry.frame:SetPoint("CENTER", UIParent, "CENTER", entry.dx, entry.baseY + rise)
  end
end

driver:SetScript("OnUpdate", function(_, elapsed)
  for i = #active, 1, -1 do
    local entry = active[i]
    entry.age = entry.age + elapsed
    local t = entry.age / DURATION
    if t >= 1 then
      Release(entry)
    else
      local pop = math.min(1, entry.age / POP_TIME)
      -- Pop in big and settle; the backdrop blooms slightly slower than the text.
      entry.frame:SetScale(entry.size * (2.0 - EaseOutQuad(pop)))
      local bloom = 120 * (0.6 + 0.55 * EaseOutQuad(math.min(1, entry.age / (POP_TIME * 1.4))))
      entry.splat:SetSize(bloom, bloom)
      local fade = t < 0.6 and 1 or (1 - (t - 0.6) / 0.4)
      entry.frame:SetAlpha(fade)
      entry.splat:SetAlpha(0.9 * fade)
      Place(entry, RISE_PIXELS * EaseOutQuad(t))
    end
  end
end)

local function SetAmount(fontString, amount)
  if amount == nil then
    fontString:SetText("")
    return
  end
  -- Secret amounts go straight to SetText (allowed, no arithmetic); readable
  -- ones are abbreviated. pcall keeps a surprise from ever throwing here.
  local ok = false
  if not (issecretvalue and issecretvalue(amount)) and AbbreviateLargeNumbers then
    ok = pcall(function() fontString:SetText(AbbreviateLargeNumbers(amount)) end)
  end
  if not ok then pcall(fontString.SetText, fontString, amount) end
end

local function ShowNumber(amount, onPlayer, style)
  if not ns.db.critNumbers then return end

  local entry = table.remove(pool)
  if not entry then
    -- All busy: recycle the oldest so a crit storm still shows the latest.
    entry = active[1]
    Release(entry)
    entry = table.remove(pool)
  end

  entry.age = 0
  entry.size = (ns.db.critNumberSize or 100) / 100
  entry.dx = math.random(-40, 40)
  entry.baseY = onPlayer and 40 or 120
  entry.plate = (not onPlayer) and C_NamePlate and C_NamePlate.GetNamePlateForUnit
    and C_NamePlate.GetNamePlateForUnit("target") or nil

  entry.text:SetFont(STANDARD_TEXT_FONT, BASE_FONT_SIZE, "THICKOUTLINE")
  entry.text:SetTextColor(style.color[1], style.color[2], style.color[3])
  SetAmount(entry.text, amount)
  entry.splat:SetTexture(ns.TEXTURE_PATH .. style.sprites[math.random(#style.sprites)] .. ".png")
  entry.splat:SetBlendMode(style.blend)
  local spriteTint = style.spriteTint or WHITE
  entry.splat:SetVertexColor(spriteTint[1], spriteTint[2], spriteTint[3])
  entry.splat:SetRotation(math.random() * math.pi * 2)
  entry.frame:SetAlpha(1)
  Place(entry, 0)
  entry.frame:Show()

  active[#active + 1] = entry
  driver:Show()
end

-- Events -------------------------------------------------------------------

local lastEffect = 0
local lastOwnCast = 0

-- Used by /hemo crit [school].
function ns.FlashCrit(schoolId)
  local style = ns.SCHOOLS[schoolId or "physical"] or ns.SCHOOLS.physical
  Flash(style)
  ShowNumber(math.random(12000, 98000), true, style)
end

-- /hemo crit demo: every school in turn, for judging the effects.
function ns.FlashAllSchools()
  for i, schoolId in ipairs(ns.SCHOOL_ORDER) do
    C_Timer.After((i - 1) * 2.0, function()
      print(string.format("|cffc0392bHemo|r: %s", ns.SCHOOLS[schoolId].name))
      ns.FlashCrit(schoolId)
    end)
  end
end

local function IsCrit(flagText)
  if issecretvalue and issecretvalue(flagText) then return false end
  return flagText == "CRITICAL" or flagText == "CRUSHING"
end

local function IsWound(action)
  if issecretvalue and issecretvalue(action) then return true end -- unreadable: let the flag decide
  return action == "WOUND"
end

local events = CreateFrame("Frame")
events:RegisterUnitEvent("UNIT_COMBAT", "player", "target")
events:RegisterUnitEvent("UNIT_SPELLCAST_SUCCEEDED", "player")
events:SetScript("OnEvent", function(_, event, unit, action, flagText, amount, schoolMask)
  if event == "UNIT_SPELLCAST_SUCCEEDED" then
    lastOwnCast = GetTime()
    return
  end
  if not IsWound(action) or not IsCrit(flagText) then return end

  local now = GetTime()
  if now - lastEffect < COOLDOWN then return end

  if unit == "player" and ns.db.critTaken then
    lastEffect = now
    local style = StyleFor(ns.ResolveSchool(schoolMask))
    Flash(style)
    ShowNumber(amount, true, style)
    ns.Fire("CRIT_TAKEN", style)
  elseif unit == "target" and ns.db.critDealt
      -- Anyone can hit the target; only attribute it to you right after a cast.
      and now - lastOwnCast <= OWN_CAST_WINDOW then
    lastEffect = now
    local style = StyleFor(ns.ResolveSchool(schoolMask))
    ShowNumber(amount, false, style)
    ns.Fire("CRIT_DEALT", style)
  end
end)
