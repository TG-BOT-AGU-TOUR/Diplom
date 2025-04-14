import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from models import Session, Tour, Booking
import config

async def add_tour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса добавления тура"""
    context.user_data['adding_tour'] = True
    context.user_data['tour_stage'] = 'name'
    await update.callback_query.message.reply_text("Введите название тура:")

async def handle_tour_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка названия тура"""
    context.user_data['tour_name'] = update.message.text
    context.user_data['tour_stage'] = 'description'
    await update.message.reply_text("Введите описание тура:")

async def handle_tour_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка описания тура"""
    context.user_data['tour_description'] = update.message.text
    context.user_data['tour_stage'] = 'image'
    await update.message.reply_text("Отправьте изображение для тура:")

async def handle_tour_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка изображения тура"""
    if not update.message.photo:
        await update.message.reply_text("Пожалуйста, отправьте изображение.")
        return
    
    photo = update.message.photo[-1]
    file = await photo.get_file()
    image_path = os.path.join(config.IMAGES_DIR, f"tour_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
    await file.download_to_drive(image_path)
    
    context.user_data['tour_image'] = image_path
    context.user_data['tour_stage'] = 'date'
    await update.message.reply_text("Введите дату тура (в формате ДД.ММ.ГГГГ или ДД.ММ.ГГГГ-ДД.ММ.ГГГГ):")

async def handle_tour_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка даты тура"""
    try:
        dates = update.message.text.split('-')
        start_date = datetime.strptime(dates[0].strip(), '%d.%m.%Y')
        end_date = datetime.strptime(dates[1].strip(), '%d.%m.%Y') if len(dates) > 1 else None
        
        context.user_data['tour_start_date'] = start_date
        context.user_data['tour_end_date'] = end_date
        context.user_data['tour_stage'] = 'price'
        await update.message.reply_text("Введите цену тура (в рублях):")
    except ValueError:
        await update.message.reply_text("Неверный формат даты. Используйте формат ДД.ММ.ГГГГ или ДД.ММ.ГГГГ-ДД.ММ.ГГГГ")

async def handle_tour_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка цены тура"""
    try:
        price = int(update.message.text)
        context.user_data['tour_price'] = price
        context.user_data['tour_stage'] = 'seats'
        await update.message.reply_text("Введите количество мест:")
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите число.")

async def handle_tour_seats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка количества мест и сохранение тура"""
    try:
        seats = int(update.message.text)
        session = Session()
        
        tour = Tour(
            name=context.user_data['tour_name'],
            description=context.user_data['tour_description'],
            image_path=context.user_data['tour_image'],
            start_date=context.user_data['tour_start_date'],
            end_date=context.user_data['tour_end_date'],
            price=context.user_data['tour_price'],
            total_seats=seats,
            available_seats=seats
        )
        
        session.add(tour)
        session.commit()
        session.close()
        
        # Очистка данных
        for key in ['adding_tour', 'tour_stage', 'tour_name', 'tour_description',
                   'tour_image', 'tour_start_date', 'tour_end_date', 'tour_price']:
            context.user_data.pop(key, None)
        
        await update.message.reply_text("✅ Тур успешно добавлен!")
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите число.")

async def edit_tour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список туров для редактирования"""
    session = Session()
    tours = session.query(Tour).filter(Tour.is_active == True).all()
    session.close()
    
    if not tours:
        await update.callback_query.message.reply_text("Нет доступных туров для редактирования.")
        return
    
    keyboard = []
    for tour in tours:
        keyboard.append([InlineKeyboardButton(tour.name, callback_data=f'edit_tour_{tour.id}')])
    
    keyboard.append([InlineKeyboardButton("Назад", callback_data='back_to_admin')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text("Выберите тур для редактирования:", reply_markup=reply_markup)

async def show_tour_edit_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает опции редактирования для выбранного тура"""
    tour_id = int(update.callback_query.data.split('_')[2])
    context.user_data['editing_tour_id'] = tour_id
    
    keyboard = [
        [InlineKeyboardButton("Изменить название", callback_data='edit_name')],
        [InlineKeyboardButton("Изменить картинку", callback_data='edit_image')],
        [InlineKeyboardButton("Изменить описание", callback_data='edit_description')],
        [InlineKeyboardButton("Изменить дату", callback_data='edit_date')],
        [InlineKeyboardButton("Изменить цену", callback_data='edit_price')],
        [InlineKeyboardButton("Изменить количество мест", callback_data='edit_seats')],
        [InlineKeyboardButton("Удалить тур", callback_data='delete_tour')],
        [InlineKeyboardButton("Назад", callback_data='back_to_tours')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text("Выберите действие:", reply_markup=reply_markup)

async def view_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает последние бронирования"""
    session = Session()
    bookings = session.query(Booking).filter(Booking.is_active == True).order_by(Booking.booking_date.desc()).limit(10).all()
    session.close()
    
    if not bookings:
        await update.callback_query.message.reply_text("Нет активных бронирований.")
        return
    
    for booking in bookings:
        keyboard = [[InlineKeyboardButton("Контакты клиента", callback_data=f'client_contacts_{booking.id}')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        end_date_str = f" - {booking.tour.end_date.strftime('%d.%m.%Y')}" if booking.tour.end_date else ""
        message = (
            f"🏖️ {booking.tour.name}\n\n"
            f"👤 Клиент: {booking.user_name}\n"
            f"📅 Дата бронирования: {booking.booking_date.strftime('%d.%m.%Y')}\n"
            f"📅 Даты тура: {booking.tour.start_date.strftime('%d.%m.%Y')}{end_date_str}"
        )
        
        await update.callback_query.message.reply_text(message, reply_markup=reply_markup)

async def show_client_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает контактную информацию клиента"""
    booking_id = int(update.callback_query.data.split('_')[2])
    
    session = Session()
    booking = session.query(Booking).filter(Booking.id == booking_id).first()
    session.close()
    
    if booking:
        message = (
            f"👤 Клиент: {booking.user_name}\n"
            f"📞 Телефон: {booking.phone_number}"
        )
        await update.callback_query.message.reply_text(message)
    else:
        await update.callback_query.message.reply_text("Бронирование не найдено.") 