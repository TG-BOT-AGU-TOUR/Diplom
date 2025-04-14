# Телеграм-бот для туристического магазина

Этот бот позволяет пользователям просматривать доступные туры, бронировать их, покупать товары для туризма и управлять своими бронированиями. Администраторы могут добавлять, редактировать и удалять туры, а также просматривать информацию о бронированиях.

## Функциональность

### Для пользователей:
- Просмотр доступных туров
- Бронирование туров
- Просмотр своих бронирований
- Отмена бронирований
- Просмотр и покупка товаров для туризма
- Связь с оператором
- Просмотр информации о магазине

### Категории товаров:
- Одежда и обувь для активного отдыха
- Кемпинг и палаточный лагерь
- Туристическое снаряжение
- Электроника для путешественников
- Продукты и напитки для путешествий
- Досуг и развлечения на отдыхе
- Уход за телом и безопасность

### Для администраторов:
- Добавление новых туров
- Редактирование существующих туров
- Удаление туров
- Просмотр информации о бронированиях
- Просмотр контактной информации клиентов
- Отмена бронирований

## Установка

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd <repository-directory>
```

2. Создайте виртуальное окружение и активируйте его:
```bash
python -m venv venv
source venv/bin/activate  # для Linux/Mac
venv\Scripts\activate     # для Windows
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Создайте файл `.env` и добавьте в него следующие переменные:
```
BOT_TOKEN=your_bot_token_here
ADMIN_ID=your_telegram_id_here

# PostgreSQL Configuration
DB_HOST=localhost
DB_PORT=5432
DB_USER=your_postgres_user
DB_PASSWORD=your_postgres_password
DB_NAME=tour_bot
```

5. Создайте директорию для изображений:
```bash
mkdir images
```

6. Создайте базу данных PostgreSQL:
```sql
CREATE DATABASE tour_bot;
```

## Запуск

1. Активируйте виртуальное окружение (если оно не активировано):
```bash
source venv/bin/activate  # для Linux/Mac
venv\Scripts\activate     # для Windows
```

2. Запустите бота:
```bash
python bot.py
```

## Структура проекта

- `bot.py` - основной файл бота
- `models.py` - модели базы данных
- `config.py` - конфигурация и информация о магазине
- `requirements.txt` - зависимости проекта
- `images/` - директория для хранения изображений туров
- `.env` - файл с переменными окружения

## База данных

Бот использует PostgreSQL для хранения данных. База данных создается автоматически при первом запуске бота.

Таблицы:
- `tours` - информация о турах
  - id (SERIAL PRIMARY KEY)
  - name (VARCHAR(255) NOT NULL)
  - description (TEXT)
  - image_path (VARCHAR(255))
  - start_date (DATE NOT NULL)
  - end_date (DATE)
  - price (INTEGER NOT NULL)
  - total_seats (INTEGER NOT NULL)
  - available_seats (INTEGER NOT NULL)
  - is_active (BOOLEAN DEFAULT TRUE)

- `bookings` - информация о бронированиях
  - id (SERIAL PRIMARY KEY)
  - user_id (BIGINT NOT NULL)
  - user_name (VARCHAR(255) NOT NULL)
  - phone_number (VARCHAR(20) NOT NULL)
  - tour_id (INTEGER REFERENCES tours(id))
  - booking_date (TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
  - is_active (BOOLEAN DEFAULT TRUE) 