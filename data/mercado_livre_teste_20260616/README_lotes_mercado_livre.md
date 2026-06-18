# Lotes pequenos para teste no Mercado Livre - 2026-06-16

Fonte: `C:/Users/pedro/Downloads/wc-product-export-16-6-2026-1781616031645.csv`

Crit?rio usado: produtos publicados no Woo, com estoque positivo, pre?o, imagem dispon?vel ou herdada do pai vari?vel, e sele??o comercial variada para testar sem sobrecarregar cadastro/fotos. N?o usei hist?rico real de vendas, porque ele n?o veio neste CSV.

Arquivos gerados:
- `mercado_livre_teste_50_produtos.csv`: sele??o completa com os 50 SKUs.
- `lote_01_equipamentos_pesca.csv`: carretilhas e molinetes.
- `lote_02_iscas_e_linhas.csv`: iscas e linhas.
- `lote_03_acessorios_pesca.csv`: caixas, boias, chumbo/sabor? e anz?is melhores.
- `lote_04_racoes_pet_premium.csv`: ra??es e itens pet premium.
- `lote_05_pet_higiene_acessorios.csv`: higiene, areia, comedouros, brinquedos e acess?rios pet.
- `familias_para_anuncios_ml.csv`: vis?o agrupada para decidir an?ncios com varia??es.

Contagem por lote:
- Lote 1: 10 SKUs
- Lote 2: 10 SKUs
- Lote 3: 10 SKUs
- Lote 4: 10 SKUs
- Lote 5: 10 SKUs

Observa??es:
- Linhas `variation` do Woo aparecem com imagem/categoria herdadas do pai, porque o export original deixa esses campos vazios na varia??o.
- Antes de publicar no Mercado Livre, revise t?tulo, categoria ML, frete, garantia e atributos obrigat?rios da categoria.
- Para an?ncios com muita varia??o, use `familias_para_anuncios_ml.csv` para agrupar os SKUs em um ?nico an?ncio quando fizer sentido.

Checagem de imagem: todas as imagens selecionadas responderam como imagem HTTP v?lida no teste r?pido.
