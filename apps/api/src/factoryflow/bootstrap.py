"""HTTP composition root. Never opens a database or applies migrations on import."""

from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from factoryflow.kernel.contracts import BusinessError
from factoryflow.kernel.quantity import QuantityError
from factoryflow.modules.archives.adapters.http import router as archive_router
from factoryflow.modules.archives.adapters.local_archive import LocalArchiveStore, build_zip
from factoryflow.modules.archives.adapters.repository import ArchiveRepository
from factoryflow.modules.archives.application.service import Archives, ArchiveWork
from factoryflow.modules.customers.adapters.http import router as customer_router
from factoryflow.modules.customers.adapters.repository import CustomerRepository
from factoryflow.modules.customers.application.service import (
    CustomerAccess,
    CustomerService,
    CustomerWork,
)
from factoryflow.modules.documents.adapters.archive_repository import ArchiveDocumentRepository
from factoryflow.modules.documents.adapters.http import router as extraction_router
from factoryflow.modules.documents.adapters.local_store import LocalEvidenceStore
from factoryflow.modules.documents.adapters.ocr import LocalExtractor
from factoryflow.modules.documents.adapters.repository import RevisionRepository
from factoryflow.modules.documents.adapters.source_repository import SourceRepository
from factoryflow.modules.documents.application.extraction import ExtractionService, ExtractionWork
from factoryflow.modules.documents.application.service import Documents
from factoryflow.modules.documents.public import ArchiveDocuments
from factoryflow.modules.fulfillment.adapters.archive_renderer import render_archive_delivery
from factoryflow.modules.fulfillment.adapters.http import router as delivery_router
from factoryflow.modules.fulfillment.adapters.layout_http import router as delivery_layout_router
from factoryflow.modules.fulfillment.adapters.layout_repository import DeliveryLayoutRepository
from factoryflow.modules.fulfillment.adapters.repository import DeliveryRepository
from factoryflow.modules.fulfillment.application.layout import DeliveryLayouts, DeliveryLayoutWork
from factoryflow.modules.fulfillment.application.service import DeliveryService, DeliveryWork
from factoryflow.modules.fulfillment.public import ArchiveDeliveries, SettlementDeliveries
from factoryflow.modules.identity.adapters.http import router as identity_router
from factoryflow.modules.identity.adapters.repository import IdentityRepository
from factoryflow.modules.identity.application.service import IdentityService, IdentityWork
from factoryflow.modules.materials.adapters.http import router as material_router
from factoryflow.modules.materials.adapters.import_file import read_import_file
from factoryflow.modules.materials.adapters.repository import MaterialRepository
from factoryflow.modules.materials.application.service import (
    MaterialCatalog,
    MaterialService,
    MaterialWork,
)
from factoryflow.modules.orders.adapters.http import router as order_router
from factoryflow.modules.orders.adapters.repository import OrderRepository
from factoryflow.modules.orders.application.service import OrderService, OrderWork
from factoryflow.modules.orders.public import (
    ArchiveOrders,
    FulfillmentOrders,
    SettlementOrderSources,
)
from factoryflow.modules.statements.adapters.archive_repository import ArchiveStatementRepository
from factoryflow.modules.statements.adapters.customer_excel import (
    inspect_template,
    preview_grid,
    validate_mapping,
)
from factoryflow.modules.statements.adapters.excel import render_excel
from factoryflow.modules.statements.adapters.export_repository import StatementExportRepository
from factoryflow.modules.statements.adapters.http import router as statement_router
from factoryflow.modules.statements.adapters.lifecycle_http import (
    router as statement_lifecycle_router,
)
from factoryflow.modules.statements.adapters.lifecycle_repository import LifecycleRepository
from factoryflow.modules.statements.adapters.repository import StatementRepository
from factoryflow.modules.statements.adapters.template_http import (
    router as statement_template_router,
)
from factoryflow.modules.statements.adapters.template_repository import StatementTemplateRepository
from factoryflow.modules.statements.application.export import StatementExports
from factoryflow.modules.statements.application.lifecycle import StatementLifecycle
from factoryflow.modules.statements.application.service import StatementService, StatementWork
from factoryflow.modules.statements.application.templates import StatementTemplates
from factoryflow.modules.statements.public import ArchiveStatements, StatementDeliveryEffects
from factoryflow.platform.backup import create_backup
from factoryflow.platform.config import Settings
from factoryflow.platform.database import REVISION, Journal, check_ready, engine_for
from factoryflow.platform.health import router as health_router
from factoryflow.platform.http import ERROR_RESPONSES, services


@dataclass
class Services:
    settings: Settings
    engine: object
    identity: IdentityService
    customers: CustomerService
    orders: OrderService
    deliveries: DeliveryService
    extraction: ExtractionService
    statements: StatementService
    statement_exports: StatementExports
    delivery_layouts: DeliveryLayouts
    archives: Archives
    statement_lifecycle: StatementLifecycle
    statement_templates: StatementTemplates
    materials: MaterialService

    def close(self):
        self.engine.dispose()

    def check_ready(self):
        check_ready(self.engine, self.settings.object_root)

    def backup(self, destination: Path, binary: Path):
        return create_backup(
            self.engine,
            destination,
            binary,
            lambda conn: sorted(
                set(RevisionRepository(conn).backup_hashes())
                | set(StatementExportRepository(conn).backup_hashes())
                | set(ArchiveRepository(conn).backup_hashes())
                | set(LifecycleRepository(conn).backup_hashes())
                | set(StatementTemplateRepository(conn).backup_hashes())
            ),
            LocalEvidenceStore(self.settings.object_root).read,
        )


def build_services(settings: Settings) -> Services:
    engine = engine_for(settings.database_url)
    store = LocalEvidenceStore(settings.object_root)

    @contextmanager
    def transaction():
        try:
            with engine.begin() as conn:
                yield conn
        except IntegrityError as error:
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", "")
            code = {
                "orders_number_unique": "ORDER_NUMBER_EXISTS",
                "customers_name_unique": "CUSTOMER_EXISTS",
                "users_username_key": "USERNAME_EXISTS",
                "statement_period_unique": "STATEMENT_PERIOD_EXISTS",
                "materials_code_unique": "MATERIAL_CODE_EXISTS",
            }.get(constraint, "INTEGRITY_CONFLICT")
            raise BusinessError(code, 409) from None

    @contextmanager
    def identity_work():
        with transaction() as conn:
            yield IdentityWork(IdentityRepository(conn), Journal(conn))

    @contextmanager
    def customer_work():
        with transaction() as conn:
            yield CustomerWork(CustomerRepository(conn), Journal(conn))

    @contextmanager
    def material_work():
        with transaction() as conn:
            yield MaterialWork(
                MaterialCatalog(MaterialRepository(conn), CustomerAccess(CustomerRepository(conn))),
                Journal(conn),
            )

    @contextmanager
    def order_work():
        with transaction() as conn:
            yield OrderWork(
                OrderRepository(conn),
                CustomerAccess(CustomerRepository(conn)),
                Documents(RevisionRepository(conn), store, SourceRepository(conn)),
                Journal(conn),
                MaterialCatalog(MaterialRepository(conn), CustomerAccess(CustomerRepository(conn))),
            )

    @contextmanager
    def delivery_work():
        with transaction() as conn:
            yield DeliveryWork(
                DeliveryRepository(conn),
                FulfillmentOrders(OrderRepository(conn)),
                CustomerAccess(CustomerRepository(conn)),
                Journal(conn),
                StatementDeliveryEffects(StatementRepository(conn), Journal(conn)),
            )

    def statements_for(conn):
        return StatementWork(
            StatementRepository(conn),
            CustomerAccess(CustomerRepository(conn)),
            SettlementDeliveries(DeliveryRepository(conn)),
            SettlementOrderSources(OrderRepository(conn)),
            Journal(conn),
            StatementExportRepository(conn),
            LifecycleRepository(conn),
            StatementTemplateRepository(conn),
        )

    def layouts_for(conn):
        return DeliveryLayoutWork(
            DeliveryLayoutRepository(conn),
            DeliveryRepository(conn),
            SettlementOrderSources(OrderRepository(conn)),
            Journal(conn),
        )

    @contextmanager
    def layout_work():
        with transaction() as conn:
            yield layouts_for(conn)

    @contextmanager
    def layout_read_work():
        with transaction() as conn:
            conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            yield layouts_for(conn)

    @contextmanager
    def statement_work():
        with transaction() as conn:
            yield statements_for(conn)

    @contextmanager
    def statement_read_work():
        with transaction() as conn:
            conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            yield statements_for(conn)

    @contextmanager
    def extraction_work():
        with transaction() as conn:
            yield ExtractionWork(SourceRepository(conn), Journal(conn))

    def archives_for(conn):
        orders = ArchiveOrders(OrderRepository(conn), CustomerAccess(CustomerRepository(conn)))
        return ArchiveWork(
            ArchiveRepository(conn),
            {
                "source": ArchiveDocuments(ArchiveDocumentRepository(conn), store, orders),
                "delivery": ArchiveDeliveries(
                    DeliveryRepository(conn),
                    DeliveryLayoutRepository(conn),
                    SettlementOrderSources(OrderRepository(conn)),
                    render_archive_delivery,
                ),
                "statement_export": ArchiveStatements(ArchiveStatementRepository(conn), store),
            },
            Journal(conn),
        )

    @contextmanager
    def archive_work():
        with transaction() as conn:
            yield archives_for(conn)

    @contextmanager
    def archive_snapshot():
        try:
            with transaction() as conn:
                conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
                yield archives_for(conn)
        except SQLAlchemyError as error:
            if getattr(error.orig, "sqlstate", None) in {"40001", "40P01"}:
                raise BusinessError("ARCHIVE_RETRY", 409) from None
            raise

    return Services(
        settings,
        engine,
        IdentityService(identity_work),
        CustomerService(customer_work),
        OrderService(order_work),
        DeliveryService(delivery_work),
        ExtractionService(
            extraction_work,
            store,
            LocalExtractor(engine=settings.ocr_engine, python=settings.ocr_python),
        ),
        StatementService(statement_work, statement_read_work),
        StatementExports(statement_work, statement_read_work, store, render_excel),
        DeliveryLayouts(layout_work, layout_read_work),
        Archives(
            archive_work,
            archive_snapshot,
            store,
            LocalArchiveStore(settings.archive_root),
            build_zip,
        ),
        StatementLifecycle(statement_work, statement_read_work, store),
        StatementTemplates(
            statement_work,
            statement_read_work,
            store,
            inspect_template,
            validate_mapping,
            render_excel,
            preview_grid,
        ),
        MaterialService(material_work, read_import_file),
    )


def create_app(web_directory: Path | None = None, settings: Settings | None = None) -> FastAPI:
    if web_directory is not None and not (web_directory / "index.html").is_file():
        raise ValueError("Web build missing: prepare apps/web/dist before local startup.")

    @asynccontextmanager
    async def lifespan(application):
        yield
        if application.state.services is not None:
            application.state.services.close()

    application = FastAPI(
        title="FactoryFlow API",
        version="0.1.0",
        description="Local identity, explicit customers and immutable human-confirmed orders.",
        openapi_url="/api/v1/openapi.json",
        docs_url="/docs" if web_directory is None else None,
        redoc_url="/redoc" if web_directory is None else None,
        lifespan=lifespan,
    )
    application.state.services = build_services(settings) if settings is not None else None
    application.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "test"]
    )

    @application.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = str(uuid4())
        origin = request.headers.get("origin")
        if (
            request.method not in {"GET", "HEAD", "OPTIONS"}
            and origin
            and origin != str(request.base_url).rstrip("/")
        ):
            response = safe_error(request, "ORIGIN_FORBIDDEN", 403)
        else:
            response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def safe_error(request, code, status, field=None):
        messages = {
            "MATERIAL_IMPORT_INVALID_FILE": (
                "无法读取这份文件，请另存为 UTF-8 CSV 或单内容工作表的 xlsx 后重试。"
            ),
            "MATERIAL_IMPORT_UNSUPPORTED": (
                "这份文件含不支持的格式，请移除公式、宏、外链、合并、隐藏内容或复杂对象，"
                "另存为明细表后重试。"
            ),
            "MATERIAL_IMPORT_LIMIT": (
                "导入上限为 2 MiB、2,000 条数据、30 列；请缩小或分批，xlsx 解压后不超过 20 MiB。"
            ),
            "MATERIAL_IMPORT_MAPPING": "表头、字段列或逐行处理选择不合适，请重新核对。",
            "MATERIAL_IMPORT_STALE": "物料或客户料号已变化，本次没有导入。请重新预览后核对。",
            "MATERIAL_IMPORT_UNRESOLVED": (
                "还有待处理的明细，或没有选择任何可导入明细，请核对后再确认。"
            ),
            "NOT_CONFIGURED": "本地服务尚未配置。",
            "LOGIN_REQUIRED": "请先登录。",
            "AUTH_FAILED": "账号或密码不正确，连续失败后请稍后再试。",
            "WRITE_FORBIDDEN": "此账号只有查看权限。",
            "CSRF_REQUIRED": "登录状态已变化，请刷新后重试。",
            "ORDER_NUMBER_EXISTS": "该客户已有这个订单号，请查看或恢复原订单。",
            "CUSTOMER_EXISTS": "该客户已存在，请直接选择。",
            "VERSION_CONFLICT": "记录已经变化，请刷新后核对。",
            "DELIVERY_LAYOUT_INVALID": "版面设置不合适，请检查文字长度、纸张可用尺寸及各列总宽度。",
            "ARCHIVE_PREVIEW_STALE": "来源文件已经变化，请刷新文件列表并重新预览。",
            "ARCHIVE_NOT_CONFIGURED": "尚未配置工作归档目录，请联系本机维护人员。",
            "ARCHIVE_STALE": "这一批文件已属于历史快照，请核对后选择下载历史 ZIP。",
            "ARCHIVE_COPY_CONFLICT": (
                "本机副本与保存的内容不一致，已停止写入，请保留现场并联系维护人员。"
            ),
            "ARCHIVE_COPY_FAILED": "本机文件写入未完成，可以重试这一批次。",
            "ARCHIVE_RETRY": "同时有记录变化，请重试本次操作。",
            "ARCHIVE_NOT_READY": "这一批文件尚未生成，请先生成或重试。",
            "ARCHIVE_LIMIT_EXCEEDED": "本次文件总量超过 50 MiB，请分批整理。",
            "IDEMPOTENCY_CONFLICT": "这次提交的内容已变化，请重新核对后提交。",
            "UNIT_REQUIRES_INTEGER_QUANTITY": "该单位的数量必须是整数。",
            "QUANTITY_INVALID_FORMAT": "数量须为非负十进制文本，最多三位小数。",
            "DELIVERY_EXCEEDS_REMAINING": "本次送货数量超过未交数量，请刷新订单后核对。",
            "DELIVERY_SOURCE_CONFLICT": "送货来源已变化或不属于当前订单，请刷新后核对。",
            "DELIVERY_INVALID_LINES": "请选择不同的订单明细，送货数量必须大于零。",
            "DELIVERY_NOT_ACTIVE": "这张送货单已经作废，不能再次作废。",
            "ACTIVE_DELIVERY_BLOCKS_CHANGE": "订单还有有效送货，不能修订或删除。",
            "FILE_TYPE_UNSUPPORTED": "仅支持 PNG、JPEG 和 PDF，请检查文件格式。",
            "FILE_TOO_LARGE": "文件超过 10 MiB，请拆分后重试。",
            "EXTRACTION_BUSY": "本地识别正在处理另一份文件，请稍后重试。",
            "SOURCE_ALREADY_IMPORTED": "这份原件已经生成订单，请从文件列表打开原订单。",
            "STATEMENT_EXPORTED_USE_VOID": "草稿已有导出，请填写原因并选择作废，历史文件会保留。",
            "STATEMENT_EXPORT_REVIEW_REQUIRED": "请先处理待核对调整、负金额或空明细，再导出。",
            "STATEMENT_EXPORT_STALE": "此文件对应旧版本，请在导出记录中选择查看历史文件。",
            "STATEMENT_EXPORT_NOT_READY": "文件尚未生成，请在导出记录中重试。",
            "STATEMENT_TEMPLATE_INVALID": "请选择支持的 Excel 排版。",
            "STATEMENT_TEMPLATE_UNSUPPORTED": (
                "此模板含首版无法可靠保留的格式。请用单工作表 .xlsx，"
                "移除宏、外链、图片图表、保护或复杂对象后重试。"
            ),
            "STATEMENT_TEMPLATE_FILE_LIMIT": "模板超过上限：2 MiB、300 行、30 列；请缩小模板范围。",
            "STATEMENT_TEMPLATE_MAPPING": (
                "字段位置不完整、重叠、隐藏或不符合明细区布局，请核对标注位置。"
            ),
            "STATEMENT_TEMPLATE_FORMULA": (
                "模板有字段位置以外的公式。请移除公式或把该位置绑定为系统计算字段。"
            ),
            "STATEMENT_TEMPLATE_FILE_CHANGED": "当前文件与检查时不同，请重新上传并确认位置。",
            "STATEMENT_TEMPLATE_NOT_FOUND": "没有找到该客户的模板版本。",
            "STATEMENT_TEMPLATE_COVERAGE": (
                "此模板缺少本单税费或调整位置，请补齐后导入，或使用内置模板。"
            ),
            "STATEMENT_TEMPLATE_OUTPUT_LIMIT": "此模板一次最多输出 1000 条明细，请使用内置模板。",
            "STATEMENT_TEMPLATE_TEXT_LIMIT": (
                "文字超出此模板单行可完整打印的范围。请加宽或合并该字段的横向空间，"
                "或使用能完整呈现该内容的排版。"
            ),
            "STATEMENT_PERIOD_EXISTS": "该客户和期间已有对账单，请打开原草稿或重开已放弃草稿。",
            "STATEMENT_QUANTITY_EXCEEDED": "结算数量超过可用送货数量，请刷新后核对。",
            "STATEMENT_SOURCE_INVALID": "送货来源已变化或不属于这个客户，请重新核对。",
            "STATEMENT_REASON_REQUIRED": "请填写调整、暂缓或部分结算的原因。",
            "STATEMENT_STATE_CONFLICT": "对账草稿状态已变化，请刷新后核对。",
            "STATEMENT_DECIMAL_INVALID": "价格、税率或调整金额格式与精度不符合要求。",
            "STATEMENT_AMOUNT_OUT_OF_RANGE": "金额超出当前支持范围，请核对输入。",
            "STATEMENT_LIFECYCLE_NOT_FOUND": "找不到对应的认可、分配或待核对记录。",
            "STATEMENT_EVIDENCE_MISMATCH": "确认依据与当前客户、来源或发送版本不一致，请重新核对。",
            "STATEMENT_PREVIEW_STALE": "预览后记录已有变化，请重新预览并核对影响。",
            "STATEMENT_QUANTITY_REQUIRED": "本次数量必须大于零。",
            "STATEMENT_PRICE_REQUIRED": "请填写人工确认的单价。",
            "STATEMENT_TARGET_MISMATCH": "认可的目标期间与本单不同，请先明确归期。",
            "STATEMENT_PRICE_CONFLICT": "同一草稿来源已有不同单价，请先核对原行。",
            "STATEMENT_APPROVED_SOURCE_PROTECTED": (
                "来源已有认可或正式结算，不能直接作废送货。请保留历史并人工处理异常。"
            ),
            "STATEMENT_UNAPPROVED_QUANTITY": "仍有未认可的草稿数量，请先明确认可或待核对去向。",
            "STATEMENT_FEES_UNKNOWN": "费用尚未完整核对，暂不能正式确认。",
            "STATEMENT_RECONFIRMATION_UNKNOWN": "再次回签要求未知，请核对客户要求。",
            "STATEMENT_RECONFIRMATION_EVIDENCE_REQUIRED": "请先登记本期收到的回签或确认反馈。",
            "STATEMENT_ADJUSTMENTS_REVIEW": "费用调整需要重新核对并保存。",
            "STATEMENT_RELATED_FEES_REVIEW": "此正式更正关联来源费用，首版需人工处理异常。",
            "STATEMENT_AMOUNT_UNCONFIRMED": "最终金额未知或为负，不能正式确认。",
            "STATEMENT_EMPTY_SETTLEMENT": "当前没有结算明细或已认可转期记录。",
            "STATEMENT_NO_PENDING_QUANTITY": "没有可延期的待结数量，或目标期早于来源日期。",
            "STATEMENT_FORMAL_CORRECTION_REQUIRED": (
                "认可已有正式结算，请从对应正式单进行有据更正。"
            ),
            "STATEMENT_REAPPROVAL_REQUIRED": "增加数量需要另行承接来源并取得认可。",
            "STATEMENT_DOWNSTREAM_EFFECTS": (
                "存在后续正式引用、退货或其他影响，首版需人工处理异常。"
            ),
        }
        return JSONResponse(
            status_code=status,
            content={
                "code": code,
                "message": messages.get(code, "操作未完成，请核对输入或本地服务状态。"),
                "field": field,
                "request_id": request.state.request_id,
            },
        )

    @application.exception_handler(BusinessError)
    async def business_error(request, error):
        return safe_error(request, error.code, error.status, error.field)

    @application.exception_handler(QuantityError)
    async def quantity_error(request, error):
        return safe_error(request, error.code, 422, "lines.quantity")

    @application.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        location = error.errors()[0]["loc"]
        return safe_error(request, "INVALID_INPUT", 422, ".".join(map(str, location)))

    @application.exception_handler(SQLAlchemyError)
    async def database_error(request, error):
        return safe_error(request, "DATABASE_UNAVAILABLE", 503)

    @application.exception_handler(OSError)
    async def storage_error(request, error):
        return safe_error(request, "STORAGE_UNAVAILABLE", 503)

    application.include_router(health_router, prefix="/api/v1")
    application.include_router(identity_router, prefix="/api/v1")
    application.include_router(customer_router, prefix="/api/v1")
    application.include_router(material_router, prefix="/api/v1")
    application.include_router(order_router, prefix="/api/v1")
    application.include_router(delivery_router, prefix="/api/v1")
    application.include_router(delivery_layout_router, prefix="/api/v1")
    application.include_router(extraction_router, prefix="/api/v1")
    application.include_router(statement_router, prefix="/api/v1")
    application.include_router(statement_template_router, prefix="/api/v1")
    application.include_router(statement_lifecycle_router, prefix="/api/v1")
    application.include_router(archive_router, prefix="/api/v1")

    @application.get("/api/v1/health/ready", operation_id="getReadiness", responses=ERROR_RESPONSES)
    def readiness(request: Request) -> dict[str, str]:
        services(request)
        return {"status": "ready", "schema_version": REVISION}

    if web_directory is not None:
        application.mount("/", StaticFiles(directory=web_directory, html=True), name="web")
    return application


app = create_app()
