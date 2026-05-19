from contextlib import asynccontextmanager
import asyncio
import secrets

from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import uvicorn

from config import ADMIN_LOGIN, ADMIN_PASSWORD

from db import (
    create_service_suggestion,
    get_service_suggestions,
    update_service_suggestion_status,
    init_db,
    seed_default_locations,
    create_request,
    get_all_requests,
    get_request,
    update_request_status,
    get_responses_for_request,
    assign_executor,
    get_locations,
    get_location_requests,
    approve_location_request,
    get_stats,
    confirm_request_done,
    create_dispute,
    resolve_dispute,
    get_executors_with_categories,

    get_all_service_categories_with_subcategories,
    get_service_categories_with_subcategories,
    create_service_category,
    create_service_subcategory,
    toggle_service_category,
    toggle_service_subcategory,

    toggle_executor_category,
    mark_category_paid,
    mark_category_free,
    get_events_version,
    get_active_ads,
    get_all_ads,
    create_ad,
    toggle_ad,
    delete_ad,
    set_service_subcategory_requires_dispatcher,
    get_service_subcategory_by_name,
)

from bot import (
    start_bot,
    notify_admin_new_request,
    notify_admin_status_changed,
    notify_executors_search,
    notify_executor_assigned,
    notify_location_approved,
)


templates = Jinja2Templates(directory="templates")
security = HTTPBasic()


def admin_auth(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(
        credentials.username,
        ADMIN_LOGIN
    )

    correct_password = secrets.compare_digest(
        credentials.password,
        ADMIN_PASSWORD
    )

    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials.username


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_default_locations()

    asyncio.create_task(start_bot())

    yield


app = FastAPI(
    title="Solovey Market",
    lifespan=lifespan
)


@app.get("/")
async def index(request: Request):
    locations = get_locations()
    service_categories = get_service_categories_with_subcategories()
    ads_top = get_active_ads("home_top")
    ads_bottom = get_active_ads("home_bottom")

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "locations": locations,
            "service_categories": service_categories,
            "ads_top": ads_top,
            "ads_bottom": ads_bottom
        }
    )


@app.post("/request")
async def create_service_request(
    category: str = Form(...),
    subcategory: str = Form(...),
    description: str = Form(...),
    public_location: str = Form(...),
    private_address: str = Form(...),
    phone: str = Form(...),
    deadline: str = Form("Не срочно")
):
    if category == "Предложить услугу":
        title = subcategory or "Предложение новой услуги"

        suggestion_description = (
            f"Срок/важность: {deadline}\n\n"
            f"{description}\n\n"
            f"Адрес/ориентир от пользователя: {private_address}"
        )

        create_service_suggestion(
            title=title,
            description=suggestion_description,
            phone=phone,
            public_location=public_location
        )

        return RedirectResponse(
            url="/suggestion-thanks",
            status_code=303
        )

    full_description = (
        f"Срок: {deadline}\n\n"
        f"{description}"
    )

    request_id = create_request(
        category,
        subcategory,
        full_description,
        public_location,
        private_address,
        phone
    )

    req = get_request(request_id)
    subcategory_row = get_service_subcategory_by_name(subcategory)

    requires_dispatcher = 1

    if subcategory_row:
        requires_dispatcher = subcategory_row["requires_dispatcher"]

    if requires_dispatcher:
        await notify_admin_new_request(req)
    else:
        update_request_status(
            request_id,
            "searching_executor",
            "Автоматическая отправка исполнителям"
        )

        req = get_request(request_id)

        await notify_admin_new_request(req)
        await notify_executors_search(req)

    return RedirectResponse(
        url="/thanks",
        status_code=303
    )

@app.get("/suggestion-thanks")
async def suggestion_thanks(request: Request):
    return templates.TemplateResponse(
        request,
        "suggestion_thanks.html",
        {}
    )


@app.get("/thanks")
async def thanks(request: Request):
    return templates.TemplateResponse(
        request,
        "thanks.html",
        {}
    )


@app.get("/admin")
async def admin(
    request: Request,
    _: str = Depends(admin_auth)
):
    rows = get_all_requests()

    requests = []

    for r in rows:
        requests.append({
            "data": r,
            "responses": get_responses_for_request(r["id"])
        })

    return templates.TemplateResponse(
        request,
        "admin.html",
        {
            "requests": requests,
            "stats": get_stats()
        }
    )


@app.get("/admin/events-version")
async def admin_events_version(
    _: str = Depends(admin_auth)
):
    return JSONResponse({
        "version": get_events_version()
    })


@app.post("/admin/request/{request_id}/status")
async def change_request_status(
    request_id: int,
    status: str = Form(...),
    comment: str = Form(""),
    _: str = Depends(admin_auth)
):
    update_request_status(
        request_id,
        status,
        comment
    )

    req = get_request(request_id)

    await notify_admin_status_changed(req)

    if status == "searching_executor":
        await notify_executors_search(req)

    return RedirectResponse(
        url="/admin",
        status_code=303
    )


@app.post("/admin/request/{request_id}/assign/{executor_id}")
async def assign_request_executor(
    request_id: int,
    executor_id: int,
    reason: str = Form(...),
    _: str = Depends(admin_auth)
):
    success = assign_executor(
        request_id,
        executor_id,
        reason
    )

    if success:
        req = get_request(request_id)

        await notify_executor_assigned(
            executor_id,
            req
        )

    return RedirectResponse(
        url="/admin",
        status_code=303
    )


@app.post("/admin/request/{request_id}/confirm-done")
async def admin_confirm_done(
    request_id: int,
    _: str = Depends(admin_auth)
):
    confirm_request_done(request_id)

    return RedirectResponse(
        "/admin",
        status_code=303
    )


@app.post("/admin/request/{request_id}/dispute")
async def admin_dispute(
    request_id: int,
    reason: str = Form(...),
    _: str = Depends(admin_auth)
):
    create_dispute(
        request_id,
        "dispatcher",
        "admin",
        reason
    )

    return RedirectResponse(
        "/admin",
        status_code=303
    )


@app.post("/admin/request/{request_id}/resolve-dispute")
async def admin_resolve_dispute(
    request_id: int,
    decision: str = Form(...),
    comment: str = Form(""),
    _: str = Depends(admin_auth)
):
    resolve_dispute(
        request_id,
        decision,
        comment
    )

    return RedirectResponse(
        "/admin",
        status_code=303
    )


@app.get("/admin/executors")
async def admin_executors(
    request: Request,
    _: str = Depends(admin_auth)
):
    rows = get_executors_with_categories()

    return templates.TemplateResponse(
        request,
        "executors.html",
        {
            "executors": rows
        }
    )


@app.post("/admin/executor/{executor_id}/category/{category_id}/toggle")
async def admin_toggle_executor_category(
    executor_id: int,
    category_id: int,
    _: str = Depends(admin_auth)
):
    toggle_executor_category(
        executor_id,
        category_id
    )

    return RedirectResponse(
        "/admin/executors",
        status_code=303
    )


@app.post("/admin/executor-category/{category_id}/paid")
async def admin_mark_category_paid(
    category_id: int,
    _: str = Depends(admin_auth)
):
    mark_category_paid(category_id)

    return RedirectResponse(
        "/admin/executors",
        status_code=303
    )


@app.post("/admin/executor-category/{category_id}/free")
async def admin_mark_category_free(
    category_id: int,
    _: str = Depends(admin_auth)
):
    mark_category_free(category_id)

    return RedirectResponse(
        "/admin/executors",
        status_code=303
    )


@app.get("/admin/ads")
async def admin_ads(
    request: Request,
    _: str = Depends(admin_auth)
):
    ads = get_all_ads()

    return templates.TemplateResponse(
        request,
        "ads.html",
        {
            "ads": ads
        }
    )


@app.post("/admin/ads/create")
async def admin_create_ad(
    title: str = Form(...),
    text: str = Form(""),
    image_url: str = Form(""),
    link_url: str = Form(""),
    button_text: str = Form("Подробнее"),
    placement: str = Form("home_top"),
    sort_order: int = Form(100),
    is_active: int = Form(1),
    _: str = Depends(admin_auth)
):
    create_ad(
        title=title,
        text=text,
        image_url=image_url,
        link_url=link_url,
        button_text=button_text,
        placement=placement,
        sort_order=sort_order,
        is_active=is_active
    )

    return RedirectResponse(
        "/admin/ads",
        status_code=303
    )


@app.post("/admin/ads/{ad_id}/toggle")
async def admin_toggle_ad(
    ad_id: int,
    _: str = Depends(admin_auth)
):
    toggle_ad(ad_id)

    return RedirectResponse(
        "/admin/ads",
        status_code=303
    )


@app.post("/admin/ads/{ad_id}/delete")
async def admin_delete_ad(
    ad_id: int,
    _: str = Depends(admin_auth)
):
    delete_ad(ad_id)

    return RedirectResponse(
        "/admin/ads",
        status_code=303
    )


@app.get("/admin/locations")
async def admin_locations(
    request: Request,
    _: str = Depends(admin_auth)
):
    rows = get_location_requests()

    return templates.TemplateResponse(
        request,
        "locations.html",
        {
            "requests": rows
        }
    )


@app.post("/admin/location-request/{request_id}/approve")
async def approve_location(
    request_id: int,
    _: str = Depends(admin_auth)
):
    req = approve_location_request(request_id)

    await notify_location_approved(req)

    return RedirectResponse(
        "/admin/locations",
        status_code=303
    )

@app.get("/admin/service-suggestions")
async def admin_service_suggestions(
    request: Request,
    _: str = Depends(admin_auth)
):
    suggestions = get_service_suggestions()

    return templates.TemplateResponse(
        request,
        "service_suggestions.html",
        {
            "suggestions": suggestions
        }
    )


@app.post("/admin/service-suggestions/{suggestion_id}/status")
async def admin_update_service_suggestion(
    suggestion_id: int,
    status: str = Form(...),
    admin_comment: str = Form(""),
    _: str = Depends(admin_auth)
):
    update_service_suggestion_status(
        suggestion_id,
        status,
        admin_comment
    )

    return RedirectResponse(
        "/admin/service-suggestions",
        status_code=303
    )


@app.get("/admin/categories")
async def admin_categories(
    request: Request,
    _: str = Depends(admin_auth)
):
    categories = get_all_service_categories_with_subcategories()

    return templates.TemplateResponse(
        request,
        "categories.html",
        {
            "categories": categories
        }
    )


@app.post("/admin/categories/create")
async def admin_create_category(
    name: str = Form(...),
    emoji: str = Form("📌"),
    sort_order: int = Form(100),
    _: str = Depends(admin_auth)
):
    create_service_category(
        name=name,
        emoji=emoji,
        sort_order=sort_order
    )

    return RedirectResponse(
        "/admin/categories",
        status_code=303
    )


@app.post("/admin/categories/{category_id}/toggle")
async def admin_toggle_category(
    category_id: int,
    _: str = Depends(admin_auth)
):
    toggle_service_category(category_id)

    return RedirectResponse(
        "/admin/categories",
        status_code=303
    )


@app.post("/admin/categories/{category_id}/subcategories/create")
async def admin_create_subcategory(
    category_id: int,
    name: str = Form(...),
    sort_order: int = Form(100),
    _: str = Depends(admin_auth)
):
    create_service_subcategory(
        category_id=category_id,
        name=name,
        sort_order=sort_order
    )

    return RedirectResponse(
        "/admin/categories",
        status_code=303
    )


@app.post("/admin/subcategories/{subcategory_id}/toggle")
async def admin_toggle_subcategory_route(
    subcategory_id: int,
    _: str = Depends(admin_auth)
):
    toggle_service_subcategory(subcategory_id)

    return RedirectResponse(
        "/admin/categories",
        status_code=303
    )


@app.post("/admin/subcategories/{subcategory_id}/dispatcher-toggle")
async def admin_toggle_subcategory_dispatcher(
    subcategory_id: int,
    requires_dispatcher: int = Form(0),
    _: str = Depends(admin_auth)
):
    set_service_subcategory_requires_dispatcher(
        subcategory_id,
        requires_dispatcher
    )

    return RedirectResponse(
        "/admin/categories",
        status_code=303
    )


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False
    )
