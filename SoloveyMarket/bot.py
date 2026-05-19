from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramNetworkError, TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from config import BOT_TOKEN, ADMIN_ID

from db import (
    add_executor,
    set_executor_subcategories,
    get_service_subcategories_flat,
    get_executors_by_subcategory,
    create_response,
    create_location_request,
    get_client,
    trust_label,
    get_locations,
    executor_mark_done,
    create_dispute,
    get_executor,
    get_executor_profile,
    set_executor_availability,
    set_executor_locations,
    get_executor_locations,
)


bot = Bot(BOT_TOKEN)
dp = Dispatcher()


async def safe_send_message(chat_id, text, **kwargs):
    try:
        return await bot.send_message(
            chat_id,
            text,
            **kwargs
        )
    except (TelegramNetworkError, TelegramBadRequest, TelegramForbiddenError) as e:
        print(f"Telegram send failed to {chat_id}: {type(e).__name__}: {e}")
        return None
    except Exception as e:
        print(f"Unexpected Telegram send failed to {chat_id}: {type(e).__name__}: {e}")
        return None


STATUS_NAMES = {
    "new": "🆕 Новая",
    "accepted": "✅ Принята",
    "rejected": "❌ Отклонена",
    "searching_executor": "👷 Ищем исполнителя",
    "in_work": "🔧 В работе",
    "executor_done": "🟡 Ожидает подтверждения",
    "dispute": "⚠️ Спор",
    "done": "✅ Выполнена",
    "canceled": "🚫 Отменена",
}


class ExecutorRegisterState(StatesGroup):
    waiting_locations = State()
    waiting_service_category = State()
    waiting_subcategories = State()


class ExecutorProfileState(StatesGroup):
    waiting_new_locations = State()
    changing_services_category = State()
    changing_services_subcategories = State()


class NewLocationState(StatesGroup):
    waiting_name = State()
    waiting_district = State()
    waiting_region = State()
    waiting_description = State()


def make_executor_start_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👷 Регистрация исполнителя")],
            [KeyboardButton(text="👤 Мой профиль")],
            [KeyboardButton(text="➕ Моего населённого пункта нет")],
        ],
        resize_keyboard=True
    )


def make_profile_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📂 Мои услуги")],
            [KeyboardButton(text="✏️ Изменить услуги")],
            [KeyboardButton(text="📍 Мои населённые пункты")],
            [KeyboardButton(text="🟢 Принимаю заявки"), KeyboardButton(text="🔴 Не принимаю заявки")],
            [KeyboardButton(text="⬅️ Главное меню")],
        ],
        resize_keyboard=True
    )


def make_locations_multi_kb(selected_locations=None):
    selected_locations = selected_locations or []
    rows = []

    for loc in get_locations():
        name = loc["name"]
        prefix = "✅ " if name in selected_locations else "☐ "
        rows.append([KeyboardButton(text=f"{prefix}{name}")])

    rows.append([KeyboardButton(text="✅ Завершить выбор")])
    rows.append([KeyboardButton(text="➕ Моего населённого пункта нет")])

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True
    )


def clean_location_text(text):
    return (
        text
        .replace("✅ ", "")
        .replace("☐ ", "")
        .strip()
    )


def get_subcategories():
    return list(get_service_subcategories_flat())


def get_category_map():
    categories = {}

    for sub in get_subcategories():
        category_name = sub["category_name"]

        if category_name not in categories:
            categories[category_name] = {
                "name": category_name,
                "emoji": sub["category_emoji"],
                "items": []
            }

        categories[category_name]["items"].append(sub)

    return categories


def make_service_categories_kb(selected_ids=None):
    selected_ids = selected_ids or []
    categories = get_category_map()
    rows = []

    for category in categories.values():
        selected_count = 0

        for sub in category["items"]:
            if sub["id"] in selected_ids:
                selected_count += 1

        suffix = f" ✅ {selected_count}" if selected_count else ""

        rows.append([
            KeyboardButton(
                text=f"{category['emoji']} {category['name']}{suffix}"
            )
        ])

    rows.append([KeyboardButton(text="✅ Завершить выбор")])

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True
    )


def normalize_category_button(text):
    categories = get_category_map()

    for category in categories.values():
        base = f"{category['emoji']} {category['name']}"

        if text == base or text.startswith(base + " ✅"):
            return category["name"]

    return None


def make_subcategories_kb(category_name, selected_ids=None):
    selected_ids = selected_ids or []
    selected_ids = set(selected_ids)
    categories = get_category_map()
    category = categories.get(category_name)

    rows = []

    if category:
        for sub in category["items"]:
            prefix = "✅ " if sub["id"] in selected_ids else "☐ "
            dispatcher_mark = " 🧑‍💼" if sub["requires_dispatcher"] else ""
            rows.append([
                KeyboardButton(
                    text=f"{prefix}{sub['name']}{dispatcher_mark}"
                )
            ])

    rows.append([KeyboardButton(text="⬅️ К разделам")])
    rows.append([KeyboardButton(text="✅ Завершить выбор")])

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True
    )


def find_subcategory_by_name(category_name, text):
    clean = (
        text
        .replace("✅ ", "")
        .replace("☐ ", "")
        .replace(" 🧑‍💼", "")
        .strip()
    )

    categories = get_category_map()
    category = categories.get(category_name)

    if not category:
        return None

    for sub in category["items"]:
        if sub["name"] == clean:
            return sub

    return None


def selected_services_text(selected_ids):
    selected_ids = set(selected_ids)
    result = []

    for sub in get_subcategories():
        if sub["id"] in selected_ids:
            result.append(
                f"{sub['category_emoji']} {sub['category_name']} → {sub['name']}"
            )

    return result


def current_subscription_ids(executor_id):
    profile = get_executor_profile(executor_id)

    if not profile:
        return []

    return [row["subcategory_id"] for row in profile["subscriptions"]]


def current_location_names(executor_id):
    rows = get_executor_locations(executor_id)
    return [row["location_name"] for row in rows]


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "Здравствуйте! Здесь можно зарегистрироваться исполнителем и получать заявки только по выбранным услугам и населённым пунктам.",
        reply_markup=make_executor_start_kb()
    )


@dp.message(F.text == "⬅️ Главное меню")
async def back_to_main(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Главное меню.",
        reply_markup=make_executor_start_kb()
    )


@dp.message(F.text == "👷 Регистрация исполнителя")
async def executor_register_start(message: Message, state: FSMContext):
    await state.set_state(ExecutorRegisterState.waiting_locations)
    await state.update_data(selected_locations=[])

    await message.answer(
        "Выберите один или несколько населённых пунктов, где вы работаете.",
        reply_markup=make_locations_multi_kb([])
    )


@dp.message(ExecutorRegisterState.waiting_locations)
async def executor_register_locations(message: Message, state: FSMContext):
    if message.text == "➕ Моего населённого пункта нет":
        await state.clear()
        await new_location_start(message, state)
        return

    data = await state.get_data()
    selected_locations = data.get("selected_locations", [])

    if message.text == "✅ Завершить выбор":
        if not selected_locations:
            await message.answer(
                "Выберите хотя бы один населённый пункт.",
                reply_markup=make_locations_multi_kb(selected_locations)
            )
            return

        await state.update_data(
            selected_subcategory_ids=[],
            current_category=None
        )

        await state.set_state(ExecutorRegisterState.waiting_service_category)

        await message.answer(
            "Теперь выберите раздел услуг.\n\n"
            "Услуги можно выбирать без лимита. Обычные заявки будут приходить автоматически. "
            "Крупные денежные заявки отмечены значком 🧑‍💼 и проходят через диспетчера.",
            reply_markup=make_service_categories_kb([])
        )
        return

    location_name = clean_location_text(message.text)
    valid_locations = [loc["name"] for loc in get_locations()]

    if location_name not in valid_locations:
        await message.answer(
            "Выберите населённый пункт кнопкой ниже.",
            reply_markup=make_locations_multi_kb(selected_locations)
        )
        return

    if location_name in selected_locations:
        selected_locations.remove(location_name)
    else:
        selected_locations.append(location_name)

    await state.update_data(selected_locations=selected_locations)

    await message.answer(
        f"Выбрано населённых пунктов: {len(selected_locations)}",
        reply_markup=make_locations_multi_kb(selected_locations)
    )


@dp.message(ExecutorRegisterState.waiting_service_category)
async def executor_register_service_category(message: Message, state: FSMContext):
    data = await state.get_data()
    selected_ids = data.get("selected_subcategory_ids", [])

    if message.text == "✅ Завершить выбор":
        await finish_executor_registration(message, state)
        return

    category_name = normalize_category_button(message.text)

    if not category_name:
        await message.answer(
            "Выберите раздел кнопкой ниже.",
            reply_markup=make_service_categories_kb(selected_ids)
        )
        return

    await state.update_data(current_category=category_name)
    await state.set_state(ExecutorRegisterState.waiting_subcategories)

    await message.answer(
        f"Раздел: {category_name}\n\n"
        f"Отметьте конкретные услуги:",
        reply_markup=make_subcategories_kb(category_name, selected_ids)
    )


@dp.message(ExecutorRegisterState.waiting_subcategories)
async def executor_register_subcategories(message: Message, state: FSMContext):
    await handle_subcategory_selection(
        message=message,
        state=state,
        category_state=ExecutorRegisterState.waiting_service_category,
        finish_func=finish_executor_registration
    )


async def handle_subcategory_selection(message: Message, state: FSMContext, category_state, finish_func):
    data = await state.get_data()
    selected_ids = data.get("selected_subcategory_ids", [])
    current_category = data.get("current_category")

    if message.text == "⬅️ К разделам":
        await state.set_state(category_state)
        await message.answer(
            "Выберите следующий раздел или завершите выбор.",
            reply_markup=make_service_categories_kb(selected_ids)
        )
        return

    if message.text == "✅ Завершить выбор":
        await finish_func(message, state)
        return

    sub = find_subcategory_by_name(current_category, message.text)

    if not sub:
        await message.answer(
            "Выберите услугу кнопкой ниже.",
            reply_markup=make_subcategories_kb(current_category, selected_ids)
        )
        return

    sub_id = sub["id"]

    if sub_id in selected_ids:
        selected_ids.remove(sub_id)
    else:
        selected_ids.append(sub_id)

    await state.update_data(selected_subcategory_ids=selected_ids)

    await message.answer(
        f"Выбрано услуг: {len(selected_ids)}\nОграничений по количеству услуг нет.",
        reply_markup=make_subcategories_kb(current_category, selected_ids)
    )


async def finish_executor_registration(message: Message, state: FSMContext):
    data = await state.get_data()
    selected_ids = data.get("selected_subcategory_ids", [])
    selected_locations = data.get("selected_locations", [])

    if not selected_locations:
        await message.answer(
            "Выберите хотя бы один населённый пункт.",
            reply_markup=make_locations_multi_kb(selected_locations)
        )
        await state.set_state(ExecutorRegisterState.waiting_locations)
        return

    if not selected_ids:
        await message.answer(
            "Выберите хотя бы одну услугу.",
            reply_markup=make_service_categories_kb(selected_ids)
        )
        await state.set_state(ExecutorRegisterState.waiting_service_category)
        return

    selected_names = selected_services_text(selected_ids)
    main_service_name = selected_names[0] if selected_names else "Исполнитель"

    add_executor(
        tg_id=message.from_user.id,
        name=message.from_user.full_name,
        category=main_service_name,
        location_name=", ".join(selected_locations)
    )

    set_executor_locations(
        executor_id=message.from_user.id,
        location_names=selected_locations
    )

    set_executor_subcategories(
        executor_id=message.from_user.id,
        subcategory_ids=selected_ids
    )

    await send_registration_result(
        message=message,
        selected_names=selected_names,
        selected_locations=selected_locations
    )

    await state.clear()


async def send_registration_result(message: Message, selected_names, selected_locations):
    result = (
        f"✅ Готово.\n\n"
        f"📍 Населённые пункты:\n"
    )

    for name in selected_locations:
        result += f"— {name}\n"

    result += (
        f"\n🔔 Вы будете получать заявки только по выбранным услугам и населённым пунктам.\n\n"
        f"📂 Услуги:\n"
    )

    for name in selected_names:
        result += f"— {name}\n"

    await message.answer(result, reply_markup=make_executor_start_kb())


@dp.message(F.text == "👤 Мой профиль")
async def executor_profile(message: Message):
    profile = get_executor_profile(message.from_user.id)

    if not profile:
        await message.answer(
            "Вы ещё не зарегистрированы как исполнитель.",
            reply_markup=make_executor_start_kb()
        )
        return

    executor = profile["executor"]
    subscriptions = profile["subscriptions"]
    locations = profile.get("locations", [])

    status = "🟢 принимает заявки" if executor["is_available"] else "🔴 не принимает заявки"

    text = (
        f"👤 Мой профиль\n\n"
        f"👷 Имя: {executor['name']}\n"
        f"🔔 Статус: {status}\n"
        f"⭐ Рейтинг: {executor['rating']}\n"
        f"✅ Выполнено: {executor['completed_count']}\n"
        f"❌ Отмен: {executor['cancel_count']}\n"
        f"⚠️ Жалоб: {executor['complaint_count']}\n"
        f"💬 Откликов: {executor['response_count']}\n"
        f"🤝 Доверие: {executor['trust_score']}\n"
        f"📍 Населённых пунктов: {len(locations)}\n"
        f"📂 Услуг подключено: {len(subscriptions)}"
    )

    await message.answer(
        text,
        reply_markup=make_profile_kb()
    )


@dp.message(F.text == "📂 Мои услуги")
async def executor_my_services(message: Message):
    profile = get_executor_profile(message.from_user.id)

    if not profile:
        await message.answer("Вы ещё не зарегистрированы.")
        return

    subscriptions = profile["subscriptions"]

    if not subscriptions:
        await message.answer("У вас пока нет выбранных услуг.")
        return

    text = "📂 Ваши услуги:\n\n"

    for i, sub in enumerate(subscriptions, start=1):
        dispatcher_text = "через диспетчера" if sub["requires_dispatcher"] else "авто"
        text += (
            f"{i}. {sub['category_emoji']} "
            f"{sub['category_name']} → {sub['subcategory_name']} "
            f"({dispatcher_text})\n"
        )

    await message.answer(
        text,
        reply_markup=make_profile_kb()
    )


@dp.message(F.text == "📍 Мои населённые пункты")
@dp.message(F.text == "📍 Изменить населённый пункт")
async def executor_edit_locations_start(message: Message, state: FSMContext):
    if not get_executor(message.from_user.id):
        await message.answer("Сначала зарегистрируйтесь как исполнитель.")
        return

    selected_locations = current_location_names(message.from_user.id)

    await state.update_data(selected_locations=selected_locations)
    await state.set_state(ExecutorProfileState.waiting_new_locations)

    await message.answer(
        "Отметьте населённые пункты, где вы готовы работать.",
        reply_markup=make_locations_multi_kb(selected_locations)
    )


@dp.message(ExecutorProfileState.waiting_new_locations)
async def executor_edit_locations_finish(message: Message, state: FSMContext):
    if message.text == "➕ Моего населённого пункта нет":
        await state.clear()
        await new_location_start(message, state)
        return

    data = await state.get_data()
    selected_locations = data.get("selected_locations", [])

    if message.text == "✅ Завершить выбор":
        if not selected_locations:
            await message.answer(
                "Нужно оставить хотя бы один населённый пункт.",
                reply_markup=make_locations_multi_kb(selected_locations)
            )
            return

        set_executor_locations(
            executor_id=message.from_user.id,
            location_names=selected_locations
        )

        await state.clear()

        text = "📍 Населённые пункты обновлены:\n\n"

        for loc in selected_locations:
            text += f"— {loc}\n"

        await message.answer(text, reply_markup=make_profile_kb())
        return

    location_name = clean_location_text(message.text)
    valid_locations = [loc["name"] for loc in get_locations()]

    if location_name not in valid_locations:
        await message.answer(
            "Выберите населённый пункт кнопкой ниже.",
            reply_markup=make_locations_multi_kb(selected_locations)
        )
        return

    if location_name in selected_locations:
        selected_locations.remove(location_name)
    else:
        selected_locations.append(location_name)

    await state.update_data(selected_locations=selected_locations)

    await message.answer(
        f"Выбрано населённых пунктов: {len(selected_locations)}",
        reply_markup=make_locations_multi_kb(selected_locations)
    )


@dp.message(F.text == "✏️ Изменить услуги")
async def executor_edit_services(message: Message, state: FSMContext):
    profile = get_executor_profile(message.from_user.id)

    if not profile:
        await message.answer("Сначала зарегистрируйтесь как исполнитель.")
        return

    selected_ids = current_subscription_ids(message.from_user.id)

    await state.update_data(
        selected_subcategory_ids=selected_ids,
        current_category=None
    )

    await state.set_state(ExecutorProfileState.changing_services_category)

    await message.answer(
        "Выберите раздел, чтобы изменить услуги.",
        reply_markup=make_service_categories_kb(selected_ids)
    )


@dp.message(ExecutorProfileState.changing_services_category)
async def executor_edit_services_category(message: Message, state: FSMContext):
    data = await state.get_data()
    selected_ids = data.get("selected_subcategory_ids", [])

    if message.text == "✅ Завершить выбор":
        await finish_executor_services_update(message, state)
        return

    category_name = normalize_category_button(message.text)

    if not category_name:
        await message.answer(
            "Выберите раздел кнопкой ниже.",
            reply_markup=make_service_categories_kb(selected_ids)
        )
        return

    await state.update_data(current_category=category_name)
    await state.set_state(ExecutorProfileState.changing_services_subcategories)

    await message.answer(
        f"Раздел: {category_name}\n\n"
        f"Отметьте нужные услуги:",
        reply_markup=make_subcategories_kb(category_name, selected_ids)
    )


@dp.message(ExecutorProfileState.changing_services_subcategories)
async def executor_edit_services_subcategories(message: Message, state: FSMContext):
    await handle_subcategory_selection(
        message=message,
        state=state,
        category_state=ExecutorProfileState.changing_services_category,
        finish_func=finish_executor_services_update
    )


async def finish_executor_services_update(message: Message, state: FSMContext):
    data = await state.get_data()
    selected_ids = data.get("selected_subcategory_ids", [])
    selected_locations = current_location_names(message.from_user.id)

    if not selected_ids:
        await message.answer(
            "Нужно оставить хотя бы одну услугу.",
            reply_markup=make_service_categories_kb(selected_ids)
        )
        await state.set_state(ExecutorProfileState.changing_services_category)
        return

    set_executor_subcategories(
        executor_id=message.from_user.id,
        subcategory_ids=selected_ids
    )

    selected_names = selected_services_text(selected_ids)

    await send_registration_result(
        message=message,
        selected_names=selected_names,
        selected_locations=selected_locations
    )

    await state.clear()


@dp.message(F.text == "🟢 Принимаю заявки")
async def executor_available_on(message: Message):
    if not get_executor(message.from_user.id):
        await message.answer("Сначала зарегистрируйтесь как исполнитель.")
        return

    set_executor_availability(message.from_user.id, True)

    await message.answer(
        "🟢 Готово. Теперь вы снова получаете подходящие заявки.",
        reply_markup=make_profile_kb()
    )


@dp.message(F.text == "🔴 Не принимаю заявки")
async def executor_available_off(message: Message):
    if not get_executor(message.from_user.id):
        await message.answer("Сначала зарегистрируйтесь как исполнитель.")
        return

    set_executor_availability(message.from_user.id, False)

    await message.answer(
        "🔴 Готово. Новые заявки временно не будут приходить.",
        reply_markup=make_profile_kb()
    )


@dp.message(F.text == "➕ Моего населённого пункта нет")
async def new_location_start(message: Message, state: FSMContext):
    await state.set_state(NewLocationState.waiting_name)
    await message.answer("Введите название населённого пункта:")


@dp.message(NewLocationState.waiting_name)
async def new_location_name(message: Message, state: FSMContext):
    await state.update_data(location_name=message.text)
    await state.set_state(NewLocationState.waiting_district)
    await message.answer("Введите район:")


@dp.message(NewLocationState.waiting_district)
async def new_location_district(message: Message, state: FSMContext):
    await state.update_data(district=message.text)
    await state.set_state(NewLocationState.waiting_region)
    await message.answer("Введите регион:")


@dp.message(NewLocationState.waiting_region)
async def new_location_region(message: Message, state: FSMContext):
    await state.update_data(region=message.text)
    await state.set_state(NewLocationState.waiting_description)
    await message.answer("Кратко опишите населённый пункт и какие услуги там востребованы:")


@dp.message(NewLocationState.waiting_description)
async def new_location_description(message: Message, state: FSMContext):
    data = await state.get_data()

    create_location_request(
        location_name=data["location_name"],
        district=data["district"],
        region=data["region"],
        description=message.text,
        executor_name=message.from_user.full_name,
        executor_tg_id=message.from_user.id
    )

    await message.answer(
        "✅ Запрос отправлен диспетчеру. После проверки населённый пункт появится в системе.",
        reply_markup=make_executor_start_kb()
    )

    if ADMIN_ID:
        await safe_send_message(
            ADMIN_ID,
            f"📍 Новый запрос на населённый пункт\n\n"
            f"🏘 {data['location_name']}\n"
            f"📍 Район: {data['district']}\n"
            f"🌎 Регион: {data['region']}\n\n"
            f"📝 {message.text}\n\n"
            f"👷 От: {message.from_user.full_name}\n"
            f"🆔 TG ID: {message.from_user.id}"
        )

    await state.clear()


async def notify_admin_new_request(req):
    if not ADMIN_ID:
        return

    text = (
        f"📩 Новая заявка №{req['id']}\n\n"
        f"📂 {req['category']}\n"
        f"🔹 {req['subcategory'] or ''}\n"
        f"📝 {req['description']}\n"
        f"📍 Ориентир: {req['public_location']}\n"
        f"🏠 Точный адрес: {req['private_address']}\n"
        f"📞 {req['phone']}\n\n"
        f"Статус: {STATUS_NAMES.get(req['status'], req['status'])}"
    )

    await safe_send_message(
        ADMIN_ID,
        text
    )


async def notify_admin_status_changed(req):
    if not ADMIN_ID:
        return

    text = (
        f"🔄 Изменён статус заявки №{req['id']}\n\n"
        f"📂 {req['category']}\n"
        f"🔹 {req['subcategory'] or ''}\n"
        f"📍 Ориентир: {req['public_location']}\n"
        f"Статус: {STATUS_NAMES.get(req['status'], req['status'])}"
    )

    if req["dispatcher_comment"]:
        text += f"\n💬 Комментарий: {req['dispatcher_comment']}"

    await safe_send_message(
        ADMIN_ID,
        text
    )


async def notify_executors_search(req):
    subcategory = req["subcategory"]

    executors = get_executors_by_subcategory(
        subcategory,
        req["public_location"]
    )

    client = get_client(req["phone"])

    client_info = "Заказчик: новый"

    if client:
        client_info = (
            f"Заказчик: {trust_label(client['trust_score'])}\n"
            f"Заявок: {client['total_requests']}\n"
            f"Отмен: {client['canceled_requests']}"
        )

    if not executors:
        if ADMIN_ID:
            await safe_send_message(
                ADMIN_ID,
                f"⚠️ По заявке №{req['id']} нет доступных исполнителей.\n"
                f"Категория: {req['category']}\n"
                f"Подкатегория: {subcategory}\n"
                f"Ориентир: {req['public_location']}"
            )
        return 0

    text = (
        f"👷 Нужен исполнитель\n\n"
        f"📌 Заявка №{req['id']}\n"
        f"📂 {req['category']}\n"
        f"🔹 {subcategory or ''}\n"
        f"📝 {req['description']}\n"
        f"📍 Ориентир: {req['public_location']}\n\n"
        f"{client_info}\n\n"
        f"Точный адрес и телефон клиента будут доступны только после назначения."
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Откликнуться",
                    callback_data=f"executor_response:{req['id']}"
                )
            ]
        ]
    )

    sent = 0

    for executor in executors:
        result = await safe_send_message(
            executor["tg_id"],
            text,
            reply_markup=kb
        )

        if result:
            sent += 1

    if ADMIN_ID:
        await safe_send_message(
            ADMIN_ID,
            f"📤 Заявка №{req['id']} отправлена исполнителям.\n"
            f"Категория: {req['category']}\n"
            f"Подкатегория: {subcategory}\n"
            f"Ориентир: {req['public_location']}\n"
            f"Отправлено: {sent}"
        )

    return sent


@dp.callback_query(F.data.startswith("executor_response:"))
async def executor_response(callback):
    request_id = int(callback.data.split(":")[1])
    executor_id = callback.from_user.id

    success = create_response(
        request_id,
        executor_id
    )

    if not success:
        await callback.answer("Вы уже откликались на эту заявку")
        return

    await callback.answer("Отклик отправлен")
    await callback.message.edit_reply_markup(reply_markup=None)

    await callback.message.answer(
        f"✅ Вы откликнулись на заявку №{request_id}. Диспетчер рассмотрит отклик."
    )

    if ADMIN_ID:
        await safe_send_message(
            ADMIN_ID,
            f"💬 Новый отклик на заявку №{request_id}\n\n"
            f"👷 Исполнитель: {callback.from_user.full_name}\n"
            f"🆔 TG ID: {executor_id}"
        )


async def notify_executor_assigned(executor_id, req):
    text = (
        f"✅ Вас назначили исполнителем\n\n"
        f"📌 Заявка №{req['id']}\n"
        f"📂 {req['category']}\n"
        f"🔹 {req['subcategory'] or ''}\n"
        f"📝 {req['description']}\n"
        f"📍 Ориентир: {req['public_location']}\n"
        f"🏠 Точный адрес: {req['private_address']}\n"
        f"📞 Телефон клиента: {req['phone']}\n\n"
        f"Свяжитесь с клиентом и выполните заявку."
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Работа выполнена",
                    callback_data=f"executor_done:{req['id']}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⚠️ Проблема",
                    callback_data=f"executor_problem:{req['id']}"
                )
            ]
        ]
    )

    await safe_send_message(
        executor_id,
        text,
        reply_markup=kb
    )


@dp.callback_query(F.data.startswith("executor_done:"))
async def executor_done_callback(callback):
    request_id = int(callback.data.split(":")[1])
    executor_id = callback.from_user.id

    success = executor_mark_done(
        request_id,
        executor_id
    )

    if not success:
        await callback.answer("Не удалось изменить статус")
        return

    await callback.answer("Заявка отмечена как выполненная")
    await callback.message.edit_reply_markup(reply_markup=None)

    await callback.message.answer(
        "✅ Диспетчер получил информацию о завершении."
    )

    if ADMIN_ID:
        await safe_send_message(
            ADMIN_ID,
            f"✅ Исполнитель сообщил о завершении заявки №{request_id}"
        )


@dp.callback_query(F.data.startswith("executor_problem:"))
async def executor_problem_callback(callback):
    request_id = int(callback.data.split(":")[1])

    create_dispute(
        request_id=request_id,
        initiator_type="executor",
        initiator_id=str(callback.from_user.id),
        reason="Исполнитель сообщил о проблеме"
    )

    await callback.answer("Спор создан")
    await callback.message.edit_reply_markup(reply_markup=None)

    await callback.message.answer(
        "⚠️ Спор отправлен диспетчеру."
    )

    if ADMIN_ID:
        await safe_send_message(
            ADMIN_ID,
            f"⚠️ Исполнитель открыл спор по заявке №{request_id}"
        )


async def notify_location_approved(req):
    if req and req["executor_tg_id"]:
        await safe_send_message(
            req["executor_tg_id"],
            f"✅ Населённый пункт добавлен в систему:\n\n"
            f"🏘 {req['location_name']}\n"
            f"Теперь можно зарегистрироваться исполнителем в этом населённом пункте."
        )


async def start_bot():
    if not BOT_TOKEN:
        print("BOT_TOKEN не указан. Бот не запущен.")
        return

    await dp.start_polling(bot)
