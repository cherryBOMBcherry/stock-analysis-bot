# библиотеки для работы в телеграм ботом
import telebot
from telebot import types

# библиотеки для работы с базами данных
import pandas as pd
import sqlite3

# библиотеки для визуализации
import matplotlib.pyplot as plt

# библиотеки для api запросов и парсинга
import gigachat
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole
import requests
import apimoex

# дополнительные библиотеки
import os
import random
import io
import re
from datetime import datetime

# инициализирую бота 
bot = telebot.TeleBot('------')
GIGACHAT_CLIENT_SECRET = "-------"
user_context = {}

# ФУНКЦИЯ ПРЕДОСТАВЛЕНИЯ ГРАФИКА ПО ЗАПРОСУ ПОЛЬЗОВАТЕЛЯ
def plot_price(df):
    df['date'] = pd.to_datetime(df['date'])
    plt.style.use('default')
    plt.figure(figsize=(12, 6))
    plt.plot(df["date"], df["close"])
    plt.title(f"Динамика цен акций {', '.join(list(df.ticker.unique()))}")
    plt.xlabel("Дата")
    plt.ylabel("Цена закрытия")
    plt.grid(True)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close()
    buf.seek(0)
    return buf

# ФУНКЦИЯ ПОДСЧЕТА СТАТИСТИК
def compute_stats(df):
    if df.empty:
        return None

    stats = {
        "ticker": df['ticker'].unique()[0],
        "mean": float(df["close"].mean()),
        "min": float(df["close"].min()),
        "max": float(df["close"].max()),
        "start_price": float(df["close"].iloc[0]),
        "end_price": float(df["close"].iloc[-1]),
    }

    stats["change_abs"] = stats["end_price"] - stats["start_price"]
    stats["change_pct"] = (
        stats["change_abs"] / stats["start_price"] * 100
        if stats["start_price"] != 0
        else None
    )
    return stats

def format_stats(stats):
    mes = []
    formatted_stats = (
        f"Стастика по тикеру {stats['ticker']} за указанный период:\n\n"
        f"Средняя цена закрытия:  {stats['mean']:.2f}\n"
        f"Минимальная цена закрытия:  {stats['min']:.2f}\n"
        f"Максимальная цена закрытия:  {stats['max']:.2f}\n"
        f"Цена на начало периода:  {stats['start_price']:.2f}\n"
        f"Цена на конец периода:  {stats['end_price']:.2f}\n"
        f"Изменение цены:  {stats['change_abs']:.2f} ({stats['change_pct']:.2f}%)\n"
    )
        
    if stats['change_abs'] > 0:
        formatted_stats += "\nЦены росли.\n"
    elif stats['change_abs'] < 0:
        formatted_stats += "\nЦены упали.\n"
    else:
        formatted_stats += "\nЦены остались без изменения.\n"
    mes.append(formatted_stats)
    return '\n'.join(mes)


# ФУНКЦИЯ ОБРАБОТКИ ЗАПРОСА ИИ
def _call_giga(system_prompt: str, user_prompt: str, temperature: float = 0.0, max_tokens: int = 500):
    payload = Chat(
        messages=[
            Messages(role=MessagesRole.SYSTEM, content=system_prompt),
            Messages(role=MessagesRole.USER, content=user_prompt),
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    with GigaChat(credentials=GIGACHAT_CLIENT_SECRET, verify_ssl_certs=False) as giga:
        response = giga.chat(payload)
    return response.choices[0].message.content

def generate_analysis_with_giga(stats_dict):
    system_prompt = (
        "Ты — финансовый аналитик. Дай краткий интересный вывод по статистике цен акций за период. Максимум 7-10 предложений."
    )
    user_prompt = (
        "Вот статистика. Напиши краткий финансовый анализ с выводами:\n\n"
        f"{stats_dict}"
    )
    result = _call_giga(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.4,
        max_tokens=500
    )
    return result

# СТАРТ БОТА

def main_menu():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add('💼 Мой портфель')
    keyboard.add('✅ Добавить актив', '❌ Удалить актив')
    keyboard.add('💡 Диверсификация портфеля')
    keyboard.add("📈 График", "📊 Статистика", '🔍 Анализ')
    keyboard.add("❓ Помощь", "😂 Мем")
    keyboard.add("📰 Новости")
    return keyboard

def inline_action_buttons():
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("📈 График", callback_data="want_graph"),
        types.InlineKeyboardButton("📊 Статистика", callback_data="want_stats"),
        types.InlineKeyboardButton("🔍 Анализ", callback_data="want_analysis")
    )
    return kb

# ОТПРАВКА ПРИВЕТСТВЕННОГО СООБЩЕНИЯ
@bot.message_handler(commands = ['start'])
def send_welcome(message):
    text = (f"✨Привет, {message.from_user.first_name}!✨\n\n"
            "Я бот аналитики акций российских компаний.\n"
            "\n"
            "Я умею:\n"
            "• строить графики\n"
            "• считать статистику\n"
            "• делать текстовый анализ\n"
            "• и помогать с управлением твоего портфеля\n"
            "\n"
            "Для того, чтобы начать, используй кнопки в главном меню."
            "\n"
            "✨Успехов!✨\n"
    )
    bot.send_message(message.chat.id, text, reply_markup=main_menu())
@bot.message_handler(func=lambda message: message.text and message.text.strip().lower().startswith('привет'))
def handle_greeting(message):
    send_welcome(message) 

# ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ПОЛУЧЕНИЯ ДАННЫХ ПО АКЦИЯМ КОМПАНИИ 
def get_stock_data(ticker, start_date = None, end_date = None):
    with requests.Session() as session:
        data = apimoex.get_board_history(session, security = ticker, start = start_date, end = end_date, 
                                        columns = ('BOARDID', 'TRADEDATE', 'OPEN', 'CLOSE', 'HIGH', 'LOW', 'VOLUME', 'VALUE'))
    df = pd.DataFrame(data)
    df = df.drop('BOARDID', axis=1)
    df.columns = ['date', 'open', 'close', 'high', 'low', 'volume', 'value']
    df['ticker'] = [ticker]*len(df)
    return df

# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ИНИЦИАЛИЗАЦИИ ПОРТФЕЛЯ
path = "portfolio.csv"
if not os.path.exists(path):
    pd.DataFrame(columns=["user_id", "тикер", "количество", "цена покупки", "сектор"]).to_csv(path, index=False)
def load_portfolio(user_id):
    df = pd.read_csv(path)
    return df[df["user_id"] == user_id].copy()
def save(user_id, ticker, quantity, buy_price, sector):
    df = pd.read_csv(path)
    new_row = pd.DataFrame([{
        "user_id": user_id,
        "тикер": ticker.upper(),
        "количество": float(quantity),
        "цена покупки": float(buy_price),
        "сектор" : sector
    }])
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(path, index=False)
def remove(user_id, ticker):
    df = pd.read_csv(path)
    df = df[~((df["user_id"] == user_id) & (df["тикер"] == ticker.upper()))]
    df.to_csv(path, index=False)

# ФУНКЦИЯ ПОКАЗАТЬ АКТИВЫ В ПОРТФЕЛЕ
@bot.message_handler(func = lambda x: x.text == "💼 Мой портфель")
def show_portfolio(message):
    user_id = message.from_user.id
    df = load_portfolio(user_id)
    if df.empty:
        bot.send_message(message.chat.id, "Портфель пуст. Добавьте активы!")
        return
    lines = ["Ваш портфель:\n"]
    income = []
    income2 = []
    for i, row in df.iterrows():
        ticker = row["тикер"]
        count = row["количество"]
        price = row["цена покупки"]
        current_df = get_stock_data(ticker)
        current_price = current_df["close"].iloc[-1]
        change = ((current_price - price) / price) * 100
        income.append(count*price)
        income2.append(count*current_price)
        lines.append(f"{ticker}: {count} шт\nЦена покупки: {price:.2f} ₽ \nТекущая цена: {current_price:.2f} ₽ \nИзменение стоимости актива {change:+.1f}%\n")
    t = f'Общая стоимость портфеля: {sum(income2)} ₽\nДоходность: {(sum(income2)*100/sum(income))-100:.2f}%'
    bot.send_message(message.chat.id, "\n".join(lines))
    bot.send_message(message.chat.id, t)

# ФУНКЦИЯ ДОБАВЛЕНИЯ АКТИВА В ПОРТФЕЛЬ
@bot.message_handler(func = lambda x: x.text == "✅ Добавить актив")
def add_asset_prompt(message):
    bot.send_message(
        message.chat.id,
        "Введите данные в формате:\nТИКЕР, КОЛИЧЕСТВО, ЦЕНА, СЕКТОР\n"
        "Пример: `SBER, 10, 250, ФИНАНСЫ`",
        parse_mode="Markdown"
    )

@bot.message_handler(regexp=r'^[A-Za-zА-Яа-яЁё]+\s*,\s*\d+\.?\d*\s*,\s*\d+\.?\d*\s*,\s*[A-Za-zА-Яа-яЁё\s]+$')
def add_asset_parse(message):
    parts = message.text.split(',')
    ticker, qty, price, sector = parts[0].upper(), float(parts[1]), float(parts[2]), parts[-1]
    user_id = message.from_user.id
    save(user_id, ticker, qty, price, sector)
    bot.send_message(message.chat.id, f"✅ Актив {ticker} добавлен в портфель!")

# ФУНКЦИЯ УДАЛИТЬ АКТИВ ИЗ ПОРТФЕЛЯ
@bot.message_handler(func = lambda x: x.text == "❌ Удалить актив")
def delete_asset_menu(message):
    user_id = message.from_user.id
    df = load_portfolio(user_id)
    if df.empty:
        bot.send_message(message.chat.id, "Портфель пуст.")
        return
    kb = types.InlineKeyboardMarkup()
    for ticker in df["тикер"].unique():
        kb.add(types.InlineKeyboardButton(f"❌ {ticker}", callback_data=f"del_{ticker}"))
    bot.send_message(message.chat.id, "Выберите актив для удаления:", reply_markup=kb)

@bot.callback_query_handler(func = lambda x: x.data.startswith("del_"))
def delete_asset_callback(call):
    ticker = call.data[4:]
    user_id = call.from_user.id
    remove(user_id, ticker)
    bot.answer_callback_query(call.id, f"{ticker} удалён!")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"✅ Актив {ticker} удалён из портфеля."
    )

# ФУНКЦИЯ АНАЛИЗ ДИВЕРСИФИКАЦИИ ПОРТФЕЛЯ
@bot.message_handler(func=lambda m: m.text == "💡 Диверсификация портфеля")
def diversification_advice(message):
    user_id = message.from_user.id
    df = load_portfolio(user_id)
    if df.empty:
        bot.send_message(message.chat.id, "Портфель пуст. Добавьте активы!")
        return
    sectors = [i.upper() for i in df["сектор"].tolist()]
    from collections import Counter
    counts = Counter(sectors)

    if len(counts) == 1:
        dominant = list(counts.keys())[0]
        bot.send_message(
            message.chat.id,
            f"⚠️ Весь портфель в секторе «{dominant}».\n"
            f"Рассмотрите диверсификацию в другие сектора.\n")
    else:
        summary = "\n".join([f"• {sector}: {count} актив(ов)" for sector, count in counts.items()])
        bot.send_message(
            message.chat.id,
            f"✅ Портфель диверсифицирован по {len(counts)} секторам:\n\n{summary}"
        )


# ФУНКЦИИ ПРЕДОСТАВЛЕНИЯ ГРАФИКА, ОПИСАТЕЛЬНЫЙ СТАТИСТИК, АНАЛИЗА ОТ ИИ
def ask_for_ticker_and_period(chat_id, mode):
    bot.send_message(chat_id, "Укажите тикер и период в формате:\n\n`ТИКЕР, ГГГГ-ДД-ММ, ГГГГ-ДД-ММ`\n\nПример: `SBER, 2025-08-15, 2025-08-30`", parse_mode="Markdown")
    user_context[chat_id] = {'тип_функции': mode}

@bot.callback_query_handler(func = lambda call: call.data in ("want_graph", "want_stats", "want_analysis"))
def handle_inline_action(call):
    mode_map = {"want_graph": "graph", "want_stats": "stats", "want_analysis": "analysis"}
    mode = mode_map[call.data]
    ask_for_ticker_and_period(call.message.chat.id, mode)
    bot.answer_callback_query(call.id)

@bot.message_handler(func = lambda x: x.text in ("📈 График", "📊 Статистика", "🔍 Анализ"))
def handle_menu_action(message):
    mode_map = {
        "📈 График": "graph",
        "📊 Статистика": "stats",
        "🔍 Анализ": "analysis"
    }
    mode = mode_map[message.text]
    ask_for_ticker_and_period(message.chat.id, mode)


@bot.message_handler(func=lambda msg: user_context.get(msg.chat.id, {}).get('тип_функции') in ('graph', 'stats', 'analysis'))
def process_ticker_and_period(message):
    chat_id = message.chat.id
    mode = user_context[chat_id]['тип_функции']
    text = message.text.strip()

    pattern = r'^([A-Za-z]+)(?:\s*,\s*(\d{4}-\d{2}-\d{2})\s*,\s*(\d{4}-\d{2}-\d{2}))?$'
    match = re.match(pattern, text)
    if not match:
        bot.send_message(chat_id, "⚠️ Неверный формат ввода. Попробуйте еще раз.", parse_mode="Markdown")
        return

    ticker = match.group(1).upper()
    start_str = match.group(2)
    end_str = match.group(3)

    try:
        start_date = datetime.strptime(start_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_str, "%Y-%m-%d")
    except ValueError:
        bot.send_message(chat_id, "Ошибка в датах.")
        return

    try:
        df = get_stock_data(ticker, start_date=start_date, end_date=end_date)
    except:
        bot.send_message(chat_id, f"❌ Нет данных по тикеру `{ticker}`.", parse_mode="Markdown")

    if mode == "graph":
        img = plot_price(df)
        bot.send_photo(chat_id, img)
        
        user_context.pop(chat_id, None)
    elif mode == "stats":
        stats = compute_stats(df)
        bot.send_message(chat_id, format_stats(stats))
        
        user_context.pop(chat_id, None)
    elif mode == "analysis":
        stats = compute_stats(df)
        analysis = generate_analysis_with_giga(stats)
        bot.send_message(chat_id, analysis)

        user_context.pop(chat_id, None)

# ФУНКЦИЯ ПОМОЩИ
@bot.message_handler(func=lambda m: m.text == "❓ Помощь")
def send_help(message):
    with requests.Session() as session:
        data = apimoex.get_board_securities(session, columns = ('SECID', 'SHORTNAME'))
    bot.send_message(
        message.chat.id,
        "🔹 Используйте кнопки для управления портфелем.\n"
        "🔹 Сейчас доступна информация по следующим тикерам:"
        "\n"
        f"{', '.join([i['SECID'] for i in data][:50])} и другим"
    )

# ФУНКЦИЯ ВЫБОРА СЛУЧАЙНОГО МЕМА
def send_random_meme(chat_id):
    meme_dir = "memes"
    meme_files = [f for f in os.listdir(meme_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    random_meme = random.choice(meme_files)
    meme_path = os.path.join(meme_dir, random_meme)
    with open(meme_path, 'rb') as photo:
        bot.send_photo(chat_id, photo)

@bot.message_handler(func=lambda x: x.text == "😂 Мем")
def send_meme(message):
    send_random_meme(message.chat.id)

# ФУНКЦИЯ ПРЕДЛОЖЕНИЯ НОВОСТЕЙ
def news_inline_keyboard():
    kb = types.InlineKeyboardMarkup()
    sites = [
        ("РБК", "https://www.rbc.ru/quote/tag/investments"),
        ("Forbes", "https://www.forbes.ru/investicii/"),
        ("Investing", "https://ru.investing.com/news"),
        ("Bloomberg", "https://www.bloomberg.com/markets"),
        ("Financial Times", "https://www.ft.com/markets"),
        ("Reuters Business", "https://www.reuters.com/business/finance/")
    ]
    # Добавляем по 2 кнопки в ряд для компактности
    for i in range(0, len(sites), 2):
        row = []
        for name, url in sites[i:i+2]:
            row.append(types.InlineKeyboardButton(text=name, url=url))
        kb.add(*row)
    return kb

@bot.message_handler(func=lambda x: x.text == "📰 Новости")
def send_news_sources(message):
    bot.send_message(
        message.chat.id,
        "Здесь предложены сайты с инвестиционными новостями.\nНажимай понравившийся и переходи читать!",
        reply_markup=news_inline_keyboard()
    )

# ФУНКЦИЯ ОБРАБОТКИ ЛЮБЫХ СООБЩЕНИЙ ПОЛЬЗОВАТЕЛЯ
def response_with_giga(user_message):
    user_prompt = f"Сообщение пользователя:\n\"\"\"{user_message}\"\"\""
    system_prompt = (
        "Ты — дружелюбный Telegram-бот, который помогает с анализом акций российских компаний. "
        "Если сообщение — вежливость (например, спасибо, круто, пока), отвечай кратко, вежливо и дружелюбно. "
        "Если сообщение — вопрос о возможностях, напомни, что ты умеешь строить графики, считать статистику и давать аналитику. "
        "Если сообщение непонятно или не относится к теме, предложи задать вопрос по акциям."
        "Ответ должен быть кратким — максимум 4-5 предложений."
        "Общайся неформально, шути и используй стикеры"
    )
    result = _call_giga(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.5,
        max_tokens=300 
    )
    return result.strip()

@bot.message_handler(func = lambda x: True, content_types=['text'])
def handle_any_message(message):
    user_text = message.text.strip()
    try:
        reply = response_with_giga(user_text)
        bot.send_message(message.chat.id, reply)
    except:
        fallback = (
            "Извини, я сейчас не могу обработать это сообщение. "
            "Напиши «привет» или воспользуйся кнопками меню!"
        )
        bot.send_message(message.chat.id, fallback)