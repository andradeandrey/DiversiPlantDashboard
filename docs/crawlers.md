Resumo da Execução dos Crawlers

  Status Final
  ┌───────────┬───────────┬─────────────────────────┐
  │  Crawler  │  Status   │        Registros        │
  ├───────────┼───────────┼─────────────────────────┤
  │ GBIF      │ Completed │ 500                     │
  ├───────────┼───────────┼─────────────────────────┤
  │ GIFT      │ Completed │ 0 (requer R/rpy2)       │
  ├───────────┼───────────┼─────────────────────────┤
  │ REFLORA   │ Completed │ 0 (API não disponível)  │
  ├───────────┼───────────┼─────────────────────────┤
  │ WCVP      │ Failed    │ 0 (erro CSV field size) │
  ├───────────┼───────────┼─────────────────────────┤
  │ TreeGOER  │ Completed │ 0 (requer dados locais) │
  ├───────────┼───────────┼─────────────────────────┤
  │ IUCN      │ Completed │ 0 (requer API key)      │
  ├───────────┼───────────┼─────────────────────────┤
  │ WorldClim │ Idle      │ -                       │
  └───────────┴───────────┴─────────────────────────┘
  Dados no Banco
  ┌────────────────┬───────┐
  │     Tabela     │ Total │
  ├────────────────┼───────┤
  │ species        │ 515   │
  ├────────────────┼───────┤
  │ species_traits │ 15    │
  ├────────────────┼───────┤
  │ common_names   │ 52    │
  └────────────────┴───────┘
  Top Famílias (GBIF)

  Oedogoniaceae      | 78
  Chaetophoraceae    | 49
  Scenedesmaceae     | 46
  Characeae          | 39

  Notas

  - GBIF: Funcionou, baixou 500 espécies (algas do reino Plantae)
  - GIFT: Precisa do pacote R GIFT instalado via rpy2
  - IUCN: Precisa de API key (obter em https://apiv3.iucnredlist.org/)
  - WCVP: Erro no tamanho do CSV - precisa ajustar limite
  - REFLORA: API do JBRJ pode estar offline


  Status Final dos Crawlers
  ┌───────────┬───────────┬───────────┬──────────────────┐
  │  Crawler  │  Status   │ Registros │       Erro       │
  ├───────────┼───────────┼───────────┼──────────────────┤
  │ GBIF      │ completed │ 500       │ -                │
  ├───────────┼───────────┼───────────┼──────────────────┤
  │ GIFT      │ completed │ 0         │ Sem R/rpy2       │
  ├───────────┼───────────┼───────────┼──────────────────┤
  │ REFLORA   │ completed │ 0         │ API offline      │
  ├───────────┼───────────┼───────────┼──────────────────┤
  │ TreeGOER  │ completed │ 0         │ Sem dados locais │
  ├───────────┼───────────┼───────────┼──────────────────┤
  │ IUCN      │ completed │ 0         │ Sem API key      │
  ├───────────┼───────────┼───────────┼──────────────────┤
  │ WCVP      │ failed    │ 0         │ CSV field size   │
  ├───────────┼───────────┼───────────┼──────────────────┤
  │ WorldClim │ idle      │ -         │ Não executado    │
  └───────────┴───────────┴───────────┴──────────────────┘
  Totais no Banco
  ┌──────────────┬───────────┐
  │    Tabela    │ Registros │
  ├──────────────┼───────────┤
  │ Espécies     │ 515       │
  ├──────────────┼───────────┤
  │ Traits       │ 15        │
  ├──────────────┼───────────┤
  │ Nomes comuns │ 52        │
  ├──────────────┼───────────┤
  │ Distribuição │ 13        │
  └──────────────┴───────────┘
  O crawler GBIF funcionou perfeitamente e baixou 500 espécies. Os demais precisam de configuração adicional:

  - GIFT: Instalar R + pacote GIFT + rpy2
  - IUCN: Obter API key em https://apiv3.iucnredlist.org/
  - WCVP: Corrigir limite de campo CSV
  - REFLORA: Verificar disponibilidade da API do JBRJ