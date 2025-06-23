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
    telegram_id = IntegerField(unique=True)  # Уникальный ID пользователя в Telegram
    username = CharField(null=True)  # @username (может отсутствовать)
    full_name = CharField(null=True)  # Полное имя пользователя
    created_ad = DateTimeField(default=datetime.now)  # Дата регистрации

# Модель истории поисковых запросов
class SearchHistory(BaseModel):
    user = ForeignKeyField(User, backref="searches")  # Связь с пользователем
    content_type = CharField()  # Тип поиска (по названию, рейтингу и т.д.)
    query = TextField(null=True)  # Текст запроса (может быть пустым)
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

    def search_movie(self, title, limit=5):
        """Поиск фильмов по названию"""
        url = f"{self.BASE_URL}movie/search"
        params = {
            "limit": limit,  # Лимит результатов (по умолчанию 5)
            "query": title,  # Поисковый запрос
        }
        # Отправка GET-запроса к API
        response = requests.get(url, headers=self.headers, params=params)
        return response.json()  # Возвращаем ответ в формате JSON
