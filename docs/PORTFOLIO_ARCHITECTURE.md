# Arquitetura e reutilização

`main.py` coordena parsing, enriquecimento, persistência e publicação. `src/parser.py` entende os formatos Athos; `src/models.py` valida entidades; `src/enricher.py` normaliza; `src/database.py` guarda whitelist/hashes; `src/sync.py` aplica mudanças no WooCommerce. `src/catalog_reconcile.py` e scripts de importação tratam reconciliação, sem constituir uma API central.

## Decisões que sustentam o case

- CSV foi a fronteira disponível do ERP. É necessário distinguir identificador textual de número e validar formatos antes de publicar.
- LITE separa autoridade do ERP (saldo/preço) da edição comercial (texto/imagem/categoria).
- SQLite atende a execução local; a whitelist evita criar produtos por acidente.
- Hashes reduzem atualizações redundantes. Isso não equivale a transação distribuída ou garantia de entrega exatamente uma vez.
- Dados incompletos não justificam zerar todo o catálogo. `ZERO_GHOST_STOCK` deve continuar desligado sem comprovação de cobertura integral.

## Componentes candidatos a projetos-base

1. **Legacy ERP Connector**: parsing e perfil sintético do export; precisa receber uma interface de adapter antes de suportar outros ERPs.
2. **Normalization Engine**: números, unidades, SKU/EAN e validação. Comparar com o conector da API antes de unificar: regras de SKU e tratamento de linhas inválidas diferem.
3. **Commerce Sync Adapter**: whitelist, diff e payload LITE para WooCommerce.

São fronteiras identificadas no código, não pacotes independentes já publicados. Não foi criada uma arquitetura de microserviços ou uma plataforma SaaS nesta manutenção.

## Compatibilidade e arquivos locais

Os nomes históricos em scripts de agendamento, labels de lock, URLs de repositório e registros de decisão podem continuar aparecendo. Alterá-los sem migração poderia duplicar tarefas ou romper automação existente. Defaults e exemplos comerciais foram generalizados; instalações devem fornecer sua configuração explicitamente.

Lotes comerciais de marketplace foram retirados do índice Git e preservados localmente. A retirada em um novo commit não elimina o histórico anterior: revisar acesso e exposição antes de promover o repositório. Não há uma declaração de ausência de segredos no histórico.
