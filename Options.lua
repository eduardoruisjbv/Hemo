-- Hemo options: native Settings API, panel under Options > AddOns > Hemo.
local _, ns = ...

function ns.OpenOptions()
  if ns.category and Settings and Settings.OpenToCategory then
    Settings.OpenToCategory(ns.category:GetID())
  end
end

local function Build()
  if ns.category or not (Settings and Settings.RegisterVerticalLayoutCategory
      and Settings.RegisterAddOnSetting) then
    return
  end

  local category, layout = Settings.RegisterVerticalLayoutCategory("Hemo")

  local function Header(text)
    if layout and CreateSettingsListSectionHeaderInitializer then
      layout:AddInitializer(CreateSettingsListSectionHeaderInitializer(text))
    end
  end

  local TAGS = {
    recommended = { "|cff66dd88[Recomendado]|r ", "Recomendado manter ativo para o efeito principal de vida baixa." },
    optional = { "|cffe0c060[Opcional]|r ", "Opcional: preferência pessoal; ajuste a gosto." },
  }

  local function Tagged(tag, label, tooltip)
    local info = TAGS[tag]
    if not info then return label, tooltip end
    return info[1] .. label, info[2] .. "\n\n" .. tooltip
  end

  local function Legend()
    if not (layout and CreateSettingsListTextEntryInitializer) then return end
    Header("Legenda")
    layout:AddInitializer(CreateSettingsListTextEntryInitializer(
      TAGS.recommended[1] .. "Mantenha ativo para o efeito principal do Hemo."))
    layout:AddInitializer(CreateSettingsListTextEntryInitializer(
      TAGS.optional[1] .. "Preferência pessoal; ajuste a gosto."))
  end

  local function Register(key, varType, label)
    local setting = Settings.RegisterAddOnSetting(category, "Hemo_" .. key, key, ns.db,
      varType, label, ns.DEFAULTS[key])
    if setting.SetValueChangedCallback then
      setting:SetValueChangedCallback(function() ns.RefreshBlood() end)
    end
    return setting
  end

  local function Checkbox(key, label, tooltip, tag)
    label, tooltip = Tagged(tag, label, tooltip)
    Settings.CreateCheckbox(category, Register(key, Settings.VarType.Boolean, label), tooltip)
  end

  local function Percent(key, label, minValue, maxValue, tooltip, tag)
    label, tooltip = Tagged(tag, label, tooltip)
    local options = Settings.CreateSliderOptions(minValue, maxValue, 5)
    options:SetLabelFormatter(MinimalSliderWithSteppersMixin.Label.Right, function(value)
      return string.format("%d%%", value)
    end)
    Settings.CreateSlider(category, Register(key, Settings.VarType.Number, label), options, tooltip)
  end

  Legend()
  Header("Vida baixa")
  Checkbox("enabled", "Ativar sangue na tela",
    "O sangue toma a tela aos poucos conforme a vida cai, com camadas assimétricas e batimento. Comando /hemo test 20 para ver.", "recommended")
  Percent("intensity", "Intensidade", 10, 100, "Força do efeito de vida baixa.", "optional")

  Header("Golpe crítico")
  Checkbox("critNumbers", "Números de crítico com sangue",
    "Desenha o dano do crítico com respingo de sangue. Os números normais da Blizzard continuam como estão.", "optional")
  Percent("critNumberSize", "Tamanho do número", 50, 200, "Tamanho do número de crítico.", "optional")
  Checkbox("critSchools", "Efeito por escola de dano",
    "Reservado: por enquanto todo crítico usa o sangue vermelho, qualquer que seja a escola.", "optional")
  Checkbox("critTaken", "Ao receber crítico",
    "Número de sangue e flash na tela, num lado aleatório (o jogo não informa a direção do golpe). Não funciona quando o jogo esconde o tipo do golpe, como em chefes e Mítica+.", "optional")
  Checkbox("critDealt", "Ao acertar crítico",
    "Número de sangue sobre o alvo quando o seu golpe é crítico. Só vale logo depois de uma magia sua.", "optional")
  Percent("critIntensity", "Intensidade do flash", 10, 100, "Força do flash na tela ao receber crítico. Comandos: /hemo crit fogo, /hemo crit demo.", "optional")

  Settings.RegisterAddOnCategory(category)
  ns.category = category
end

ns.Register("SETTINGS_READY", Build)
