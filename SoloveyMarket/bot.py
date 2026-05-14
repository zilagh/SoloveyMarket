from aiogram import Bot, Dispatcher, F
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

from config import BOT_TOKEN, ADMIN_ID, FREE_CATEGORY_LIMIT, EXTRA_CATEGORY_PRICE

from db import (
    add_executor,
    set_executor_categories,
    get_executors_by_category,
    create_response,
    create_location_request,
    get_client,
    trust_label,
    get_locations,
    executor_mark_done,
    create_dispute,
)


bot = Bot(BOT_TOKEN)
dp = Dispatcher()


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


CATEGORIES = [
    "Доставка",
    "Строительство",
    "Ремонт и мастер",
    "Сантехника",
    "Электрика",
    "Земельные вопросы",
    "Юридические услуги",
    "Уборка",
    "Спецтехника",
]


class ExecutorRegisterState(StatesGroup):
    waiting_location = State()
    waiting_categories = State()


class NewLocationState(StatesGroup):
    waiting_name = State()
    waiting_district = State()
    waiting_region = State()
    waiting_description = State()


def make_executor_start_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👷 Регистрация исполнителя")],
            [KeyboardButton(text="➕ Моего населённого пункта нет")],
        ],
        resize_keyboard=True
    )


def make_locations_kb():
    rows = []

    for loc in get_locations():
        rows.append([KeyboardButton(text=loc["name"])])

    rows.append([KeyboardButton(text="➕ Моего населённого пункта нет")])

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True
    )


def make_categories_multi_kb(selected=None):
    selected = selected or []
    rows = []

    for category in CATEGORIES:
        prefix = "✅ " if category in selected else "☐ "
        rows.append([KeyboardButton(text=prefix + category)])

    rows.append([KeyboardButton(text="✅ Завершить выбор")])

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True
    )


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "Здравствуйте! Здесь можно зарегистрироваться исполнителем и получать заявки по своему району.",
        reply_markup=make_executor_start_kb()
    )


@dp.message(F.text == "👷 Регистрация исполнителя")
async def executor_register_start(message: Message, state: FSMContext):
    await state.set_state(ExecutorRegisterState.waiting_location)

    await message.answer(
        "Выберите населённый пункт, где вы работаете:",
        reply_markup=make_locations_kb()
    )


@dp.message(ExecutorRegisterState.waiting_location)
async def executor_register_location(message: Message, state: FSMContext):
    if message.text == "➕ Моего населённого пункта нет":
        await state.clear()
        await new_location_start(message, state)
        return

    await state.update_data(
        location_name=message.text,
        selected_categories=[]
    )

    await state.set_state(ExecutorRegisterState.waiting_categories)

    await message.answer(
        f"Выберите одну или несколько категорий.\n\n"
        f"Первые {FREE_CATEGORY_LIMIT} категории — бесплатно.\n"
        f"{FREE_CATEGORY_LIMIT + 1}-я и далее — {EXTRA_CATEGORY_PRICE} ₽/мес за каждую.",
        reply_markup=make_categories_multi_kb([])
    )


@dp.message(ExecutorRegisterState.waiting_categories)
async def executor_register_categories(message: Message, state: FSMContext):
    data = await state.get_data()
    selected = data.get("selected_categories", [])

    text = (
        message.text
        .replace("✅ ", "")
        .replace("☐ ", "")
    )

    if message.text == "✅ Завершить выбор":
        if not selected:
            await message.answer(
                "Выберите хотя бы одну категорию.",
                reply_markup=make_categories_multi_kb(selected)
            )
            return

        location_name = data.get("location_name")

        add_executor(
            tg_id=message.from_user.id,
            name=message.from_user.full_name,
            category=selected[0],
            location_name=location_name
        )

        set_executor_categories(
            executor_id=message.from_user.id,
            categories=selected
        )

        paid_count = max(0, len(selected) - FREE_CATEGORY_LIMIT)
        paid_sum = paid_count * EXTRA_CATEGORY_PRICE

        result = (
            f"✅ Регистрация завершена.\n\n"
            f"📍 Населённый пункт: {location_name}\n"
            f"📂 Категории:\n"
        )

        for i, cat in enumerate(selected, start=1):
            if i <= FREE_CATEGORY_LIMIT:
                result += f"— {cat} бесплатно\n"
            else:
                result += f"— {cat} платно\n"

        if paid_count:
            result += (
                f"\n💳 Платных категорий: {paid_count}\n"
                f"К оплате: {paid_sum} ₽/мес\n\n"
                f"Пока платные категории активируются диспетчером вручную."
            )

            if ADMIN_ID:
                await bot.send_message(
                    ADMIN_ID,
                    f"💳 Исполнитель выбрал платные категории\n\n"
                    f"👷 {message.from_user.full_name}\n"
                    f"🆔 TG ID: {message.from_user.id}\n"
                    f"📍 {location_name}\n"
                    f"📂 Всего категорий: {len(selected)}\n"
                    f"💰 К оплате: {paid_sum} ₽/мес"
                )
        else:
            result += "\nВсе выбранные категории подключены бесплатно."

        await message.answer(result)
        await state.clear()
        return

    if text not in CATEGORIES:
        await message.answer(
            "Выберите категорию кнопкой ниже.",
            reply_markup=make_categories_multi_kb(selected)
        )
        return

    if text in selected:
        selected.remove(text)
    else:
        selected.append(text)

    await state.update_data(
        selected_categories=selected
    )

    paid_count = max(0, len(selected) - FREE_CATEGORY_LIMIT)

    info = (
        f"Выбрано категорий: {len(selected)}\n"
        f"Бесплатно: до {FREE_CATEGORY_LIMIT}\n"
    )

    if paid_count:
        info += f"Платных категорий: {paid_count} × {EXTRA_CATEGORY_PRICE} ₽/мес\n"

    await message.answer(
        info,
        reply_markup=make_categories_multi_kb(selected)
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
        "✅ Запрос отправлен диспетчеру. После проверки населённый пункт появится в системе."
    )

    if ADMIN_ID:
        await bot.send_message(
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

    await bot.send_message(
        ADMIN_ID,
        text
    )


async def notify_admin_status_changed(req):
    if not ADMIN_ID:
        return

    text = (
        f"🔄 Изменён статус заявки №{req['id']}\n\n"
        f"📂 {req['category']}\n"
        f"📍 Ориентир: {req['public_location']}\n"
        f"Статус: {STATUS_NAMES.get(req['status'], req['status'])}"
    )

    if req["dispatcher_comment"]:
        text += f"\n💬 Комментарий: {req['dispatcher_comment']}"

    await bot.send_message(
        ADMIN_ID,
        text
    )


async def notify_executors_search(req):
    executors = get_executors_by_category(
        req["category"],
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
            await bot.send_message(
                ADMIN_ID,
                f"⚠️ По заявке №{req['id']} нет исполнителей.\n"
                f"Категория: {req['category']}\n"
                f"Ориентир: {req['public_location']}"
            )
        return

    text = (
        f"👷 Нужен исполнитель\n\n"
        f"📌 Заявка №{req['id']}\n"
        f"📂 {req['category']}\n"
        f"🔹 {req['subcategory'] or ''}\n"
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
        try:
            await bot.send_message(
                executor["tg_id"],
                text,
                reply_markup=kb
            )
            sent += 1
        except Exception:
            pass

    if ADMIN_ID:
        await bot.send_message(
            ADMIN_ID,
            f"📤 Заявка №{req['id']} отправлена исполнителям.\n"
            f"Категория: {req['category']}\n"
            f"Ориентир: {req['public_location']}\n"
            f"Отправлено: {sent}"
        )


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
        await bot.send_message(
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

    await bot.send_message(
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
        await bot.send_message(
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
        await bot.send_message(
            ADMIN_ID,
            f"⚠️ Исполнитель открыл спор по заявке №{request_id}"
        )


async def notify_location_approved(req):
    if req and req["executor_tg_id"]:
        try:
            await bot.send_message(
                req["executor_tg_id"],
                f"✅ Населённый пункт добавлен в систему:\n\n"
                f"🏘 {req['location_name']}\n"
                f"Теперь можно зарегистрироваться исполнителем в этом населённом пункте."
            )
        except Exception:
            pass


async def start_bot():
    if not BOT_TOKEN:
        print("BOT_TOKEN не указан. Бот не запущен.")
        return

    await dp.start_polling(bot)
