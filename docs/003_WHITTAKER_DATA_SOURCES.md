# Fontes de Dados para o Diagrama de Whittaker

**Data**: 2026-01-08
**Status**: Documentado

## Origem dos Dados

O diagrama de Whittaker classifica biomas baseado em **temperatura média anual** (eixo X) e **precipitação média anual** (eixo Y). Os dados originais vêm de:

### Referência Original
> Whittaker, R. H. (1975). *Communities and Ecosystems*. 2nd ed. Macmillan, New York.

### Referência Digitalizada
> Ricklefs, R. E. (2008). *The economy of nature*. W. H. Freeman and Company. **Figura 5.5**, Capítulo 5 (Biological Communities, The biome concept).

---

## Pacotes R com Dados Disponíveis

### 1. plotbiomes (Recomendado)
- **Repositório**: https://github.com/valentinitnelav/plotbiomes
- **Dados**: 775 vértices de polígonos para 9 biomas
- **Formato**: `Whittaker_biomes` (data.frame) e `Whittaker_biomes_poly` (SpatialPolygonsDataFrame)
- **Citação**: Valentin Ștefan, & Sam Levin. (2018). plotbiomes: R package for plotting Whittaker biomes with ggplot2 (v1.0.0). Zenodo. https://doi.org/10.5281/zenodo.7145245

**Instalação e Uso:**
```r
devtools::install_github("valentinitnelav/plotbiomes")
library(plotbiomes)
data(Whittaker_biomes)
write.csv(Whittaker_biomes, "whittaker_biomes.csv", row.names=FALSE)
```

### 2. BIOMEplot
- **Repositório**: https://github.com/kunstler/BIOMEplot
- **Dados**: 106 pontos para 9 biomas
- **Arquivo direto**: `inst/extdata/biomes.csv`

### 3. ggbiome
- **Repositório**: https://github.com/guillembagaria/ggbiome
- **Funcionalidade adicional**: Obtém MAT/MAP de coordenadas geográficas

---

## Estrutura dos Dados

### Colunas do Dataset `Whittaker_biomes`
| Coluna | Descrição |
|--------|-----------|
| `temp_c` | Temperatura média anual em °C |
| `precp_cm` | Precipitação média anual em cm |
| `biome_id` | Identificador numérico do bioma (1-9) |
| `biome` | Nome do bioma |

### Os 9 Biomas de Whittaker
| ID | Nome | Temp (°C) | Precip (cm) |
|----|------|-----------|-------------|
| 1 | Tundra | -15 a 0 | 0-50 |
| 2 | Boreal forest | -10 a 5 | 30-150 |
| 3 | Temperate seasonal forest | 0 a 20 | 75-200 |
| 4 | Temperate rain forest | 5 a 20 | 200-450 |
| 5 | Tropical rain forest | 20 a 30 | 200-450 |
| 6 | Tropical seasonal forest/savanna | 15 a 30 | 100-200 |
| 7 | Subtropical desert | 15 a 30 | 0-30 |
| 8 | Temperate grassland/desert | -5 a 20 | 0-75 |
| 9 | Woodland/shrubland | 5 a 25 | 30-100 |

---

## Processo de Digitalização

Os dados foram extraídos seguindo este processo:
1. PDF do livro de Ricklefs (2008), Figura 5.5
2. Conversão via Inkscape para PostScript
3. Importação para R usando pacote `grImport`
4. Extração das coordenadas dos paths PostScript
5. Transformação para unidades de temperatura/precipitação

---

## Implementação no DiversiPlant

Os dados do pacote `plotbiomes` foram extraídos e implementados em:
- **Arquivo de dados**: `data/whittaker_biomes.csv` (775 vértices de polígonos)
- **Servidor**: `custom_server/server_app.py` - função `whittaker_diagram()`

### Extração dos Dados
```r
# Comando usado para extrair os dados do pacote R
load('/tmp/Whittaker_biomes.rda')  # Baixado de GitHub
write.csv(Whittaker_biomes, 'data/whittaker_biomes.csv', row.names=FALSE)
```

### Código de Implementação (Python/Plotly)
```python
# Carregar dados reais
whittaker_df = pd.read_csv(WHITTAKER_DATA_PATH)

# Plotar cada bioma como polígono
for biome_name in biome_order:
    biome_data = whittaker_df[whittaker_df['biome'] == biome_name]
    fig.add_trace(go.Scatter(
        x=biome_data['temp_c'].tolist(),
        y=biome_data['precp_cm'].tolist(),
        fill="toself",
        fillcolor=WHITTAKER_COLORS[biome_name],
        name=biome_name,
        mode="lines"
    ))
```

### Mapeamento UI → Whittaker
Os tipos de clima e bioma da UI são mapeados para os biomas de Whittaker:

**Climate Types → Whittaker:**
| UI | Whittaker Biomes |
|----|------------------|
| Continental | Boreal Forest, Temperate Seasonal Forest |
| Polar | Tundra |
| Temperate | Temperate Rain Forest, Temperate Seasonal Forest |
| Dry | Subtropical Desert, Temperate Grassland/Desert |
| Highland | Tundra, Boreal Forest |
| Tropical Rainy | Tropical Rain Forest, Tropical Seasonal Forest |

**Biome Types → Whittaker:**
| UI | Whittaker Biomes |
|----|------------------|
| Boreal Forest (Taiga) | Boreal Forest |
| Deserts & Xeric Shrublands | Subtropical Desert |
| Mediterranean Forests | Woodland/Shrubland |
| Temperate Broadleaf & Mixed Forests | Temperate Seasonal Forest |
| Tropical Moist Broadleaf Forests | Tropical Rain Forest |

---

## Referências

1. Whittaker, R.H. (1975). Communities and Ecosystems. 2d ed. Macmillan, New York.
2. Ricklefs, R. E. (2008). The economy of nature. W. H. Freeman and Company.
3. Valentin Ștefan, & Sam Levin. (2018). plotbiomes: R package for plotting Whittaker biomes with ggplot2. Zenodo. https://doi.org/10.5281/zenodo.7145245
