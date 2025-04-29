# -*- coding: utf-8 -*-
import random
from sqlite3 import Time
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
        self.bridge_unlocked = False  # Новый флаг для доступа на мостик

    def is_alive(self):
        return self.health > 0 and self.infection < 100 and self.radiation < 100

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
}

# Монстры (добавлен Зомби-капитан)
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
    {
        "name": "Зомби-капитан",
        "health": 120,
        "full_health": 120,
        "damage": 30,
        "desc": "Перед вами стоит фигура в потрёпанной капитанской форме. Его лицо бледное, глаза мутные, но он всё ещё держит в руке бластер.",
        "special": True,  # Особый монстр для мостика
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
    "bridge": "Мостик корабля",
}

# Инициализация игрока
player = Player()

# Подсчёт времени
start_time = time.time()

# Заранее заданные ответы для тестирования (расширено!)
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
    ]
)


def print_with_pause(text, delay=1):
    print(text)  # Печатает новую строку после завершения текста
    time.sleep(delay)


print_with_pause(
    """
=== Добро пожаловать на станцию 'Гелиос-9' ===    

Тьма.
Ты приходишь в себя в аварийной капсуле. В ушах звенит. На языке металлический привкус.
С трудом открываешь глаза — аварийные огни мигают красным. Станция "Гелиос-9" лежит в агонии.
Твои лёгкие сжимаются от зловонного, тяжёлого воздуха.
Где-то вдалеке слышатся странные звуки — отдалённые стоны или скрежет когтей по металлу.
"""
)


def safe_input(prompt):
    try:
        if test_mode:
            value = next(predefined_inputs)
            print(f"{prompt}{value}")
        else:
            value = input(prompt)
        return value
    except StopIteration:
        print(f"{prompt}2")
        return "2"


def show_status():
    print("------------------------------------")
    print(
        f"\n[СТАТУС] Здоровье: {player.health}% | Жажда: {player.thirst}% | Голод: {player.hunger}% | Радиация: {player.radiation}% | Инфекция: {player.infection}%"
    )
    print(
        f"[ИНВЕНТАРЬ] ({len(player.inventory)}/{player.inventory_limit()}): {', '.join(player.inventory) if player.inventory else 'Пусто'}"
    )


def search_area(location):
    print_with_pause("\nВы обыскиваете помещение...")
    found = random.choices(list(items.keys()), k=2)
    for f in found:
        if (
            (f == "pistol" and player.weapon)
            or (f == "gasmask" and player.has_gasmask)
            or (f == "armor" and player.has_armor)
            or (f == "big_backpack" and player.backpack_size > 5)
        ):
            continue
        if random.randint(1, 100) <= (20 if f in ["pistol", "ammo"] else 70):
            if f == "gasmask":
                player.has_gasmask = True
                print_with_pause(f"Вы нашли и надели: {items[f]}")
            elif f == "armor":
                player.has_armor = True
                print_with_pause(f"Вы нашли и надели: {items[f]}")
            elif f == "big_backpack":
                player.backpack_size = 10
                print_with_pause(
                    f"Вы нашли: {items[f]}! Теперь ваш инвентарь вмещает больше предметов."
                )
            elif f == "pistol":
                player.weapon = items[f]
                print_with_pause(f"Вы нашли оружие: {items[f]}!")
            else:
                if len(player.inventory) < player.inventory_limit():
                    player.inventory.append(items[f])
                    print_with_pause(f"Вы нашли: {items[f]}")
                else:
                    print_with_pause("Нет места в инвентаре!")


def random_encounter(location):
    if location == "Мостик корабля" and not player.bridge_unlocked:
        # Специальный монстр для мостика
        monster = next(m for m in monsters if m["name"] == "Зомби-капитан")
        print_with_pause(
            f"\n{monster['desc']}\n[ОПАСНОСТЬ] На вас нападает {monster['name']}!"
        )
        fight(monster.copy())
        if monster["health"] <= 0:
            player.bridge_unlocked = True
            print_with_pause(
                "\nВы победили капитана. С его тела вы снимаете карточку доступа к панели управления!"
            )
            bridge_puzzle()
    elif random.randint(1, 100) <= 40:
        monster = random.choice([m for m in monsters if not m.get("special", False)])
        print_with_pause(
            f"\n{monster['desc']}\n[ОПАСНОСТЬ] На вас нападает {monster['name']}!"
        )
        fight(monster.copy())


def bridge_puzzle():
    print("\nПеред вами панель управления с цифровым замком.")
    print("На экране мигает сообщение: 'Введите код из 3 цифр'")
    print_with_pause("Подсказка: сумма цифр равна 10, произведение равно 36")

    code = "244"  # Простой код для примера (2+4+4=10, 2*4*4=36)
    attempts = 3

    while attempts > 0:
        guess = safe_input(f"Попытка {4 - attempts}/3. Введите код: ")
        if guess == code:
            print("\nДоступ разрешен! Активирую режим самоуничтожения...")
            print("Станция будет уничтожена через 60 секунд.")
            print_with_pause("Вы бежите к спасательной капсуле...")
            time.sleep(3)
            print_with_pause("\nКапсула успешно стартовала! Вы спаслись!")
            player.health = 0  # Завершаем игру "победой"
            return True
        else:
            attempts -= 1
            print("Неверный код! Доступ запрещен.")
            if attempts > 0:
                print(f"Осталось попыток: {attempts}")

    print("\nСистема заблокирована! Самоуничтожение невозможно.")
    return False


def get_monster_status(monster):
    monster_health_status = "здоров"  # Default status
    for status in health_status:
        if monster["health"] <= monster["full_health"] * status["share"]:
            monster_health_status = status["status"]
            break  # Exit loop once the appropriate status is found

    return monster_health_status


def fight(monster):
    while monster["health"] > 0 and player.is_alive():
        action = safe_input("\n(1) Атаковать  (2) Убежать > ")
        if action == "1":
            # Атака игрока
            if player.weapon == items["pistol"]:
                # Проверяем наличие патронов
                try:
                    ammo_index = player.inventory.index(items["ammo"])
                    player.inventory.pop(ammo_index)  # Тратим один патрон
                    damage = random.randint(25, 40)  # Увеличим урон от пистолета
                    print("Вы стреляете из пистолета!")
                except ValueError:
                    print("У вас нет патронов! Атакуете врукопашную.")
                    damage = random.randint(5, 10)
            elif player.weapon:  # Другое оружие (если будет)
                damage = random.randint(15, 25)  # Пример для другого оружия
                print(f"Вы атакуете с помощью {player.weapon}!")
            else:  # Рукопашная атака
                damage = random.randint(5, 10)
                print("Вы бьете кулаками!")

            monster["health"] -= damage
            print(f"Вы нанесли {damage} урона.")
            if monster["health"] <= 0:
                monster_status = get_monster_status(0, monster["full_health"])
                print(f"Монстр {monster_status}.")
                break  # Монстр побежден, выходим из цикла атаки монстра
            else:
                monster_status = get_monster_status(
                    monster["health"], monster["full_health"]
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

        if monster["health"] > 0:
            hit = monster["damage"]
            if player.has_armor:
                hit = int(hit * 0.7)  # Броня поглощает 30% урона
            player.health -= hit
            print(f"{monster['name']} наносит вам {hit} урона!")
            print_with_pause(f"Ваше здоровье: {player.health}%")
        else:
            print_with_pause(f"\nВы победили {monster['name']}!")
            if (
                monster["name"] == "Мутант-сталкер"
                and len(player.inventory) < player.inventory_limit()
            ):
                player.inventory.append(items["ammo"])
                print_with_pause("Вы нашли патроны!")
            elif (
                monster["name"] == "Раздутый ужас"
                and len(player.inventory) < player.inventory_limit()
            ):
                player.inventory.append(items["antivirus"])
                print_with_pause("Вы нашли антивирусный шприц!")
            return

 
def use_item():
    if not player.inventory:
        print("\nУ вас нет предметов!")
        return

    print("\nВаши предметы:")
    for idx, item in enumerate(player.inventory):
        print(f"({idx}) {item}")

    choice = safe_input("Выберите номер предмета для использования: ")
    if choice.isdigit():
        choice = int(choice)
        if 0 <= choice < len(player.inventory):
            item = player.inventory.pop(choice)
            if item == items["water"]:
                player.thirst = max(player.thirst - 30, 0)
                print("Вы утолили жажду.")
            elif item == items["food"]:
                player.hunger = max(player.hunger - 30, 0)
                print("Вы утолили голод.")
            elif item == items["medkit"]:
                player.health = min(player.health + 40, 100)
                print("Вы восстановили здоровье.")
            elif item == items["antivirus"]:
                player.infection = max(player.infection - 50, 0)
                print("Вы замедлили распространение вируса.")


def progress_status():
    player.hunger += 5
    player.thirst += 5
    if player.hunger >= 100 or player.thirst >= 100:
        print_with_pause("\nВы страдаете от голода или жажды!")
        player.health -= 10
    if not player.has_gasmask:
        print_with_pause("\nВы дышите токсичным воздухом")
        player.infection += 5
    player.radiation += random.randint(0, 3)
    time.sleep(1)


def select_location():
    while True:
        print("\nДоступные локации:")
        for idx, loc in enumerate(locations.values()):
            print(f"({idx+1}) {loc}")
        print("\n(0) Использовать предмет")
        choice = safe_input("Выберите действие: ")
        if choice == "0":
            use_item()
        elif choice.isdigit() and int(choice) - 1 in range(len(locations)):
            loc_name = list(locations.values())[int(choice) - 1]
            print_with_pause(f"\nВы направились в {loc_name}")
            return loc_name
        else:
            print("Неверный ввод!")


def show_lose_condition():
    print("\nВы погибли")
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


def play_game():

    while player.is_alive():
        show_status()
        loc_name = select_location()
        search_area(loc_name)
        random_encounter(loc_name)

        if player.is_alive():
            progress_status()

    if not player.is_alive() and player.health <= 0 and player.bridge_unlocked:
        print("\nПоздравляем! Вы активировали самоуничтожение станции и спаслись!")
    elif player.is_alive():
        print("\nПоздравляем! Вы выжили и спаслись!")
    else:
        show_lose_condition()
    print(f"Время выживания: {int(time.time() - start_time)} секунд.")


if __name__ == "__main__":
    play_game()
