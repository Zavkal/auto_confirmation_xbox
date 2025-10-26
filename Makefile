# Makefile для Auto Confirmation Service

# Переменные
COMPOSE_FILE = docker-compose.yml
SERVICE_NAME = auto-confirmation
CONTAINER_NAME = auto_confirmation_xbox_consumer

# Цвета для вывода
BLUE = \033[0;34m
GREEN = \033[0;32m
YELLOW = \033[1;33m
RED = \033[0;31m
NC = \033[0m # No Color

.PHONY: help build up down restart logs status clean test

# Показать помощь (по умолчанию)
help: ## Показать справку по командам
	@echo "$(BLUE)Auto Confirmation Service - Команды управления$(NC)"
	@echo ""
	@echo "$(GREEN)Основные команды:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-15s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Примеры использования:$(NC)"
	@echo "  make build    # Собрать и запустить контейнер"
	@echo "  make logs     # Посмотреть логи"
	@echo "  make down     # Остановить контейнер"

# Проверка наличия .env файла
check-env:
	@if [ ! -f ".env" ]; then \
		echo "$(RED)Ошибка: Файл .env не найден!$(NC)"; \
		echo "Создайте файл .env с необходимыми переменными:"; \
		echo "RABBITMQ_USER=your_username"; \
		echo "RABBITMQ_PASS=your_password"; \
		echo "RABBITMQ_HOST=your_host"; \
		echo "RABBITMQ_QUEUE_REQUEST=request_queue"; \
		echo "RABBITMQ_QUEUE_RESPONSE=response_queue"; \
		exit 1; \
	fi


# Сборка образа
build: check-env ## Собрать Docker образ
	@echo "$(BLUE)Сборка Docker образа...$(NC)"
	docker compose build
	@echo "$(GREEN)Образ собран успешно!$(NC)"

# Запуск контейнера
up: check-env ## Запустить контейнер
	@echo "$(BLUE)Запуск контейнера...$(NC)"
	docker compose up -d
	@echo "$(GREEN)Контейнер запущен!$(NC)"
	@echo "$(YELLOW)Для просмотра логов: make logs$(NC)"

# Сборка и запуск
start: build up ## Собрать и запустить контейнер

# Остановка контейнера
down: ## Остановить контейнер
	@echo "$(BLUE)Остановка контейнера...$(NC)"
	docker compose down
	@echo "$(GREEN)Контейнер остановлен!$(NC)"

# Перезапуск контейнера
restart: ## Перезапустить контейнер
	@echo "$(BLUE)Перезапуск контейнера...$(NC)"
	docker compose down
	docker compose up -d
	@echo "$(GREEN)Контейнер перезапущен!$(NC)"

# Просмотр логов
logs: ## Просмотр логов контейнера
	@echo "$(BLUE)Просмотр логов...$(NC)"
	docker compose logs -f --tail=100

# Статус контейнера
status: ## Показать статус контейнера
	@echo "$(BLUE)Статус контейнера:$(NC)"
	docker compose ps

# Очистка
clean: ## Остановить и удалить контейнер, очистить образы
	@echo "$(YELLOW)Остановка и удаление контейнера...$(NC)"
	docker compose down --remove-orphans
	@echo "$(GREEN)Очистка завершена!$(NC)"



# Тестирование соединения
test: ## Тестировать соединение с RabbitMQ
	@echo "$(BLUE)Тестирование соединения...$(NC)"
	docker compose run --rm auto-confirmation python -c "from rabbit.consumer import rabbitmq_consumer; print('Тест соединения...')"

# Мониторинг в реальном времени
monitor: ## Мониторинг логов в реальном времени
	@echo "$(BLUE)Мониторинг логов...$(NC)"
	@echo "$(YELLOW)Нажмите Ctrl+C для выхода$(NC)"
	docker compose logs -f

# Резервное копирование логов
backup-logs: ## Создать резервную копию логов
	@echo "$(BLUE)Создание резервной копии логов...$(NC)"
	@mkdir -p backups
	@tar -czf backups/logs-$(shell date +%Y%m%d-%H%M%S).tar.gz logs/ 2>/dev/null || echo "Нет логов для резервного копирования"
	@echo "$(GREEN)Резервная копия создана в папке backups/$(NC)"
