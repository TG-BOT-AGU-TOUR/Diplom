import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import config
from models import Session, Tour, Booking
from admin import (
    add_tour, handle_tour_name, handle_tour_description, handle_tour_image,
    handle_tour_date, handle_tour_price, handle_tour_seats, edit_tour,
    show_tour_edit_options, view_bookings, show_client_contacts
)

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
TOKEN = os.getenv('BOT_TOKEN')

# Состояния для ConversationHandler
TOUR_NAME, TOUR_DESCRIPTION, TOUR_IMAGE, TOUR_START_DATE, TOUR_END_DATE, TOUR_PRICE, TOUR_SEATS = range(7)
BOOKING_NAME, BOOKING_PHONE = range(2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    # Проверяем, первый ли это запуск бота
    if 'welcome_shown' not in context.user_data:
        welcome_message = """
👋 Добро пожаловать в туристический магазин!

Здесь вы можете:
🏖️ Просмотреть доступные туры
📋 Забронировать понравившийся тур
🛍️ Купить товары для туризма
ℹ️ Узнать информацию о нас
📞 Связаться с нами
"""
        await update.message.reply_text(welcome_message)
        context.user_data['welcome_shown'] = True
    
    keyboard = [
        ["🏖️ Просмотреть туры", "📋 Мои бронирования"],
        ["🛍️ Товары для туризма"],
        ["ℹ️ Информация", "📞 Контакты"]
    ]
    
    if str(update.effective_user.id) == os.getenv('ADMIN_ID'):
        keyboard.append(["👨‍💼 Админ панель"])
    
    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False
    )
    
    await update.message.reply_text(
        "Выберите действие:",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = """
Доступные команды:
/tours - Просмотр доступных туров
/add_tour - Добавить новый тур
/my_bookings - Просмотр моих бронирований
    """
    await update.message.reply_text(help_text)

async def tours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр доступных туров"""
    session = Session()
    tours = session.query(Tour).filter(Tour.is_active == True).all()
    
    if not tours:
        await update.message.reply_text("На данный момент нет доступных туров.")
        return
    
    for tour in tours:
        message = f"""
Название: {tour.name}
Описание: {tour.description}
Дата начала: {tour.start_date}
Дата окончания: {tour.end_date}
Цена: {tour.price} руб.
Доступно мест: {tour.available_seats} из {tour.total_seats}
        """
        if tour.image_path and os.path.exists(tour.image_path):
            with open(tour.image_path, 'rb') as photo:
                await update.message.reply_photo(photo=photo, caption=message)
        else:
            await update.message.reply_text(message)

async def add_tour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса добавления тура"""
    if str(update.effective_user.id) != os.getenv('ADMIN_ID'):
        await update.message.reply_text("У вас нет прав для добавления туров.")
        return
    
    await update.message.reply_text("Введите название тура:")
    return TOUR_NAME

async def tour_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение названия тура"""
    context.user_data['tour_name'] = update.message.text
    await update.message.reply_text("Введите описание тура:")
    return TOUR_DESCRIPTION

async def tour_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение описания тура"""
    context.user_data['tour_description'] = update.message.text
    await update.message.reply_text("Отправьте фотографию тура:")
    return TOUR_IMAGE

async def handle_tour_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка загрузки изображения тура"""
    photo = update.message.photo[-1]
    
    # Создаем директорию для изображений, если она не существует
    os.makedirs('tour_images', exist_ok=True)
    
    # Путь для сохранения нового изображения
    new_image_path = f'tour_images/{photo.file_id}.jpg'
    
    # Скачиваем и сохраняем новое изображение
    file = await context.bot.get_file(photo.file_id)
    await file.download_to_drive(new_image_path)
    
    if context.user_data.get('editing_field') == 'image':
        # Редактирование существующего тура
        session = Session()
        tour = session.query(Tour).filter(Tour.id == context.user_data['editing_tour_id']).first()
        
        if tour:
            # Удаляем старое изображение, если оно существует
            if tour.image_path and os.path.exists(tour.image_path):
                os.remove(tour.image_path)
            
            # Обновляем путь к изображению
            tour.image_path = new_image_path
            session.commit()
            
            await update.message.reply_text("✅ Изображение тура успешно обновлено!")
        else:
            await update.message.reply_text("❌ Ошибка: тур не найден.")
        session.close()
        context.user_data.clear()
    elif context.user_data.get('adding_tour') and context.user_data.get('tour_stage') == 'image':
        # Добавление нового тура
        context.user_data['image_path'] = new_image_path
        await update.message.reply_text("Введите дату начала тура в формате ДД.ММ.ГГГГ:")
        context.user_data['tour_stage'] = 'start_date'

async def tour_start_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение даты начала тура"""
    try:
        start_date = datetime.strptime(update.message.text, '%Y-%m-%d').date()
        context.user_data['tour_start_date'] = start_date
        await update.message.reply_text("Введите дату окончания тура (YYYY-MM-DD):")
        return TOUR_END_DATE
    except ValueError:
        await update.message.reply_text("Неверный формат даты. Используйте формат YYYY-MM-DD:")
        return TOUR_START_DATE

async def tour_end_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение даты окончания тура"""
    try:
        end_date = datetime.strptime(update.message.text, '%Y-%m-%d').date()
        context.user_data['tour_end_date'] = end_date
        await update.message.reply_text("Введите цену тура:")
        return TOUR_PRICE
    except ValueError:
        await update.message.reply_text("Неверный формат даты. Используйте формат YYYY-MM-DD:")
        return TOUR_END_DATE

async def tour_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение цены тура"""
    try:
        price = int(update.message.text)
        context.user_data['tour_price'] = price
        await update.message.reply_text("Введите общее количество мест:")
        return TOUR_SEATS
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите число:")
        return TOUR_PRICE

async def tour_seats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение количества мест и сохранение тура"""
    try:
        seats = int(update.message.text)
        session = Session()
        
        new_tour = Tour(
            name=context.user_data['tour_name'],
            description=context.user_data['tour_description'],
            image_path=context.user_data['image_path'],
            start_date=context.user_data['tour_start_date'],
            end_date=context.user_data['tour_end_date'],
            price=context.user_data['tour_price'],
            total_seats=seats,
            available_seats=seats
        )
        
        session.add(new_tour)
        session.commit()
        
        await update.message.reply_text("Тур успешно добавлен!")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите число:")
        return TOUR_SEATS

async def book_tour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса бронирования тура"""
    try:
        tour_id = int(context.args[0])
        session = Session()
        tour = session.query(Tour).filter(Tour.id == tour_id, Tour.is_active == True).first()
        
        if not tour:
            await update.message.reply_text("Тур не найден или недоступен.")
            return ConversationHandler.END
        
        if tour.available_seats <= 0:
            await update.message.reply_text("К сожалению, все места уже заняты.")
            return ConversationHandler.END
        
        context.user_data['booking_tour_id'] = tour_id
        await update.message.reply_text("Введите ваше имя:")
        return BOOKING_NAME
    except (IndexError, ValueError):
        await update.message.reply_text("Использование: /book <ID_тура>")
        return ConversationHandler.END

async def booking_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение имени для бронирования"""
    context.user_data['booking_name'] = update.message.text
    await update.message.reply_text("Введите ваш номер телефона:")
    return BOOKING_PHONE

async def booking_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение телефона и сохранение бронирования"""
    phone = update.message.text
    session = Session()
    
    new_booking = Booking(
        user_id=update.effective_user.id,
        user_name=context.user_data['booking_name'],
        phone_number=phone,
        tour_id=context.user_data['booking_tour_id']
    )
    
    tour = session.query(Tour).filter(Tour.id == context.user_data['booking_tour_id']).first()
    tour.available_seats -= 1
    
    session.add(new_booking)
    session.commit()
    
    await update.message.reply_text("Бронирование успешно создано!")
    return ConversationHandler.END

async def show_my_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает бронирования пользователя"""
    user_id = update.effective_user.id
    session = Session()
    
    bookings = session.query(Booking).join(Tour).filter(
        Booking.user_id == user_id,
        Booking.is_active == True
    ).all()
    
    if not bookings:
        await update.message.reply_text("У вас нет активных бронирований.")
        session.close()
        return
    
    keyboard_main = [
        ["🏠 Главное меню"]
    ]
    reply_markup_main = ReplyKeyboardMarkup(keyboard_main, resize_keyboard=True)
    await update.message.reply_text("Ваши бронирования:", reply_markup=reply_markup_main)
    
    for booking in bookings:
        inline_keyboard = [
            [
                InlineKeyboardButton("📞 Связаться с оператором", callback_data=f"contact_operator"),
                InlineKeyboardButton("❌ Отменить бронирование", callback_data=f"cancel_booking_{booking.id}")
            ]
        ]
        inline_markup = InlineKeyboardMarkup(inline_keyboard)
        
        tour = session.query(Tour).get(booking.tour_id)
        end_date_str = f" - {tour.end_date.strftime('%d.%m.%Y')}" if tour.end_date else ""
        
        message = (
            f"🏖️ {tour.name}\n\n"
            f"📅 Даты: {tour.start_date.strftime('%d.%m.%Y')}{end_date_str}\n"
            f"💰 Цена: {tour.price} руб.\n"
            f"📅 Дата бронирования: {booking.booking_date.strftime('%d.%m.%Y')}"
        )
        
        await update.message.reply_text(message, reply_markup=inline_markup)
    
    session.close()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    text = update.message.text
    
    if text == "🏖️ Просмотреть туры":
        await show_tours(update, context)
    elif text == "📋 Мои бронирования":
        await show_my_bookings(update, context)
    elif text == "🛍️ Товары для туризма":
        await show_tourism_products(update, context)
    elif text == "👕 Одежда и обувь":
        await show_clothing_products(update, context)
    elif text == "⛺ Кемпинг и палатки":
        await show_camping_products(update, context)
    elif text == "🎒 Туристическое снаряжение":
        await show_equipment_products(update, context)
    elif text == "📱 Электроника":
        await show_electronics_products(update, context)
    elif text == "🍎 Продукты и напитки":
        await show_food_products(update, context)
    elif text == "🎮 Досуг и развлечения":
        await show_entertainment_products(update, context)
    elif text == "🧴 Уход и безопасность":
        await show_care_products(update, context)
    elif text == "⬅️ Назад":
        await show_tourism_products(update, context)
    elif text == "🏠 Главное меню":
        await start(update, context)
    elif text == "ℹ️ Информация":
        message = await update.message.reply_text(config.SHOP_INFO)
    elif text == "📞 Контакты":
        message = await update.message.reply_text(config.CONTACT_INFO)
    elif text == "👨‍💼 Админ панель" and str(update.effective_user.id) == os.getenv('ADMIN_ID'):
        keyboard = [
            ["➕ Добавить тур", "✏️ Редактировать тур"],
            ["📋 Просмотреть бронирования"],
            ["⬅️ Назад в главное меню"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)
    elif text == "✏️ Редактировать тур" and str(update.effective_user.id) == os.getenv('ADMIN_ID'):
        session = Session()
        tours = session.query(Tour).filter(Tour.is_active == True).all()
        if not tours:
            await update.message.reply_text("Нет доступных туров для редактирования.")
        else:
            for tour in tours:
                message = f"""
🏖️ Тур #{tour.id}
📍 Название: {tour.name}
📝 Описание: {tour.description}
📅 Дата начала: {tour.start_date}
📅 Дата окончания: {tour.end_date}
💰 Цена: {tour.price} руб.
👥 Всего мест: {tour.total_seats}
🎫 Доступно мест: {tour.available_seats}
"""
                # Создаем инлайн-клавиатуру для каждого тура
                inline_keyboard = [
                    [
                        InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_{tour.id}"),
                        InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete_{tour.id}")
                    ]
                ]
                inline_markup = InlineKeyboardMarkup(inline_keyboard)
                
                if tour.image_path and os.path.exists(tour.image_path):
                    with open(tour.image_path, 'rb') as photo:
                        await update.message.reply_photo(
                            photo=photo,
                            caption=message,
                            reply_markup=inline_markup
                        )
                else:
                    await update.message.reply_text(
                        message,
                        reply_markup=inline_markup
                    )
        session.close()
    elif text == "Изменить название" and context.user_data.get('editing_tour_id'):
        await update.message.reply_text("Введите новое название тура:")
        context.user_data['editing_field'] = 'name'
    elif text == "Изменить описание" and context.user_data.get('editing_tour_id'):
        await update.message.reply_text("Введите новое описание тура:")
        context.user_data['editing_field'] = 'description'
    elif text == "Изменить даты" and context.user_data.get('editing_tour_id'):
        await update.message.reply_text("Введите новую дату начала тура (ДД.ММ.ГГГГ):")
        context.user_data['editing_field'] = 'start_date'
    elif text == "Изменить цену" and context.user_data.get('editing_tour_id'):
        await update.message.reply_text("Введите новую цену тура:")
        context.user_data['editing_field'] = 'price'
    elif text == "Изменить количество мест" and context.user_data.get('editing_tour_id'):
        await update.message.reply_text("Введите новое количество мест:")
        context.user_data['editing_field'] = 'seats'
    elif text == "Изменить фото" and context.user_data.get('editing_tour_id'):
        await update.message.reply_text("Пожалуйста, отправьте новую фотографию тура.")
        context.user_data['editing_field'] = 'image'
    elif text == "⬅️ Назад в главное меню":
        keyboard = [
            ["🏖️ Просмотреть туры", "📋 Мои бронирования"],
            ["🛍️ Товары для туризма"],
            ["ℹ️ Информация", "📞 Контакты"]
        ]
        if str(update.effective_user.id) == os.getenv('ADMIN_ID'):
            keyboard.append(["👨‍💼 Админ панель"])
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)
    elif context.user_data.get('editing_field') and context.user_data.get('editing_tour_id'):
        session = Session()
        tour = session.query(Tour).filter(Tour.id == context.user_data['editing_tour_id']).first()
        
        if not tour:
            await update.message.reply_text("Тур не найден.")
            context.user_data.clear()
            return
        
        field = context.user_data['editing_field']
        try:
            if field == 'name':
                tour.name = update.message.text
            elif field == 'description':
                tour.description = update.message.text
            elif field == 'start_date':
                tour.start_date = datetime.strptime(update.message.text, '%d.%m.%Y').date()
                await update.message.reply_text("Введите новую дату окончания тура (ДД.ММ.ГГГГ):")
                context.user_data['editing_field'] = 'end_date'
                return
            elif field == 'end_date':
                tour.end_date = datetime.strptime(update.message.text, '%d.%m.%Y').date()
            elif field == 'price':
                tour.price = int(update.message.text)
            elif field == 'seats':
                new_seats = int(update.message.text)
                seats_diff = new_seats - tour.total_seats
                tour.total_seats = new_seats
                tour.available_seats += seats_diff
            
            session.commit()
            await update.message.reply_text("Информация успешно обновлена!")
            
            # Показываем обновленную информацию о туре
            message = f"""
Обновленные данные тура #{tour.id}:
Название: {tour.name}
Описание: {tour.description}
Дата начала: {tour.start_date}
Дата окончания: {tour.end_date}
Цена: {tour.price} руб.
Всего мест: {tour.total_seats}
Доступно мест: {tour.available_seats}
            """
            await update.message.reply_text(message)
            
            # Возвращаемся в админ-панель
            keyboard = [
                ["➕ Добавить тур", "✏️ Редактировать тур"],
                ["📋 Просмотреть бронирования"],
                ["⬅️ Назад в главное меню"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text("", reply_markup=reply_markup)
            
        except ValueError:
            await update.message.reply_text("Неверный формат данных. Пожалуйста, попробуйте снова.")
        finally:
            session.close()
            context.user_data.clear()
    elif text == "➕ Добавить тур" and str(update.effective_user.id) == os.getenv('ADMIN_ID'):
        await update.message.reply_text("Введите название тура:")
        context.user_data['adding_tour'] = True
        context.user_data['tour_stage'] = 'name'
    elif context.user_data.get('adding_tour'):
        if context.user_data.get('tour_stage') == 'name':
            context.user_data['tour_name'] = text
            await update.message.reply_text("Введите описание тура:")
            context.user_data['tour_stage'] = 'description'
        elif context.user_data.get('tour_stage') == 'description':
            context.user_data['tour_description'] = text
            await update.message.reply_text("Отправьте фотографию тура:")
            context.user_data['tour_stage'] = 'image'
        elif context.user_data.get('tour_stage') == 'start_date':
            try:
                start_date = datetime.strptime(text, '%d.%m.%Y').date()
                context.user_data['tour_start_date'] = start_date
                await update.message.reply_text("Введите дату окончания тура (ДД.ММ.ГГГГ):")
                context.user_data['tour_stage'] = 'end_date'
            except ValueError:
                await update.message.reply_text("Неверный формат даты. Используйте формат ДД.ММ.ГГГГ:")
        elif context.user_data.get('tour_stage') == 'end_date':
            try:
                end_date = datetime.strptime(text, '%d.%m.%Y').date()
                context.user_data['tour_end_date'] = end_date
                await update.message.reply_text("Введите цену тура (только число):")
                context.user_data['tour_stage'] = 'price'
            except ValueError:
                await update.message.reply_text("Неверный формат даты. Используйте формат ДД.ММ.ГГГГ:")
        elif context.user_data.get('tour_stage') == 'price':
            try:
                price = int(text)
                context.user_data['tour_price'] = price
                await update.message.reply_text("Введите количество мест:")
                context.user_data['tour_stage'] = 'seats'
            except ValueError:
                await update.message.reply_text("Введите корректное число:")
        elif context.user_data.get('tour_stage') == 'seats':
            try:
                seats = int(text)
                session = Session()
                
                new_tour = Tour(
                    name=context.user_data['tour_name'],
                    description=context.user_data['tour_description'],
                    image_path=context.user_data.get('image_path'),
                    start_date=context.user_data['tour_start_date'],
                    end_date=context.user_data['tour_end_date'],
                    price=context.user_data['tour_price'],
                    total_seats=seats,
                    available_seats=seats,
                    is_active=True
                )
                
                session.add(new_tour)
                session.commit()
                
                await update.message.reply_text("✅ Тур успешно добавлен!")
                
                # Показываем информацию о добавленном туре
                message = f"""
🏖️ Тур успешно создан!

📍 Название: {new_tour.name}
📝 Описание: {new_tour.description}
📅 Дата начала: {new_tour.start_date.strftime('%d.%m.%Y')}
📅 Дата окончания: {new_tour.end_date.strftime('%d.%m.%Y')}
💰 Цена: {new_tour.price} руб.
👥 Количество мест: {new_tour.total_seats}
"""
                await update.message.reply_text(message)
                
                session.close()
                context.user_data.clear()
            except ValueError:
                await update.message.reply_text("Введите корректное число:")
    elif text == "📋 Просмотреть бронирования" and str(update.effective_user.id) == os.getenv('ADMIN_ID'):
        session = Session()
        bookings = session.query(Booking).filter(Booking.is_active == True).all()
        if not bookings:
            await update.message.reply_text("Нет активных бронирований.")
        else:
            for booking in bookings:
                tour = session.query(Tour).filter(Tour.id == booking.tour_id).first()
                message = f"""
Бронирование #{booking.id}
Тур: {tour.name}
Пользователь: {booking.user_name}
Телефон: {booking.phone_number}
Дата бронирования: {booking.booking_date}
                """
                # Добавляем кнопку отмены бронирования
                keyboard = [
                    [InlineKeyboardButton("❌ Отменить бронирование", callback_data=f"admin_cancel_booking_{booking.id}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(message, reply_markup=reply_markup)
        session.close()
    elif text == "⬅️ Назад в главное меню":
        keyboard = [
            ["🏖️ Просмотреть туры", "📋 Мои бронирования"],
            ["🛍️ Товары для туризма"],
            ["ℹ️ Информация", "📞 Контакты"]
        ]
        if str(update.effective_user.id) == os.getenv('ADMIN_ID'):
            keyboard.append(["👨‍💼 Админ панель"])
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)

async def edit_tour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Редактирование тура"""
    if str(update.effective_user.id) != os.getenv('ADMIN_ID'):
        await update.message.reply_text("У вас нет прав для редактирования туров.")
        return

    try:
        tour_id = int(context.args[0])
        session = Session()
        tour = session.query(Tour).filter(Tour.id == tour_id, Tour.is_active == True).first()
        
        if not tour:
            await update.message.reply_text("Тур не найден или недоступен.")
            return
        
        keyboard = [
            ["Изменить название", "Изменить описание"],
            ["Изменить даты", "Изменить цену"],
            ["Изменить количество мест", "Изменить фото"],
            ["Назад в админ панель"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        message = f"""
Редактирование тура #{tour.id}

Текущие данные:
Название: {tour.name}
Описание: {tour.description}
Дата начала: {tour.start_date}
Дата окончания: {tour.end_date}
Цена: {tour.price} руб.
Всего мест: {tour.total_seats}
Доступно мест: {tour.available_seats}

Выберите, что хотите изменить:
        """
        await update.message.reply_text(message, reply_markup=reply_markup)
        context.user_data['editing_tour_id'] = tour_id
        
    except (IndexError, ValueError):
        await update.message.reply_text("Использование: /edit_tour <ID_тура>")

async def show_tours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список доступных туров"""
    session = Session()
    tours = session.query(Tour).filter(Tour.is_active == True).all()
    session.close()
    
    if not tours:
        if update.callback_query:
            await update.callback_query.message.reply_text("На данный момент нет доступных туров.")
        else:
            await update.message.reply_text("На данный момент нет доступных туров.")
        return
    
    keyboard_main = [
        ["🏠 Главное меню"]
    ]
    reply_markup_main = ReplyKeyboardMarkup(keyboard_main, resize_keyboard=True)
    
    target = update.callback_query.message if update.callback_query else update.message
    await target.reply_text("Доступные туры:", reply_markup=reply_markup_main)
    
    for tour in tours:
        inline_keyboard = [
            [InlineKeyboardButton("🎫 Забронировать", callback_data=f"book_{tour.id}")]
        ]
        inline_markup = InlineKeyboardMarkup(inline_keyboard)
        
        end_date_str = f" - {tour.end_date.strftime('%d.%m.%Y')}" if tour.end_date else ""
        message = (
            f"🏖️ {tour.name}\n\n"
            f"📝 {tour.description}\n\n"
            f"📅 Даты: {tour.start_date.strftime('%d.%m.%Y')}{end_date_str}\n"
            f"💰 Цена: {tour.price} руб.\n"
            f"🎫 Доступно мест: {tour.available_seats}"
        )
        
        if tour.image_path:
            with open(tour.image_path, 'rb') as photo:
                await target.reply_photo(
                    photo=photo,
                    caption=message,
                    reply_markup=inline_markup
                )
        else:
            await target.reply_text(
                message,
                reply_markup=inline_markup
            )

async def show_tourism_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает категории товаров для туризма"""
    keyboard = [
        ["👕 Одежда и обувь", "⛺ Кемпинг и палатки"],
        ["🎒 Туристическое снаряжение", "📱 Электроника"],
        ["🍎 Продукты и напитки", "🎮 Досуг и развлечения"],
        ["🧴 Уход и безопасность"],
        ["🏠 Главное меню"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Выберите категорию товаров:", reply_markup=reply_markup)

async def show_clothing_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает товары категории 'Одежда и обувь'"""
    message = """
👕 Одежда и обувь для активного отдыха:

1. Ветровки и дождевики
2. Термобелье
3. Трекинговые ботинки
4. Спортивные костюмы
5. Головные уборы
6. Перчатки и варежки
7. Носки для активного отдыха
8. Купальные принадлежности
"""
    await update.message.reply_text(message)

async def show_camping_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает товары категории 'Кемпинг и палаточный лагерь'"""
    message = """
⛺ Кемпинг и палаточный лагерь:

1. Палатки различных размеров
2. Спальные мешки
3. Кемпинговая мебель
4. Газовые горелки
5. Посуда для кемпинга
6. Фонари и освещение
7. Тенты и навесы
8. Коврики для сна
"""
    await update.message.reply_text(message)

async def show_equipment_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает товары категории 'Туристическое снаряжение'"""
    message = """
🎒 Туристическое снаряжение:

1. Рюкзаки и сумки
2. Трекинговые палки
3. Компасы и навигация
4. Мультитулы и ножи
5. Веревки и карабины
6. Гермомешки
7. Фляги и термосы
8. Аптечки первой помощи
"""
    await update.message.reply_text(message)

async def show_electronics_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает товары категории 'Электроника для путешественников'"""
    message = """
📱 Электроника для путешественников:

1. Power bank
2. Солнечные панели
3. Навигаторы
4. Экшн-камеры
5. Портативные колонки
6. Умные часы
7. Планшеты для навигации
8. Компактные зарядные устройства
"""
    await update.message.reply_text(message)

async def show_food_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает товары категории 'Продукты и напитки'"""
    message = """
🍎 Продукты и напитки для путешествий:

1. Сухие пайки
2. Энергетические батончики
3. Сублимированная еда
4. Чай и кофе в дорогу
5. Изотоники
6. Орехи и сухофрукты
7. Консервы
8. Вода и напитки
"""
    await update.message.reply_text(message)

async def show_entertainment_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает товары категории 'Досуг и развлечения'"""
    message = """
🎮 Досуг и развлечения на отдыхе:

1. Настольные игры
2. Спортивный инвентарь
3. Книги и журналы
4. Музыкальные инструменты
5. Фотоаппараты
6. Дроны
7. Гамаки
8. Мячи и игры
"""
    await update.message.reply_text(message)

async def show_care_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает товары категории 'Уход за телом и безопасность'"""
    message = """
🧴 Уход за телом и безопасность:

1. Средства от насекомых
2. Солнцезащитные средства
3. Гигиенические наборы
4. Репелленты
5. Аптечки
6. Средства для очистки воды
7. Дезинфицирующие средства
8. Средства для ухода за кожей
"""
    await update.message.reply_text(message)

async def handle_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка бронирования тура"""
    query = update.callback_query
    tour_id = int(query.data.split('_')[1])
    
    session = Session()
    tour = session.query(Tour).filter(Tour.id == tour_id).first()
    
    if not tour or tour.available_seats <= 0:
        await query.message.reply_text("Извините, этот тур больше не доступен.")
        session.close()
        return
    
    context.user_data['booking_tour_id'] = tour_id
    await query.message.reply_text(
        "Пожалуйста, отправьте свой номер телефона для бронирования.\n"
        "Вы можете отправить его в формате +7XXXXXXXXXX или поделиться контактом."
    )
    session.close()

async def handle_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка номера телефона при бронировании"""
    if not update.message.contact and not update.message.text:
        await update.message.reply_text("Пожалуйста, отправьте номер телефона или поделитесь контактом.")
        return
    
    phone_number = update.message.contact.phone_number if update.message.contact else update.message.text
    tour_id = context.user_data.get('booking_tour_id')
    
    if not tour_id:
        await update.message.reply_text("Произошла ошибка. Пожалуйста, начните бронирование заново.")
        return
    
    session = Session()
    tour = session.query(Tour).filter(Tour.id == tour_id).first()
    
    if not tour or tour.available_seats <= 0:
        await update.message.reply_text("Извините, этот тур больше не доступен.")
        session.close()
        return
    
    # Создание бронирования
    booking = Booking(
        user_id=update.effective_user.id,
        user_name=update.effective_user.full_name,
        phone_number=phone_number,
        tour_id=tour_id
    )
    
    tour.available_seats -= 1
    session.add(booking)
    session.commit()
    
    # Отправка уведомления администратору
    admin_message = (
        f"🔔 Новое бронирование!\n\n"
        f"Тур: {tour.name}\n"
        f"Пользователь: {booking.user_name}\n"
        f"Телефон: {booking.phone_number}"
    )
    
    await context.bot.send_message(chat_id=ADMIN_ID, text=admin_message)
    
    await update.message.reply_text(
        "✅ Бронирование успешно оформлено!\n"
        "Вы можете просмотреть свои бронирования в разделе 'Мои бронирования'."
    )
    session.close()
    
    # Возвращаем пользователя в главное меню
    await start(update, context)

async def cancel_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена бронирования"""
    query = update.callback_query
    await query.answer()
    
    booking_id = int(query.data.split('_')[2])
    user_id = update.effective_user.id
    
    session = Session()
    booking = session.query(Booking).filter(
        Booking.id == booking_id,
        Booking.user_id == user_id,
        Booking.is_active == True
    ).first()
    
    if booking:
        tour = session.query(Tour).get(booking.tour_id)
        booking.is_active = False
        tour.available_seats += 1
        session.commit()
        
        # Отправляем уведомление администратору
        admin_message = (
            f"❌ Отмена бронирования\n\n"
            f"Тур: {tour.name}\n"
            f"Пользователь: {booking.user_name}\n"
            f"Телефон: {booking.phone_number}"
        )
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_message)
        
        await query.message.reply_text(
            "✅ Бронирование успешно отменено.\n"
            "Вы можете просмотреть другие туры в разделе 'Просмотреть туры'."
        )
        await show_my_bookings(update, context)
    else:
        await query.message.reply_text("❌ Бронирование не найдено или уже отменено.")
    
    session.close()

async def contact_operator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает контактную информацию оператора"""
    await update.callback_query.message.reply_text(config.CONTACT_INFO)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на инлайн-кнопки"""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith('book_'):
        tour_id = int(query.data.split('_')[1])
        session = Session()
        tour = session.query(Tour).filter(Tour.id == tour_id).first()
        
        if not tour or tour.available_seats <= 0:
            await query.message.reply_text("Извините, этот тур больше не доступен.")
            session.close()
            return
        
        context.user_data['booking_tour_id'] = tour_id
        
        keyboard = [[KeyboardButton("📱 Поделиться контактом", request_contact=True)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        
        await query.message.reply_text(
            "Пожалуйста, отправьте свой номер телефона для бронирования.\n"
            "Вы можете отправить его в формате +7XXXXXXXXXX или нажать кнопку ниже:",
            reply_markup=reply_markup
        )
        session.close()
    elif query.data.startswith('edit_'):
        if str(update.effective_user.id) != os.getenv('ADMIN_ID'):
            await query.message.reply_text("У вас нет прав для редактирования туров.")
            return
            
        tour_id = int(query.data.split('_')[1])
        session = Session()
        tour = session.query(Tour).filter(Tour.id == tour_id, Tour.is_active == True).first()
        
        if not tour:
            await query.message.reply_text("Тур не найден или недоступен.")
            session.close()
            return
        
        keyboard = [
            ["Изменить название", "Изменить описание"],
            ["Изменить даты", "Изменить цену"],
            ["Изменить количество мест", "Изменить фото"],
            ["Назад в админ панель"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        message = f"""
✏️ Редактирование тура #{tour.id}

Текущие данные:
📍 Название: {tour.name}
📝 Описание: {tour.description}
📅 Дата начала: {tour.start_date}
📅 Дата окончания: {tour.end_date}
💰 Цена: {tour.price} руб.
👥 Всего мест: {tour.total_seats}
🎫 Доступно мест: {tour.available_seats}

Выберите, что хотите изменить:
"""
        await query.message.reply_text(message, reply_markup=reply_markup)
        context.user_data['editing_tour_id'] = tour_id
        session.close()
        
    elif query.data.startswith('delete_'):
        if str(update.effective_user.id) != os.getenv('ADMIN_ID'):
            await query.message.reply_text("У вас нет прав для удаления туров.")
            return
            
        tour_id = int(query.data.split('_')[1])
        session = Session()
        tour = session.query(Tour).filter(Tour.id == tour_id, Tour.is_active == True).first()
        
        if tour:
            # Удаляем файл изображения, если он существует
            if tour.image_path and os.path.exists(tour.image_path):
                try:
                    os.remove(tour.image_path)
                except Exception as e:
                    logger.error(f"Ошибка при удалении файла изображения: {e}")
            
            tour.is_active = False
            session.commit()
            await query.message.reply_text(f"✅ Тур '{tour.name}' успешно удален.")
        else:
            await query.message.reply_text("❌ Тур не найден или уже удален.")
        
        session.close()
        
    elif query.data.startswith('cancel_booking_'):
        await cancel_booking(update, context)
    elif query.data == 'contact_operator':
        await contact_operator(update, context)
    elif query.data.startswith('admin_cancel_booking_'):
        if str(update.effective_user.id) != os.getenv('ADMIN_ID'):
            await query.answer("У вас нет прав для отмены бронирований.")
            return
            
        booking_id = int(query.data.split('_')[3])
        session = Session()
        booking = session.query(Booking).filter(Booking.id == booking_id, Booking.is_active == True).first()
        
        if booking:
            tour = session.query(Tour).get(booking.tour_id)
            booking.is_active = False
            tour.available_seats += 1
            session.commit()
            
            await query.message.reply_text(
                f"✅ Бронирование #{booking.id} успешно отменено.\n"
                f"Тур: {tour.name}\n"
                f"Пользователь: {booking.user_name}"
            )
        else:
            await query.message.reply_text("❌ Бронирование не найдено или уже отменено.")
        
        session.close()

def main():
    """Запуск бота"""
    application = Application.builder().token(os.getenv('BOT_TOKEN')).build()
    
    # Добавление обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("tours", tours))
    application.add_handler(CommandHandler("my_bookings", show_my_bookings))
    application.add_handler(CommandHandler("edit_tour", edit_tour))
    application.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, handle_tour_image))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.CONTACT, handle_phone_number))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main() 