# Auditoria técnica — 29/07/2026

## Decisão

O núcleo do AquaFlora Stock Sync deve ser **simplificado de forma incremental,
sem reescrita**. Parser, enriquecimento, modelos e modo LITE têm testes úteis e
continuam sendo a rota operacional segura. O feature creep está concentrado nas
ferramentas auxiliares de imagens, dashboard, bot, backup e geração editorial.

## Escopo validado

- Repositório inteiro inventariado: código principal, `src`, dashboard, scripts,
  testes, documentação e automação Windows.
- Branch local sincronizada com `origin/main` no início da auditoria.
- 113 testes passaram.
- Compilação de todos os módulos Python passou.
- Cobertura total medida em 43%.

Cobertura das áreas mais relevantes:

| Área | Cobertura |
| --- | ---: |
| Reconciliador de catálogo | 92% |
| Modelos | 94% |
| Enriquecimento | 87% |
| Parser Athos | 83% |
| Banco local | 69% |
| Sync WooCommerce | 53% |
| `main.py` | 32% |
| Dashboard | 24% |
| Scraper de imagens | 23% |

## Problemas corrigidos

1. **Estado falso de sincronização:** um lote LITE rejeitado pelo WooCommerce
   ainda podia ter seus hashes gravados no SQLite. A execução seguinte julgaria
   que não havia mudança e pularia produtos que nunca chegaram ao site. Agora só
   respostas confirmadas pelo WooCommerce atualizam o estado local.
2. **Estoque negativo:** saldos negativos do ERP agora são limitados a zero antes
   de formar o produto enriquecido e o payload da API.
3. **Índices SQLite não aplicados:** os índices já declarados para produtos,
   histórico e imagens agora são realmente criados.
4. **Upload inseguro no dashboard:** nomes com travessia de diretório são
   rejeitados e uploads CSV têm limite de 10 MB.
5. **Dependências incompletas:** dependências usadas diretamente por HTTP,
   scraper, observação de arquivos e SFTP foram declaradas.
6. **Configuração Pydantic obsoleta:** migração para `SettingsConfigDict`,
   removendo o aviso de depreciação do Pydantic 2.
7. **Reconciliação ad hoc não reproduzível:** foi criado um comando testado para
   proteger pet/pesca/ração, recuperar apenas produtos diversos do export antigo
   e atualizar preço/estoque pelo Athos atual.

## Feature creep encontrado

O projeto mistura quatro produtos em um único ambiente:

1. sincronização operacional LITE de preço/estoque;
2. reconstrução FULL de catálogo e conteúdo editorial;
3. busca, curadoria e upload de imagens;
4. dashboard, bot Discord, agendamento e backup.

Os maiores sinais são `src/image_scraper.py` (1.950 linhas), `main.py` (1.521),
`dashboard/app.py` (1.094) e funções isoladas com 150–466 linhas. Isso aumenta
dependências, superfície de falha e esforço de teste, mas remover essas áreas sem
um inventário de uso real seria arriscado.

## Próxima simplificação recomendada

1. Manter `main.py --lite`, parser, sync e SQLite como núcleo operacional.
2. Separar dependências em grupos: núcleo, dashboard, imagens e desenvolvimento.
3. Mover exportadores e reconciliações de catálogo para um pacote próprio,
   retirando essa responsabilidade do `main.py`.
4. Dividir as funções longas do scraper, bot e dashboard antes de adicionar novas
   funcionalidades.
5. Elevar primeiro a cobertura de `src/sync.py`, `main.py` e dashboard; são áreas
   que podem alterar produção ou iniciar processos.
6. Decidir se `price_history` será conectado ao sync ou removido; hoje existe no
   banco, mas não é alimentado pela rotina.

## Limites operacionais

- O modo FULL continua capaz de substituir conteúdo editorial; não deve ser a
  rotina automática. Use LITE para preço e estoque.
- O dashboard usa comandos predefinidos, mas a autenticação é opcional. Não o
  exponha publicamente com autenticação desativada.
- Esta auditoria não publicou produtos nem executou import no WooCommerce.
- O CSV diverso gerado tem 577 produtos; 87 produtos antigos ausentes no Athos
  ficaram fora; pet/pesca/ração tiveram zero vazamentos.
- O SKU `4637` (Tacho P 35Cm - Mc) é o único produto exportado sem imagem herdada.
