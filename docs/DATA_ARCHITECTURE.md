# DiversiPlant - Arquitetura de Dados

## Resumo Executivo

Este documento responde às questões levantadas sobre a arquitetura de dados do DiversiPlant, incluindo conformidade com Darwin Core, fontes de dados utilizadas e escopo das listas de espécies.

---

## 1. Sistema Geográfico Utilizado

### TDWG WGSRPD Level 3

**Usamos exclusivamente TDWG Level 3** (World Geographical Scheme for Recording Plant Distributions).

- **Fonte oficial**: https://github.com/tdwg/wgsrpd
- **Formato**: GeoJSON convertido para PostGIS
- **Total de regiões**: 369 regiões globalmente
- **Regiões do Brasil**:
  | Código | Nome | Área Aproximada |
  |--------|------|-----------------|
  | BZC | Brazil West-Central | Goiás, MT, MS, DF |
  | BZE | Brazil Northeast | BA, SE, AL, PE, PB, RN, CE, PI, MA |
  | BZL | Brazil Southeast | SP, RJ, ES, MG |
  | BZN | Brazil North | AM, PA, AC, RO, RR, AP, TO |
  | BZS | Brazil South | PR, SC, RS |

### Conformidade com Darwin Core

O TDWG WGSRPD é o padrão oficial do Darwin Core para distribuição de plantas:
- **dwc:countryCode** → Nível 1 (continente)
- **dwc:locality** → Pode mapear para Level 3
- **dwc:locationID** → Código TDWG (ex: "BZS" para Sul do Brasil)

Referência: https://dwc.tdwg.org/terms/#location

---

## 2. Fontes de Dados e Seus Papéis

### 2.1 WCVP (World Checklist of Vascular Plants)

**Papel**: Fonte PRIMÁRIA para distribuição geográfica

```
Tabela: wcvp_distribution
Campos: taxon_id, tdwg_code, establishment_means, endemic
Registros: ~2M registros de distribuição
```

- **O que fornece**: Lista de espécies por região TDWG com status (nativo/introduzido/endêmico)
- **Atualização**: Anual (Kew Gardens)
- **Cobertura**: Global, todas as plantas vasculares
- **URL**: https://wcvp.science.kew.org/

### 2.2 GIFT (Global Inventory of Floras and Traits)

**Papel**: Fonte PRIORITÁRIA para growth_form (traits funcionais)

```
Tabela: species_traits (source = 'gift')
Campos: growth_form, dispersal_syndrome, nitrogen_fixer
Registros: ~350K espécies com traits
```

- **O que fornece**: Traits funcionais (dispersão, fixação N, altura)
- **Prioridade**: GIFT é prioritário por usar definições mais consistentes:
  - Distingue **liana** (trepadeira lenhosa) de **vine** (trepadeira herbácea)
  - Usa lógica Climber.R de Renata (trait_1.2.2 + trait_1.4.2)
- **Acesso**: Via pacote R `GIFT`
- **URL**: https://gift.uni-goettingen.de/

### 2.3 REFLORA (Flora do Brasil 2020)

**Papel**: Fonte SECUNDÁRIA para espécies brasileiras (fallback quando GIFT vazio)

```
Tabela: species_traits (source = 'reflora')
Campos: growth_form, life_form, stratum
Registros: ~50K espécies brasileiras com traits
```

- **O que fornece**: Características morfológicas, nomes populares em português
- **Prioridade**: Usado quando GIFT não tem dados para espécies brasileiras
- **Cobertura**: ~50.000 espécies brasileiras
- **URL**: http://floradobrasil.jbrj.gov.br/

### 2.4 WCVP (para growth_form)

**Papel**: Fonte TERCIÁRIA para traits (fallback quando GIFT e REFLORA vazios)

```
Tabela: species_traits (source = 'wcvp')
Campos: growth_form
Nota: WCVP usa 'climber' genérico (não distingue liana/vine)
```

- **O que fornece**: Growth form básico de desambiguação
- **Limitação**: Usa "climber" genérico sem distinção liana vs vine
- **URL**: https://wcvp.science.kew.org/

### 2.5 TreeGOER (Tree Global Occurrences and Ecoregions)

**Papel**: Validação de ÁRVORES por ecorregião

```
Tabela: species_traits (source = 'treegoer')
Campos: growth_form = 'tree', ecoregion
Registros: ~80% das árvores globais
```

- **O que fornece**: Validação de que uma espécie é de fato uma árvore em determinada ecorregião
- **Cobertura**: Global, apenas árvores
- **URL**: https://treegoer.eu/

### 2.6 WorldClim

**Papel**: Dados climáticos (CRAWLER DISPONÍVEL, FILTRAGEM NÃO IMPLEMENTADA)

```
Status: Crawler existe em crawlers/worldclim.py
Campos disponíveis: 19 variáveis bioclimáticas (BIO1-BIO19)
Resolução: 1km (30 arc-seconds)
```

- **O que fornece**: Dados climáticos para futura filtragem de compatibilidade
- **Variáveis principais**:
  - BIO1: Temperatura média anual
  - BIO5: Temperatura máxima do mês mais quente
  - BIO6: Temperatura mínima do mês mais frio
  - BIO12: Precipitação anual
  - BIO15: Sazonalidade de precipitação
- **Status atual**: O crawler existe e pode buscar dados climáticos, mas a **filtragem de espécies baseada em clima NÃO está implementada** na aplicação web
- **URL**: https://worldclim.org/

### 2.7 GBIF (Global Biodiversity Information Facility)

**Papel**: NÃO USADO para listas de distribuição

```
Status: Disponível para consulta, mas NÃO integrado às listas atuais
```

- **Por que não usamos para distribuição**: GBIF contém registros de OCORRÊNCIA (pontos GPS de observações), não listas curadas de distribuição nativa
- **Diferença crítica**:
  - WCVP: "Espécie X é NATIVA da região Y" (curado por taxonomistas)
  - GBIF: "Espécie X foi OBSERVADA no ponto GPS Z" (pode ser cultivo, escape, erro)
- **Uso futuro potencial**: Validação de presença, dados de fenologia

---

## 3. O Que as Queries Retornam

### 3.1 Query Atual: Espécies por Região TDWG

```sql
SELECT s.canonical_name, su.is_tree, sr.is_native, sr.is_introduced
FROM species s
JOIN species_unified su ON s.id = su.species_id
JOIN species_regions sr ON s.id = sr.species_id
WHERE sr.tdwg_code = 'BZS';
```

**Retorna**: Todas as espécies com registro de distribuição WCVP para a região

**Inclui**:
- ✅ Espécies NATIVAS (is_native = TRUE)
- ✅ Espécies INTRODUZIDAS (is_introduced = TRUE)
- ✅ Espécies ENDÊMICAS (is_endemic = TRUE)

**NÃO inclui**:
- ❌ Espécies sem registro WCVP para a região
- ❌ Espécies apenas cultivadas (sem estabelecimento)
- ❌ Registros de ocorrência casual

### 3.2 Filtros Disponíveis

```sql
-- Apenas nativas
WHERE sr.is_native = TRUE AND sr.is_introduced = FALSE

-- Apenas endêmicas (APENAS nesta região)
WHERE sr.is_endemic = TRUE

-- Nativas + naturalizadas (excluindo invasoras recentes)
WHERE sr.is_native = TRUE OR sr.is_introduced = TRUE
```

### 3.3 Contagens Atuais (Janeiro 2026)

| Tabela | Registros | Descrição |
|--------|-----------|-----------|
| species | 448,749 | Todas as espécies (base) |
| species_unified | 328,269 | Espécies com traits consolidados |
| species_regions | 1,358,240 | Pares espécie-região (WCVP) |
| species_geometry | 362,631 | Espécies com geometria calculada |

**Interpretação**:
- 328K espécies têm informação de growth_form
- 362K espécies têm pelo menos 1 registro de região com geometria TDWG
- Média de ~4 regiões TDWG por espécie

---

## 4. Contagens por Região TDWG

### O que temos HOJE

✅ Espécies que **ocorrem naturalmente** em uma região TDWG (segundo WCVP)
✅ Traits consolidados com sistema de **prioridade** (gift > reflora > wcvp > treegoer)
❌ Filtragem climática **NÃO implementada** (crawler existe, mas não integrado)

### Como Funciona a Query Atual

O sistema aplica apenas filtragem geográfica:

```sql
-- Query atual (SEM filtragem climática)
SELECT COUNT(*)
FROM species_unified su
JOIN species_regions sr ON su.species_id = sr.species_id
WHERE sr.tdwg_code = 'BZS'
  AND su.is_tree = TRUE;
```

### Exemplo: BZS (Brazil South)

Contagens brutas da tabela `species_unified` + `species_regions`:

| Tipo | Quantidade |
|------|------------|
| **Árvores** | 791 |
| **Arbustos** | 2,591 |
| **Ervas** | 4,612 |
| **Trepadeiras** | 30 |

**Nota sobre os números**: Estes valores representam espécies com `growth_form` definido na tabela `species_unified` após aplicação do sistema de prioridade de fontes. Espécies podem ter classificações diferentes em fontes distintas (ex: *Euterpe edulis* é "palm" no REFLORA mas "tree" no TreeGOER).

### Sistema de Prioridade de Traits

Quando múltiplas fontes têm dados para a mesma espécie, usamos esta ordem de prioridade:

1. **GIFT** (definições mais consistentes: liana vs vine, lógica Climber.R)
2. **REFLORA** (fallback para espécies brasileiras sem dados GIFT)
3. **WCVP** (usa 'climber' genérico, sem distinção liana/vine)
4. **TreeGOER** (última opção para validação de árvores)

**Motivação da prioridade GIFT**: A definição de growth_form no GIFT é mais coerente com as funcionalidades do DiversiPlant porque distingue **liana** (trepadeira lenhosa) de **vine** (trepadeira herbácea) e usa a lógica Climber.R de Renata que combina `trait_1.2.2` + `trait_1.4.2`.

Isso explica por que os números diferem de queries diretas em `wcvp_distribution` + `species_traits`.

### Filtragem Climática (A IMPLEMENTAR)

Para implementar filtragem climática no futuro:

```
Espécies filtradas = WHERE (
  especie IN regiao_tdwg (WCVP)
  AND clima_local WITHIN envelope_climatico_especie (WorldClim)
)
```

**Fontes de dados climáticos disponíveis**:
- **WorldClim 2.1**: Crawler existe em `crawlers/worldclim.py` - precisa integração
- **CHELSA**: Dados climáticos de alta resolução - disponível para integração futura
- **TRY Database**: Traits funcionais incluindo tolerâncias - disponível para integração futura

---

## 5. Status de Implementação

### Implementado

1. ✅ Filtro por região TDWG Level 3
2. ✅ Distinção nativo/introduzido/endêmico
3. ✅ Filtro por growth_form (árvore/arbusto/erva/trepadeira)
4. ✅ Query PostGIS por coordenadas
5. ✅ Tabelas unificadas (`species_unified`, `species_regions`, `species_geometry`)
6. ✅ Sistema de prioridade de fontes para traits
7. ✅ Crawler WorldClim (busca dados climáticos)

### Próximos Passos (a implementar)

1. 🔄 **Filtragem climática**: Integrar WorldClim para filtrar espécies por compatibilidade
2. 🔄 Calcular envelopes climáticos por espécie
3. 🔄 Matching climático baseado em localização do usuário
4. 🔄 Adicionar tolerância a geadas como filtro

### Longo Prazo

1. ⏳ Refinar envelopes climáticos com dados de ocorrência GBIF
2. ⏳ Integrar dados de altitude/elevação
3. ⏳ Adicionar dados de solo (SoilGrids)
4. ⏳ Modelagem de nicho com MaxEnt/biomod2
5. ⏳ Integração com CHELSA para maior resolução climática

---

## 6. Glossário Darwin Core

| Termo DwC | Nossa Implementação |
|-----------|---------------------|
| `dwc:scientificName` | `species.canonical_name` |
| `dwc:family` | `species.family` |
| `dwc:genus` | `species.genus` |
| `dwc:locationID` | `species_regions.tdwg_code` |
| `dwc:establishmentMeans` | `species_regions.is_native`, `is_introduced` |
| `dwc:occurrenceStatus` | Não implementado (seria GBIF) |

Referência completa: https://dwc.tdwg.org/terms/

---

## Contato

Para discussão sobre estratégia de espécies climaticamente adaptadas:
- **Autor**: Stickybit <dev@stickybit.com.br>
- **Data**: 2026-01-20
- **Última atualização**: 2026-01-20 (corrigido: WorldClim não está integrado para filtragem)
