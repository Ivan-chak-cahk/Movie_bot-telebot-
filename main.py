# Импорт необходимых библиотек
import os
from dotenv import load_dotenv
import requests
from peewee import *
from datetime import datetime
import telebot
from telebot.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton

# --- КОНФИГУРАЦИЯ ---
# Загружаем переменные окружения из файла .env
load_dotenv()

# Получаем токены из переменных окружения
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')  # Токен вашего Telegram бота
API_KEY = os.getenv('KINOPOISK_API_KEY')  # API ключ для доступа к Kinopoisk

# Инициализируем бота
bot = telebot.TeleBot(TOKEN)

# --- БАЗА ДАННЫХ ---
# Создаем соединение с SQLite базой данных
db = SqliteDatabase('movies.db')

# Базовый класс модели для наследования
class BaseModel(Model):
    class Meta:
        database = db  # Все модели будут использовать эту БД

# Модель пользователя Telegram
class User(BaseModel):
    user_id = IntegerField(unique=True)  # Уникальный ID пользователя в Telegram
    username = CharField(null=True)  # @username (может отсутствовать)
    full_name = CharField(null=True)  # Полное имя пользователя
    created_ad = DateTimeField(default=datetime.now)  # Дата регистрации

# Модель истории поисковых запросов
class SearchHistory(BaseModel):
    user = ForeignKeyField(User, backref="searches")  # Связь с пользователем
    search_type = CharField()  # Тип поиска (по названию, рейтингу и т.д.)
    query = TextField(null=True)  # Текст запроса (может быть пустым)
    genre = CharField(null=True)  # Жанр
    limit = IntegerField(null=True)  # Лимит
    min_rating = FloatField(null=True)  # мин рейтинг
    max_rating = FloatField(null=True)  # макс рейтинг
    created_ad = DateTimeField(default=datetime.now)  # Время поиска

# Модель истории найденных фильмов
class MovieHistory(BaseModel):
    search = ForeignKeyField(SearchHistory, backref="movies")  # Связь с поисковым запросом
    movie_id = IntegerField()  # ID фильма в Kinopoisk API
    title = CharField()  # Название фильма
    description = TextField(null=True)  # Описание (может отсутствовать)
    rating = FloatField(null=True)  # Рейтинг (может отсутствовать)
    year = IntegerField(null=True)  # Год выпуска
    genres = CharField(null=True)  # Жанры (строка с перечислением)
    age_rating = CharField(null=True)  # Возрастной рейтинг (16+, 18+ и т.д.)
    poster_url = CharField(null=True)  # Ссылка на постер
    is_watched = BooleanField(default=False)  # Отметка о просмотре

# Создаем таблицы в базе данных
db.connect()
db.create_tables([User, SearchHistory, MovieHistory])

# --- РАБОТА С API KINOPOISK ---
class KinopoiskAPI:
    # Базовый URL для API Kinopoisk (версия 1.4)
    BASE_URL = "https://api.kinopoisk.dev/v1.4/"

    def __init__(self, api_key):
        self.api_key = api_key
        # Заголовки для запросов (с API-ключом)
        self.headers = {"X-API-KEY": self.api_key}

    def search_movie(self, params):
        """Базовый метод для поиска фильмов"""
        url = f"{self.BASE_URL}movie"
        # Отправка GET-запроса к API
        response = requests.get(url, headers=self.headers, params=params)
        return response.json()  # Возвращаем ответ в формате JSON

    def search_by_name(self, title, genre=None, limit=5):
        """Поиск по названию с опциональной фильтрацией по жанру"""
        params = {
            "page": 1,  # Пагинация (первая страница)
            "limit": limit,  # Лимит результатов (по умолчанию 5)
            "name": title,  # Поисковый запрос
        }
        if genre:
            params["genres.name"] = genre  # Добавляем фильтр по жанру
        return self.search_movie(params)

    def search_by_rating(self, min_rating, max_rating, genre=None, limit=5):
        """Поиск по рейтингу"""
        params = {
            "page": 1,
            "limit": limit,
            "rating.kp": f"{min_rating}-{max_rating}",  # Фильтр по рейтингу (например, "7-9")
        }
        if genre:
            params["genres.name"] = genre
        return self.search_movie(params)

    def search_by_budget(self, budget_type, genre=None, limit=5):
        """Поиск по бюджету"""
        params = {
            "page": 1,
            "limit": limit,
            "sortField": "budget.value",  # Сортировка по бюджету
            # Сортировка: -1 = по убыванию (высокий бюджет), 1 = по возрастанию (низкий бюджет)
            "sortType": -1 if budget_type == "high" else 1,
        }
        if genre:
            params["genres.name"] = genre
        return self.search_movie(params)

# --- КЛАВИАТУРА ---
def get_main_menu():
    """Клава главного меню"""
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("Поиск фильмов", callback_data="search_movies"),
        InlineKeyboardButton("История поиска", callback_data="view_history"),
    )
    return markup

def get_search_keyboard():
    """Клава для вида поиска"""
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("По названию", callback_data="by_title"),
        InlineKeyboardButton("По рейтингу", callback_data="by_rating"),
        InlineKeyboardButton("Низкобюджетные", callback_data="low_budget"),
        InlineKeyboardButton("Высокобюджетные", callback_data="high_budget")
    )
    return markup

def get_genres_keyboard():
    """Добавляет клавиатуру для выбора жанра"""
    genres = ["боевик", "комедия", "драма", "ужасы", "фантастика", "триллер"]
    markup = InlineKeyboardMarkup(row_width=2)  # определяет количество кнопок в одной строке клавиатуры
    # Создаем кнопки для каждого жанра
    buttons = [InlineKeyboardButton(genre, callback_data=f"genre_{genres}") for genre in genres]
    markup.add(*buttons)
    markup.add(InlineKeyboardButton("Пропустить", callback_data="genre_skip"))
    return markup

def get_limit_keyboard():
    """Добавляет клавиатуру для выбора количества результатов"""
    markup = InlineKeyboardMarkup(row_width=5)
    # Кнопки от 1 до 10
    buttons = [InlineKeyboardButton(str(i), callback_data=f"limit_{i}") for i in range(1, 11)]
    markup.add(*buttons)
    return markup

def get_movie_action_markup(movie_id):
    """Создает кнопки действий для фильма"""
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("Просмотрено", callback_data=f"watched_{movie_id}"),
        InlineKeyboardButton("Не смотрел", callback_data=f"unwatched_{movie_id}"),
    )
    return markup

# --- ФОРМАТИРОВАНИЕ ---
def format_info_movie(movie):
    """Форматирует информацию о фильме для вывода в тг"""
    return (
        f"<b>{movie.get("name", "Без названия")}</b>\n"
        f"Год: {movie.get("year", "Неизвестно")}\n"
        f"Рейтинг: {movie.get('rating', {}).get('kp', 'нет')}\n"
        f"Жанры: {", ".join(g["name"] for g in movie.get("genres", []))}\n"
        f"Возрастной рейтинг: {movie.get("AgeRating", "Неизвестно")}+\n\n"
        f"Описание: {movie.get("descriptions", "Описание отсутствует")[:300]}..."
    )

# --- ОБРАБОТЧИКИ КОМАНД ---
@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    """Обработчик команды /start"""
    # Создаем или получаем пользователя из базы данных
    User.get_or_create(
        user_id=message.from_user.id,  # получаем если есть
        defaults={                     # если нет, то создаём
            'username': message.from_user.username,
            'full_name': message.from_user.full_name,
        }
    )
    # Отправляем приветственное сообщение
    bot.send_message(
        message.chat.id,
        "Добро пожаловать в бота для поиска фильмов и сериалов!\n"
        "Я помогу вам найти информацию о них.\n"
        "Выберите действие",
        reply_markup=get_main_menu()
    )

# ПОИСК ПО НАЗВАНИЮ
# @bot.callback_query_handler(func=lambda call: call.data == "search_movies")
