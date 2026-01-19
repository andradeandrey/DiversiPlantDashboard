
### Análise Detalhada dos Tipos de Escalada

Baseado em literatura botânica especializada ([Sperotto et al. 2020](https://tncvasconcelos.github.io/papers/Sperottoetal2020_climbers.pdf), [Smithsonian Lianas Project](https://naturalhistory.si.edu/research/botany/research/lianas-and-climbing-plants-neotropics/lianas-introduction)), segue análise de cada tipo:

---

#### 1. **Scrambler** (Escandente/Apoiante)

**Definição:** Plantas com caules longos e flexíveis que se apoiam sobre outras plantas ou estruturas, mas **não possuem mecanismo especializado de escalada** (sem gavinhas, raízes adventícias ou volubilidade).

**Exemplos:**
- *Bougainvillea spectabilis* - Liana com espinhos curvos
- *Rosa* spp. (roseiras trepadeiras) - Arbustos escandentes com acúleos
- *Smilax laurifolia* (greenbriar)

**Evidência botânica:**
> "Scramblers, in particular, are **exclusively woody**, unlike twiners and tendril climbers." — [Sperotto et al. 2020](https://link.springer.com/article/10.1007/s12229-020-09218-y)

> "Bougainvillea spectabilis is a species of thorny, **evergreen liana**... woody climber can reach heights of 15–40 feet." — [Britannica](https://www.britannica.com/plant/bougainvillea)

**Recomendação:** `scrambler` → **`liana`**

**Justificativa:** Scramblers são **exclusivamente lenhosos** segundo a literatura. São classificados como "escalada passiva" junto com hook climbers e root climbers.

---

#### 2. **Root Climber** (Trepadeira com Raízes Adventícias)

**Definição:** Plantas que escalam usando raízes adventícias que aderem a superfícies (cascas de árvores, rochas, paredes).

**Exemplos:**
- *Hedera helix* (hera) - Liana perene lenhosa
- *Ficus pumila* (figueira-trepadeira) - Liana lenhosa
- *Monstera deliciosa* - Hemiepífita lenhosa
- *Philodendron* spp. - Hemiepífitas lenhosas
- *Toxicodendron radicans* (poison ivy) - Liana lenhosa

**Evidência botânica:**
> "Root climbers are not constrained at all by large support diameters, unlike twining plants and tendril climbers." — [PMC Behavioural Ecology](https://pmc.ncbi.nlm.nih.gov/articles/PMC4363473/)

> "In wet virgin forest, you will be surrounded by tall trees covered in **root climbing lianas**... Ficus punctata is a common **large liana**." — [Borneo Ficus Project](https://borneoficus.info/2021/10/09/open-your-eyes-root-climbing-figs-are-all-around-you/)

**Recomendação:** `root climber` → **`liana`**

**Justificativa:** Root climbers são **predominantemente lenhosos** (Hedera, Ficus, Monstera, Philodendron). São plantas perenes que desenvolvem caules lignificados com o tempo.

---

#### 3. **Tendril Climber** (Trepadeira com Gavinhas)

**Definição:** Plantas que escalam usando gavinhas (estruturas modificadas de folhas, pecíolos ou caules) que se enrolam em suportes.

**Exemplos Herbáceos (vine):**
- *Passiflora* spp. (maracujá) - Maioria herbácea ou semi-lenhosa
- *Cucumis*, *Cucurbita* (pepino, abóbora) - Anuais herbáceas
- *Lathyrus* (ervilha-de-cheiro) - Anual herbácea

**Exemplos Lenhosos (liana):**
- *Vitis* spp. (uva, videira) - Liana lenhosa perene
- *Parthenocissus* (hera-japonesa) - Liana lenhosa
- *Bignoniaceae* (cipós) - Lianas lenhosas tropicais

**Evidência botânica:**
> "Climbing is widespread within genus *Passiflora*, and the vast majority of its >500 species are climbers... climbing Passiflora species bear axillary tendrils." — [Oxford Academic](https://academic.oup.com/jxb/article/73/4/1190/6407680)

> "*Vitis amurensis* is classified as a **tendril liana** (woody climber)." — [Agriculture.Institute](https://agriculture.institute/floriculture-and-landscaping/classification-woody-climbers-uses-flowering-season/)

**Recomendação:** `tendril climber` → **Consultar `trait_1.2.2`**

**Justificativa:** Este é o único tipo onde há divisão clara entre herbáceos e lenhosos. A decisão deve ser baseada no campo `trait_1.2.2`:
- Se `trait_1.2.2` = tree/shrub → `liana`
- Se `trait_1.2.2` = herb → `vine`
- Se `trait_1.2.2` = NA → `vine` (default conservador, pois a maioria das espécies comuns são herbáceas)

---

#### 4. **Twining** (Volúvel/Enrolador)

**Definição:** Plantas cujo caule principal se enrola helicoidalmente em torno de suportes.

**Exemplos Herbáceos (maioria):**
- *Ipomoea* spp. (morning glory, batata-doce) - **700+ espécies**, maioria herbácea anual
- *Convolvulus arvensis* (campainha) - Herbácea perene
- *Phaseolus* spp. (feijão) - Herbácea anual
- *Dioscorea* spp. (cará, inhame) - Herbácea perene

**Exemplos Lenhosos (minoria):**
- *Lonicera* spp. (madressilva) - Liana lenhosa
- *Wisteria* spp. (glicínia) - Liana lenhosa
- *Actinidia deliciosa* (kiwi) - Liana lenhosa
- *Aristolochia* spp. (papo-de-peru) - Liana lenhosa

**Evidência botânica:**
> "Among Taiwan's 555 climbers, the **twining stem type was the most common, with 255 species (46%)**." — [Botanical Studies](https://as-botanicalstudies.springeropen.com/articles/10.1186/s40529-023-00399-4)

> "Annual (herbaceous) twiners dry out and die back completely after autumn, like *Ipomoea*... Perennial twiners or lianas **become woody** and include *Aristolochia*, *Lonicera*, *Actinidia*." — [Fassadengruen](https://www.fassadengruen.de/en/twining-plants.html)

> "Most Convolvulaceae species are **herbaceous perennial vines**... The main genera is *Ipomoea*, with **over 700 species**." — [Convolvulaceae Unlimited](https://www.convolvulaceae.myspecies.info/content/v-herbaceous-climber)

**Recomendação:** `twining` → **`vine`** (default)

**Justificativa:** A maioria estatística dos twiners são herbáceos (Convolvulaceae domina com 1.850 espécies). No entanto, se `trait_1.2.2` indicar tree/shrub, deve-se usar `liana`.

---

#### 5. **Hook Climber** (Trepadeira com Ganchos/Espinhos)

**Definição:** Plantas que usam estruturas pontiagudas (espinhos, acúleos, ganchos) para se apoiar e escalar.

**Exemplos:**
- *Bougainvillea* spp. - Liana com espinhos curvos de até 5cm
- *Rosa* spp. (roseiras trepadeiras) - Arbustos com acúleos
- *Rubus* spp. (amora, framboesa) - Arbustos escandentes
- *Uncaria* spp. (unha-de-gato) - Lianas com ganchos
- Palmeiras escandentes (*Calamus*, rattan)

**Evidência botânica:**
> "*Bougainvillea spectabilis*... woody climber can reach heights of 15–40 feet, featuring elliptical to ovate leaves along with **large, curved thorns for support**." — [Britannica](https://www.britannica.com/plant/bougainvillea)

> "Hook climbers use **hooks or grapnels** as passive climbing mechanism... classified together with scramblers as passive climbers." — [Sperotto et al. 2020](https://link.springer.com/article/10.1007/s12229-020-09218-y)

**Recomendação:** `hook climber` → **`liana`**

**Justificativa:** Hook climbers são **predominantemente lenhosos**. Os ganchos/espinhos são estruturas lignificadas que requerem caules lenhosos para suporte.

---

#### 6. **Leaning** (Apoiante/Inclinado)

**Definição:** Plantas com caules semi-rígidos que se inclinam ou arqueiam sobre outras plantas, sem mecanismo ativo de escalada.

**Características:**
- Não possuem gavinhas, raízes adventícias ou caule volúvel
- Caules longos mas parcialmente rígidos
- Comportamento intermediário entre arbusto e trepadeira
- Frequentemente classificados junto com scramblers

**Evidência botânica:**
> "The distinction between climbing and self-supporting plants is often blurred by the occurrence of plants with long, **semi-rigid stems that arch or lean over other plants**. These less efficient climbers are known as clambering, scrambling or **leaning plants**." — [Smithsonian](https://naturalhistory.si.edu/research/botany/research/lianas-and-climbing-plants-neotropics/lianas-introduction)

> "Leaning climber = **unarmed scramblers** (without spines/hooks)." — [Sperotto et al. 2020](https://link.springer.com/article/10.1007/s12229-020-09218-y)

**Recomendação:** `leaning` → **Consultar `trait_1.2.2`**

**Justificativa:** "Leaning" indica comportamento, não estrutura. A planta pode ser arbusto escandente (shrub) ou trepadeira propriamente dita. Usar o campo `trait_1.2.2` para determinar:
- Se `trait_1.2.2` = tree/shrub → manter valor original
- Se `trait_1.2.2` = herb → `vine` ou `forb` dependendo do contexto

---

#### 7. **Epiphytic Climber** (Trepadeira Epifítica/Hemiepífita)

**Definição:** Plantas que combinam hábito trepador com epifitismo. Geralmente começam no solo e sobem em árvores (hemiepífitas secundárias) ou germinam em árvores e descem raízes ao solo (hemiepífitas primárias).

**Exemplos:**
- *Philodendron* spp. - Hemiepífitas secundárias
- *Monstera deliciosa* - Hemiepífita secundária
- *Ficus* spp. (estranguladores) - Hemiepífitas primárias
- *Vanilla* (baunilha) - Orquídea hemiepífita

**Evidência botânica:**
> "Most members of *Philodendron* are **hemiepiphytic**, meaning that they grow on trees as **appressed climbers or as vines**, while being rooted in the soil." — [Aroid.org](http://www.aroid.org/genera/philodendron/habgrowpat.php)

> "Secondary hemiepiphytes: germination is in the soil and plants grow in a creeping fashion until a suitable tree is located... growth proceeds upwards toward more well-illuminated regions." — [Aroid.org](http://www.aroid.org/genera/philodendron/habgrowpat.php)

**Recomendação:** `epiphytic climber` → **`liana`**

**Justificativa:** Hemiepífitas trepadeiras são **predominantemente lenhosas** (Araceae, Moraceae). Possuem caules que lignificam com o tempo e são perenes. A alternativa seria `epiphyte`, mas o comportamento trepador é a característica dominante.

---

### Proposta de Mapeamento Final

```python
CLIMBER_TYPE_MAP = {
    # ══════════════════════════════════════════════════════════════
    # VALORES ORIGINAIS DO CLIMBER.R (já validados)
    # ══════════════════════════════════════════════════════════════
    'liana': 'liana',           # Trepadeira lenhosa
    'vine': 'vine',             # Trepadeira herbácea
    'self-supporting': None,    # Usa trait_1.2.2 (não é trepadeira)

    # ══════════════════════════════════════════════════════════════
    # ESCALADA PASSIVA - Predominantemente lenhosos
    # ══════════════════════════════════════════════════════════════
    'scrambler': 'liana',       # ✓ Exclusivamente lenhosos (Sperotto 2020)
    'hook climber': 'liana',    # ✓ Estruturas lignificadas (Bougainvillea)
    'root climber': 'liana',    # ✓ Hedera, Ficus, Philodendron - lenhosos

    # ══════════════════════════════════════════════════════════════
    # ESCALADA ATIVA - Maioria herbáceos
    # ══════════════════════════════════════════════════════════════
    'twining': 'vine',          # ✓ Ipomoea (700+ spp), Convolvulus - herbáceos

    # ══════════════════════════════════════════════════════════════
    # CASOS ESPECIAIS - Requer consulta a trait_1.2.2
    # ══════════════════════════════════════════════════════════════
    'tendril climber': None,    # ⚠ Misto: Vitis=liana, Passiflora=vine
    'leaning': None,            # ⚠ Comportamento, não estrutura

    # ══════════════════════════════════════════════════════════════
    # HEMIEPÍFITAS
    # ══════════════════════════════════════════════════════════════
    'epiphytic climber': 'liana',  # ✓ Philodendron, Monstera - lenhosos
}
```
