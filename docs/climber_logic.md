# Lógica do Climber.R - Determinação de Forma de Crescimento

**Autora:** Renata Rodrigues Lucas
**Implementação Python:** `crawlers/gift.py`

---

## Contexto

O banco de dados GIFT (Global Inventory of Floras and Traits) armazena informações sobre formas de crescimento de plantas em **dois campos separados**:

| Campo | ID GIFT | Descrição | Cobertura |
|-------|---------|-----------|-----------|
| `trait_value_1.2.2` | 1.2.2 | Forma de crescimento geral | ~178.875 espécies |
| `trait_value_1.4.2` | 1.4.2 | Tipo de trepadeira | ~96.072 espécies |

O problema é que esses campos são **independentes** e podem gerar classificações incorretas quando usados isoladamente.

---

## O Problema

### Exemplo: Passiflora edulis (Maracujá)

```
trait_1.2.2 = "herb"        → Classificaria como erva
trait_1.4.2 = "vine"        → Indica que é trepadeira

Resultado ERRADO (só trait_1.2.2): herb
Resultado CORRETO (combinando):    vine (trepadeira herbácea)
```

### Exemplo: Bauhinia sp. (Cipó-escada)

```
trait_1.2.2 = "shrub"       → Classificaria como arbusto
trait_1.4.2 = "liana"       → Indica que é trepadeira lenhosa

Resultado ERRADO (só trait_1.2.2): shrub
Resultado CORRETO (combinando):    liana (trepadeira lenhosa)
```

---

## Regras de Prioridade

O script Climber.R estabelece a seguinte hierarquia:

```
┌─────────────────────────────────────────────────────────────────┐
│                    REGRAS DE PRIORIDADE                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Se trait_1.4.2 = "liana"  → SEMPRE retorna "liana"          │
│     (trepadeira lenhosa, ignora trait_1.2.2)                    │
│                                                                 │
│  2. Se trait_1.4.2 = "vine"   → SEMPRE retorna "vine"           │
│     (trepadeira herbácea, ignora trait_1.2.2)                   │
│                                                                 │
│  3. Se trait_1.4.2 = "self-supporting" → usa trait_1.2.2        │
│     (planta auto-sustentada, não é trepadeira)                  │
│                                                                 │
│  4. Se trait_1.4.2 = NA/vazio → usa trait_1.2.2                 │
│     (sem informação de trepadeira, usa forma geral)             │
│                                                                 │
│  5. Normalização: "herb" → "forb"                               │
│     (termo mais preciso botanicamente)                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## ⚠️ Casos Não Previstos no Climber.R

O script Climber.R trata **apenas 3 valores** de `trait_1.4.2`:
- `liana`
- `vine`
- `self-supporting`

Porém, o GIFT pode conter **outros valores** que não estão cobertos explicitamente:

### Valores Pendentes de Definição

| Valor GIFT | Descrição | Comportamento Atual | Sugestão |
|------------|-----------|---------------------|----------|
| `scrambler` | Trepadeira escandente/apoiante | Cai no fallback → `other` | **liana** ou **vine**? |
| `root climber` | Trepadeira com raízes adventícias (ex: Hedera, Ficus) | Cai no fallback → `other` | **liana**? |
| `tendril climber` | Trepadeira com gavinhas (ex: Passiflora, Vitis) | Cai no fallback → `other` | **vine** ou **liana**? |
| `twining` | Trepadeira volúvel (ex: Ipomoea, Convolvulus) | Cai no fallback → `other` | **vine**? |
| `hook climber` | Trepadeira com ganchos/espinhos (ex: Bougainvillea) | Cai no fallback → `other` | **liana**? |
| `leaning` | Planta apoiante | Cai no fallback → `other` | **self-supporting**? |
| `epiphytic climber` | Trepadeira epífita | Cai no fallback → `other` | **liana** ou **epiphyte**? |

### Fallback Atual

No R original:
```r
TRUE ~ trait_value_1.4.2  # Mantém o valor original (não normaliza)
```

No Python atual:
```python
# Se climber tem valor não reconhecido, tenta normalizar
if climber:
    return self._normalize_growth_form_value(climber)
return 'other'
```

### Questões para Definir com a Equipe

1. **scrambler** → Deve ser classificado como `liana` (lenhoso) ou `vine` (herbáceo)?
2. **root climber** → Geralmente são lenhosos (Hedera, Ficus), então `liana`?
3. **tendril climber** → Depende se é herbáceo ou lenhoso?
4. **twining** → Maioria são herbáceas (Ipomoea), então `vine`?
5. **hook climber** → Geralmente lenhosos (Bougainvillea), então `liana`?
6. **leaning** → É realmente auto-sustentado ou precisa de suporte?

### Proposta de Mapeamento (Pendente Validação)

```python
CLIMBER_TYPE_MAP = {
    # Já definidos no Climber.R
    'liana': 'liana',
    'vine': 'vine',
    'self-supporting': None,  # usa trait_1.2.2

    # Propostas para validação
    'scrambler': 'liana',        # ?
    'root climber': 'liana',     # ?
    'tendril climber': 'vine',   # ? depende se herbáceo/lenhoso
    'twining': 'vine',           # ?
    'hook climber': 'liana',     # ?
    'leaning': None,             # ? usa trait_1.2.2
    'epiphytic climber': 'liana', # ?
}
```

> **IMPORTANTE:** Este mapeamento precisa ser validado pela equipe antes de implementar.

---

## Tabela de Decisão Completa

| trait_1.4.2 (Climber) | trait_1.2.2 (Growth Form) | Resultado Final |
|-----------------------|---------------------------|-----------------|
| `liana` | tree | **liana** |
| `liana` | shrub | **liana** |
| `liana` | herb | **liana** |
| `liana` | (qualquer) | **liana** |
| `liana` | NA | **liana** |
| `vine` | tree | **vine** |
| `vine` | shrub | **vine** |
| `vine` | herb | **vine** |
| `vine` | (qualquer) | **vine** |
| `vine` | NA | **vine** |
| `self-supporting` | tree | tree |
| `self-supporting` | shrub | shrub |
| `self-supporting` | herb | **forb** |
| `self-supporting` | palm | palm |
| `self-supporting` | NA | other |
| NA | tree | tree |
| NA | shrub | shrub |
| NA | herb | **forb** |
| NA | graminoid | graminoid |
| NA | NA | other |

---

## Valores de Saída Padronizados

Após aplicar a lógica, os valores possíveis de `growth_form` são:

| Valor | Descrição | Uso em SAF |
|-------|-----------|------------|
| `tree` | Árvore | Estrato emergente/alto |
| `shrub` | Arbusto | Estrato médio |
| `subshrub` | Subarbusto | Estrato médio-baixo |
| `palm` | Palmeira | Estrato variável |
| `liana` | Trepadeira lenhosa | Requer suporte, perene |
| `vine` | Trepadeira herbácea | Requer suporte, anual/bianual |
| `forb` | Erva não-graminoide | Estrato baixo |
| `graminoid` | Gramínea/capim | Estrato baixo, cobertura |
| `bamboo` | Bambu | Estrato médio-alto |
| `fern` | Samambaia | Estrato baixo, sombra |
| `succulent` | Suculenta | Estrato baixo, xerófito |
| `aquatic` | Aquática | Áreas alagadas |
| `epiphyte` | Epífita | Sobre outras plantas |
| `other` | Não classificado | Verificar manualmente |

---

## Por Que Isso Importa

### Para Sistemas Agroflorestais (SAF)

A classificação correta de trepadeiras é **crítica** para o planejamento de SAFs:

1. **Trepadeiras precisam de suporte**
   - Lianas e vines não se sustentam sozinhas
   - Precisam de tutores ou árvores hospedeiras
   - Se classificadas como "herb", o sistema pode sugerir plantio sem suporte

2. **Competição por luz**
   - Trepadeiras competem com a copa das árvores
   - Lianas podem sufocar árvores se não manejadas
   - Importante saber quais espécies têm esse comportamento

3. **Planejamento de consórcios**
   - Vines (herbáceas) são geralmente anuais → ciclo curto
   - Lianas (lenhosas) são perenes → ciclo longo
   - Diferentes estratégias de manejo

---

## Implementação

### Python (crawlers/gift.py)

```python
def determine_growth_form(trait_1_4_2: str, trait_1_2_2: str) -> str:
    """
    Determina growth_form baseado nas regras do Climber.R
    """
    # Normalização
    climber = trait_1_4_2.lower().strip() if trait_1_4_2 else None
    growth = trait_1_2_2.lower().strip() if trait_1_2_2 else None

    # herb → forb
    if growth in ['herb', 'herbaceous']:
        growth = 'forb'

    # Regra 1: liana SEMPRE tem prioridade
    if climber == 'liana':
        return 'liana'

    # Regra 2: vine SEMPRE tem prioridade
    if climber == 'vine':
        return 'vine'

    # Regra 3: self-supporting usa trait_1.2.2
    if climber == 'self-supporting':
        return growth if growth else 'other'

    # Regra 4: NA usa trait_1.2.2
    if climber is None:
        return growth if growth else 'other'

    return 'other'
```

### R Original (Climber.R)

```r
spp_data <- comb_data %>%
  mutate(
    growth_form = case_when(
      trait_value_1.4.2 == "liana" ~ "liana",
      trait_value_1.4.2 == "vine" ~ "vine",
      trait_value_1.4.2 == "self-supporting" & trait_value_1.2.2 == "herb" ~ "forb",
      trait_value_1.4.2 == "self-supporting" ~ trait_value_1.2.2,
      is.na(trait_value_1.4.2) & trait_value_1.2.2 == "herb" ~ "forb",
      is.na(trait_value_1.4.2) ~ trait_value_1.2.2,
      TRUE ~ trait_value_1.4.2
    )
  )
```

---

## Testes de Validação

A implementação Python possui 9 testes automatizados:

```bash
pytest tests/unit/test_crawlers.py::TestGIFTCrawler -v
```

| Teste | Descrição |
|-------|-----------|
| `test_determine_growth_form_liana_priority` | Liana sempre tem prioridade |
| `test_determine_growth_form_vine_priority` | Vine sempre tem prioridade |
| `test_determine_growth_form_self_supporting` | Self-supporting usa trait_1.2.2 |
| `test_determine_growth_form_herb_to_forb` | Herb é normalizado para forb |
| `test_determine_growth_form_na_climber` | NA usa trait_1.2.2 |
| `test_determine_growth_form_case_insensitive` | Case-insensitive |
| `test_normalize_growth_form_value` | Normalização de valores |
| `test_valid_growth_forms_constant` | Constante VALID_GROWTH_FORMS |

---

## Referências

- GIFT Database: https://gift.uni-goettingen.de/
- GIFT R Package: https://biogeomacro.github.io/GIFT/
- Weigelt, P., König, C. & Kreft, H. (2020). GIFT – A Global Inventory of Floras and Traits for macroecology and biogeography. Journal of Biogeography, 47, 16-43.
