# -*- coding: utf-8 -*-
import random
import time
import logging
import asyncio # Для асинхронных пауз

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

# --- Настройка логирования ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Константы ---
TOKEN = "7739893547:AAFLu8HPySBvGWbuyQIbsgIzlpXslUg2hyU" # !!! ЗАМЕНИТЕ НА ВАШ ТОКЕН !!!
TIME_LIMIT = 600 # 10 минут

# ======================================================
# КЛАССЫ И ДАННЫЕ ИЗ ОРИГИНАЛЬНОЙ ИГРЫ (с небольшими адаптациями)
# ======================================================

class Player:
    # ... (Класс Player остается почти таким же) ...
    def __init__(self):
        self.health = 100
        self.hunger = 0
        self.thirst = 0
        self.radiation = 0
        self.infection = 0
        self.inventory = []
        self.weapon = None
        self.has_gasmask = False
        self.has_armor = False
        self.backpack_size = 5
        # Убраны флаги мостика, они будут в общем состоянии пользователя

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

# Предметы (можно сделать классы или оставить словари)
items = {
    "water": "Бутылка воды", "food": "Питательный блок", "medkit": "Аптечка",
    "antivirus": "Антивирусный шприц", "gasmask": "Противогаз", "ammo": "Патроны",
    "pistol": "Пистолет-плазматрон", "armor": "Броня", "big_backpack": "Большой рюкзак",
}

# Монстры
monsters_data = { # Используем словарь для легкого доступа по имени
    "stalker": {
        "name": "Мутант-сталкер", "health": 50, "full_health": 50, "damage": 15,
        "desc": "Вдруг из вентиляционной шахты выползает существо...",
        "loot": ["ammo"] # Пример лута
    },
    "horror": {
        "name": "Раздутый ужас", "health": 80, "full_health": 80, "damage": 25,
        "desc": "Из тьмы на вас идет огромная колышащаяся масса...",
        "loot": ["antivirus"]
    },
    "captain": {
        "name": "Зомби-капитан", "health": 120, "full_health": 120, "damage": 30,
        "desc": "У штурвала стоит фигура в истлевшей капитанской форме...",
        "is_boss": True, # Флаг босса
        "loot": [] # Можно добавить ключ-карту, если нужна
    },
}

# Локации
locations = {
    "medbay": "Медицинский отсек", "engineering": "Инженерный цех",
    "quarters": "Жилые отсеки", "reactor": "Реакторный блок",
    "laboratory": "Главная лаборатория", "bridge": "Мостик корабля"
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
            'player': Player(),
            'current_location_key': None, # Начинаем вне локации
            'captain_defeated': False,
            'bridge_puzzle_attempted': False,
            'puzzle_attempts_left': 3,
            'puzzle_code': None, # Будет генерироваться при входе на мостик
            'start_time': time.time(),
            'last_action_time': time.time(),
            'current_monster': None, # Данные текущего монстра в бою
            'expected_input': None, # Что бот ожидает ('location', 'fight', 'item', 'puzzle_code')
            'last_message_id': None, # ID последнего сообщения с кнопками для редактирования
        }
    # Обновляем время последнего действия при каждом доступе
    game_states[chat_id]['last_action_time'] = time.time()
    return game_states[chat_id]

def reset_user_state(chat_id: int):
    """Сбрасывает состояние для начала новой игры."""
    if chat_id in game_states:
        del game_states[chat_id]
    return get_user_state(chat_id) # Создаем новое чистое состояние

def check_time_bot(user_state: dict) -> bool:
    """Проверяет время игры для бота."""
    elapsed_time = time.time() - user_state['start_time']
    return elapsed_time <= TIME_LIMIT

def get_time_warning(user_state: dict) -> str | None:
    """Возвращает предупреждение о времени, если осталось мало."""
    elapsed_time = time.time() - user_state['start_time']
    if TIME_LIMIT - elapsed_time < 60 and TIME_LIMIT - elapsed_time > 0:
         return f"\n[ВРЕМЯ] Осталось меньше минуты!"
    return None

# ======================================================
# АДАПТИРОВАННЫЕ ИГРОВЫЕ ФУНКЦИИ
# ======================================================

def get_status_text(player: Player) -> str:
    """Возвращает текстовое представление статуса игрока."""
    status = (
        f"[СТАТУС] ❤️{player.health}% | "
        f"💧{player.thirst}% | 🍞{player.hunger}% | "
        f"☢️{player.radiation}% | ☣️{player.infection}%"
    )
    inventory_str = ', '.join(player.inventory) if player.inventory else 'Пусто'
    inventory = f"[ИНВЕНТАРЬ] ({len(player.inventory)}/{player.inventory_limit()}): {inventory_str}"
    equipped = []
    if player.weapon: equipped.append(player.weapon)
    if player.has_armor: equipped.append(items["armor"])
    if player.has_gasmask: equipped.append(items["gasmask"])
    equipment = f"[ЭКИПИРОВКА]: {', '.join(equipped)}" if equipped else ""
    return f"{status}\n{inventory}\n{equipment}"

def progress_status_bot(user_state: dict) -> list[str]:
    """Обновляет статус игрока и возвращает список сообщений об изменениях."""
    player = user_state['player']
    messages = []

    # Базовые потребности
    hunger_increase = random.randint(4, 7)
    thirst_increase = random.randint(5, 8)
    player.hunger = min(player.hunger + hunger_increase, 100)
    player.thirst = min(player.thirst + thirst_increase, 100)

    if player.hunger >= 80: messages.append("Вы чувствуете сильный голод...")
    if player.thirst >= 80: messages.append("Вас мучает сильная жажда...")
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
             player.health = 0 # Мгновенная смерть

    rad_increase = random.randint(0, 4)
    if rad_increase > 0:
        player.radiation = min(player.radiation + rad_increase, 100)
        messages.append(f"Уровень радиации немного повысился (+{rad_increase}% ☢️).")
        if player.radiation >= 100:
             messages.append("Вы получили смертельную дозу радиации!")
             player.health = 0 # Мгновенная смерть

    player.health = max(0, player.health)
    return messages

def search_area_bot(user_state: dict, location_key: str) -> list[str]:
    """Обыскивает локацию и возвращает список найденных предметов/сообщений."""
    player = user_state['player']
    location_name = locations.get(location_key, "Неизвестная локация")
    messages = [f"Вы обыскиваете локацию '{location_name}'..."]
    found_count = 0

    for _ in range(2): # Две попытки поиска
        if random.randint(1, 100) <= 60:
            # --- Логика выбора предмета (упрощена для примера) ---
            possible_items_keys = list(items.keys())
            # Тут должна быть логика весов как в оригинале, но пока упростим
            found_item_key = random.choice(possible_items_keys)
            item_name = items[found_item_key]

            # --- Обработка найденного ---
            # (Нужно перенести логику из оригинальной search_area)
            if found_item_key == "gasmask" and not player.has_gasmask:
                 player.has_gasmask = True
                 messages.append(f"Вы нашли и надели: {item_name}")
                 found_count += 1
            elif found_item_key == "armor" and not player.has_armor:
                 player.has_armor = True
                 messages.append(f"Вы нашли и надели: {item_name}")
                 found_count += 1
            elif found_item_key == "big_backpack" and player.backpack_size == 5:
                 player.backpack_size = 10
                 messages.append(f"Вы нашли: {item_name}! Инвентарь увеличен.")
                 found_count += 1
            elif found_item_key == "pistol" and not player.weapon:
                 player.weapon = item_name
                 messages.append(f"Вы нашли оружие: {item_name}!")
                 # Дать патроны
                 if len(player.inventory) < player.inventory_limit():
                     player.inventory.append(items["ammo"])
                     messages.append("В комплекте было несколько патронов.")
                 found_count += 1
            elif found_item_key not in ["gasmask", "armor", "big_backpack", "pistol"]:
                 if len(player.inventory) < player.inventory_limit():
                     player.inventory.append(item_name)
                     messages.append(f"Вы нашли: {item_name}")
                     found_count += 1
                 else:
                     messages.append(f"Вы нашли {item_name}, но нет места!")

    if found_count == 0:
        messages.append("Ничего ценного найти не удалось.")
    return messages

def get_random_monster_key() -> str | None:
    """Возвращает ключ случайного монстра (не босса)."""
    available_monsters = [k for k, v in monsters_data.items() if not v.get('is_boss')]
    if not available_monsters: return None
    return random.choice(available_monsters)

# ======================================================
# ФУНКЦИИ ДЛЯ ГЕНЕРАЦИИ КЛАВИАТУР
# ======================================================

def build_main_keyboard(user_state: dict) -> InlineKeyboardMarkup:
    """Создает клавиатуру с выбором локаций и действием 'Использовать предмет'."""
    player = user_state['player']
    keyboard = []
    # Кнопки локаций
    for key, name in locations.items():
        button_text = name
        callback_data = f"loc_{key}"
        if key == "bridge":
            if not user_state['captain_defeated']:
                button_text += " (Прегражден!)"
            elif not user_state['bridge_puzzle_attempted']:
                button_text += " (Свободен)"
            else:
                button_text += " (Заблокирован)"
                callback_data = "info_bridge_locked" # Не даем войти, если заблокировано

        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

    # Кнопка инвентаря
    if player.inventory:
        keyboard.append([InlineKeyboardButton("🎒 Использовать предмет", callback_data="inventory_open")])
    else:
        keyboard.append([InlineKeyboardButton("🎒 Инвентарь пуст", callback_data="info_inventory_empty")])

    return InlineKeyboardMarkup(keyboard)

def build_inventory_keyboard(player: Player) -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора предмета из инвентаря."""
    keyboard = []
    if not player.inventory:
        keyboard.append([InlineKeyboardButton("Инвентарь пуст", callback_data="inventory_close")])
    else:
        for idx, item_name in enumerate(player.inventory):
            # Пропускаем предметы, которые нельзя использовать напрямую
            item_key = next((k for k, v in items.items() if v == item_name), None)
            if item_key not in ["ammo", "pistol", "armor", "gasmask", "big_backpack"]:
                 keyboard.append([InlineKeyboardButton(f"Использовать: {item_name}", callback_data=f"item_use_{idx}")])
            else:
                 keyboard.append([InlineKeyboardButton(f"{item_name} (Нельзя использовать)", callback_data=f"info_item_passive_{idx}")])

        keyboard.append([InlineKeyboardButton("❌ Закрыть инвентарь", callback_data="inventory_close")])
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
# ОБРАБОТЧИКИ КОМАНД И КОЛБЭКОВ TELEGRAM
# ======================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start. Начинает новую игру."""
    chat_id = update.effective_chat.id
    logger.info(f"User {chat_id} started the game.")
    user_state = reset_user_state(chat_id) # Сброс и инициализация

    welcome_text = (
        "=== Добро пожаловать на станцию 'Гелиос-9' ===\n\n"
        "Тьма. Ты приходишь в себя в аварийной капсуле...\n"
        "(Полный текст вступления)\n\n"
        "Ваша цель - выжить и найти способ сбежать."
    )
    await update.message.reply_text(welcome_text)
    # Сразу показываем статус и опции
    await show_main_screen(update, context, chat_id)

async def show_main_screen(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_to_edit_id: int | None = None):
    """Отображает основной экран: статус и выбор локации/предмета."""
    user_state = get_user_state(chat_id)
    player = user_state['player']

    # Проверка условий конца игры
    if not player.is_alive():
        await send_game_over(update, context, chat_id, "player_dead")
        return
    if not check_time_bot(user_state):
        await send_game_over(update, context, chat_id, "time_out")
        return

    # Формируем сообщение
    status_text = get_status_text(player)
    time_warning = get_time_warning(user_state)
    message_text = status_text + (f"\n{time_warning}" if time_warning else "") + "\n\nКуда отправиться?"

    keyboard = build_main_keyboard(user_state)
    user_state['expected_input'] = 'location' # Ожидаем выбор локации или инвентаря

    # Отправляем или редактируем сообщение
    if message_to_edit_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_to_edit_id,
                text=message_text,
                reply_markup=keyboard
            )
            user_state['last_message_id'] = message_to_edit_id
        except Exception as e: # Если сообщение не найдено или не изменилось
            logger.warning(f"Failed to edit message {message_to_edit_id}: {e}")
            sent_message = await context.bot.send_message(chat_id, message_text, reply_markup=keyboard)
            user_state['last_message_id'] = sent_message.message_id
    else:
        # Удаляем старое сообщение с кнопками, если оно было
        if user_state.get('last_message_id'):
             try:
                 await context.bot.delete_message(chat_id, user_state['last_message_id'])
             except Exception: pass # Ничего страшного, если не удалилось

        sent_message = await context.bot.send_message(chat_id, message_text, reply_markup=keyboard)
        user_state['last_message_id'] = sent_message.message_id


async def handle_location_choice(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int, loc_key: str):
    """Обрабатывает выбор локации."""
    user_state = get_user_state(chat_id)
    player = user_state['player']
    loc_name = locations.get(loc_key, "Неизвестно")
    message_id_to_edit = user_state.get('last_message_id')

    turn_messages = [] # Сообщения за этот ход

    # --- Особая логика для Мостика ---
    if loc_key == "bridge":
        if not user_state['captain_defeated']:
            turn_messages.append(f"Вы пытаетесь пройти на '{loc_name}', но путь преграждает...")
            # Начинаем бой с капитаном
            captain_data = monsters_data['captain'].copy() # Берем копию
            user_state['current_monster'] = captain_data
            user_state['expected_input'] = 'fight'
            monster_status_text = f"{captain_data['desc']}\n[ОПАСНОСТЬ] На вас нападает {captain_data['name']}!"
            fight_keyboard = build_fight_keyboard()
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=message_id_to_edit,
                text=f"{monster_status_text}\n\n{get_status_text(player)}", # Показываем статус в бою
                reply_markup=fight_keyboard
            )
            return # Выходим, ждем действия в бою
        elif not user_state['bridge_puzzle_attempted']:
             turn_messages.append(f"Вы входите на '{loc_name}'. Путь свободен.")
             # Начинаем загадку
             await start_bridge_puzzle(update, context, chat_id, message_id_to_edit)
             return # Выходим, ждем ввода кода
        else: # Капитан побежден, попытка была
             turn_messages.append(f"Вы снова на '{loc_name}'. Терминал самоуничтожения заблокирован.")
             # Просто показываем сообщение и возвращаем на главный экран
             await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id_to_edit, text='\n'.join(turn_messages))
             await asyncio.sleep(2) # Пауза для чтения
             await show_main_screen(update, context, chat_id)
             return

    # --- Обычные локации ---
    else:
        user_state['current_location_key'] = loc_key
        turn_messages.append(f"Вы направились в '{loc_name}'.")

        # 1. Обыск локации
        search_results = search_area_bot(user_state, loc_key)
        turn_messages.extend(search_results)
        # Промежуточная отправка результатов поиска
        await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id_to_edit, text='\n'.join(turn_messages))
        await asyncio.sleep(1.5) # Пауза для чтения

        if not player.is_alive(): # Проверка после обыска (мало ли что)
             await send_game_over(update, context, chat_id, "player_dead")
             return

        # 2. Случайная встреча
        encounter_chance = 40 # 40%
        if random.randint(1, 100) <= encounter_chance:
            monster_key = get_random_monster_key()
            if monster_key:
                monster_data = monsters_data[monster_key].copy()
                user_state['current_monster'] = monster_data
                user_state['expected_input'] = 'fight'
                monster_status_text = f"{monster_data['desc']}\n[ОПАСНОСТЬ] На вас нападает {monster_data['name']}!"
                fight_keyboard = build_fight_keyboard()
                # Обновляем сообщение, начиная бой
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id_to_edit,
                    text=f"{monster_status_text}\n\n{get_status_text(player)}",
                    reply_markup=fight_keyboard
                )
                return # Выходим, ждем действия в бою
            else:
                 turn_messages.append("Вы слышите странные звуки, но никого не видите.")
        else:
            turn_messages.append("В локации тихо.")

        # 3. Прогресс статуса (если не было боя)
        progress_msgs = progress_status_bot(user_state)
        turn_messages.extend(progress_msgs)

        # Финальная отправка сообщений за ход и возврат на главный экран
        await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id_to_edit, text='\n'.join(turn_messages))
        await asyncio.sleep(2) # Пауза для чтения

        # Проверка смерти после прогресса статуса
        if not player.is_alive():
             await send_game_over(update, context, chat_id, "player_dead")
             return

        await show_main_screen(update, context, chat_id) # Показать главный экран для следующего хода


async def handle_fight_action(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int, action: str):
    """Обрабатывает действие игрока в бою (атака или побег)."""
    user_state = get_user_state(chat_id)
    player = user_state['player']
    monster = user_state.get('current_monster')
    message_id_to_edit = user_state.get('last_message_id')

    if not monster or user_state.get('expected_input') != 'fight':
        logger.warning(f"Unexpected fight action from {chat_id} when not in fight.")
        # Можно отправить сообщение об ошибке или просто вернуть на главный экран
        await show_main_screen(update, context, chat_id, message_id_to_edit)
        return

    fight_log = [] # Лог событий боя за этот раунд

    if action == "attack":
        # Атака игрока
        player_damage = 0
        if player.weapon == items["pistol"]:
            try:
                ammo_index = player.inventory.index(items["ammo"])
                player.inventory.pop(ammo_index)
                player_damage = random.randint(25, 40)
                fight_log.append(f"Вы стреляете из плазматрона! (-1 {items['ammo']})")
            except ValueError:
                player_damage = random.randint(5, 10)
                fight_log.append("Нет патронов! Вы бьете кулаками!")
        else: # Рукопашная
            player_damage = random.randint(5, 10)
            fight_log.append("Вы бьете кулаками!")

        monster['health'] -= player_damage
        monster['health'] = max(0, monster['health']) # Не уходим в минус
        fight_log.append(f"Вы нанесли {player_damage} урона. Здоровье монстра: {monster['health']}/{monster['full_health']}")

        if monster['health'] <= 0:
            # Монстр побежден
            fight_log.append(f"\nВы победили {monster['name']}!")
            # --- Лут ---
            loot_key = next((k for k, v in monsters_data.items() if v['name'] == monster['name']), None)
            if loot_key and monsters_data[loot_key].get('loot'):
                 for item_loot_key in monsters_data[loot_key]['loot']:
                     if len(player.inventory) < player.inventory_limit():
                         player.inventory.append(items[item_loot_key])
                         fight_log.append(f"Вы нашли: {items[item_loot_key]}")
                     else:
                         fight_log.append(f"Вы нашли {items[item_loot_key]}, но нет места!")

            # --- Особый случай: Капитан ---
            if monster.get('is_boss'):
                 user_state['captain_defeated'] = True
                 fight_log.append("Путь на мостик свободен!")
                 # Сразу переходим к загадке
                 await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id_to_edit, text='\n'.join(fight_log))
                 await asyncio.sleep(2)
                 await start_bridge_puzzle(update, context, chat_id, message_id_to_edit)
                 user_state['current_monster'] = None # Убираем монстра из состояния
                 return

            # Обычный монстр побежден, возвращаемся на главный экран после паузы
            user_state['current_monster'] = None
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id_to_edit, text='\n'.join(fight_log))
            await asyncio.sleep(2)
            # Прогресс статуса после боя
            progress_msgs = progress_status_bot(user_state)
            if progress_msgs:
                 await context.bot.send_message(chat_id, "\n".join(progress_msgs))
                 await asyncio.sleep(1.5)

            await show_main_screen(update, context, chat_id)
            return

    elif action == "flee":
        escape_chance = 60
        if random.randint(1, 100) <= escape_chance:
            fight_log.append("Вы успешно сбежали!")
            user_state['current_monster'] = None
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id_to_edit, text='\n'.join(fight_log))
            await asyncio.sleep(1.5)
            # Прогресс статуса после побега
            progress_msgs = progress_status_bot(user_state)
            if progress_msgs:
                 await context.bot.send_message(chat_id, "\n".join(progress_msgs))
                 await asyncio.sleep(1.5)
            await show_main_screen(update, context, chat_id)
            return
        else:
            fight_log.append("Не удалось сбежать!")
            # Монстр атакует после неудачного побега

    # Атака монстра (если он жив и игрок не сбежал/не победил)
    if monster['health'] > 0:
        monster_damage = monster['damage']
        if player.has_armor:
            reduction = 0.3
            monster_damage = int(monster_damage * (1 - reduction))
            fight_log.append("Броня поглотила часть урона.")
        player.health -= monster_damage
        player.health = max(0, player.health)
        fight_log.append(f"{monster['name']} наносит вам {monster_damage} урона!")

        if not player.is_alive():
            fight_log.append(f"Ваше здоровье: {player.health}%")
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id_to_edit, text='\n'.join(fight_log))
            await asyncio.sleep(1.5)
            await send_game_over(update, context, chat_id, "player_dead")
            return

    # Бой продолжается, обновляем сообщение
    status_text = get_status_text(player)
    fight_keyboard = build_fight_keyboard()
    await context.bot.edit_message_text(
        chat_id=chat_id, message_id=message_id_to_edit,
        text=f"{'\n'.join(fight_log)}\n\n{status_text}",
        reply_markup=fight_keyboard
    )


async def handle_inventory_action(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int, callback_data: str):
    """Обрабатывает действия в инвентаре (открытие, использование, закрытие)."""
    user_state = get_user_state(chat_id)
    player = user_state['player']
    message_id_to_edit = user_state.get('last_message_id')

    if callback_data == "inventory_open":
        inventory_keyboard = build_inventory_keyboard(player)
        await context.bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id_to_edit,
            reply_markup=inventory_keyboard
        )
        user_state['expected_input'] = 'item'
    elif callback_data == "inventory_close":
        # Просто возвращаем главную клавиатуру
        await show_main_screen(update, context, chat_id, message_id_to_edit)
    elif callback_data.startswith("item_use_"):
        item_index = int(callback_data.split("_")[-1])
        if 0 <= item_index < len(player.inventory):
            item_to_use = player.inventory.pop(item_index)
            use_message = f"Вы использовали: {item_to_use}."
            # Применяем эффекты
            if item_to_use == items["water"]:
                player.thirst = max(player.thirst - 40, 0)
                use_message += " Жажда утолена."
            elif item_to_use == items["food"]:
                player.hunger = max(player.hunger - 40, 0)
                use_message += " Голод утолен."
            elif item_to_use == items["medkit"]:
                player.health = min(player.health + 50, 100)
                use_message += " Здоровье восстановлено."
            elif item_to_use == items["antivirus"]:
                player.infection = max(player.infection - 60, 0)
                use_message += " Распространение вируса замедлено."
            else: # Предмет нельзя использовать так
                 use_message = f"{item_to_use} нельзя использовать напрямую."
                 player.inventory.insert(item_index, item_to_use) # Вернуть обратно

            # Отправляем сообщение об использовании и возвращаемся на главный экран
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id_to_edit, text=use_message)
            await asyncio.sleep(1.5)
            # Прогресс статуса после использования предмета
            progress_msgs = progress_status_bot(user_state)
            if progress_msgs:
                 await context.bot.send_message(chat_id, "\n".join(progress_msgs))
                 await asyncio.sleep(1.5)

            await show_main_screen(update, context, chat_id)
        else:
            await context.bot.answer_callback_query(update.callback_query.id, "Ошибка: Предмет не найден.")
            await show_main_screen(update, context, chat_id, message_id_to_edit) # Вернуть на главный экран
    elif callback_data.startswith("info_"): # Обработка информационных кнопок
         query = update.callback_query
         if "inventory_empty" in callback_data:
             await query.answer("Ваш инвентарь пуст.", show_alert=True)
         elif "item_passive" in callback_data:
             await query.answer("Этот предмет используется автоматически или при атаке.", show_alert=True)
         elif "bridge_locked" in callback_data:
              await query.answer("Терминал мостика заблокирован после неудачной попытки.", show_alert=True)


async def start_bridge_puzzle(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id_to_edit: int):
    """Начинает загадку на мостике."""
    user_state = get_user_state(chat_id)
    user_state['expected_input'] = 'puzzle_code'
    user_state['puzzle_attempts_left'] = 3
    # Генерируем код только один раз при первой попытке
    if user_state.get('puzzle_code') is None:
         user_state['puzzle_code'] = str(random.randint(1000, 9999))
         logger.info(f"Generated puzzle code for {chat_id}: {user_state['puzzle_code']}") # Логируем код для отладки

    puzzle_text = (
        "Вы подходите к главному терминалу мостика.\n"
        "На экране мерцает запрос кода доступа.\n\n"
        f"Введите 4-значный код [{user_state['puzzle_attempts_left']} попытк{'а' if user_state['puzzle_attempts_left']==1 else 'и'}]:"
    )
    # Убираем клавиатуру, ждем текстового ввода
    await context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id_to_edit,
        text=puzzle_text,
        reply_markup=None # Убираем кнопки
    )

async def handle_puzzle_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает ввод кода для загадки."""
    chat_id = update.effective_chat.id
    user_state = get_user_state(chat_id)
    message_id_to_edit = user_state.get('last_message_id') # ID сообщения с запросом кода

    if user_state.get('expected_input') != 'puzzle_code':
        # Игнорируем текст, если не ожидаем код
        return

    attempt = update.message.text.strip()
    result_message = ""

    if not attempt.isdigit() or len(attempt) != 4:
        result_message = "Ошибка ввода. Код должен состоять из 4 цифр.\n"
        # Не уменьшаем попытки за неверный формат
    else:
        user_state['puzzle_attempts_left'] -= 1
        correct_code = user_state.get('puzzle_code', '????') # Получаем код из состояния

        if attempt == correct_code:
            result_message = (
                "\n[КОД ПРИНЯТ]\n"
                "Система самоуничтожения активирована! Сирены взвыли!\n"
                "У вас есть немного времени, чтобы добраться до спасательной капсулы!"
            )
            await context.bot.send_message(chat_id, result_message)
            await asyncio.sleep(2)
            await send_game_over(update, context, chat_id, "win_bridge")
            return # Игра выиграна
        else:
            result_message = "[ДОСТУП ОТКЛОНЕН]\n"
            if user_state['puzzle_attempts_left'] > 0:
                # Подсказка
                if int(attempt) < int(correct_code):
                    result_message += "Подсказка: Загаданный код больше.\n"
                else:
                    result_message += "Подсказка: Загаданный код меньше.\n"
                result_message += f"Осталось попыток: {user_state['puzzle_attempts_left']}"
            else:
                result_message += "Попытки исчерпаны. Терминал блокируется!"
                user_state['bridge_puzzle_attempted'] = True # Отмечаем неудачу

    # Показываем результат и либо просим ввести снова, либо сообщаем о блокировке
    if user_state['puzzle_attempts_left'] > 0 and (attempt.isdigit() and len(attempt) == 4):
         # Просим ввести код снова
         await context.bot.send_message(chat_id, result_message + "\n\nВведите 4-значный код:")
         # Не меняем expected_input, все еще ждем код
    else:
         # Попытки кончились или была ошибка формата в последней попытке
         await context.bot.send_message(chat_id, result_message)
         user_state['expected_input'] = None # Больше не ждем код
         await asyncio.sleep(2)
         await show_main_screen(update, context, chat_id) # Возврат на главный экран


async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Основной обработчик нажатий на Inline-кнопки."""
    query = update.callback_query
    await query.answer() # Обязательно подтвердить получение колбэка
    chat_id = query.message.chat_id
    callback_data = query.data
    user_state = get_user_state(chat_id) # Получаем текущее состояние

    logger.info(f"Callback from {chat_id}: {callback_data}")

    # Проверка на ожидаемый ввод (базовая)
    current_expected = user_state.get('expected_input')

    # --- Маршрутизация по типу callback_data ---
    if callback_data.startswith("loc_") and current_expected == 'location':
        loc_key = callback_data.split("_")[1]
        await handle_location_choice(update, context, chat_id, loc_key)
    elif callback_data.startswith("fight_") and current_expected == 'fight':
        action = callback_data.split("_")[1]
        await handle_fight_action(update, context, chat_id, action)
    elif (callback_data.startswith("inventory_") or callback_data.startswith("item_") or callback_data.startswith("info_item")) \
         and (current_expected == 'location' or current_expected == 'item'): # Разрешаем доступ к инвентарю с главного экрана или из него самого
        await handle_inventory_action(update, context, chat_id, callback_data)
    elif callback_data.startswith("info_"): # Обработка прочих инфо-кнопок
         await handle_inventory_action(update, context, chat_id, callback_data) # Переиспользуем для info_*
    else:
        logger.warning(f"Unexpected callback '{callback_data}' for state '{current_expected}' from {chat_id}")
        # Можно отправить сообщение об ошибке или просто проигнорировать
        await query.answer("Неожиданное действие.", show_alert=True)


async def send_game_over(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int, reason: str):
    """Отправляет сообщение о конце игры и сбрасывает состояние."""
    user_state = game_states.get(chat_id)
    if not user_state: return # Состояние уже сброшено

    player = user_state['player']
    elapsed_time = int(time.time() - user_state['start_time'])
    final_message = "=== ИГРА ОКОНЧЕНА ===\n"

    if reason == "win_bridge":
        final_message += (
            "\nСирены воют! Таймер самоуничтожения запущен!\n"
            "Вы бежите к спасательной капсуле и в последнюю секунду стартуете...\n"
            "Станция 'Гелиос-9' взрывается позади вас яркой вспышкой!\n\n"
            "🎉 ПОЗДРАВЛЯЕМ С ПОБЕДОЙ! 🎉"
        )
    elif reason == "player_dead":
        final_message += "\nВы не смогли выжить на станции 'Гелиос-9'.\nПричина: "
        if player.health <= 0: final_message += "Смертельные раны."
        elif player.hunger >= 100: final_message += "Смерть от голода."
        elif player.thirst >= 100: final_message += "Смерть от жажды."
        elif player.infection >= 100: final_message += "Инфекция захватила организм."
        elif player.radiation >= 100: final_message += "Смертельная доза радиации."
        else: final_message += "Неизвестна."
        final_message += "\n\n💀 КОНЕЦ ИГРЫ 💀"
    elif reason == "time_out":
        final_message += (
             "\nВремя вышло! Системы жизнеобеспечения отказали окончательно.\n"
             "Вы не смогли найти способ спастись вовремя.\n\n"
             "💀 КОНЕЦ ИГРЫ 💀"
        )
    else:
        final_message += "\nИгра завершена по неизвестной причине."

    final_message += f"\n\nВремя выживания: {elapsed_time} секунд."
    final_message += "\n\nЧтобы начать заново, введите /start"

    # Удаляем сообщение с кнопками, если оно было
    last_msg_id = user_state.get('last_message_id')
    if last_msg_id:
        try:
            await context.bot.delete_message(chat_id, last_msg_id)
        except Exception: pass

    await context.bot.send_message(chat_id, final_message)

    # Сброс состояния
    if chat_id in game_states:
        del game_states[chat_id]
    logger.info(f"Game over for user {chat_id}. Reason: {reason}")


# ======================================================
# ОСНОВНАЯ ФУНКЦИЯ ЗАПУСКА БОТА
# ======================================================

def main() -> None:
    """Запуск бота."""
    application = Application.builder().token(TOKEN).build()

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    # Можно добавить /help, /status и т.д.

    # Обработчик нажатий на кнопки
    application.add_handler(CallbackQueryHandler(callback_query_handler))

    # Обработчик текстовых сообщений (для ввода кода загадки)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_puzzle_input))

    # Запуск бота
    logger.info("Starting bot...")
    application.run_polling()

if __name__ == "__main__":
    main()
