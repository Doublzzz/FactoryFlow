import { getLocale, msg, type Locale, type UiMessage } from "./i18n";
import { createFactoryFlowClient, type components } from "@factoryflow/api-client";

export type Schemas = components["schemas"];
export type ArchiveSettings = Schemas["ArchiveSettings"];
export type ArchiveSource = Schemas["ArchiveSource"];
export type ArchivePreview = Schemas["ArchivePreview"];
export type ArchivePreviewRequest = Schemas["ArchivePreviewRequest"];
export type ArchiveBatch = Schemas["ArchiveBatch"];
export type ArchiveRule = ArchiveSettings["rule"];
export type Statement = Schemas["StatementDetail"];
export type StatementDraft = Schemas["DraftInput"];
export type StatementCandidate = Schemas["StatementCandidate"];
export type StatementExport = Schemas["StatementExportDetail"];
export type StatementSettings = Schemas["StatementSettingsDetail"];
export type StatementTemplate = Schemas["TemplateDetail"];
export type TemplateMapping = Schemas["TemplateMapping"];
export type StatementAdjustment = Schemas["AdjustmentInput"];
export type Session = Schemas["SessionResponse"];
export type Customer = Schemas["CustomerResponse"];
export type Material = Schemas["MaterialResponse"];
export type MaterialInput = Schemas["MaterialInput"];
export type MaterialCode = Schemas["MaterialCodeResponse"];
export type MaterialChoice = Schemas["OrderMaterialChoice"];
export type MaterialImportFile = Schemas["MaterialImportFile"];
export type MaterialImportInput = Schemas["MaterialImportInput"];
export type MaterialImportChoice = Schemas["MaterialImportChoice"];
export type MaterialImportInspection = Schemas["MaterialImportInspection"];
export type MaterialImportPreview = Schemas["MaterialImportPreview"];
export type MaterialImportResult = Schemas["MaterialImportResult"];
export type OrderInput = Schemas["OrderInput"];
export type OrderDetail = Schemas["OrderDetail"];
export type OrderPreview = Schemas["OrderPreview"];
export type OpenLine = Schemas["OpenLine"];
export type Evidence = Schemas["EvidenceResponse"];
export type DeliveryInput = Schemas["DeliveryInput"];
export type Delivery = Schemas["DeliveryDetail"];
export type DeliverySummary = Schemas["DeliverySummary"];
export type DeliveryLayout = Schemas["DeliveryLayoutDetail"];
export type DeliveryLayoutConfig = Schemas["DeliveryLayoutConfig"];
export type Extraction = Schemas["ExtractionDetail"];
export type SourceSummary = Schemas["SourceSummary"];

const client = createFactoryFlowClient();
let csrfToken = "";
export const setCSRF = (value: string) => { csrfToken = value; };
const options = () => ({ signal: AbortSignal.timeout(15000), headers: { "X-CSRF-Token": csrfToken } });
const commandOptions = (key: string) => ({ ...options(), params: { header: { "Idempotency-Key": key } } });

export class ApiError extends Error {
  constructor(message: string, public code: string, public status: number, public field?: string | null) { super(message); }
}

function value<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data !== undefined && result.response.ok) return result.data;
  const error = result.error as Schemas["ErrorResponse"] | undefined;
  if (error?.code === "LOGIN_REQUIRED") window.dispatchEvent(new Event("factoryflow:session-expired"));
  throw new ApiError(error?.message ?? "本地服务暂时不可用，请重试。", error?.code ?? "SERVICE_UNAVAILABLE", result.response.status, error?.field);
}

const serviceErrors: Record<string, string> = {
  "MATERIAL_IMPORT_INVALID_FILE": "无法读取这份文件，请另存为 UTF-8 CSV 或单内容工作表的 xlsx 后重试。",
  "MATERIAL_IMPORT_UNSUPPORTED": "这份文件含不支持的格式，请移除公式、宏、外链、合并、隐藏内容或复杂对象，另存为明细表后重试。",
  "MATERIAL_IMPORT_LIMIT": "导入上限为 2 MiB、2,000 条数据、30 列；请缩小或分批，xlsx 解压后不超过 20 MiB。",
  "MATERIAL_IMPORT_MAPPING": "表头、字段列或逐行处理选择不合适，请重新核对。",
  "MATERIAL_IMPORT_STALE": "物料或客户料号已变化，本次没有导入。请重新预览后核对。",
  "MATERIAL_IMPORT_UNRESOLVED": "还有待处理的明细，或没有选择任何可导入明细，请核对后再确认。",
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
  "ARCHIVE_COPY_CONFLICT": "本机副本与保存的内容不一致，已停止写入，请保留现场并联系维护人员。",
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
  "STATEMENT_TEMPLATE_UNSUPPORTED": "此模板含首版无法可靠保留的格式。请用单工作表 .xlsx，移除宏、外链、图片图表、保护或复杂对象后重试。",
  "STATEMENT_TEMPLATE_FILE_LIMIT": "模板超过上限：2 MiB、300 行、30 列；请缩小模板范围。",
  "STATEMENT_TEMPLATE_MAPPING": "字段位置不完整、重叠、隐藏或不符合明细区布局，请核对标注位置。",
  "STATEMENT_TEMPLATE_FORMULA": "模板有字段位置以外的公式。请移除公式或把该位置绑定为系统计算字段。",
  "STATEMENT_TEMPLATE_FILE_CHANGED": "当前文件与检查时不同，请重新上传并确认位置。",
  "STATEMENT_TEMPLATE_NOT_FOUND": "没有找到该客户的模板版本。",
  "STATEMENT_TEMPLATE_COVERAGE": "此模板缺少本单税费或调整位置，请补齐后导入，或使用内置模板。",
  "STATEMENT_TEMPLATE_OUTPUT_LIMIT": "此模板一次最多输出 1000 条明细，请使用内置模板。",
  "STATEMENT_TEMPLATE_TEXT_LIMIT": "文字超出此模板单行可完整打印的范围。请加宽或合并该字段的横向空间，或使用能完整呈现该内容的排版。",
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
  "STATEMENT_APPROVED_SOURCE_PROTECTED": "来源已有认可或正式结算，不能直接作废送货。请保留历史并人工处理异常。",
  "STATEMENT_UNAPPROVED_QUANTITY": "仍有未认可的草稿数量，请先明确认可或待核对去向。",
  "STATEMENT_FEES_UNKNOWN": "费用尚未完整核对，暂不能正式确认。",
  "STATEMENT_RECONFIRMATION_UNKNOWN": "再次回签要求未知，请核对客户要求。",
  "STATEMENT_RECONFIRMATION_EVIDENCE_REQUIRED": "请先登记本期收到的回签或确认反馈。",
  "STATEMENT_ADJUSTMENTS_REVIEW": "费用调整需要重新核对并保存。",
  "STATEMENT_RELATED_FEES_REVIEW": "此正式更正关联来源费用，首版需人工处理异常。",
  "STATEMENT_AMOUNT_UNCONFIRMED": "最终金额未知或为负，不能正式确认。",
  "STATEMENT_EMPTY_SETTLEMENT": "当前没有结算明细或已认可转期记录。",
  "STATEMENT_NO_PENDING_QUANTITY": "没有可延期的待结数量，或目标期早于来源日期。",
  "STATEMENT_FORMAL_CORRECTION_REQUIRED": "认可已有正式结算，请从对应正式单进行有据更正。",
  "STATEMENT_REAPPROVAL_REQUIRED": "增加数量需要另行承接来源并取得认可。",
  "STATEMENT_DOWNSTREAM_EFFECTS": "存在后续正式引用、退货或其他影响，首版需人工处理异常。"
};

export function message(error: unknown): UiMessage {
  if (!(error instanceof ApiError)) return msg("未收到本地服务的响应，请检查连接后重试。");
  const materialErrors: Record<string, string> = {
    MATERIAL_CODE_EXISTS: "这个我方料号已存在，请选择已有物料或换一个号码。",
    MATERIAL_NUMBER_BUSY: "自动编号暂未成功，请重试或填写自己的料号。",
    MATERIAL_VERSION_CONFLICT: "物料资料已被更新，请重新选择后再保存。订单也可以暂不关联物料。",
    MATERIAL_MAPPING_CONFLICT: "客户料号对应已变化，请重新核对，不能覆盖旧预览。",
    MATERIAL_IDENTITY_IMMUTABLE: "已填写的规格和单位不在这里换成另一种货物；可新建物料后更正订单关联。",
    MATERIAL_INACTIVE: "这条物料已停用，请选择其他物料或暂不关联。",
    MATERIAL_NOT_FOUND: "未找到这条物料，请重新查询。",
    MATERIAL_LINE_NOT_CURRENT: "订单明细已修订，请刷新后操作当前明细。",
  };
  let key = materialErrors[error.code] ?? serviceErrors[error.code] ?? "操作未完成，请核对输入或本地服务状态。";
  if (error.code === "STATEMENT_EXTERNAL_NUMBER_INVALID") key = "客户外部单号须为 120 字以内，不能含换行或控制字符。";
  if (error.code === "STATEMENT_EXTERNAL_NUMBER_MISMATCH") key = "外部单号与发送依据或待核对记录不一致，请核对号码后重新发送或承接。";
  if (error.code === "STATEMENT_TEMPLATE_COVERAGE" && error.field === "external_document_number") key = "客户模板需要外部送货／退货单号，请为每条明细填写后再导出。";
  if (error.code === "SERVICE_UNAVAILABLE") key = "本地服务暂时不可用，请重试。";
  const fields: Record<string, string> = { full_name: "客户名称", customer_id: "客户", order_number: "客户订单号", business_date: "订单日期", currency: "币种", lines: "订单明细", description: "品名", quantity: "数量", unit: "单位", source_unit_price: "订单单价", source_amount: "原单金额", reason: "操作原因", password: "密码", username: "账号" };
  const parts = error.field?.split(".") ?? [];
  const name = fields[parts.at(-1) ?? ""];
  if (!name) return msg(key);
  return parts[0] === "lines" && /^\d+$/.test(parts[1] ?? "")
    ? msg("{0}（第 {1} 行：{2}）", [msg(key), Number(parts[1]) + 1, msg(name)])
    : msg("{0}（{1}）", [msg(key), msg(name)]);
}

export const api = {
  inspectMaterialImport: (body: MaterialImportFile) => client.POST("/api/v1/materials/imports/inspect", { ...options(), signal: AbortSignal.timeout(45000), body }).then(value),
  previewMaterialImport: (body: MaterialImportInput) => client.POST("/api/v1/materials/imports/preview", { ...options(), signal: AbortSignal.timeout(45000), body }).then(value),
  confirmMaterialImport: (body: Schemas["MaterialImportConfirm"], key: string) => client.POST("/api/v1/materials/imports/confirm", { ...commandOptions(key), signal: AbortSignal.timeout(45000), body }).then(value),
  materials: (q = "", offset = 0) => client.GET("/api/v1/materials", { ...options(), params: { query: { q, offset, limit: 50 } } }).then(value),
  createMaterial: (body: MaterialInput, key: string) => client.POST("/api/v1/materials", { ...commandOptions(key), body }).then(value),
  updateMaterial: (material_id: string, body: Schemas["MaterialUpdate"], key: string) => client.POST("/api/v1/materials/{material_id}", { ...options(), params: { path: { material_id }, header: { "Idempotency-Key": key } }, body }).then(value),
  materialCodes: (material_id?: string, customer_id?: string, customer_code?: string) => client.GET("/api/v1/material-codes", { ...options(), params: { query: { ...(material_id ? { material_id } : {}), ...(customer_id ? { customer_id } : {}), ...(customer_code !== undefined ? { customer_code } : {}) } } }).then(value),
  saveMaterialCode: (body: Schemas["MaterialCodeInput"], key: string) => client.POST("/api/v1/material-codes", { ...commandOptions(key), body }).then(value),
  linkOrderMaterials: (order_id: string, body: Schemas["OrderMaterialLinksInput"], key: string) => client.POST("/api/v1/orders/{order_id}/material-links", { ...options(), params: { path: { order_id }, header: { "Idempotency-Key": key } }, body }).then(value),
  recordStatementSent: (statement_id: string, body: Schemas["SentInput"], key: string) => client.POST("/api/v1/statements/{statement_id}/sent", { ...options(), params: { path: { statement_id }, header: { "Idempotency-Key": key } }, body }).then(value),
  recordStatementFeedback: (statement_id: string, body: Schemas["FeedbackInput"], key: string) => client.POST("/api/v1/statements/{statement_id}/feedback", { ...options(), params: { path: { statement_id }, header: { "Idempotency-Key": key } }, body }).then(value),
  approveStatement: (statement_id: string, body: Schemas["ApproveInput"], key: string) => client.POST("/api/v1/statements/{statement_id}/approve", { ...options(), params: { path: { statement_id }, header: { "Idempotency-Key": key } }, body }).then(value),
  reviewStatement: (statement_id: string, body: Schemas["ReviewInput"], key: string) => client.POST("/api/v1/statements/{statement_id}/review", { ...options(), params: { path: { statement_id }, header: { "Idempotency-Key": key } }, body }).then(value),
  claimStatementReview: (statement_id: string, body: Schemas["ClaimReviewInput"], key: string) => client.POST("/api/v1/statements/{statement_id}/claim-review", { ...options(), params: { path: { statement_id }, header: { "Idempotency-Key": key } }, body }).then(value),
  reserveStatementApproval: (statement_id: string, body: Schemas["ReserveInput"], key: string) => client.POST("/api/v1/statements/{statement_id}/reserve", { ...options(), params: { path: { statement_id }, header: { "Idempotency-Key": key } }, body }).then(value),
  releaseStatementAllocation: (statement_id: string, body: Schemas["ReleaseInput"], key: string) => client.POST("/api/v1/statements/{statement_id}/release", { ...options(), params: { path: { statement_id }, header: { "Idempotency-Key": key } }, body }).then(value),
  settleStatement: (statement_id: string, body: Schemas["SettleInput"], key: string) => client.POST("/api/v1/statements/{statement_id}/settle", { ...options(), params: { path: { statement_id }, header: { "Idempotency-Key": key } }, body }).then(value),
  deferStatementApproval: (approval_id: string, body: Schemas["DeferInput"], key: string) => client.POST("/api/v1/statement-approvals/{approval_id}/defer", { ...options(), params: { path: { approval_id }, header: { "Idempotency-Key": key } }, body }).then(value),
  correctStatementApproval: (approval_id: string, body: Schemas["CorrectApprovalInput"], key: string) => client.POST("/api/v1/statement-approvals/{approval_id}/correct", { ...options(), params: { path: { approval_id }, header: { "Idempotency-Key": key } }, body }).then(value),
  correctStatementSettlement: (statement_id: string, body: Schemas["CorrectSettlementInput"], key: string) => client.POST("/api/v1/statements/{statement_id}/correct", { ...options(), params: { path: { statement_id }, header: { "Idempotency-Key": key } }, body }).then(value),
  previewStatementSettlement: (statement_id: string, body: Schemas["SettlementPreviewInput"]) => client.POST("/api/v1/statements/{statement_id}/settlement-preview", { ...options(), params: { path: { statement_id } }, body }).then(value),
  previewStatementDefer: (approval_id: string, body: Schemas["DeferPreviewInput"]) => client.POST("/api/v1/statement-approvals/{approval_id}/defer-preview", { ...options(), params: { path: { approval_id } }, body }).then(value),
  previewApprovalCorrection: (approval_id: string, body: Schemas["CorrectApprovalPreviewInput"]) => client.POST("/api/v1/statement-approvals/{approval_id}/correct-preview", { ...options(), params: { path: { approval_id } }, body }).then(value),
  previewSettlementCorrection: (statement_id: string, body: Schemas["CorrectSettlementPreviewInput"]) => client.POST("/api/v1/statements/{statement_id}/correction-preview", { ...options(), params: { path: { statement_id } }, body }).then(value),
  statementLifecycle: (statement_id: string) => client.GET("/api/v1/statements/{statement_id}/lifecycle", { ...options(), params: { path: { statement_id } } }).then(value),
  statementApprovals: (customer_id: string, cursor?: string) => client.GET("/api/v1/statement-approvals", { ...options(), params: { query: { customer_id, ...(cursor ? { cursor } : {}), limit: 50 } } }).then(value),
  statementReviews: (customer_id: string, cursor?: string) => client.GET("/api/v1/statement-reviews", { ...options(), params: { query: { customer_id, ...(cursor ? { cursor } : {}), limit: 50 } } }).then(value),
  archiveSettings: () => client.GET("/api/v1/archive-settings", options()).then(value),
  saveArchiveSettings: (body: Schemas["SaveArchiveSettings"], key: string) => client.POST("/api/v1/archive-settings", { ...commandOptions(key), body }).then(value),
  archiveSources: (kind: ArchiveSource["kind"], cursor?: string) => client.GET("/api/v1/archive-sources", { ...options(), params: { query: { kind, ...(cursor ? { cursor } : {}), limit: 25 } } }).then(value),
  previewArchive: (body: ArchivePreviewRequest) => client.POST("/api/v1/archives/preview", { ...options(), body }).then(value),
  createArchive: (body: Schemas["ArchiveCreateRequest"], key: string) => client.POST("/api/v1/archives", { ...commandOptions(key), signal: AbortSignal.timeout(30000), body }).then(value),
  archives: (cursor?: string) => client.GET("/api/v1/archives", { ...options(), params: { query: { ...(cursor ? { cursor } : {}) } } }).then(value),
  archive: (identifier: string) => client.GET("/api/v1/archives/{identifier}", { ...options(), params: { path: { identifier } } }).then(value),
  generateArchive: (identifier: string) => client.POST("/api/v1/archives/{identifier}/generate", { ...options(), signal: AbortSignal.timeout(60000), params: { path: { identifier } } }).then(value),
  downloadArchive: async (item: ArchiveBatch) => {
    const response = await fetch(`/api/v1/archives/${item.id}/file?historical=${!item.current}`, { ...options(), signal: AbortSignal.timeout(30000) });
    if (!response.ok) value({ response, error: await response.json() });
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a"); link.href = url;
    link.download = `工作文件-${item.id}${item.current ? "" : "-历史快照"}.zip`;
    document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 10000);
  },
  deliveryLayout: (locale: Locale = getLocale()) => client.GET("/api/v1/delivery-layout", { ...options(), params: { query: { locale } } }).then(value),
  saveDeliveryLayout: (body: Schemas["SaveDeliveryLayout"], key: string) => client.POST("/api/v1/delivery-layout", { ...commandOptions(key), body }).then(value),
  previewDeliveryLayout: async (delivery_id: string, config: DeliveryLayoutConfig, locale: Locale) => {
    const response = await fetch("/api/v1/delivery-layout/preview", { ...options(), method: "POST", headers: { ...options().headers, "Content-Type": "application/json" }, body: JSON.stringify({ delivery_id, config, locale }) });
    if (!response.ok) value({ response, error: await response.json() });
    return response.text();
  },
  statement: (statement_id: string) => client.GET("/api/v1/statements/{statement_id}", { ...options(), params: { path: { statement_id } } }).then(value),
  statements: (customer_id: string, cursor?: string) => client.GET("/api/v1/statements", { ...options(), params: { query: { customer_id, ...(cursor ? { cursor } : {}) } } }).then(value),
  statementCandidates: (customer_id: string, period_start: string, period_end: string, statement_id?: string, cursor?: string) => client.GET("/api/v1/statement-candidates", { ...options(), params: { query: { customer_id, period_start, period_end, ...(statement_id ? { statement_id } : {}), ...(cursor ? { cursor } : {}) } } }).then(value),
  createStatement: (body: StatementDraft, key: string) => client.POST("/api/v1/statements", { ...commandOptions(key), body }).then(value),
  saveStatement: (statement_id: string, body: Schemas["SaveDraftInput"], key: string, reopen = false) => reopen
    ? client.POST("/api/v1/statements/{statement_id}/reopen", { ...options(), params: { path: { statement_id }, header: { "Idempotency-Key": key } }, body }).then(value)
    : client.POST("/api/v1/statements/{statement_id}/save", { ...options(), params: { path: { statement_id }, header: { "Idempotency-Key": key } }, body }).then(value),
  closeStatement: (statement_id: string, body: Schemas["AbandonDraftInput"], key: string, exported: boolean) => exported
    ? client.POST("/api/v1/statements/{statement_id}/void", { ...options(), params: { path: { statement_id }, header: { "Idempotency-Key": key } }, body }).then(value)
    : client.POST("/api/v1/statements/{statement_id}/abandon", { ...options(), params: { path: { statement_id }, header: { "Idempotency-Key": key } }, body }).then(value),
  statementSettings: (customer_id: string) => client.GET("/api/v1/customers/{customer_id}/statement-settings", { ...options(), params: { path: { customer_id } } }).then(value),
  saveStatementSettings: (customer_id: string, body: Schemas["StatementSettingsInput"], key: string) => client.POST("/api/v1/customers/{customer_id}/statement-settings", { ...options(), params: { path: { customer_id }, header: { "Idempotency-Key": key } }, body }).then(value),
  statementExports: (statement_id: string, cursor?: string) => client.GET("/api/v1/statements/{statement_id}/exports", { ...options(), params: { path: { statement_id }, query: { ...(cursor ? { cursor } : {}) } } }).then(value),
  createStatementExport: (statement_id: string, expected_version: number, template_id: StatementSettings["template_id"], key: string, locale: Locale, customer_template_id?: string | null) => client.POST("/api/v1/statements/{statement_id}/exports", { ...options(), params: { path: { statement_id }, header: { "Idempotency-Key": key } }, body: { expected_version, template_id, customer_template_id: customer_template_id ?? null, locale } }).then(value),
  statementTemplates: (customer_id: string, cursor?: string) => client.GET("/api/v1/customers/{customer_id}/statement-templates", { ...options(), params: { path: { customer_id }, query: { ...(cursor ? { cursor } : {}) } } }).then(value),
  statementTemplate: (customer_id: string, template_id: string) => client.GET("/api/v1/customers/{customer_id}/statement-templates/{template_id}", { ...options(), params: { path: { customer_id, template_id } } }).then(value),
  inspectStatementTemplate: (customer_id: string, body: Schemas["TemplateFileInput"]) => client.POST("/api/v1/customers/{customer_id}/statement-templates/inspect", { ...options(), params: { path: { customer_id } }, body }).then(value),
  previewStatementTemplate: (customer_id: string, body: Schemas["TemplatePreviewInput"]) => client.POST("/api/v1/customers/{customer_id}/statement-templates/preview", { ...options(), signal: AbortSignal.timeout(30000), params: { path: { customer_id } }, body }).then(value),
  importStatementTemplate: (customer_id: string, body: Schemas["TemplateImportInput"], key: string) => client.POST("/api/v1/customers/{customer_id}/statement-templates", { ...options(), params: { path: { customer_id }, header: { "Idempotency-Key": key } }, body }).then(value),
  generateStatementExport: (export_id: string) => client.POST("/api/v1/statement-exports/{export_id}/generate", { ...options(), signal: AbortSignal.timeout(30000), params: { path: { export_id } } }).then(value),
  downloadStatementExport: async (item: StatementExport) => {
    const response = await fetch(`/api/v1/statement-exports/${item.id}/file?historical=${!item.current}`, { ...options() });
    if (!response.ok) value({ response, error: await response.json() });
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a"); link.href = url;
    link.download = `Statement-${item.statement_status === "confirmed" ? "Final" : "Draft"}-v${item.statement_version}-${item.id}${item.current ? "" : "-Historical"}.xlsx`;
    document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 10000);
  },
  upload: async (file: File, key: string) => {
    const response = await fetch("/api/v1/sources", { method: "POST", body: file, signal: AbortSignal.timeout(30000), headers: { "X-CSRF-Token": csrfToken, "Idempotency-Key": key, "X-Filename": encodeURIComponent(file.name), "Content-Type": file.type } });
    const body = await response.json();
    return value<Schemas["SourceResult"]>({ response, ...(response.ok ? { data: body } : { error: body }) });
  },
  sources: (cursor?: string) => client.GET("/api/v1/sources", { ...options(), params: { query: { ...(cursor ? { cursor } : {}), limit: 20 } } }).then(value),
  extract: (source_id: string, key: string) => client.POST("/api/v1/sources/{source_id}/extractions", { ...commandOptions(key), signal: AbortSignal.timeout(110000), params: { path: { source_id }, header: { "Idempotency-Key": key } } }).then(value),
  extraction: (extraction_id: string) => client.GET("/api/v1/extractions/{extraction_id}", { ...options(), params: { path: { extraction_id } } }).then(value),
  createDelivery: (body: DeliveryInput, key: string) => client.POST("/api/v1/deliveries", { ...commandOptions(key), body }).then(value),
  deliveries: (customer_id?: string, cursor?: string) => client.GET("/api/v1/deliveries", { ...options(), params: { query: { ...(customer_id ? { customer_id } : {}), ...(cursor ? { cursor } : {}), limit: 50 } } }).then(value),
  delivery: (delivery_id: string) => client.GET("/api/v1/deliveries/{delivery_id}", { ...options(), params: { path: { delivery_id } } }).then(value),
  voidDelivery: (delivery_id: string, expected_version: number, reason: string, key: string) => client.POST("/api/v1/deliveries/{delivery_id}/void", { ...options(), params: { path: { delivery_id }, header: { "Idempotency-Key": key } }, body: { expected_version, reason } }).then(value),
  session: () => client.GET("/api/v1/auth/session", options()).then(value),
  login: (username: string, password: string) => client.POST("/api/v1/auth/login", { ...options(), body: { username, password } }).then(value),
  logout: async () => {
    const result = await client.POST("/api/v1/auth/logout", options());
    if (!result.response.ok) value(result);
  },
  customers: () => client.GET("/api/v1/customers", options()).then(value),
  createCustomer: (full_name: string, key: string) => client.POST("/api/v1/customers", { ...commandOptions(key), body: { full_name } }).then(value),
  openLines: (customer_id?: string, cursor?: string, status: "active" | "deleted" = "active") => client.GET("/api/v1/orders/open-lines", {
    ...options(), params: { query: { ...(customer_id ? { customer_id } : {}), ...(cursor ? { cursor } : {}), status, limit: 50 } },
  }).then(value),
  detail: (order_id: string) => client.GET("/api/v1/orders/{order_id}", { ...options(), params: { path: { order_id } } }).then(value),
  preview: (body: OrderInput) => client.POST("/api/v1/orders/preview", { ...options(), body }).then(value),
  confirm: (body: OrderInput, key: string) => client.POST("/api/v1/orders", { ...commandOptions(key), body }).then(value),
  revise: (order_id: string, body: OrderInput, expected_version: number, reason: string, key: string) => client.POST("/api/v1/orders/{order_id}/revisions", {
    ...options(), params: { path: { order_id }, header: { "Idempotency-Key": key } }, body: { order: body, expected_version, reason },
  }).then(value),
  changeStatus: (order_id: string, target: "active" | "deleted", expected_version: number, reason: string, key: string) => target === "deleted"
    ? client.POST("/api/v1/orders/{order_id}/delete", { ...options(), params: { path: { order_id }, header: { "Idempotency-Key": key } }, body: { expected_version, reason } }).then(value)
    : client.POST("/api/v1/orders/{order_id}/restore", { ...options(), params: { path: { order_id }, header: { "Idempotency-Key": key } }, body: { expected_version, reason } }).then(value),
  evidence: (revision_id: string) => client.GET("/api/v1/documents/{revision_id}", { ...options(), params: { path: { revision_id } } }).then(value),
};
