# Plano: Melhoria da Categorização de Growth Form (WCVP)

**Status:** Aguardando aprovação
**Data:** 2026-01-28

## Problema

O crawler WCVP (`crawlers/wcvp.py:160-179`) usa parsing simplista por substring que:
- Não distingue **liana** vs **vine** (retorna "climber" genérico para 10,282 espécies)
- Não normaliza **herb** → **forb** (81,094 espécies)
- Deixa **52,328 espécies sem categoria** (NULL)
- Ignora **epífitas** (15,402), **suculentas** (4,500+), **aquáticas** (1,500+)

### Dados WCVP (ricos mas mal aproveitados)
```
"liana" (4,020)                 → mapeia para "climber" (deveria ser "liana")
"climbing shrub" (2,711)        → mapeia para "shrub"   (deveria ser "liana")
"scrambling shrub" (2,171)      → mapeia para "shrub"   (deveria ser "liana")
"climbing perennial" (706)      → mapeia para NULL      (deveria ser "vine")
"epiphyte" (15,402)             → mapeia para NULL      (deveria ser "epiphyte")
"perennial" (50,485)            → mapeia para NULL      (deveria ser "forb")
```

### Dados GIFT (referência - bem estruturados)
```
forb: 91,912 | tree: 26,054 | shrub: 20,891 | liana: 5,072 | vine: 2,094
```

## Solução

Reescrever `_parse_life_form()` com lógica sofisticada que:
1. Distingue **liana** (lenhoso) vs **vine** (herbáceo) baseado no contexto
2. Mapeia **epífitas**, **suculentas** e **aquáticas** corretamente
3. Normaliza ciclos de vida (annual/perennial/biennial) → **forb**
4. Mantém prioridade GIFT > WCVP (GIFT continua mais preciso para trepadeiras)

---

## Arquivos a Modificar

### 1. `crawlers/wcvp.py` (principal)
- Adicionar dicionário `WCVP_LIFE_FORM_MAPPINGS` com mapeamentos completos
- Reescrever método `_parse_life_form()` (linhas 160-179)

### 2. `crawlers/base.py` (suporte)
- Atualizar `_save_traits()` para incluir coluna `_wcvp_life_form_raw`

### 3. Nova migração SQL
- `database/migrations/011_wcvp_life_form_raw.sql` - adicionar coluna de auditoria

### 4. Script de reprocessamento
- `scripts/reprocess_wcvp_growth_forms.py` - atualizar dados existentes

---

## Implementação

### Passo 1: Novo `_parse_life_form()` em `wcvp.py`

```python
def _parse_life_form(self, life_form: str) -> Optional[str]:
    """Parse WCVP life_form distinguindo liana/vine e mapeando epífitas."""
    if not life_form:
        return None

    lf = life_form.lower().strip()

    # Trepadeiras - ordem importa! Checar lenhosos antes de herbáceos
    if 'liana' in lf:
        return 'liana'
    if 'climbing shrub' in lf or 'scrambling shrub' in lf:
        return 'liana'
    if 'climbing subshrub' in lf or 'scrambling subshrub' in lf:
        return 'liana'
    if 'climbing' in lf:
        # Se herbáceo → vine, senão → liana
        if any(h in lf for h in ['annual', 'perennial', 'herb', 'geophyte']):
            return 'vine'
        return 'liana'
    if 'scrambling' in lf:
        if any(h in lf for h in ['annual', 'perennial', 'herb']):
            return 'vine'
        return 'liana'
    if 'climber' in lf or 'vine' in lf:
        return 'climber'  # Genérico quando não dá para distinguir

    # Epífitas
    if 'epiphyt' in lf or 'hemiepiphyt' in lf:
        return 'epiphyte'

    # Suculentas
    if 'succulent' in lf:
        return 'succulent'

    # Aquáticas
    if any(a in lf for a in ['aquatic', 'hydro', 'helophyte']):
        return 'aquatic'

    # Palma/Bambu/Samambaia (antes de tree/shrub)
    if 'palm' in lf:
        return 'palm'
    if 'bamboo' in lf:
        return 'bamboo'
    if 'fern' in lf:
        return 'fern'

    # Gramíneas
    if any(g in lf for g in ['graminoid', 'grass', 'sedge', 'rush']):
        return 'graminoid'

    # Árvores/Arbustos (depois de filtrar trepadeiras)
    if 'tree' in lf:
        return 'tree'
    if 'shrub' in lf:
        return 'shrub'
    if 'subshrub' in lf:
        return 'subshrub'

    # Herbáceas / Ciclos de vida → forb
    if any(h in lf for h in ['herb', 'annual', 'perennial', 'biennial', 'geophyte']):
        return 'forb'

    # Litófitas e parasitas → forb
    if 'lithophyte' in lf or 'parasit' in lf:
        return 'forb'

    return None
```

### Passo 2: Migração SQL

```sql
-- 011_wcvp_life_form_raw.sql
ALTER TABLE species_traits
ADD COLUMN IF NOT EXISTS _wcvp_life_form_raw VARCHAR(200);

COMMENT ON COLUMN species_traits._wcvp_life_form_raw
IS 'Valor bruto de lifeform_description do WCVP para auditoria';
```

### Passo 3: Script de Reprocessamento

Script Python que:
1. Lê todos os `species_traits` com `source='wcvp'` e `life_form IS NOT NULL`
2. Aplica novo `_parse_life_form()` em cada `life_form`
3. Atualiza `growth_form` onde o resultado mudou
4. Atualiza `species_unified` após o processo

### Passo 4: Atualizar `species_unified`

```sql
-- Após reprocessamento, executar migração 003 novamente ou:
REFRESH MATERIALIZED VIEW species_unified;  -- se for view materializada
-- ou executar query de consolidação
```

---

## Melhorias Esperadas

| Categoria | Antes | Depois | Mudança |
|-----------|-------|--------|---------|
| forb | herb: 81k | forb: ~144k | +63k (de annual/perennial/NULL) |
| NULL | 52k | ~5k | -47k |
| climber | 10k | ~2k | -8k (split para liana/vine) |
| liana | 0 | ~6k | +6k |
| vine | 0 | ~4k | +4k |
| epiphyte | 0 | ~27k | +27k |
| succulent | 0 | ~5k | +5k |
| aquatic | 0 | ~1.5k | +1.5k |

---

## Verificação

1. **Antes da implementação**: Salvar counts atuais
   ```sql
   SELECT growth_form, COUNT(*) FROM species_traits
   WHERE source = 'wcvp' GROUP BY growth_form;
   ```

2. **Após implementação**: Comparar counts
   - Espera-se ~0 registros com `growth_form = 'herb'`
   - Espera-se ~6k com `growth_form = 'liana'`
   - Espera-se ~27k com `growth_form = 'epiphyte'`

3. **Validação manual**: Verificar espécies conhecidas
   ```sql
   -- Passiflora (vine - trepadeira herbácea)
   SELECT canonical_name, growth_form FROM species_unified
   WHERE canonical_name LIKE 'Passiflora%' LIMIT 10;

   -- Bougainvillea (liana - trepadeira lenhosa)
   SELECT canonical_name, growth_form FROM species_unified
   WHERE canonical_name LIKE 'Bougainvillea%' LIMIT 10;
   ```

4. **Testes unitários**: Criar `tests/test_wcvp_growth_form.py`

---

## Ordem de Execução

1. [ ] Criar migração 011 (adicionar coluna `_wcvp_life_form_raw`)
2. [ ] Atualizar `base.py` `_save_traits()` para nova coluna
3. [ ] Reescrever `wcvp.py` `_parse_life_form()`
4. [ ] Criar script `scripts/reprocess_wcvp_growth_forms.py`
5. [ ] Aplicar migração
6. [ ] Executar script de reprocessamento
7. [ ] Atualizar `species_unified`
8. [ ] Validar resultados
9. [ ] Criar testes unitários

---

## Referências

- **GIFT Climber.R logic**: `crawlers/gift.py:222-336` - referência para lógica de trepadeiras
- **Contrato GIFT**: `contrato/gift.md` e `contrato/climber_logic.md`
- **Schema**: `database/schema.sql` e `database/migrations/002_unified_schema.sql`
