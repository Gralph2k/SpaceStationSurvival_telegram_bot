# -*- coding: utf-8 -*-
import random

# from sqlite3 import Time # Этот импорт не используется, можно убрать
import time

test_mode = False


# Игрок
class Player:
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

    def is_alive(self):
        # Добавим проверку на голод и жажду для большей ясности при проигрыше
        return (
            self.health > 0
            and self.infection < 100
            and self.radiation < 100
            and self.hunger < 100
            and self.thirst < 100
        )

    def inventory_limit(self):
        return self.backpack_size


# Предметы
items = {
    "water": "Бутылка воды",
    "food": "Питательный блок",
    "medkit": "Аптечка",
    "antivirus": "Антивирусный шприц",
    "gasmask": "Противогаз",
    "ammo": "Патроны",
    "pistol": "Пистолет-плазматрон",
    "armor": "Броня",
    "big_backpack": "Большой рюкзак",
    # Можно добавить ключ-карту капитана как предмет, если захочется усложнить
    # "captain_keycard": "Ключ-карта капитана"
}

# Монстры
monsters = [
    {
        "name": "Мутант-сталкер",
        "health": 50,
        "full_health": 50,
        "damage": 15,
        "desc": "Вдруг из вентиляционной шахты выползает существо — пародия на человека, его кожа чёрная и покрыта язвами.",
    },
    {
        "name": "Раздутый ужас",
        "health": 80,
        "full_health": 80,
        "damage": 25,
        "desc": "Из тьмы на вас идет огромная колышащаяся масса в обрывках летного костюма",
    },
    # --- Новый монстр ---
    {
        "name": "Зомби-капитан",
        "health": 120,  # Сделаем его покрепче
        "full_health": 120,
        "damage": 30,  # И посильнее
        "desc": "У штурвала стоит фигура в истлевшей капитанской форме. Она поворачивается, и пустые глазницы устремляются на вас.",
    },
]

health_status = [
    {"share": 0, "status": "мёртв"},
    {"share": 0.25, "status": "практически мёртв"},
    {"share": 0.5, "status": "слаб"},
    {"share": 0.75, "status": "ранен"},
]

# Локации
locations = {
    "medbay": "Медицинский отсек",
    "engineering": "Инженерный цех",
    "quarters": "Жилые отсеки",
    "reactor": "Реакторный блок",
    "laboratory": "Главная лаборатория",
    "bridge": "Мостик корабля",  # --- Новая локация ---
}

# Инициализация игрока (оставим здесь для глобального доступа)
player = Player()

# --- Флаг для отслеживания победы над капитаном ---
captain_defeated = False
# --- Флаг для отслеживания попытки взлома терминала ---
bridge_puzzle_attempted = False

# Подсчёт времени (перенесем инициализацию в play_game)
start_time = 0

# Заранее заданные ответы для тестирования
predefined_inputs = iter(
    [
        "0",
        "2",
        "1",
        "1",
        "2",
        "3",
        "1",
        "0",
        "2",
        "2",
        "4",
        "2",
        "1",
        "1",
        "0",
        "2",
        "3",
        "2",
        "1",
        "2",
        "0",
        "1",
        "2",
        "4",
        "6",  # Попытка пойти на мостик
        "1",
        "1",
        "1",
        "1",
        "1",  # Бой с капитаном
        "1234",  # Неверный код для загадки
        "5",  # Пойти в лабораторию
        "1",
        "1",  # Обыск, бой
        "0",
        "3",  # Использовать аптечку
        "6",  # Снова на мостик (должно сказать, что терминал заблокирован)
        # ... можно добавить еще шагов ...
    ]
)


def safe_input(prompt):
    """Безопасный ввод с поддержкой тестового режима."""
    try:
        if test_mode:
            # Добавим небольшую паузу в тестовом режиме для читаемости
            time.sleep(0.1)
            value = next(predefined_inputs)
            print(f"{prompt}{value}")
        else:
            value = input(prompt)
        return value.strip()  # Убираем лишние пробелы
    except StopIteration:
        # Если тестовые вводы закончились, можно выбрать действие по умолчанию
        # Например, использовать предмет (0) или пойти в первую локацию (1)
        print(f"{prompt}1 (автоматический ввод)")
        return "1"
    except EOFError:  # Обработка Ctrl+D / конца файла
        print(f"{prompt}1 (автоматический ввод при EOF)")
        return "1"


def show_status():
    """Отображает текущий статус игрока и инвентарь."""
    print("------------------------------------")
    print(
        f"\n[СТАТУС] Здоровье: {player.health}% | Жажда: {player.thirst}% | Голод: {player.hunger}% | Радиация: {player.radiation}% | Инфекция: {player.infection}%"
    )
    inventory_str = ", ".join(player.inventory) if player.inventory else "Пусто"
    print(
        f"[ИНВЕНТАРЬ] ({len(player.inventory)}/{player.inventory_limit()}): {inventory_str}"
    )
    # Дополнительно покажем экипировку
    equipped = []
    if player.weapon:
        equipped.append(player.weapon)
    if player.has_armor:
        equipped.append(items["armor"])
    if player.has_gasmask:
        equipped.append(items["gasmask"])
    if equipped:
        print(f"[ЭКИПИРОВКА]: {', '.join(equipped)}")


def search_area(location_name):
    """Игрок обыскивает текущую локацию."""
    print(f"\nВы обыскиваете локацию '{location_name}'...")
    # Шанс найти что-то зависит от локации? Пока нет.
    found_count = 0
    # Ищем 2 раза с шансом успеха
    for _ in range(2):
        # Базовый шанс найти что-то
        if random.randint(1, 100) <= 60:  # 60% шанс найти хоть что-то за попытку
            possible_items = list(items.keys())
            # Уменьшим шанс найти оружие/броню/рюкзак, если они уже есть
            weights = [1] * len(possible_items)
            for i, item_key in enumerate(possible_items):
                if (
                    (item_key == "pistol" and player.weapon)
                    or (item_key == "gasmask" and player.has_gasmask)
                    or (item_key == "armor" and player.has_armor)
                    or (item_key == "big_backpack" and player.backpack_size > 5)
                ):
                    weights[i] = 0.1  # Сильно режем шанс дубликата уникального предмета
                elif item_key in ["pistol", "armor", "big_backpack", "gasmask"]:
                    weights[i] = 0.5  # Режем шанс найти уникальный предмет в целом
                elif item_key == "ammo" and not player.weapon:
                    weights[i] = 0.2  # Меньше шанс найти патроны без оружия

            # Нормализуем веса, чтобы избежать ошибки, если все веса нулевые
            if sum(weights) == 0:
                continue

            found_item_key = random.choices(possible_items, weights=weights, k=1)[0]

            # Обработка найденного предмета
            if found_item_key == "gasmask":
                if not player.has_gasmask:
                    player.has_gasmask = True
                    print(f"Вы нашли: {items[found_item_key]} (Автоматически надет)")
                    found_count += 1
                # else: # Если уже есть, можно найти что-то другое или ничего
                #     print("Вы нашли еще один противогаз, но ваш еще в порядке.")
            elif found_item_key == "armor":
                if not player.has_armor:
                    player.has_armor = True
                    print(f"Вы нашли: {items[found_item_key]} (Надето)")
                    found_count += 1
            elif found_item_key == "big_backpack":
                if player.backpack_size == 5:
                    player.backpack_size = 10
                    print(
                        f"Вы нашли: {items[found_item_key]}! Теперь ваш инвентарь вмещает больше предметов."
                    )
                    found_count += 1
            elif found_item_key == "pistol":
                if not player.weapon:
                    player.weapon = items[found_item_key]
                    print(f"Вы нашли оружие: {items[found_item_key]}!")
                    # Дадим немного патронов при нахождении пистолета
                    if len(player.inventory) < player.inventory_limit():
                        player.inventory.append(items["ammo"])
                        print("В комплекте было несколько патронов.")
                    found_count += 1
            else:  # Обычные предметы
                if len(player.inventory) < player.inventory_limit():
                    player.inventory.append(items[found_item_key])
                    print(f"Вы нашли: {items[found_item_key]}")
                    found_count += 1
                else:
                    print(
                        f"Вы нашли {items[found_item_key]}, но нет места в инвентаре!"
                    )

    if found_count == 0:
        print("Ничего ценного найти не удалось.")


def random_encounter(location_name):
    """Шанс встретить монстра в локации."""
    # На мостике монстров нет (кроме капитана при входе)
    if location_name == locations["bridge"]:
        return

    # Шанс встречи зависит от локации? Пока нет.
    if random.randint(1, 100) <= 40:  # 40% шанс встречи
        monster_data = random.choice(
            [m for m in monsters if m["name"] != "Зомби-капитан"]
        )  # Исключаем капитана из случайных встреч
        # Передаем копию данных монстра, чтобы не портить шаблон
        fight(monster_data.copy())


def get_monster_status(monster_health, monster_full_health):
    """Возвращает текстовое описание состояния монстра по его здоровью."""
    share = monster_health / monster_full_health
    if share <= 0:
        return health_status[0]["status"]  # мёртв
    if share <= 0.25:
        return health_status[1]["status"]  # практически мёртв
    if share <= 0.5:
        return health_status[2]["status"]  # слаб
    if share <= 0.75:
        return health_status[3]["status"]  # ранен
    return "здоров"  # Если больше 75%


def fight(monster_instance):
    """
    Процесс боя с монстром.
    Возвращает: "win", "flee", "player_dead", "error".
    """
    print(
        f"\n{monster_instance['desc']}\n[ОПАСНОСТЬ] На вас нападает {monster_instance['name']}!"
    )

    while monster_instance["health"] > 0 and player.is_alive():
        monster_status = get_monster_status(
            monster_instance["health"], monster_instance["full_health"]
        )
        print(
            f"Здоровье монстра ({monster_status}): {monster_instance['health']}/{monster_instance['full_health']}"
        )
        print(f"Ваше здоровье: {player.health}%")

        action = safe_input("\n(1) Атаковать  (2) Убежать > ")

        if action == "1":
            # Атака игрока
            if player.weapon == items["pistol"]:
                # Проверяем наличие патронов
                try:
                    ammo_index = player.inventory.index(items["ammo"])
                    player.inventory.pop(ammo_index)  # Тратим один патрон
                    damage = random.randint(25, 40)  # Увеличим урон от пистолета
                    print("Вы стреляете из плазматрона!")
                except ValueError:
                    print("У вас нет патронов! Атакуете врукопашную.")
                    damage = random.randint(5, 10)
            elif player.weapon:  # Другое оружие (если будет)
                damage = random.randint(15, 25)  # Пример для другого оружия
                print(f"Вы атакуете с помощью {player.weapon}!")
            else:  # Рукопашная атака
                damage = random.randint(5, 10)
                print("Вы бьете кулаками!")

            monster_instance["health"] -= damage
            print(f"Вы нанесли {damage} урона.")
            if monster_instance["health"] <= 0:
                monster_status = get_monster_status(0, monster_instance["full_health"])
                print(f"Монстр {monster_status}.")
                break  # Монстр побежден, выходим из цикла атаки монстра
            else:
                monster_status = get_monster_status(
                    monster_instance["health"], monster_instance["full_health"]
                )
                print(f"Монстр {monster_status}.")

        elif action == "2":
            # Попытка побега
            escape_chance = 60  # Базовый шанс 60%
            if random.randint(1, 100) <= escape_chance:
                print("Вы успешно сбежали!")
                return "flee"
            else:
                print("Не удалось сбежать!")
                # Монстр атакует в ответ после неудачного побега

        else:
            print("Неверное действие.")
            continue  # Повторить запрос действия без атаки монстра

        # Атака монстра (если он еще жив и игрок не сбежал)
        if monster_instance["health"] > 0:
            hit = monster_instance["damage"]
            # Снижение урона от брони
            if player.has_armor:
                reduction = 0.3  # Броня поглощает 30% урона
                hit = int(hit * (1 - reduction))
                print("Броня поглотила часть урона.")
            player.health -= hit
            player.health = max(0, player.health)  # Здоровье не уходит в минус
            print(f"{monster_instance['name']} наносит вам {hit} урона!")
            if not player.is_alive():
                # Здоровье игрока упало до 0 или ниже
                print(f"Ваше здоровье: {player.health}%")
                return "player_dead"  # Игрок погиб

    # Цикл завершился, проверяем результат
    if monster_instance["health"] <= 0:
        print(f"\nВы победили {monster_instance['name']}!")
        # --- Лут с монстров ---
        if monster_instance["name"] == "Мутант-сталкер":
            if len(player.inventory) < player.inventory_limit():
                player.inventory.append(items["ammo"])
                print("Вы нашли патроны!")
        elif monster_instance["name"] == "Раздутый ужас":
            if len(player.inventory) < player.inventory_limit():
                player.inventory.append(items["antivirus"])
                print("Вы нашли антивирусный шприц!")
        elif monster_instance["name"] == "Зомби-капитан":
            print(
                "С тела капитана падает ключ-карта... но терминал все еще требует код."
            )
            # Можно добавить выпадение ключ-карты как предмета, если нужно
            # if len(player.inventory) < player.inventory_limit():
            #     player.inventory.append(items["captain_keycard"])
            #     print("Вы подобрали ключ-карту капитана.")
        return "win"
    elif not player.is_alive():
        # Этот случай уже обработан внутри цикла, но для полноты
        return "player_dead"
    else:
        # Сюда не должны попасть при нормальном завершении
        print("ОШИБКА: Неопределенное состояние после боя.")
        return "error"


def use_item():
    """Использование предмета из инвентаря."""
    if not player.inventory:
        print("\nИнвентарь пуст!")
        return False  # Возвращаем False, если нечего использовать

    print("\nВаши предметы:")
    for idx, item_name in enumerate(player.inventory):
        print(f"({idx}) {item_name}")
    print(f"({len(player.inventory)}) Отмена")

    while True:
        choice = safe_input("Выберите номер предмета для использования или отмены: ")
        if choice.isdigit():
            choice_idx = int(choice)
            if 0 <= choice_idx < len(player.inventory):
                item_to_use = player.inventory.pop(
                    choice_idx
                )  # Удаляем и получаем предмет
                print(f"\nВы использовали: {item_to_use}")
                # Применение эффектов
                if item_to_use == items["water"]:
                    player.thirst = max(
                        player.thirst - 40, 0
                    )  # Вода утоляет жажду лучше
                    print("Вы утолили жажду.")
                elif item_to_use == items["food"]:
                    player.hunger = max(
                        player.hunger - 40, 0
                    )  # Еда утоляет голод лучше
                    print("Вы утолили голод.")
                elif item_to_use == items["medkit"]:
                    player.health = min(player.health + 50, 100)  # Аптечка лечит больше
                    print("Вы восстановили здоровье.")
                elif item_to_use == items["antivirus"]:
                    player.infection = max(
                        player.infection - 60, 0
                    )  # Антивирус эффективнее
                    print("Вы замедлили распространение вируса.")
                elif item_to_use == items["ammo"]:
                    print(
                        "Патроны нельзя 'использовать' таким образом. Они тратятся при стрельбе."
                    )
                    player.inventory.insert(
                        choice_idx, item_to_use
                    )  # Вернуть патроны обратно
                    return False  # Действие не выполнено
                # Добавить другие предметы по необходимости
                else:
                    print("Этот предмет нельзя использовать напрямую.")
                    player.inventory.insert(
                        choice_idx, item_to_use
                    )  # Вернуть предмет обратно
                    return False  # Действие не выполнено

                return True  # Предмет успешно использован
            elif choice_idx == len(player.inventory):
                print("Отмена использования предмета.")
                return False  # Отмена
            else:
                print("Неверный номер предмета.")
        else:
            print("Введите номер.")


def progress_status():
    """Обновляет состояние игрока со временем (голод, жажда и т.д.)."""
    # Увеличиваем базовые потребности
    player.hunger += random.randint(4, 7)
    player.thirst += random.randint(5, 8)
    player.hunger = min(player.hunger, 100)  # Ограничиваем 100%
    player.thirst = min(player.thirst, 100)  # Ограничиваем 100%

    # Штрафы за высокие потребности
    if player.hunger >= 80:
        print("\nВы чувствуете сильный голод...")
        if player.hunger >= 100:
            print("Вы умираете от голода!")
            player.health -= 15  # Больше урона при 100%
    if player.thirst >= 80:
        print("\nВас мучает сильная жажда...")
        if player.thirst >= 100:
            print("Вы умираете от жажды!")
            player.health -= 15  # Больше урона при 100%

    # Влияние окружения
    if not player.has_gasmask:
        toxic_air_effect = random.randint(3, 6)
        print(f"\nВы дышите токсичным воздухом (+{toxic_air_effect}% инфекции).")
        player.infection += toxic_air_effect
        player.infection = min(player.infection, 100)
        if player.infection >= 100:
            print("Инфекция полностью захватила ваш организм!")
            player.health = 0  # Мгновенная смерть от инфекции

    rad_increase = random.randint(0, 4)
    if rad_increase > 0:
        print(f"Уровень радиации немного повысился (+{rad_increase}%).")
        player.radiation += rad_increase
        player.radiation = min(player.radiation, 100)
        if player.radiation >= 100:
            print("Вы получили смертельную дозу радиации!")
            player.health = 0  # Мгновенная смерть от радиации

    player.health = max(0, player.health)  # Убедимся, что здоровье не ушло в минус


def check_time():
    """Проверяет, не вышло ли время игры."""
    global start_time
    elapsed_time = time.time() - start_time
    time_limit = 600  # 10 минут
    if elapsed_time > time_limit:
        print(f"\nПрошло {time_limit // 60} минут...")
        print("Системы жизнеобеспечения станции окончательно отказали!")
        return False  # Время вышло
    # Можно добавить предупреждение о времени
    elif time_limit - elapsed_time < 60:  # Меньше минуты осталось
        print(f"\n[ВРЕМЯ] Осталось меньше минуты!")

    return True  # Время еще есть


# --- Новая функция для загадки ---
def solve_bridge_puzzle():
    """
    Обрабатывает загадку с кодом на мостике.
    Возвращает True, если решено, иначе False.
    """
    global bridge_puzzle_attempted
    bridge_puzzle_attempted = True  # Отмечаем попытку

    print("\nВы подходите к главному терминалу мостика.")
    print("На экране мерцает запрос кода доступа.")
    # Генерируем случайный 4-значный код
    code = str(random.randint(1000, 9999))
    if test_mode:
        print(f"(DEBUG: Код самоуничтожения: {code})")  # Подсказка для теста

    # Дадим игроку 3 попытки
    for attempt_num in range(3):
        remaining_attempts = 3 - attempt_num
        prompt = f"Введите 4-значный код [{remaining_attempts} попытк{'а' if remaining_attempts==1 else 'и'}]: "
        attempt = safe_input(prompt)

        if not attempt.isdigit() or len(attempt) != 4:
            print("Ошибка ввода. Код должен состоять из 4 цифр.")
            continue  # Попытка не засчитывается

        if attempt == code:
            print("\n[КОД ПРИНЯТ]")
            print("Система самоуничтожения активирована! Сирены взвыли!")
            print(
                "У вас есть немного времени, чтобы добраться до спасательной капсулы!"
            )
            return True  # Успех
        else:
            print("[ДОСТУП ОТКЛОНЕН]")
            if remaining_attempts > 1:
                # Дадим подсказку (больше/меньше)
                if int(attempt) < int(code):
                    print("Подсказка: Загаданный код больше.")
                else:
                    print("Подсказка: Загаданный код меньше.")
            else:
                print("Попытки исчерпаны. Терминал блокируется!")

    return False  # Провал


def select_location():
    """
    Позволяет игроку выбрать локацию или использовать предмет.
    Возвращает:
        - Имя локации (str) для перехода.
        - "WIN_BRIDGE" (str) если игра выиграна на мостике.
        - None если использован предмет или действие отменено/не удалось.
    """
    global captain_defeated, bridge_puzzle_attempted  # Указываем, что будем менять глобальные переменные

    while True:
        print("\nКуда отправиться?")
        # Получаем список кортежей (ключ, имя) из словаря локаций
        available_locations = list(locations.items())

        for idx, (key, name) in enumerate(available_locations):
            # Добавим пометку для мостика
            if key == "bridge":
                if not captain_defeated:
                    print(f"({idx+1}) {name} (Путь прегражден!)")
                elif captain_defeated and not bridge_puzzle_attempted:
                    print(f"({idx+1}) {name} (Путь свободен)")
                else:  # Капитан побежден, попытка была
                    print(f"({idx+1}) {name} (Терминал заблокирован)")
            else:
                print(f"({idx+1}) {name}")

        print("\n(0) Использовать предмет из инвентаря")
        choice = safe_input("Выберите действие: ")

        if choice == "0":
            if use_item():
                return None  # Предмет использован, ход засчитан, но локация не меняется
            else:
                continue  # Неудачное использование или отмена, остаемся в меню выбора

        elif choice.isdigit():
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(available_locations):
                loc_key, loc_name = available_locations[choice_idx]

                # --- Особая логика для Мостика ---
                if loc_key == "bridge":
                    if not captain_defeated:
                        print(
                            f"\nВы пытаетесь пройти на '{loc_name}', но путь преграждает..."
                        )
                        # Находим данные Зомби-капитана
                        captain_monster_data = next(
                            (m for m in monsters if m["name"] == "Зомби-капитан"), None
                        )
                        if not captain_monster_data:
                            print("ОШИБКА КОНФИГУРАЦИИ: Зомби-капитан не найден!")
                            return None  # Предотвращаем падение

                        # Начинаем бой с КОПИЕЙ данных капитана
                        fight_result = fight(captain_monster_data.copy())

                        if fight_result == "win":
                            print(f"Путь на '{loc_name}' свободен.")
                            captain_defeated = True  # Отмечаем победу
                            # Сразу после победы предлагаем решить загадку
                            if solve_bridge_puzzle():
                                return "WIN_BRIDGE"  # Сигнал победы в игре!
                            else:
                                # Загадка не решена, bridge_puzzle_attempted уже True
                                print(
                                    "Вы не смогли активировать систему. Нужно искать другой путь или ждать..."
                                )
                                return None  # Остаемся в меню выбора локации
                        elif fight_result == "flee":
                            print(f"Вы отступили от '{loc_name}'.")
                            return None  # Остаемся в меню выбора локации
                        else:  # Игрок погиб в бою
                            # Основной цикл игры обработает player.is_alive() == False
                            return None  # Остаемся в меню (хотя игра скоро закончится)

                    elif captain_defeated and not bridge_puzzle_attempted:
                        # Капитан побежден, но загадку еще не пытались решить (маловероятно при текущей логике, но пусть будет)
                        print(f"\nВы входите на '{loc_name}'. Путь свободен.")
                        if solve_bridge_puzzle():
                            return "WIN_BRIDGE"
                        else:
                            print("Вы не смогли активировать систему.")
                            return None
                    else:  # Капитан побежден и попытка решения загадки была
                        print(
                            f"\nВы снова на '{loc_name}'. Терминал самоуничтожения заблокирован."
                        )
                        # Ничего больше здесь сделать нельзя
                        return None  # Остаемся в меню выбора

                # --- Обычные локации ---
                else:
                    print(f"\nВы направились в '{loc_name}'")
                    return loc_name  # Возвращаем имя локации для дальнейших действий
            else:
                print("Неверный номер локации!")
        else:
            print("Неверный ввод! Введите номер.")


def play_game():
    """Основной игровой цикл."""
    global start_time, player, captain_defeated, bridge_puzzle_attempted  # Объявим изменяемые глобальные переменные
    # Сброс состояния перед началом новой игры
    player = Player()
    captain_defeated = False
    bridge_puzzle_attempted = False
    start_time = time.time()  # Запускаем таймер

    # Стартовое сообщение
    print("\n" + "=" * 35)
    print("=== Добро пожаловать на станцию 'Гелиос-9' ===")
    print("=" * 35)
    print(
        """
Тьма.
Ты приходишь в себя в аварийной капсуле. В ушах звенит.
На языке металлический привкус. С трудом открываешь глаза —
аварийные огни мигают красным. Станция 'Гелиос-9' лежит в агонии.
Твои лёгкие сжимаются от зловонного, тяжёлого воздуха.
Где-то вдалеке слышатся странные звуки — отдалённые стоны
или скрежет когтей по металлу... Твоя цель - выжить и найти способ сбежать.
"""
    )

    location_result = None  # Хранит результат выбора локации

    # Основной цикл игры
    while player.is_alive():
        # 1. Проверка времени
        if not check_time():
            break  # Время вышло, конец игры

        # 2. Показать статус
        show_status()

        # 3. Выбор действия (локация или предмет)
        location_result = (
            select_location()
        )  # Может вернуть имя локации, None или "WIN_BRIDGE"

        # 4. Обработка результата выбора
        if location_result == "WIN_BRIDGE":
            # Победа через мостик! Выходим из цикла.
            break
        elif location_result is None:
            # Игрок использовал предмет, сбежал из боя, не смог войти на мостик,
            # не решил загадку или отменил действие.
            # Локация не меняется, но время идет.
            print("\nХод продолжается...")
            # Прогресс статуса происходит всегда, если игрок жив
            progress_status()
            # Пауза для читаемости
            time.sleep(1)
            continue  # Переходим к следующей итерации цикла (снова показать статус и выбор)
        else:
            # Игрок успешно выбрал и вошел в обычную локацию
            current_location_name = location_result

            # 5. Действия в локации (если вошли)
            search_area(current_location_name)

            # Проверяем, жив ли игрок после обыска (мало ли что)
            if not player.is_alive():
                break

            random_encounter(current_location_name)

            # Проверяем, жив ли игрок после возможного боя
            if not player.is_alive():
                break

            # 6. Прогресс статуса (голод, жажда и т.д.)
            progress_status()

            # 7. Пауза перед следующим ходом
            print("\n...")  # Небольшой индикатор паузы
            time.sleep(1)  # Пауза в 1 секунду

    # --- Конец игры ---
    elapsed_time = time.time() - start_time
    print("\n" + "=" * 35)
    print("=== ИГРА ОКОНЧЕНА ===")
    print("=" * 35)

    # Определяем причину окончания игры
    if location_result == "WIN_BRIDGE" and player.is_alive():
        print("\nСирены воют! Таймер самоуничтожения запущен!")
        print("Вы бежите к спасательной капсуле и в последнюю секунду стартуете...")
        print("Станция 'Гелиос-9' взрывается позади вас яркой вспышкой!")
        print("\n🎉 ПОЗДРАВЛЯЕМ С ПОБЕДОЙ! 🎉")
    elif not player.is_alive():
        print("\nВы не смогли выжить на станции 'Гелиос-9'.")
        # Уточним причину смерти
        if player.health <= 0:
            print("Причина: Смертельные раны.")
        # Проверки голода/жажды/инфекции/радиации теперь внутри is_alive, но можно добавить сюда для ясности
        elif player.hunger >= 100:
            print("Причина: Смерть от голода.")
        elif player.thirst >= 100:
            print("Причина: Смерть от жажды.")
        elif player.infection >= 100:
            print("Причина: Инфекция захватила организм.")
        elif player.radiation >= 100:
            print("Причина: Смертельная доза радиации.")
        else:
            print(
                "Причина: Неизвестна (возможно, комбинация факторов)."
            )  # На всякий случай
        print("\n💀 КОНЕЦ ИГРЫ 💀")
    elif elapsed_time > 600:  # Время вышло, но игрок еще жив
        print("\nВремя вышло! Системы жизнеобеспечения отказали окончательно.")
        print("Вы не смогли найти способ спастись вовремя.")
        print("\n💀 КОНЕЦ ИГРЫ 💀")
    else:
        # Сюда не должны попасть, но на всякий случай
        print("\nИгра завершена по неизвестной причине.")

    print(f"Время выживания: {int(elapsed_time)} секунд.")
    print("=" * 35)


# Запуск игры
if __name__ == "__main__":
    # test_mode = True # Раскомментируйте для автоматического прохождения по predefined_inputs
    play_game()
