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
    recommended = { "|cff66dd88[Recommended]|r ", "Recommended to keep enabled for the core low-health effect." },
    optional = { "|cffe0c060[Optional]|r ", "Optional: personal preference; leave disabled if you prefer a quieter screen." },
  }

  local function Tagged(tag, label, tooltip)
    local info = TAGS[tag]
    if not info then return label, tooltip end
    return info[1] .. label, info[2] .. "\n\n" .. tooltip
  end

  local function Legend()
    Header("Legend")
    if layout and CreateSettingsListTextEntryInitializer then
      layout:AddInitializer(CreateSettingsListTextEntryInitializer(
        "|cff66dd88[Recommended]|r Keep enabled for the core Hemo effect."
      ))
      layout:AddInitializer(CreateSettingsListTextEntryInitializer(
        "|cffe0c060[Optional]|r Personal preference; adjust to taste."
      ))
    end
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
    "Ativa estilos associados à escola do golpe. As escolas têm configurações próprias, mas atualmente compartilham o visual de sangue vermelho.", "optional")
  Checkbox("critTaken", "Ao receber crítico",
    "Número de sangue e flash na tela, num lado aleatório (o jogo não informa a direção do golpe). Não funciona quando o jogo esconde o tipo do golpe, como em chefes e Mítica+.", "optional")
  Checkbox("critDealt", "Ao acertar crítico",
    "Número de sangue sobre o alvo quando o seu golpe é crítico. Só vale logo depois de uma magia sua.", "optional")
  Percent("critIntensity", "Intensidade do flash", 10, 100, "Força do flash na tela ao receber crítico. Comandos: /hemo crit fogo, /hemo crit demo.", "optional")

  Settings.RegisterAddOnCategory(category)
  ns.category = category
end

ns.Register("SETTINGS_READY", Build)
