from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BusinessCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    currency: str = "INR"
    timezone: str = "Asia/Kolkata"


class BusinessResponse(BaseModel):
    id: int
    name: str
    currency: str
    timezone: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DatabaseConnectionTest(BaseModel):
    db_type: str
    host: str
    port: int
    database_name: str
    username: str
    password: str
    ssl: bool = False


class DatabaseConnectionCreate(DatabaseConnectionTest):
    name: str = Field(min_length=2, max_length=255)


class DataSourceResponse(BaseModel):
    id: int
    name: str
    source_type: str
    status: str
    last_sync_at: datetime | None
    next_sync_at: datetime | None
    last_error: str | None
    records_imported: int
    is_paused: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ColumnMappingItem(BaseModel):
    source_column: str
    target_field: str


class ColumnMappingConfirm(BaseModel):
    dataset_type: str
    source_name: str
    mappings: list[ColumnMappingItem]


class ImportValidationSummary(BaseModel):
    job_id: int
    filename: str
    detected_dataset: str | None
    total_records: int
    valid_records: int
    warning_records: int
    error_records: int
    issues: list[dict[str, Any]]


class DateRangeFilter(BaseModel):
    start_date: datetime | None = None
    end_date: datetime | None = None
    compare_previous: bool = True
    category_id: int | None = None
    product_id: int | None = None
    customer_id: int | None = None
    region: str | None = None
    country: str | None = None
    sales_channel: str | None = None
    order_status: str | None = None
    payment_method: str | None = None
    granularity: str = "daily"


class KPICard(BaseModel):
    key: str
    label: str
    value: float | int | str | None = None
    change_pct: float | None = None
    format: str = "number"
    unavailable_reason: str | None = None


class ChartSeries(BaseModel):
    name: str
    data: list[dict[str, Any]]


class AnalyticsResponse(BaseModel):
    kpis: list[KPICard]
    charts: list[ChartSeries]
    tables: list[dict[str, Any]] = []
    meta: dict[str, Any] = {}


class InsightResponse(BaseModel):
    id: int
    insight_type: str
    title: str
    description: str
    impact: str | None
    recommended_action: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertResponse(BaseModel):
    id: int
    severity: str
    title: str
    message: str
    category: str | None
    is_read: bool
    is_dismissed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class DataAvailability(BaseModel):
    orders: bool = False
    products: bool = False
    customers: bool = False
    inventory: bool = False
    returns: bool = False
    marketing: bool = False
    events: bool = False


class ShopifyConnectRequest(BaseModel):
    shop_domain: str
    access_token: str
    name: str = "Shopify Store"


class WooCommerceConnectRequest(BaseModel):
    store_url: str
    consumer_key: str
    consumer_secret: str
    name: str = "WooCommerce Store"


class ConnectorRegisterRequest(BaseModel):
    name: str
    business_id: int


class ConnectorRegisterResponse(BaseModel):
    agent_id: int
    agent_token: str
    message: str


class DashboardLayoutSave(BaseModel):
    name: str = "Default"
    is_default: bool = True
    layout: dict[str, Any]


class AdSpendCreate(BaseModel):
    channel: str
    spend: float = Field(ge=0)
    date: datetime
    campaign: str | None = None


class AdSpendResponse(BaseModel):
    id: int
    channel: str | None
    spend: float
    date: datetime
    campaign: str | None

    model_config = {"from_attributes": True}


class SavedCustomReportCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    metric: str
    dimension: str
    date_range_preset: str = "30d"
    chart_type: str = "bar"
    filters: dict[str, Any] = {}


class SavedCustomReportResponse(BaseModel):
    id: int
    name: str
    metric: str
    dimension: str
    date_range_preset: str
    chart_type: str
    filters_json: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ScheduledReportCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    frequency: str = "weekly"
    recipient_email: EmailStr | None = None
    webhook_url: str | None = None
    is_active: bool = True


class ScheduledReportResponse(BaseModel):
    id: int
    name: str
    frequency: str
    recipient_email: str | None
    webhook_url: str | None
    is_active: bool
    last_sent_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AIQueryRequest(BaseModel):
    query: str


class AIQueryResponse(BaseModel):
    query: str
    intent: str
    answer: str
    data: list[dict[str, Any]] = []
    chart_type: str = "table"

