# -*- coding: utf-8 -*-
import random
import time
import logging
import asyncio  # Для асинхронных пауз
import os  # Для получения токена из переменных окружения

# --- Библиотека Telegram ---
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode  # Для форматирования текста (если понадобится)
from telegram.error import BadRequest  # Для обработки ошибок редактирования сообщений

# --- Настройка логирования ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# Уменьшим "болтливость" некоторых библиотек
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- Константы ---
TOKEN = ""
TIME_LIMIT = 600  # 10 минут

# ======================================================
# КЛАССЫ И ДАННЫЕ ИЗ ИГРЫ (Адаптировано из V2)
# ======================================================


class Player:
    def __init__(self):
        self.health = 100
        self.hunger = 0
        self.thirst = 0
        self.radiation = 0
        self.infection = 0
        self.inventory = []  # Будет хранить названия предметов (str)
        self.weapon = None  # Будет хранить название оружия (str) или None
        self.has_gasmask = False
        self.has_armor = False
        self.backpack_size = 5

    def is_alive(self):
        return (
            self.health > 0
            and self.infection < 100
            and self.radiation < 100
            and self.hunger < 100
            and self.thirst < 100
        )

    def inventory_limit(self):
        return self.backpack_size


# Предметы (словари удобны для доступа по ключу)
items = {
    "water": {"name": "Бутылка воды", "usable": True},
    "food": {"name": "Питательный блок", "usable": True},
    "medkit": {"name": "Аптечка", "usable": True},
    "antivirus": {"name": "Антивирусный шприц", "usable": True},
    "gasmask": {"name": "Противогаз", "usable": False, "equipable": True},
    "ammo": {"name": "Патроны", "usable": False},
    "pistol": {"name": "Пистолет-плазматрон", "usable": False, "equipable": True},
    "armor": {"name": "Броня", "usable": False, "equipable": True},
    "big_backpack": {"name": "Большой рюкзак", "usable": False, "equipable": True},
    # "captain_keycard": {"name": "Ключ-карта капитана", "usable": False} # Если решите добавить
}

# Монстры (словарь для легкого доступа по ключу)
monsters_data = {
    "stalker": {
        "name": "Мутант-сталкер",
        "health": 50,
        "full_health": 50,
        "damage": 15,
        "desc": "Вдруг из вентиляционной шахты выползает существо — пародия на человека, его кожа чёрная и покрыта язвами.",
        "loot": ["ammo"],  # Ключ предмета
    },
    "horror": {
        "name": "Раздутый ужас",
        "health": 80,
        "full_health": 80,
        "damage": 25,
        "desc": "Из тьмы на вас идет огромная колышащаяся масса в обрывках летного костюма.",
        "loot": ["antivirus"],  # Ключ предмета
    },
    "captain": {
        "name": "Зомби-капитан",
        "health": 120,
        "full_health": 120,
        "damage": 30,
        "desc": "У штурвала стоит фигура в истлевшей капитанской форме. Она поворачивается, и пустые глазницы устремляются на вас.",
        "is_boss": True,  # Флаг босса
        "loot": [],  # Можно добавить ключ-карту, если нужна: ["captain_keycard"]
    },
}

# Локации
locations = {
    "medbay": "Медицинский отсек",
    "engineering": "Инженерный цех",
    "quarters": "Жилые отсеки",
    "reactor": "Реакторный блок",
    "laboratory": "Главная лаборатория",
    "bridge": "Мостик корабля",
}

# ======================================================
# УПРАВЛЕНИЕ СОСТОЯНИЕМ ИГРЫ ДЛЯ БОТА
# ======================================================

# Словарь для хранения состояния игры каждого пользователя
# Ключ: chat_id, Значение: словарь с состоянием
game_states = {}


def get_user_state(chat_id: int) -> dict:
    """Получает или инициализирует состояние игры для пользователя."""
    if chat_id not in game_states:
        game_states[chat_id] = {
            "player": Player(),
            "current_location_key": None,  # Начинаем вне локации
            "captain_defeated": False,
            "bridge_puzzle_attempted": False,  # Пытался ли решить загадку
            "puzzle_code": None,  # Будет генерироваться при входе на мостик
            "start_time": time.time(),
            "last_action_time": time.time(),
            "current_monster": None,  # Данные текущего монстра в бою {ключ: данные_копия}
            "expected_input": None,  # Что бот ожидает ('location', 'fight', 'item', 'puzzle_code', None)
            "last_message_id": None,  # ID последнего сообщения с кнопками для редактирования
        }
    # Обновляем время последнего действия при каждом доступе (можно убрать, если не нужно)
    # game_states[chat_id]['last_action_time'] = time.time()
    return game_states[chat_id]


def reset_user_state(chat_id: int):
    """Сбрасывает состояние для начала новой игры."""
    if chat_id in game_states:
        del game_states[chat_id]
    # Возвращаем новое, чистое состояние
    return get_user_state(chat_id)


def check_time_bot(user_state: dict) -> bool:
    """Проверяет время игры для бота."""
    elapsed_time = time.time() - user_state["start_time"]
    return elapsed_time <= TIME_LIMIT


def get_time_warning(user_state: dict) -> str | None:
    """Возвращает предупреждение о времени, если осталось мало."""
    elapsed_time = time.time() - user_state["start_time"]
    remaining_time = TIME_LIMIT - elapsed_time
    if 0 < remaining_time < 60:
        return f"\n⏳ *Осталось меньше минуты!*"
    return None


# ======================================================
# АДАПТИРОВАННЫЕ ИГРОВЫЕ ФУНКЦИИ (из V2)
# ======================================================


def get_status_text(player: Player) -> str:
    """Возвращает текстовое представление статуса игрока."""
    status = (
        f"❤️ Здоровье: {player.health}% 💧 Жажда: {player.thirst}% | 🍞 Голод: {player.hunger}%\n"
        f"☢️ Радиация: {player.radiation}% | ☣️ Инфекция: {player.infection}%"
    )
    inventory_items = [
        items[key]["name"] for key in player.inventory
    ]  # Получаем имена по ключам
    inventory_str = ", ".join(inventory_items) if inventory_items else "Пусто"
    inventory = f"🎒 Инвентарь ({len(player.inventory)}/{player.inventory_limit()}): {inventory_str}"

    equipped = []
    if player.weapon:
        equipped.append(player.weapon)  # Храним имя оружия
    if player.has_armor:
        equipped.append(items["armor"]["name"])
    if player.has_gasmask:
        equipped.append(items["gasmask"]["name"])
    equipment = f"🔧 Экипировка: {', '.join(equipped)}" if equipped else ""

    return f"{status}\n{inventory}\n{equipment}"


def progress_status_bot(user_state: dict) -> list[str]:
    """Обновляет статус игрока и возвращает список сообщений об изменениях (из V2)."""
    player = user_state["player"]
    messages = []

    # Базовые потребности
    hunger_increase = random.randint(4, 7)
    thirst_increase = random.randint(5, 8)
    player.hunger = min(player.hunger + hunger_increase, 100)
    player.thirst = min(player.thirst + thirst_increase, 100)

    if player.hunger >= 80 and player.hunger < 100:
        messages.append("Вы чувствуете сильный голод...")
    if player.thirst >= 80 and player.thirst < 100:
        messages.append("Вас мучает сильная жажда...")
    if player.hunger >= 100:
        messages.append("Истощение от голода отнимает силы!")
        player.health -= 15
    if player.thirst >= 100:
        messages.append("Обезвоживание отнимает силы!")
        player.health -= 15

    # Окружение
    if not player.has_gasmask:
        toxic_air_effect = random.randint(3, 6)
        player.infection = min(player.infection + toxic_air_effect, 100)
        messages.append(f"Вы дышите токсичным воздухом (+{toxic_air_effect}% ☣️).")
        if player.infection >= 100:
            messages.append("Инфекция полностью захватила ваш организм!")
            player.health = 0  # Мгновенная смерть от инфекции

    rad_increase = random.randint(0, 4)
    if rad_increase > 0:
        player.radiation = min(player.radiation + rad_increase, 100)
        messages.append(f"Уровень радиации немного повысился (+{rad_increase}% ☢️).")
        if player.radiation >= 100:
            messages.append("Вы получили смертельную дозу радиации!")
            player.health = 0  # Мгновенная смерть от радиации

    player.health = max(0, player.health)  # Убедимся, что здоровье не ушло в минус
    return messages


def search_area_bot(user_state: dict, location_key: str) -> list[str]:
    """Обыскивает локацию, возвращает список сообщений (логика из V2)."""
    player = user_state["player"]
    location_name = locations.get(location_key, "Неизвестная локация")

    messages = [f"Вы обыскиваете локацию '{location_name}'..."]
    found_count = 0

    for _ in range(2):  # Две попытки поиска
        if random.randint(1, 100) <= 60:  # 60% шанс найти что-то за попытку
            possible_items_keys = list(items.keys())
            weights = [1.0] * len(possible_items_keys)  # Используем float для весов

            # Уменьшаем шанс найти экипировку, если она уже есть или не нужна
            for i, item_key in enumerate(possible_items_keys):
                is_equip = items[item_key].get("equipable", False)
                already_have = (
                    (item_key == "pistol" and player.weapon)
                    or (item_key == "gasmask" and player.has_gasmask)
                    or (item_key == "armor" and player.has_armor)
                    or (item_key == "big_backpack" and player.backpack_size > 5)
                )
                if is_equip and already_have:
                    weights[i] = 0.1  # Сильно режем шанс дубликата
                elif is_equip:
                    weights[i] = 0.5  # Режем шанс найти уникальный предмет в целом
                elif item_key == "ammo" and not player.weapon:
                    weights[i] = 0.2  # Меньше шанс найти патроны без оружия

            # Нормализуем веса, чтобы избежать ошибки, если все веса нулевые
            total_weight = sum(weights)
            if total_weight <= 0:
                continue  # Нечего выбирать

            found_item_key = random.choices(possible_items_keys, weights=weights, k=1)[
                0
            ]
            item_info = items[found_item_key]
            item_name = item_info["name"]

            # --- Обработка найденного ---
            if found_item_key == "gasmask":
                if not player.has_gasmask:
                    player.has_gasmask = True
                    messages.append(f"✅ Найдено и надето: {item_name}")
                    found_count += 1
            elif found_item_key == "armor":
                if not player.has_armor:
                    player.has_armor = True
                    messages.append(f"✅ Найдено и надето: {item_name}")
                    found_count += 1
            elif found_item_key == "big_backpack":
                if player.backpack_size == 5:
                    player.backpack_size = 10
                    messages.append(
                        f"✅ Найден {item_name}! Инвентарь увеличен до {player.backpack_size}."
                    )
                    found_count += 1
            elif found_item_key == "pistol":
                if not player.weapon:
                    player.weapon = item_name  # Сохраняем имя оружия
                    messages.append(f"🔫 Найдено оружие: {item_name}!")
                    # Дать патроны
                    if len(player.inventory) < player.inventory_limit():
                        player.inventory.append("ammo")  # Добавляем ключ патронов
                        messages.append("⚡️ В комплекте были патроны.")
                    found_count += 1
            else:  # Обычные предметы (вода, еда, аптечка, антивирус, патроны)
                if len(player.inventory) < player.inventory_limit():
                    player.inventory.append(found_item_key)  # Добавляем ключ предмета
                    messages.append(f"➕ Найдено: {item_name}")
                    found_count += 1
                else:
                    messages.append(f"⚠️ Найден {item_name}, но в рюкзаке нет места!")

    if found_count == 0:
        messages.append("Ничего ценного найти не удалось.")
    return messages


def get_random_monster_key() -> str | None:
    """Возвращает ключ случайного монстра (не босса)."""
    available_monsters = [k for k, v in monsters_data.items() if not v.get("is_boss")]
    if not available_monsters:
        return None
    return random.choice(available_monsters)


def get_monster_status_text(monster_health: int, monster_full_health: int) -> str:
    """Возвращает текстовое описание состояния монстра."""
    share = monster_health / monster_full_health if monster_full_health > 0 else 0
    if share <= 0:
        return "мёртв"
    if share <= 0.25:
        return "практически мёртв"
    if share <= 0.5:
        return "слаб"
    if share <= 0.75:
        return "ранен"
    return "здоров"


# ======================================================
# ФУНКЦИИ ДЛЯ ГЕНЕРАЦИИ КЛАВИАТУР
# ======================================================


def build_main_keyboard(user_state: dict) -> InlineKeyboardMarkup:
    """Создает клавиатуру с выбором локаций и действием 'Использовать предмет'."""
    player = user_state["player"]
    keyboard = []
    # Кнопки локаций
    for key, name in locations.items():
        button_text = name
        callback_data = f"loc_{key}"
        if key == "bridge":
            if not user_state["captain_defeated"]:
                button_text += " (Прегражден!)"
            elif not user_state["bridge_puzzle_attempted"]:
                button_text += " (Свободен)"
            else:  # Капитан побежден, попытка была
                button_text += " (Заблокирован)"
                # Можно сделать кнопку неактивной или дать инфо-колбэк
                # callback_data = "info_bridge_locked"

        keyboard.append(
            [InlineKeyboardButton(button_text, callback_data=callback_data)]
        )

    # Кнопка инвентаря
    if player.inventory:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "🎒 Использовать предмет", callback_data="inventory_open"
                )
            ]
        )
    else:
        # Можно сделать кнопку неактивной или информативной
        keyboard.append(
            [
                InlineKeyboardButton(
                    "🎒 Инвентарь пуст", callback_data="info_inventory_empty"
                )
            ]
        )

    return InlineKeyboardMarkup(keyboard)


def build_inventory_keyboard(player: Player) -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора предмета из инвентаря."""
    keyboard = []
    if not player.inventory:
        keyboard.append(
            [InlineKeyboardButton("Инвентарь пуст", callback_data="inventory_close")]
        )
    else:
        # Группируем предметы для удобства
        item_counts = {}
        for item_key in player.inventory:
            item_counts[item_key] = item_counts.get(item_key, 0) + 1

        # Создаем кнопки для каждого типа предмета
        item_keys_in_inventory = sorted(item_counts.keys())  # Сортируем для порядка
        for item_key in item_keys_in_inventory:
            item_info = items[item_key]
            item_name = item_info["name"]
            count = item_counts[item_key]
            button_text = f"{item_name} x{count}"

            if item_info.get("usable", False):
                # Передаем ключ предмета для использования
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            f"Использовать: {button_text}",
                            callback_data=f"item_use_{item_key}",
                        )
                    ]
                )
            else:
                # Показываем, но сделать неактивной или информативной
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            f"{button_text} (Пассивный)",
                            callback_data=f"info_item_passive_{item_key}",
                        )
                    ]
                )

        keyboard.append(
            [
                InlineKeyboardButton(
                    "❌ Закрыть инвентарь", callback_data="inventory_close"
                )
            ]
        )
    return InlineKeyboardMarkup(keyboard)


def build_fight_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для боя."""
    keyboard = [
        [
            InlineKeyboardButton("⚔️ Атаковать", callback_data="fight_attack"),
            InlineKeyboardButton("🏃 Убежать", callback_data="fight_flee"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


# ======================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ОБРАБОТЧИКОВ
# ======================================================


async def send_image(
    update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int, image_path: str
):
    """Отправляет изображение пользователю."""
    try:
        base_path = "SpaceStationSurvival\\images\\"  # Путь к папке с изображениями
        with open(base_path + image_path, "rb") as image_file:
            await context.bot.send_photo(chat_id=chat_id, photo=image_file)
    except Exception as e:
        logger.error(f"Error sending image to {chat_id}: {e}")


async def edit_or_send_message(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    message_id: int | None = None,
):
    """Пытается отредактировать сообщение, если не получается - отправляет новое."""
    new_message_id = None
    message_id = None
    if message_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN,  # Используем Markdown для *предупреждений*
            )
            new_message_id = message_id
        except BadRequest as e:
            if "Message is not modified" in str(e):
                # Сообщение не изменилось, ничего страшного
                new_message_id = message_id
                pass
            elif "message to edit not found" in str(e):
                logger.warning(
                    f"Message {message_id} to edit not found for chat {chat_id}. Sending new one."
                )
                message_id = None  # Сбрасываем ID, чтобы отправить новое
            else:
                logger.error(
                    f"Failed to edit message {message_id} for chat {chat_id}: {e}"
                )
                message_id = None  # Сбрасываем ID, чтобы отправить новое
        except Exception as e:
            logger.error(
                f"Unexpected error editing message {message_id} for chat {chat_id}: {e}"
            )
            message_id = None  # Сбрасываем ID, чтобы отправить новое

    if not message_id:  # Если редактирование не удалось или не было ID
        sent_message = await context.bot.send_message(
            chat_id, text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
        )
        new_message_id = sent_message.message_id

    return new_message_id


async def show_main_screen(
    update: Update | None,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_to_edit_id: int | None = None,
    extra_messages: list[str] | None = None,
):
    """
    Отображает основной экран: статус, доп. сообщения и выбор локации/предмета.
    Обновляет user_state['last_message_id'].
    """
    user_state = get_user_state(chat_id)
    player = user_state["player"]

    # 0. Проверка условий конца игры ПЕРЕД отображением
    if not player.is_alive():
        await send_game_over(update, context, chat_id, "player_dead")
        return
    if not check_time_bot(user_state):
        await send_game_over(update, context, chat_id, "time_out")
        return

    # 1. Формируем текст сообщения
    status_text = get_status_text(player)
    time_warning = get_time_warning(user_state)
    message_lines = []
    if extra_messages:
        message_lines.extend(extra_messages)
        message_lines.append("-" * 20)  # Разделитель
    message_lines.append(status_text)
    if time_warning:
        message_lines.append(time_warning)
    message_lines.append("\nКуда отправиться?")

    message_text = "\n".join(message_lines)

    # 2. Генерируем клавиатуру
    keyboard = build_main_keyboard(user_state)
    user_state["expected_input"] = "location"  # Ожидаем выбор локации или инвентаря

    # 3. Отправляем или редактируем сообщение
    new_message_id = await edit_or_send_message(
        context, chat_id, message_text, keyboard, message_to_edit_id
    )
    user_state["last_message_id"] = new_message_id


# ======================================================
# ОБРАБОТЧИКИ КОМАНД И КОЛБЭКОВ TELEGRAM
# ======================================================


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start. Начинает новую игру."""
    chat_id = update.effective_chat.id
    logger.info(f"User {chat_id} started the game.")
    user_state = reset_user_state(chat_id)  # Сброс и инициализация

    welcome_text = (
        "=== Добро пожаловать на станцию 'Гелиос-9' ===\n\n"
        "Тьма.\n"
        "Ты приходишь в себя в аварийной капсуле. В ушах звенит.\n"
        "На языке металлический привкус. С трудом открываешь глаза —\n"
        "аварийные огни мигают красным. Станция 'Гелиос-9' лежит в агонии.\n"
        "Твои лёгкие сжимаются от зловонного, тяжёлого воздуха.\n"
        "Где-то вдалеке слышатся странные звуки — отдалённые стоны\n"
        "или скрежет когтей по металлу...\n\n"
        "*Твоя цель - выжить и найти способ сбежать.*"
    )
    current_directory = os.getcwd()
    print(f"Текущая рабочая папка: {current_directory}")
    await send_image(update, context, chat_id, "locations/hall.jpeg")
    # Отправляем приветствие как отдельное сообщение
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)
    # Сразу показываем основной экран
    await show_main_screen(update, context, chat_id)


async def handle_location_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int, loc_key: str
):
    """Обрабатывает выбор локации."""
    user_state = get_user_state(chat_id)
    player = user_state["player"]
    loc_name = locations.get(loc_key, "Неизвестно")
    message_id_to_edit = user_state.get("last_message_id")

    turn_messages = []  # Сообщения за этот ход

    # --- Особая логика для Мостика ---
    if loc_key == "bridge":
        if not user_state["captain_defeated"]:
            turn_messages.append(
                f"Вы пытаетесь пройти на '{loc_name}', но путь преграждает..."
            )
            # Начинаем бой с капитаном
            captain_data = monsters_data["captain"].copy()  # Берем копию
            user_state["current_monster"] = {
                "key": "captain",
                "data": captain_data,
            }  # Сохраняем ключ и данные
            user_state["expected_input"] = "fight"
            await send_image(update, context, chat_id, "monsters/captain.jpeg")
            monster_status_text = (
                f"{captain_data['desc']}\n\n*На вас нападает {captain_data['name']}!*"
            )
            fight_keyboard = build_fight_keyboard()
            # Показываем описание монстра и статус игрока перед боем
            status_now = get_status_text(player)
            new_msg_id = await edit_or_send_message(
                context,
                chat_id,
                f"{monster_status_text}\n\n{status_now}",
                fight_keyboard,
                message_id_to_edit,
            )
            user_state["last_message_id"] = new_msg_id
            return  # Выходим, ждем действия в бою

        elif not user_state["bridge_puzzle_attempted"]:
            turn_messages.append(f"Вы входите на '{loc_name}'. Путь свободен.")
            # Начинаем загадку
            await start_bridge_puzzle(
                update, context, chat_id, message_id_to_edit, turn_messages
            )
            return  # Выходим, ждем ввода кода
        else:  # Капитан побежден, попытка была
            turn_messages.append(
                f"Вы снова на '{loc_name}'. Терминал самоуничтожения заблокирован."
            )
            # Просто показываем сообщение и возвращаем на главный экран
            await show_main_screen(
                update, context, chat_id, message_id_to_edit, turn_messages
            )
            return

    # --- Обычные локации ---
    else:
        user_state["current_location_key"] = loc_key
        # turn_messages.append(f"Вы направились в '{loc_name}'.")

        # 1. Обыск локации
        await send_image(update, context, chat_id, "locations/" + loc_key + ".jpeg")
        search_results = search_area_bot(user_state, loc_key)
        turn_messages.extend(search_results)

        # Промежуточное отображение результатов поиска (без кнопок)
        # temp_msg_id = await edit_or_send_message(
        #    context, chat_id, "\n".join(turn_messages), None, message_id_to_edit
        # )
        # user_state["last_message_id"] = temp_msg_id  # Обновляем ID
        # await asyncio.sleep(2)  # Пауза для чтения

        if not player.is_alive():  # Проверка после обыска
            await send_game_over(update, context, chat_id, "player_dead")
            return

        # 2. Случайная встреча
        encounter_chance = 40  # 40%
        if random.randint(1, 100) <= encounter_chance:
            monster_key = get_random_monster_key()
            if monster_key:
                monster_data = monsters_data[monster_key].copy()
                await send_image(
                    update, context, chat_id, "monsters/" + monster_key + ".jpeg"
                )
                user_state["current_monster"] = {
                    "key": monster_key,
                    "data": monster_data,
                }
                user_state["expected_input"] = "fight"
                monster_status_text = f"{monster_data['desc']}\n\n*На вас нападает {monster_data['name']}!*"
                fight_keyboard = build_fight_keyboard()
                # Обновляем сообщение, начиная бой
                status_now = get_status_text(player)
                new_msg_id = await edit_or_send_message(
                    context,
                    chat_id,
                    f"{monster_status_text}\n\n{status_now}",
                    fight_keyboard,
                    user_state["last_message_id"],  # Используем обновленный ID
                )
                user_state["last_message_id"] = new_msg_id
                return  # Выходим, ждем действия в бою
            else:
                turn_messages.append("Вы слышите странные звуки, но никого не видите.")
        else:
            turn_messages.append("В локации тихо.")

        # 3. Прогресс статуса (если не было боя)
        progress_msgs = progress_status_bot(user_state)
        if progress_msgs:
            turn_messages.append("-" * 20)  # Разделитель
            turn_messages.extend(progress_msgs)

        # Финальная отправка сообщений за ход и возврат на главный экран
        await show_main_screen(
            update, context, chat_id, user_state["last_message_id"], turn_messages
        )


async def handle_fight_action(
    update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int, action: str
):
    """Обрабатывает действие игрока в бою (атака или побег)."""
    user_state = get_user_state(chat_id)
    player = user_state["player"]
    monster_info = user_state.get("current_monster")
    message_id_to_edit = user_state.get("last_message_id")

    if not monster_info or user_state.get("expected_input") != "fight":
        logger.warning(f"Unexpected fight action from {chat_id} when not in fight.")
        await show_main_screen(
            update,
            context,
            chat_id,
            message_id_to_edit,
            ["Произошла ошибка состояния боя."],
        )
        return

    monster_key = monster_info["key"]
    monster = monster_info["data"]  # Работаем с копией данных монстра
    monster_name = monster["name"]
    monster_full_health = monster["full_health"]

    fight_log = []  # Лог событий боя за этот раунд

    if action == "attack":
        # Атака игрока
        player_damage = 0
        if player.weapon == items["pistol"]["name"]:
            try:
                # Ищем ключ "ammo" в инвентаре
                ammo_index = player.inventory.index("ammo")
                player.inventory.pop(ammo_index)  # Тратим один патрон (ключ)
                player_damage = random.randint(25, 40)
                fight_log.append(
                    f"💥 Вы стреляете из плазматрона! (-1 {items['ammo']['name']})"
                )
            except ValueError:
                player_damage = random.randint(5, 10)
                fight_log.append("⚠️ Нет патронов! Вы бьете кулаками!")
        else:  # Рукопашная
            player_damage = random.randint(5, 10)
            fight_log.append("👊 Вы бьете кулаками!")

        monster["health"] -= player_damage
        monster["health"] = max(0, monster["health"])  # Не уходим в минус
        monster_status_text = get_monster_status_text(
            monster["health"], monster_full_health
        )
        fight_log.append(
            f"Вы нанесли {player_damage} урона. Монстр {monster_status_text}"
        )

        if monster["health"] <= 0:
            # Монстр побежден
            fight_log.append(f"\n🏆 *Вы победили {monster_name}!*")
            # --- Лут ---
            # Используем данные из оригинального monsters_data по ключу
            original_monster_data = monsters_data.get(monster_key, {})
            if original_monster_data.get("loot"):
                for item_loot_key in original_monster_data["loot"]:
                    if len(player.inventory) < player.inventory_limit():
                        player.inventory.append(item_loot_key)  # Добавляем ключ лута
                        fight_log.append(f"✨ Вы нашли: {items[item_loot_key]['name']}")
                    else:
                        fight_log.append(
                            f"⚠️ Найден {items[item_loot_key]['name']}, но нет места!"
                        )

            # --- Особый случай: Капитан ---
            if monster.get("is_boss"):
                user_state["captain_defeated"] = True
                fight_log.append("\n*Путь на мостик свободен!*")
                # Сразу переходим к загадке
                await start_bridge_puzzle(
                    update, context, chat_id, message_id_to_edit, fight_log
                )
                user_state["current_monster"] = None  # Убираем монстра из состояния
                return

            # Обычный монстр побежден
            user_state["current_monster"] = None
            # Показываем лог победы и лута (без кнопок)
            temp_msg_id = await edit_or_send_message(
                context, chat_id, "\n".join(fight_log), None, message_id_to_edit
            )
            user_state["last_message_id"] = temp_msg_id
            await asyncio.sleep(2.5)

            # Прогресс статуса после боя
            progress_msgs = progress_status_bot(user_state)
            await show_main_screen(
                update, context, chat_id, user_state["last_message_id"], progress_msgs
            )
            return

    elif action == "flee":
        escape_chance = 60
        if random.randint(1, 100) <= escape_chance:
            fight_log.append("Вы успешно сбежали!")
            await send_image(update, context, chat_id, "locations/hall.jpeg")
            user_state["current_monster"] = None
            # Показываем сообщение о побеге (без кнопок)
            temp_msg_id = await edit_or_send_message(
                context, chat_id, "\n".join(fight_log), None, message_id_to_edit
            )
            user_state["last_message_id"] = temp_msg_id
            await asyncio.sleep(1.5)
            # Прогресс статуса после побега
            progress_msgs = progress_status_bot(user_state)
            await show_main_screen(
                update, context, chat_id, user_state["last_message_id"], progress_msgs
            )
            return
        else:
            fight_log.append("Не удалось сбежать!")
            # Монстр атакует после неудачного побега

    # Атака монстра (если он жив и игрок не сбежал/не победил)
    if monster["health"] > 0:
        monster_damage = monster["damage"]
        if player.has_armor:
            reduction = 0.3
            absorbed = int(monster_damage * reduction)
            monster_damage -= absorbed
            fight_log.append(f"🛡️ Броня поглотила {absorbed} урона.")
        player.health -= monster_damage
        player.health = max(0, player.health)
        fight_log.append(f"🩸 {monster_name} наносит вам {monster_damage} урона!")

        if not player.is_alive():
            fight_log.append(f"Ваше здоровье: {player.health}%")
            # Показываем лог с последним ударом (без кнопок)
            temp_msg_id = await edit_or_send_message(
                context, chat_id, "\n".join(fight_log), None, message_id_to_edit
            )
            user_state["last_message_id"] = temp_msg_id
            await asyncio.sleep(1.5)
            await send_game_over(update, context, chat_id, "player_dead")
            return

    # Бой продолжается, обновляем сообщение
    status_text = get_status_text(player)
    fight_keyboard = build_fight_keyboard()
    monster_status_text = get_monster_status_text(
        monster["health"], monster_full_health
    )
    fight_message = (
        f"{monster_name} {monster_status_text}\n"
        f"{'-'*40}\n"
        f"{'\n'.join(fight_log)}\n"
        f"{'-'*40}\n"
        f"{status_text}"
    )
    new_msg_id = await edit_or_send_message(
        context, chat_id, fight_message, fight_keyboard, message_id_to_edit
    )
    user_state["last_message_id"] = new_msg_id


async def handle_inventory_action(
    update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int, callback_data: str
):
    """Обрабатывает действия в инвентаре (открытие, использование, закрытие, инфо)."""
    user_state = get_user_state(chat_id)
    player = user_state["player"]
    message_id_to_edit = user_state.get("last_message_id")
    query = update.callback_query  # Получаем объект query для ответа

    if callback_data == "inventory_open":
        # Проверяем, не в бою ли мы
        if user_state.get("expected_input") == "fight":
            await query.answer(
                "Нельзя открыть инвентарь во время боя!", show_alert=True
            )
            return

        inventory_keyboard = build_inventory_keyboard(player)
        # Редактируем только клавиатуру текущего сообщения
        try:
            await context.bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=message_id_to_edit,
                reply_markup=inventory_keyboard,
            )
            user_state["expected_input"] = "item"  # Ожидаем выбор предмета
        except BadRequest as e:
            if "Message is not modified" in str(e):
                pass  # Клавиатура уже такая
            else:
                logger.error(f"Error editing markup for inventory: {e}")
        except Exception as e:
            logger.error(f"Unexpected error editing markup for inventory: {e}")

    elif callback_data == "inventory_close":
        # Просто возвращаем главную клавиатуру (без доп. сообщений)
        await show_main_screen(update, context, chat_id, message_id_to_edit)

    elif callback_data.startswith("item_use_"):
        item_key_to_use = callback_data[len("item_use_") :]
        use_messages = []
        item_used_successfully = False

        if item_key_to_use in player.inventory:
            item_info = items[item_key_to_use]
            item_name = item_info["name"]

            if item_info.get("usable", False):
                player.inventory.remove(
                    item_key_to_use
                )  # Удаляем один экземпляр предмета
                use_messages.append(f"✅ Вы использовали: {item_name}.")
                item_used_successfully = True

                # Применяем эффекты
                if item_key_to_use == "water":
                    player.thirst = max(player.thirst - 40, 0)
                    use_messages.append("Жажда утолена.")
                elif item_key_to_use == "food":
                    player.hunger = max(player.hunger - 40, 0)
                    use_messages.append("Голод утолен.")
                elif item_key_to_use == "medkit":
                    player.health = min(player.health + 50, 100)
                    use_messages.append("Здоровье восстановлено.")
                elif item_key_to_use == "antivirus":
                    player.infection = max(player.infection - 60, 0)
                    use_messages.append("Распространение вируса замедлено.")
                # Добавить другие используемые предметы если нужно
            else:
                # Это не должно происходить, т.к. кнопка должна быть неактивной
                use_messages.append(f"⚠️ {item_name} нельзя использовать напрямую.")
                await query.answer(
                    f"{item_name} нельзя использовать напрямую.", show_alert=True
                )

        else:
            use_messages.append("⚠️ Ошибка: Предмет не найден в инвентаре.")
            await query.answer("Ошибка: Предмет не найден.", show_alert=True)

        # Показываем результат использования и возвращаемся на главный экран
        # Сначала покажем сообщение об использовании (без кнопок)
        temp_msg_id = await edit_or_send_message(
            context, chat_id, "\n".join(use_messages), None, message_id_to_edit
        )
        user_state["last_message_id"] = temp_msg_id
        await asyncio.sleep(1.5)

        # Если предмет был успешно использован, применяем прогресс статуса
        progress_msgs = []
        if item_used_successfully:
            progress_msgs = progress_status_bot(user_state)

        # Возвращаемся на главный экран с результатами прогресса (если были)
        await show_main_screen(
            update, context, chat_id, user_state["last_message_id"], progress_msgs
        )

    # Обработка информационных кнопок (нажатие на них не должно менять основной экран)
    elif callback_data.startswith("info_"):
        if "inventory_empty" in callback_data:
            await query.answer(
                "Ваш инвентарь пуст.", show_alert=False
            )  # Можно и не показывать alert
        elif "item_passive" in callback_data:
            item_key = callback_data[len("info_item_passive_") :]
            item_name = items.get(item_key, {}).get("name", "Этот предмет")
            if item_key == "ammo":
                await query.answer(
                    f"{item_name} используются автоматически при стрельбе.",
                    show_alert=True,
                )
            elif items.get(item_key, {}).get("equipable"):
                await query.answer(
                    f"{item_name} экипируется автоматически при нахождении.",
                    show_alert=True,
                )
            else:
                await query.answer(
                    f"{item_name} нельзя использовать напрямую.", show_alert=True
                )
        elif "bridge_locked" in callback_data:
            await query.answer(
                "Терминал мостика заблокирован после неудачной попытки.",
                show_alert=True,
            )
        # Добавить другие info кнопки если нужно


async def start_bridge_puzzle(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id_to_edit: int,
    intro_messages: list[str] | None = None,
):
    """Начинает загадку на мостике."""
    user_state = get_user_state(chat_id)
    user_state["expected_input"] = "puzzle_code"
    # Генерируем код только один раз при первой попытке входа на мостик после победы над капитаном
    if user_state.get("puzzle_code") is None:
        user_state["puzzle_code"] = str(random.randint(1000, 9999))
        logger.info(
            f"Generated puzzle code for {chat_id}: {user_state['puzzle_code']}"
        )  # Логируем код для отладки

    puzzle_intro = [
        "Вы подходите к главному терминалу мостика.",
        "На экране мерцает запрос кода доступа.",
    ]
    if intro_messages:
        puzzle_intro = intro_messages + ["-" * 20] + puzzle_intro

    puzzle_text = "\n".join(puzzle_intro) + "\n\n*Введите 4-значный код [3 попытки]:*"

    # Убираем клавиатуру, ждем текстового ввода
    new_msg_id = await edit_or_send_message(
        context, chat_id, puzzle_text, None, message_id_to_edit
    )
    user_state["last_message_id"] = new_msg_id


async def handle_puzzle_input(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Обрабатывает ввод кода для загадки."""
    chat_id = update.effective_chat.id
    user_state = get_user_state(chat_id)
    # ID сообщения с запросом кода должен быть уже в user_state['last_message_id']
    message_id_to_edit = user_state.get("last_message_id")

    if user_state.get("expected_input") != "puzzle_code":
        # Игнорируем текст, если не ожидаем код
        # Можно отправить вежливое сообщение типа "Я не понимаю эту команду сейчас."
        # await update.message.reply_text("Сейчас я ожидаю код доступа или команду /start.")
        return

    # Удаляем сообщение пользователя с кодом для чистоты чата
    try:
        await context.bot.delete_message(chat_id, update.message.message_id)
    except Exception as e:
        logger.warning(f"Could not delete user puzzle input message: {e}")

    attempt = update.message.text.strip()
    result_message = ""
    puzzle_solved = False
    puzzle_failed = False

    # Получаем код из состояния (он должен быть сгенерирован в start_bridge_puzzle)
    correct_code = user_state.get("puzzle_code")
    if not correct_code:
        logger.error(f"Puzzle code not found in state for chat {chat_id}!")
        await context.bot.send_message(
            chat_id,
            "Произошла внутренняя ошибка с кодом доступа. Попробуйте вернуться сюда позже.",
        )
        user_state["expected_input"] = None  # Сбрасываем ожидание
        await asyncio.sleep(2)
        await show_main_screen(update, context, chat_id, message_id_to_edit)
        return

    # Счетчик попыток теперь внутри состояния не нужен, т.к. мы даем 3 попытки на сессию ввода
    # Вместо этого используем флаг bridge_puzzle_attempted

    if not attempt.isdigit() or len(attempt) != 4:
        result_message = (
            "⚠️ Ошибка ввода. Код должен состоять из 4 цифр.\nПопробуйте еще раз:"
        )
        # Не меняем состояние, просто просим ввести снова
    else:
        if attempt == correct_code:
            result_message = (
                "✅ *КОД ПРИНЯТ*\n"
                "Система самоуничтожения активирована! Сирены взвыли!\n"
                "У вас есть немного времени, чтобы добраться до спасательной капсулы!"
            )
            puzzle_solved = True
            # Не отмечаем bridge_puzzle_attempted = True при успехе
        else:
            result_message = "❌ *ДОСТУП ОТКЛОНЕН*\n"
            # Дадим подсказку (больше/меньше)
            if int(attempt) < int(correct_code):
                result_message += "Подсказка: Загаданный код больше.\n"
            else:
                result_message += "Подсказка: Загаданный код меньше.\n"

            # Считаем, что одна неудачная попытка ввода блокирует терминал
            result_message += "\n*Терминал блокируется!*"
            puzzle_failed = True
            user_state["bridge_puzzle_attempted"] = True  # Отмечаем неудачу

    # Показываем результат
    # Редактируем сообщение с запросом кода, добавляя результат
    new_msg_id = await edit_or_send_message(
        context, chat_id, result_message, None, message_id_to_edit
    )
    user_state["last_message_id"] = new_msg_id
    await asyncio.sleep(2.5)  # Даем время прочитать результат

    if puzzle_solved:
        await send_game_over(update, context, chat_id, "win_bridge")
    elif puzzle_failed:
        user_state["expected_input"] = None  # Больше не ждем код
        await show_main_screen(
            update,
            context,
            chat_id,
            user_state["last_message_id"],
            ["Вы не смогли взломать терминал."],
        )  # Возврат на главный экран
    else:  # Ошибка ввода (не цифры или не та длина)
        # Повторно запрашиваем ввод, редактируя сообщение с ошибкой
        puzzle_intro = [
            "Вы подходите к главному терминалу мостика.",
            "На экране мерцает запрос кода доступа.",
        ]
        puzzle_text = (
            "\n".join(puzzle_intro) + f"\n\n{result_message}"
        )  # Добавляем сообщение об ошибке
        new_msg_id = await edit_or_send_message(
            context, chat_id, puzzle_text, None, user_state["last_message_id"]
        )
        user_state["last_message_id"] = new_msg_id
        # user_state['expected_input'] остается 'puzzle_code'


async def callback_query_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Основной обработчик нажатий на Inline-кнопки."""
    query = update.callback_query
    # Отвечаем на колбэк как можно скорее, чтобы кнопка перестала "грузиться"
    # Ответ можно дать позже, если нужно показать alert
    # await query.answer() # Убрал немедленный ответ, т.к. он может быть в handle_inventory_action

    chat_id = query.message.chat_id
    callback_data = query.data
    user_state = get_user_state(chat_id)  # Получаем текущее состояние

    logger.info(
        f"Callback from {chat_id}: {callback_data} | Expected: {user_state.get('expected_input')}"
    )

    # Проверка на ожидаемый ввод
    current_expected = user_state.get("expected_input")

    try:
        # --- Маршрутизация по типу callback_data ---
        if callback_data.startswith("loc_") and current_expected == "location":
            await query.answer()  # Отвечаем на колбэк
            loc_key = callback_data.split("_")[1]
            await handle_location_choice(update, context, chat_id, loc_key)

        elif callback_data.startswith("fight_") and current_expected == "fight":
            await query.answer()
            action = callback_data.split("_")[1]
            await handle_fight_action(update, context, chat_id, action)

        elif (
            callback_data.startswith("inventory_")
            or callback_data.startswith("item_use_")
            or callback_data.startswith("info_")
        ) and (current_expected == "location" or current_expected == "item"):
            # Разрешаем доступ к инвентарю с главного экрана или из него самого
            # Ответ на query будет внутри handle_inventory_action
            await handle_inventory_action(update, context, chat_id, callback_data)

        # elif callback_data.startswith("info_"): # Обработка прочих инфо-кнопок уже включена выше
        #      await handle_inventory_action(update, context, chat_id, callback_data)

        else:
            # Неожиданный колбэк для текущего состояния
            logger.warning(
                f"Unexpected callback '{callback_data}' for state '{current_expected}' from {chat_id}"
            )
            await query.answer(
                "Неверное действие для текущей ситуации.", show_alert=True
            )

    except Exception as e:
        logger.exception(
            f"Error processing callback '{callback_data}' for chat {chat_id}: {e}"
        )
        try:
            await query.answer(
                "Произошла ошибка при обработке действия.", show_alert=True
            )
        except Exception:  # Если даже ответ на колбэк не удался
            pass
        # Попытаемся вернуть пользователя на главный экран
        try:
            await show_main_screen(
                update,
                context,
                chat_id,
                user_state.get("last_message_id"),
                ["Произошла ошибка, возвращаю в главное меню."],
            )
        except Exception as final_e:
            logger.error(
                f"Failed to return user {chat_id} to main screen after error: {final_e}"
            )


async def send_game_over(
    update: Update | None, context: ContextTypes.DEFAULT_TYPE, chat_id: int, reason: str
):
    """Отправляет сообщение о конце игры и сбрасывает состояние."""
    user_state = game_states.get(chat_id)
    if not user_state:
        return  # Состояние уже сброшено или игра не начиналась

    player = user_state["player"]
    elapsed_time = int(time.time() - user_state["start_time"])
    final_message = "=== ИГРА ОКОНЧЕНА ===\n"

    if reason == "win_bridge":
        await send_image(update, context, chat_id, "status/win.jpeg")
        final_message += (
            "\nСирены воют! Таймер самоуничтожения запущен!\n"
            "Вы бежите к спасательной капсуле и в последнюю секунду стартуете...\n"
            "Станция 'Гелиос-9' взрывается позади вас яркой вспышкой!\n\n"
            "🎉 *ПОЗДРАВЛЯЕМ С ПОБЕДОЙ!* 🎉"
        )
    elif reason == "player_dead":
        await send_image(update, context, chat_id, "status/lose.jpeg")
        final_message += "\nВы не смогли выжить на станции 'Гелиос-9'.\n*Причина:* "
        if player.health <= 0:
            final_message += "Смертельные раны."
        elif player.hunger >= 100:
            final_message += "Смерть от голода."
        elif player.thirst >= 100:
            final_message += "Смерть от жажды."
        elif player.infection >= 100:
            final_message += "Инфекция захватила организм."
        elif player.radiation >= 100:
            final_message += "Смертельная доза радиации."
        else:
            final_message += "Неизвестна (возможно, комбинация факторов)."
        final_message += "\n\n💀 *КОНЕЦ ИГРЫ* 💀"
    elif reason == "time_out":
        final_message += (
            "\nВремя вышло! Системы жизнеобеспечения отказали окончательно.\n"
            "Вы не смогли найти способ спастись вовремя.\n\n"
            "💀 *КОНЕЦ ИГРЫ* 💀"
        )
    else:
        final_message += "\nИгра завершена по неизвестной причине."

    final_message += f"\n\n*Время выживания:* {elapsed_time} секунд."
    final_message += "\n\nЧтобы начать заново, введите /start"

    # Удаляем последнее сообщение с кнопками, если оно было
    last_msg_id = user_state.get("last_message_id")
    if last_msg_id:
        try:
            # Сначала убираем кнопки, потом отправляем финальное сообщение
            await context.bot.edit_message_reply_markup(
                chat_id, last_msg_id, reply_markup=None
            )
        except Exception:
            pass  # Игнорируем ошибки редактирования старого сообщения

    await context.bot.send_message(
        chat_id, final_message, parse_mode=ParseMode.MARKDOWN
    )

    # Сброс состояния пользователя
    if chat_id in game_states:
        del game_states[chat_id]
    logger.info(f"Game over for user {chat_id}. Reason: {reason}")


# ======================================================
# ОСНОВНАЯ ФУНКЦИЯ ЗАПУСКА БОТА
# ======================================================
def get_bot_token(token_file: str):
    try:
        # Открываем файл и читаем первую строку, убирая лишние пробелы/переносы строк
        with open(token_file, "r", encoding="utf-8") as f:
            return f.readline().strip()
        if not TOKEN:
            logger.error(
                f"Файл '{token_file}' найден, но он пуст или содержит только пробелы."
            )
            return None  # Убедимся, что TOKEN None, если он пустой
    except FileNotFoundError:
        logger.error(
            f"Файл с токеном '{token_file}' не найден. Пожалуйста, создайте его и поместите туда токен бота."
        )
    except Exception as e:
        logger.error(f"Произошла ошибка при чтении файла с токеном '{token_file}': {e}")
        return None


def main() -> None:
    """Запуск бота."""
    TOKEN = get_bot_token("SpaceStationSurvival\\bot_token")
    print(TOKEN)
    application = Application.builder().token(TOKEN).build()

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    # Можно добавить /help, /status (покажет текущий статус без хода) и т.д.

    # Обработчик нажатий на кнопки
    application.add_handler(CallbackQueryHandler(callback_query_handler))

    # Обработчик текстовых сообщений (для ввода кода загадки)
    # Он должен срабатывать только если мы ожидаем ввод кода
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_puzzle_input)
    )

    # Запуск бота
    logger.info("Starting bot...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )  # Явно указываем типы обновлений


if __name__ == "__main__":
    main()
