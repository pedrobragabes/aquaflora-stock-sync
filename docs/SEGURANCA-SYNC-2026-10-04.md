# Reconciliação de estoque — 04/10/2026

O LITE continua sendo o modo operacional recomendado e já ignora zeragem de SKUs ausentes. A proteção foi ampliada para a opção destrutiva de reconciliação FULL.

O CLI recusa encaminhar `ZERO_GHOST_STOCK` quando há modo teste, exclusões, erro de enriquecimento, inventário vazio, whitelist não mapeada ou quantidade processada inferior a 90% da quantidade de produtos mapeados. O sync também recusa a zeragem quando recebe lista vazia ou quando alguma atualização falhou. As atualizações confirmadas preservam a lógica existente de hashes e o LITE preserva os campos editoriais.

O limite de 90% é uma barreira contra quedas grandes, **não uma prova de export completo**: cem SKUs diferentes podem ter a mesma contagem. A opção continua desativada por padrão e só pode ser solicitada após confirmação humana de inventário completo. Nenhuma execução real foi feita nesta revisão.

## Verificação

Os testes usam fixtures, SQLite temporário e API falsa. Foram preservados os testes de LITE, falhas de lote e SKUs pai protegidos; acrescentados cenários de lista vazia, falha de sync, inventário parcial, exclusões e falha de enriquecimento. O teste do CLI confirma que a opção é transmitida como false para um export parcial.

Há quatro testes locais ainda não versionados no checkout WIP. Esse arquivo foi consultado como evidência da pendência e preservado. A implementação e a suíte ampliada foram feitas em worktree independente, a partir da main canônica.

O novo CI compila os módulos e executa a suíte sintética com Python 3.13. Não possui chaves WooCommerce/Discord nem executa `main.py` contra a loja. A instalação das tarefas e os logs de produção continuam precisando de verificação no PC da loja.
