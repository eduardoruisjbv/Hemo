-- Damage schools and the look of a critical hit in each.
--
-- UNIT_COMBAT passes the school as a bit mask: Physical 1, Holy 2, Fire 4,
-- Nature 8, Frost 16, Shadow 32, Arcane 64. Chaos is every school at once
-- (127). Like the hit flag, the mask can be a secret value in restricted
-- content; then there is no way to tell the school and the plain blood
-- (physical) effect is used instead.
local _, ns = ...

local PHYSICAL, HOLY, FIRE, NATURE, FROST, SHADOW, ARCANE = 1, 2, 4, 8, 16, 32, 64
local CHAOS_MASK = 127

-- Multi-school hits (Frostfire, Shadowflame, Spellstrike...) take the first
-- school found in this order, magic before physical.
local PRIORITY = {
  { FIRE, "fire" }, { FROST, "frost" }, { SHADOW, "shadow" }, { ARCANE, "arcane" },
  { NATURE, "nature" }, { HOLY, "holy" }, { PHYSICAL, "physical" },
}

-- Look of a crit. For now every school uses the same original red blood: the
-- schools stay defined (name, id) so a per-school look can be added later by
-- giving an entry its own fields.
--   layers:    full-screen textures, all heavy on the LEFT (mirrored at random)
--   tint:      optional colour multiplied onto the layer (nil = untouched)
--   overlay:   optional second full-screen layer drawn over the blood
--   sprites:   backdrop for the number; spriteTint colours it
--   color:     number colour
--   burstFrom: starting scale of the screen layer (smaller = bigger burst)
--   inTime:    seconds to reach full strength (snap vs creep)
--   drift:     {x, y} pixels the layer slides while it fades
--   peak:      maximum alpha
local function blood(name)
  return {
    name = name, layers = { "blood_left", "blood_right" },
    sprites = { "splat_1", "splat_2", "splat_3" },
    blend = "BLEND", color = { 0.95, 0.12, 0.12 },
    burstFrom = 0.35, inTime = 0.14, drift = { 0, -34 }, peak = 0.85,
  }
end

ns.SCHOOLS = {
  physical = blood("Físico"), fire = blood("Fogo"), frost = blood("Gelo"),
  shadow = blood("Sombra"), arcane = blood("Arcano"), nature = blood("Natureza"),
  holy = blood("Sagrado"), chaos = blood("Caos"),
}

ns.SCHOOL_ORDER = { "physical", "fire", "frost", "shadow", "arcane", "nature", "holy", "chaos" }

-- Returns a key of ns.SCHOOLS for a school mask (or nil/secret -> "physical").
function ns.ResolveSchool(mask)
  if mask == nil or (issecretvalue and issecretvalue(mask)) or type(mask) ~= "number" then
    return "physical"
  end
  if mask >= CHAOS_MASK then return "chaos" end
  for _, entry in ipairs(PRIORITY) do
    if bit.band(mask, entry[1]) ~= 0 then return entry[2] end
  end
  return "physical"
end
