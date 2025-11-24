import json
import telebot
from telebot import types
from config.config import TELEGRAM_TOKEN, DATABASE_URL
from gigachat_promt import parse_user_query_with_giga, generate_analysis_with_giga, response_with_giga
from prompts import PARSE_PROMPT
from analysis import plot_price_chart, compute_stats, query_prices, format_stats, get_available_companies
from sqlalchemy import text
import os
import random

bot = telebot.TeleBot(TELEGRAM_TOKEN)
user_context = {}
# -------------------------------------------------------
#  Кнопки
# -------------------------------------------------------

def main_menu():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("📈 График", "📊 Статистика")
    keyboard.add("🔍 Анализ", "❓ Помощь", "🎭 Мем")
    return keyboard


def inline_action_buttons():
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("📈 График", callback_data="want_graph"),
        types.InlineKeyboardButton("📊 Статистика", callback_data="want_stats"),
        types.InlineKeyboardButton("🔍 Анализ", callback_data="want_analysis")
    )
    return kb

def send_error(chat_id, text):
    bot.send_message(
        chat_id, 
        f"⚠️ {text}\n\nПопробуйте ещё раз или нажмите «❓ Помощь».", 
        reply_markup=main_menu()
    )


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):  # ← изменено: теперь принимает message
    # bot.send_sticker(message.chat.id, "CAACAgIAAxkBAAEMmKtmvKfY7nXQZ7Y6RvW5x9K5X0D4jwACDwADwDZPE6qzh8qWVj6dNgQ")

    text = (f"Привет, {message.from_user.first_name}!👋\n\n"
            "Я бот аналитики акций технологических компаний за 2024 год.\n"
            "\n"
            "Я умею:\n"
            "• строить графики\n"
            "• считать статистику\n"
            "• делать текстовый анализ\n"
            "• работать с несколькими компаниями одновременно\n\n"
            "\n"
            "Напиши свой запрос, например:\n"
            "• Покажи график Apple за март\n"
            "• Статистика NVDA и MSFT за апрель\n"
            "• Сделай анализ Google за первое полугодие\n"
    )
    bot.send_message(message.chat.id, text, reply_markup=main_menu())

@bot.message_handler(func=lambda message: message.text and message.text.strip().lower().startswith('привет'))
def handle_greeting(message):
    send_welcome(message)

@bot.message_handler(func=lambda m: True, content_types=['text'])
def handle_text(message):
    global user_context
    chat_id = message.chat.id
    user_ms = message.text.strip()
    
    if user_ms in ["📈 График", "📊 Статистика", "🔍 Анализ"]:
        bot.send_message(
            chat_id,
            "Укажите компанию и период, например:\n\n"
            "• График AAPL за март\n"
            "• Статистика NVDA за апрель\n"
            "• Анализ Google за год"
        )
        return
    
    def send_help_message(chat_id):
        companies = get_available_companies(DATABASE_URL)
        companies_list = "\n".join(f"• {ticker}" for ticker in companies)

        help_text = (
            "Вот что я умею:\n"
            "📊 • Строить графики цен акций\n"
            "🧮 • Считать статистику (среднее, максимум, волатильность и т.д.)\n"
            "💬 • Давать текстовый анализ на основе данных за 2024 год\n\n"
            "🏢 Доступны данные по следующим компаниям:\n"
            f"{companies_list}\n\n"
            "📋 Примеры запросов:\n"
            "• График AAPL за март\n"
            "• Статистика NVDA и MSFT за апрель\n"
            "• Анализ Google за первое полугодие\n\n"
            "Жду ваш запрос! 🚀"
        )
        bot.send_message(chat_id, help_text, reply_markup=main_menu())    
    
    if user_ms == "❓ Помощь":
        send_help_message(chat_id)
        return
    
    def send_random_meme(chat_id):
        meme_dir = "memes"
        meme_files = [f for f in os.listdir(meme_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        random_meme = random.choice(meme_files)
        meme_path = os.path.join(meme_dir, random_meme)

        try:
            with open(meme_path, 'rb') as photo:
                bot.send_photo(chat_id, photo)
        except Exception as e:
            bot.send_message(chat_id, "Не удалось отправить мем 😅 Попробуйте ещё раз!")
            print(f"Ошибка отправки мема: {e}")

    if user_ms == "🎭 Мем":
        send_random_meme(chat_id)
        return

    bot.send_chat_action(chat_id, 'typing')

    try:

        giga_resp = parse_user_query_with_giga(PARSE_PROMPT, user_ms)
        try:
            parsed = json.loads(giga_resp)
        except Exception:
            cleaned = giga_resp.strip().strip('`')
            parsed = json.loads(cleaned)
    except Exception as e:
        bot.send_message(chat_id, f"К сожалению, я не смог понять запрос 🤔\nПопробуйте еще раз!")
        return
    

    aim = parsed.get('Aim')
    ticker = parsed.get('ticker')
    start_date = parsed.get('start_date')
    end_date = parsed.get('end_date')

    user_context[chat_id] = {
        "tickers": ticker,
        "start_date": start_date,
        "end_date": end_date
    }

    if not ticker:
        try:
            reply = response_with_giga(f"Пользователь спросил: {user_ms}") #но не указан тикер акции.
            bot.send_message(chat_id, reply)
        except Exception:
            send_error(chat_id, "Не удалось определить компанию 🏷️")
        return

    try:
        df = query_prices(DATABASE_URL, ticker, start_date=start_date, end_date=end_date)
    except:
        bot.send_message(chat_id, f"К сожалению произошла ошибка, повторите попытку еще раз ((")
        return

    if df is None or df.empty:
        bot.send_message(chat_id, "Данные за указанный период / тикер не найдены.")
        return

    if aim == 'график':
        try:
            img_buf = plot_price_chart(df)
            bot.send_photo(chat_id, img_buf)
        except Exception as e:
            bot.send_message(chat_id, f"Ошибка построения графика: {e}")
            return

        stats = compute_stats(df)
        bot.send_message(chat_id, generate_analysis_with_giga(stats))
        bot.send_message(chat_id, "Хотите дополнительно?", reply_markup=inline_action_buttons())
    
    elif aim == 'статистика':
        stats = compute_stats(df)
        bot.send_message(chat_id, format_stats(stats), parse_mode='html')
        # bot.send_message(chat_id, generate_analysis_with_giga(stats))
        bot.send_message(chat_id, "Хотите дополнительно?", reply_markup=inline_action_buttons())

    elif aim == 'анализ':
        stats = compute_stats(df)
        bot.send_message(chat_id, 'Краткая аналитическая сводка: \n')
        bot.send_message(chat_id, generate_analysis_with_giga(stats))
        bot.send_message(chat_id, "Что ещё показать?", reply_markup=inline_action_buttons())
    
    else:
        bot.send_message(
            chat_id,
            "Кажется, я не понял, что именно вы хотите сделать 🤔",
            reply_markup=inline_action_buttons()
        )


@bot.callback_query_handler(func=lambda c: True)
def callback_handler(call):
    global user_context
    chat_id = call.message.chat.id
    ctx = user_context.get(chat_id)

    if ctx is None:
        bot.send_message(chat_id, "Сначала сделайте запрос: например «График AAPL за апрель»")
        return
    

    if call.data == "want_graph":
        try:
            df = query_prices(
                DATABASE_URL,
                ctx["tickers"],
                start_date=ctx["start_date"],
                end_date=ctx["end_date"]
            )
            img_buf = plot_price_chart(df)
            bot.send_photo(chat_id, img_buf)

        except Exception as e:
            bot.send_message(chat_id, f"Ошибка построения графика: {e}")
            return

    elif call.data == "want_stats":
        df = query_prices(
            DATABASE_URL,
            ctx["tickers"],
            start_date=ctx["start_date"],
            end_date=ctx["end_date"]
        )
        stats = compute_stats(df)
        bot.send_message(chat_id, format_stats(stats), parse_mode='html')

    elif call.data == "want_analysis":
        df = query_prices(
            DATABASE_URL,
            ctx["tickers"],
            start_date=ctx["start_date"],
            end_date=ctx["end_date"]
        )
        stats = compute_stats(df)
        bot.send_message(chat_id, generate_analysis_with_giga(stats))


bot.polling(none_stop=True)