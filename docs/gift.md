# GIFT - Integração de Growth Form e Climber

## Como o GIFT Organiza os Dados

O GIFT (Global Inventory of Floras and Traits) armazena atributos de plantas em campos separados. Para "forma de crescimento", existem **dois campos relevantes**:

### trait_value_1.2.2 (Growth Form / Woodiness)

- **Cobertura:** ~178,875 espécies
- **Valores típicos:**
  - `tree`
  - `shrub`
  - `herb`
  - `subshrub`
  - `woody` (ambíguo!)
  - `herbaceous`

### trait_value_1.4.2 (Climber Type)

- **Cobertura:** ~96,072 espécies
- **Valores típicos:**
  - `self-supporting` → NÃO é trepadeira
  - `vine` → É trepadeira herbácea
  - `liana` → É trepadeira lenhosa
  - `scrambler` → É trepadeira apoiante
  - `root climber` → É trepadeira com raízes adventícias

---

## O Problema

Os dois campos são **independentes**, o que gera inconsistências:

### Exemplo 1: Passiflora edulis (Maracujá)

| Campo       | Valor GIFT     | Problema              |
|-------------|----------------|-----------------------|
| trait_1.2.2 | "herbaceous"   | Correto, mas...       |
| trait_1.4.2 | "vine"         | ...é uma trepadeira!  |

- Se usarmos apenas trait_1.2.2 → `herb` (ERRADO para agrofloresta)
- Precisamos combinar → `climber` (CORRETO)

### Exemplo 2: Araucaria angustifolia (Araucária)

| Campo       | Valor GIFT       | Resultado   |
|-------------|------------------|-------------|
| trait_1.2.2 | "tree"           | ✓ Correto   |
| trait_1.4.2 | "self-supporting"| ✓ Confirma  |

- Resultado final → `tree` (CORRETO)

---

## A Lógica Condicional - Script Climber.R (Renata)

### Código Original (R/dplyr)

```r
spp_data <- comb_data %>%
  mutate(
    growth_form = case_when(
      # LIANA sempre tem prioridade (trepadeira lenhosa)
      trait_value_1.4.2 == "liana" & trait_value_1.2.2 == "shrub" ~ "liana",
      trait_value_1.4.2 == "liana" & trait_value_1.2.2 == "herb" ~ "liana",
      trait_value_1.4.2 == "liana" & is.na(trait_value_1.2.2) ~ "liana",
      trait_value_1.4.2 == "liana" & trait_value_1.2.2 == "other" ~ "liana",
      trait_value_1.4.2 == "liana" & trait_value_1.2.2 == "tree" ~ "liana",
      trait_value_1.4.2 == "liana" & trait_value_1.2.2 == "forb" ~ "liana",
      trait_value_1.4.2 == "liana" & trait_value_1.2.2 == "subshrub" ~ "liana",
      trait_value_1.4.2 == "liana" & trait_value_1.2.2 == "palm" ~ "liana",

      # SELF-SUPPORTING usa trait_1.2.2
      trait_value_1.4.2 == "self-supporting" & is.na(trait_value_1.2.2) ~ "other",
      trait_value_1.4.2 == "self-supporting" & trait_value_1.2.2 == "forb" ~ "forb",
      trait_value_1.4.2 == "self-supporting" & trait_value_1.2.2 == "graminoid" ~ "graminoid",
      trait_value_1.4.2 == "self-supporting" & trait_value_1.2.2 == "herb" ~ "forb",
      trait_value_1.4.2 == "self-supporting" & trait_value_1.2.2 == "other" ~ "other",
      trait_value_1.4.2 == "self-supporting" & trait_value_1.2.2 == "palm" ~ "palm",
      trait_value_1.4.2 == "self-supporting" & trait_value_1.2.2 == "shrub" ~ "shrub",
      trait_value_1.4.2 == "self-supporting" & trait_value_1.2.2 == "subshrub" ~ "subshrub",
      trait_value_1.4.2 == "self-supporting" & trait_value_1.2.2 == "tree" ~ "tree",

      # VINE sempre tem prioridade (trepadeira herbácea)
      trait_value_1.4.2 == "vine" & trait_value_1.2.2 == "shrub" ~ "vine",
      trait_value_1.4.2 == "vine" & trait_value_1.2.2 == "herb" ~ "vine",
      trait_value_1.4.2 == "vine" & is.na(trait_value_1.2.2) ~ "vine",
      trait_value_1.4.2 == "vine" & trait_value_1.2.2 == "other" ~ "vine",
      trait_value_1.4.2 == "vine" & trait_value_1.2.2 == "tree" ~ "vine",
      trait_value_1.4.2 == "vine" & trait_value_1.2.2 == "forb" ~ "vine",
      trait_value_1.4.2 == "vine" & trait_value_1.2.2 == "subshrub" ~ "vine",
      trait_value_1.4.2 == "vine" & trait_value_1.2.2 == "graminoid" ~ "vine",

      # Quando trait_1.4.2 é NA, usa trait_1.2.2
      is.na(trait_value_1.4.2) & trait_value_1.2.2 == "forb" ~ "forb",
      is.na(trait_value_1.4.2) & trait_value_1.2.2 == "graminoid" ~ "graminoid",
      is.na(trait_value_1.4.2) & trait_value_1.2.2 == "herb" ~ "forb",  # herb → forb
      is.na(trait_value_1.4.2) & trait_value_1.2.2 == "other" ~ "other",
      is.na(trait_value_1.4.2) & trait_value_1.2.2 == "palm" ~ "palm",
      is.na(trait_value_1.4.2) & trait_value_1.2.2 == "shrub" ~ "shrub",
      is.na(trait_value_1.4.2) & trait_value_1.2.2 == "subshrub" ~ "subshrub",
      is.na(trait_value_1.4.2) & trait_value_1.2.2 == "tree" ~ "tree",

      TRUE ~ trait_value_1.4.2  # Fallback
    )
  )
```

### Regras de Prioridade (Resumo)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  trait_1.4.2          │  trait_1.2.2      │  Resultado                      │
├───────────────────────┼───────────────────┼─────────────────────────────────┤
│  "liana"              │  (qualquer)       │  "liana"     ← SEMPRE PRIORIDADE│
│  "vine"               │  (qualquer)       │  "vine"      ← SEMPRE PRIORIDADE│
│  "self-supporting"    │  "tree"           │  "tree"                         │
│  "self-supporting"    │  "shrub"          │  "shrub"                        │
│  "self-supporting"    │  "herb"           │  "forb"      ← NORMALIZA        │
│  "self-supporting"    │  NA               │  "other"                        │
│  NA                   │  "tree"           │  "tree"                         │
│  NA                   │  "herb"           │  "forb"      ← NORMALIZA        │
│  NA                   │  (outro)          │  (valor de trait_1.2.2)         │
└───────────────────────┴───────────────────┴─────────────────────────────────┘
```

### Decisões de Design

1. **Preserva distinção liana vs vine** (não normaliza para "climber" genérico)
   - `liana` = trepadeira lenhosa
   - `vine` = trepadeira herbácea

2. **Normaliza herb → forb** (termo mais preciso botanicamente)

3. **Hierarquia clara:**
   - Trepadeiras (liana/vine) SEMPRE sobrescrevem growth_form
   - Self-supporting SEMPRE defere para trait_1.2.2

### Implementação Python Equivalente

```python
def determine_growth_form(trait_1_4_2: str, trait_1_2_2: str) -> str:
    """
    Determina growth_form baseado nas regras do Climber.R

    Args:
        trait_1_4_2: Valor de GIFT trait_value_1.4.2 (climber type)
        trait_1_2_2: Valor de GIFT trait_value_1.2.2 (growth form)

    Returns:
        Growth form normalizado
    """
    # Normalização de herb → forb
    if trait_1_2_2 == 'herb':
        trait_1_2_2 = 'forb'

    # Liana e vine sempre têm prioridade
    if trait_1_4_2 == 'liana':
        return 'liana'

    if trait_1_4_2 == 'vine':
        return 'vine'

    # Self-supporting usa trait_1.2.2
    if trait_1_4_2 == 'self-supporting':
        return trait_1_2_2 if trait_1_2_2 else 'other'

    # Quando trait_1.4.2 é None/NA, usa trait_1.2.2
    if trait_1_4_2 is None:
        return trait_1_2_2 if trait_1_2_2 else 'other'

    # Fallback
    return trait_1_4_2 or 'other'
```

### Valores Finais de Growth Form

| Valor        | Descrição                        | Uso no SAF                    |
|--------------|----------------------------------|-------------------------------|
| `tree`       | Árvore                           | Estrato emergente/alto        |
| `shrub`      | Arbusto                          | Estrato médio                 |
| `subshrub`   | Subarbusto                       | Estrato médio-baixo           |
| `palm`       | Palmeira                         | Estrato variável              |
| `liana`      | Trepadeira lenhosa               | Requer suporte, estrato médio |
| `vine`       | Trepadeira herbácea              | Requer suporte, estrato baixo |
| `forb`       | Erva não-graminoide              | Estrato baixo                 |
| `graminoid`  | Gramínea/capim                   | Estrato baixo                 |
| `other`      | Não classificado                 | Verificar manualmente         |

---

## Por Que Isso Importa para o DiversiPlant

No contexto de **sistemas agroflorestais**, a classificação correta é crítica:

| Forma de Crescimento | Uso no SAF                    | Impacto de Erro                          |
|----------------------|-------------------------------|------------------------------------------|
| **tree**             | Estrato emergente/alto        | Sombreamento excessivo se mal posicionada|
| **shrub**            | Estrato médio                 | Competição com culturas                  |
| **climber**          | Precisa de suporte (tutor)    | Planta morre sem estrutura adequada      |
| **herb**             | Estrato baixo                 | Sub-aproveitamento do espaço vertical    |

Se *Passiflora* for classificada como "herb" em vez de "climber", o sistema pode sugerir plantá-la no estrato baixo, quando na verdade ela precisa de tutores ou árvores de suporte.

---

## Questões para Definir com a Equipe

1. Quais valores de trait_1.4.2 devem ser mapeados para "climber"?
2. Como tratar quando trait_1.2.2 = "woody" + trait_1.4.2 = "liana"?
3. Existe prioridade? (trait_1.4.2 sempre sobrescreve trait_1.2.2?)
4. Quais ambiguidades do GIFT foram identificadas que precisam de regras especiais?
5. Devemos preservar subtipos (vine, liana, scrambler) ou normalizar tudo para "climber"?

---

## Abordagem de Implementação

### Opção 1: Incorporar lógica no Crawler

**Prós:**
- Dados já entram limpos no banco
- Pipeline único
- Garante consistência

**Contras:**
- Requer traduzir R → Python
- Acoplamento forte com regras que podem mudar

### Opção 2: Pós-Processamento com Script R

**Prós:**
- Mantém código R da Renata intacto
- Ela pode atualizar independentemente
- Facilita auditoria científica

**Contras:**
- Duas etapas para sincronizar
- Dependência do ambiente R

### Recomendação: Híbrido

```
Fase 1 (agora):   Crawler → Banco (bruto) → Script R → Banco (limpo)
Fase 2 (estável): Traduzir lógica validada para Python no crawler
```

---

## Referências

- [GIFT Database](https://gift.uni-goettingen.de/)
- [GIFT R Package](https://biogeomacro.github.io/GIFT/)
- Script: `Climber.R` (Renata Rodrigues Lucas)


---

Crawler GIFT atualizado. Aqui está o resumo das mudanças:

  Resumo das Alterações

  crawlers/gift.py
  ┌────────────────────────────────┬────────────────────────────────────────────────────────────────────┐
  │            Mudança             │                             Descrição                              │
  ├────────────────────────────────┼────────────────────────────────────────────────────────────────────┤
  │ TRAIT_IDS['growth_form']       │ Corrigido de 1.2.1 para 1.2.2                                      │
  ├────────────────────────────────┼────────────────────────────────────────────────────────────────────┤
  │ VALID_GROWTH_FORMS             │ Nova constante com valores válidos alinhados ao Climber.R          │
  ├────────────────────────────────┼────────────────────────────────────────────────────────────────────┤
  │ determine_growth_form()        │ Novo método - implementa lógica do Climber.R                       │
  ├────────────────────────────────┼────────────────────────────────────────────────────────────────────┤
  │ _normalize_growth_form_value() │ Novo método - normalização individual (herb→forb, grass→graminoid) │
  ├────────────────────────────────┼────────────────────────────────────────────────────────────────────┤
  │ combine_species_traits()       │ Novo método - combina trait_1.2.2 e trait_1.4.2 por espécie        │
  ├────────────────────────────────┼────────────────────────────────────────────────────────────────────┤
  │ run_with_climber_logic()       │ Novo método - executa pipeline completo com lógica Climber.R       │
  ├────────────────────────────────┼────────────────────────────────────────────────────────────────────┤
  │ _normalize_growth_form()       │ Removido - substituído por _normalize_growth_form_value()          │
  └────────────────────────────────┴────────────────────────────────────────────────────────────────────┘
  i18n/locales/*/messages.json

  Adicionadas traduções para:
  - liana - Liana (trepadeira lenhosa)
  - vine - Cipó (trepadeira herbácea)
  - forb - Erva não-graminoide
  - graminoid - Graminoide
  - subshrub - Subarbusto
  - other - Outro

  tests/unit/test_crawlers.py

  Adicionados 8 novos testes para validar a lógica Climber.R:
  - test_determine_growth_form_liana_priority
  - test_determine_growth_form_vine_priority
  - test_determine_growth_form_self_supporting
  - test_determine_growth_form_herb_to_forb
  - test_determine_growth_form_na_climber
  - test_determine_growth_form_case_insensitive
  - test_normalize_growth_form_value
  - test_valid_growth_forms_constant