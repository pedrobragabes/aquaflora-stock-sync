# AquaFlora Stock Sync - Makefile
# Uso: make <comando>

.PHONY: help sync scrape upload analyze test clean install

# Variáveis
PYTHON = python
INPUT_FILE = data/input/Athos.csv

help: ## Mostra esta ajuda
	@echo.
	@echo  AquaFlora Stock Sync - Comandos Disponiveis
	@echo  ============================================
	@echo.
	@echo  make install     - Instalar dependencias
	@echo  make sync        - Sincronizar estoque (dry-run)
	@echo  make sync-real   - Sincronizar estoque (producao)
	@echo  make scrape      - Buscar imagens (limite 50)
	@echo  make scrape-all  - Buscar todas as imagens
	@echo  make upload      - Upload de imagens FTP
	@echo  make analyze     - Analisar produtos sem imagem
	@echo  make test        - Rodar testes
	@echo  make dashboard   - Iniciar dashboard web
	@echo  make bot         - Iniciar bot Discord
	@echo  make clean       - Limpar cache e logs
	@echo.

install: ## Instalar dependências
	$(PYTHON) -m pip install -r requirements.txt

sync: ## Sync estoque (dry-run)
	$(PYTHON) main.py --input $(INPUT_FILE) --dry-run

sync-real: ## Sync estoque (produção)
	$(PYTHON) main.py --input $(INPUT_FILE)

sync-lite: ## Sync apenas preço/estoque
	$(PYTHON) main.py --input $(INPUT_FILE) --lite

scrape: ## Buscar imagens (limite 50)
	$(PYTHON) scrape_all_images.py --limit 50

scrape-all: ## Buscar todas as imagens
	$(PYTHON) scrape_all_images.py

scrape-stock: ## Buscar imagens (só produtos com estoque)
	$(PYTHON) scrape_all_images.py --stock-only

upload: ## Upload imagens FTP (dry-run)
	$(PYTHON) upload_images.py --dry-run

upload-real: ## Upload imagens FTP (produção)
	$(PYTHON) upload_images.py

analyze: ## Analisar produtos sem imagem
	$(PYTHON) scripts/analyze_missing_products.py

test: ## Rodar testes
	$(PYTHON) -m pytest tests/ -v

dashboard: ## Iniciar dashboard web
	$(PYTHON) -m dashboard.app

bot: ## Iniciar bot Discord
	$(PYTHON) bot_control.py

clean: ## Limpar cache e logs antigos
	@echo Limpando cache...
	@if exist data\search_cache.json del data\search_cache.json
	@if exist __pycache__ rd /s /q __pycache__
	@if exist src\__pycache__ rd /s /q src\__pycache__
	@echo Cache limpo!

clean-all: clean ## Limpar tudo (incluindo logs)
	@echo Limpando logs...
	@if exist logs rd /s /q logs
	@echo Logs limpos!
