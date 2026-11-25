import ipaddress
import json
import os
import socket
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import get_current_user, get_verified_business, require_roles
from app.core.encryption import encrypt_value
from app.database.session import get_db
from app.imports.detection import inspect_file
from app.imports.validation import build_mapping_dict, import_valid_records, validate_dataframe, validate_file_magic_bytes
from app.integrations.connectors import (
    create_database_source,
    sync_database_source,
    sync_shopify,
    sync_woocommerce,
    test_database_connection,
)
from app.models import (
    ColumnMapping,
    ConnectorAgent,
    Customer,
    DataSource,
    DataSourceStatus,
    DataSourceType,
    ImportJob,
    ImportJobStatus,
    Inventory,
    Order,
    OrderItem,
    Product,
    Return,
    User,
    UserRole,
)
from app.schemas import (
    ColumnMappingConfirm,
    ConnectorRegisterRequest,
    ConnectorRegisterResponse,
    DatabaseConnectionCreate,
    DatabaseConnectionTest,
    DataSourceResponse,
    ShopifyConnectRequest,
    WooCommerceConnectRequest,
)

router = APIRouter(prefix="/data", tags=["data"])


def validate_target_host_ssrf(host: str) -> None:
    """Validate target host is not a restricted internal address (OWASP A03 SSRF Protection)."""
    clean_host = host.strip().lower()
    settings = get_settings()
    if clean_host in ("localhost", "127.0.0.1", "::1", "169.254.169.254", "0.0.0.0"):
        if settings.app_env.lower() == "production":
            raise HTTPException(status_code=400, detail="Connections to private/internal addresses are blocked in production.")
        return

    try:
        ip_list = socket.getaddrinfo(clean_host, None)
        for item in ip_list:
            ip_str = item[4][0]
            ip_obj = ipaddress.ip_address(ip_str)
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_reserved:
                if settings.app_env.lower() == "production":
                    raise HTTPException(
                        status_code=400,
                        detail="Target host resolves to a private/restricted IP range.",
                    )
    except socket.gaierror:
        raise HTTPException(status_code=400, detail="Host resolution failed or invalid host.")


@router.post("/test-connection")
async def test_connection(
    payload: DatabaseConnectionTest,
    user: User = Depends(require_roles(UserRole.admin, UserRole.analyst)),
):
    validate_target_host_ssrf(payload.host)
    return await test_database_connection(
        payload.db_type, payload.host, payload.port,
        payload.database_name, payload.username, payload.password, payload.ssl,
    )


@router.post("/connect-database", response_model=DataSourceResponse)
async def connect_database(
    business_id: int,
    payload: DatabaseConnectionCreate,
    user: User = Depends(require_roles(UserRole.admin, UserRole.analyst)),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    validate_target_host_ssrf(payload.host)
    test = await test_database_connection(
        payload.db_type, payload.host, payload.port,
        payload.database_name, payload.username, payload.password, payload.ssl,
    )
    if not test["success"]:
        raise HTTPException(status_code=400, detail=test["message"])
    source = await create_database_source(
        db, business_id, payload.name, payload.db_type,
        payload.host, payload.port, payload.database_name,
        payload.username, payload.password, payload.ssl,
    )
    await sync_database_source(db, source)
    return source


@router.post("/upload/{business_id}")
async def upload_files(
    business_id: int,
    files: list[UploadFile] = File(...),
    user: User = Depends(require_roles(UserRole.admin, UserRole.analyst)),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    settings = get_settings()
    upload_dir = Path(settings.upload_dir) / str(business_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for file in files:
        if not file.filename:
            continue
        ext = file.filename.lower().split(".")[-1]
        if ext not in ("csv", "xlsx", "xls"):
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.filename}")

        file_id = uuid.uuid4().hex
        dest = upload_dir / f"{file_id}_{file.filename}"
        content = await file.read()
        if len(content) > settings.max_upload_size_mb * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File size exceeds maximum allowed limit.")
        dest.write_bytes(content)

        if not validate_file_magic_bytes(str(dest), file.filename):
            dest.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail=f"File signature validation failed for {file.filename}")

        inspection = inspect_file(str(dest), file.filename)
        job = ImportJob(
            business_id=business_id,
            filename=file.filename,
            detected_dataset=inspection["detected_dataset"],
            status=ImportJobStatus.validating,
            column_mappings_json=json.dumps(inspection["suggested_mappings"]),
        )
        db.add(job)
        await db.flush()

        mappings = build_mapping_dict(inspection["suggested_mappings"])
        import pandas as pd
        if file.filename.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(dest)
        else:
            df = pd.read_csv(dest)

        validation = validate_dataframe(df, inspection["detected_dataset"] or "orders", mappings)
        job.total_records = validation["total_records"]
        job.valid_records = validation["valid_records"]
        job.warning_records = validation["warning_records"]
        job.error_records = validation["error_records"]
        job.validation_report_json = json.dumps(validation)
        job.status = ImportJobStatus.ready

        results.append({
            "job_id": job.id,
            "filename": file.filename,
            "inspection": inspection,
            "validation": validation,
            "file_path": str(dest),
        })

    return {"uploads": results}


@router.post("/confirm-mapping/{business_id}")
async def confirm_mapping(
    business_id: int,
    payload: ColumnMappingConfirm,
    user: User = Depends(require_roles(UserRole.admin, UserRole.analyst)),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    mapping = ColumnMapping(
        business_id=business_id,
        dataset_type=payload.dataset_type,
        source_name=payload.source_name,
        mappings_json=json.dumps([m.model_dump() for m in payload.mappings]),
    )
    db.add(mapping)
    await db.flush()
    return {"success": True, "mapping_id": mapping.id}


@router.post("/import/{business_id}/{job_id}")
async def import_job(
    business_id: int,
    job_id: int,
    user: User = Depends(require_roles(UserRole.admin, UserRole.analyst)),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    result = await db.execute(select(ImportJob).where(ImportJob.id == job_id, ImportJob.business_id == business_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found")

    settings = get_settings()
    upload_dir = Path(settings.upload_dir) / str(business_id)
    matches = list(upload_dir.glob(f"*_{job.filename}"))
    if not matches:
        raise HTTPException(status_code=404, detail="Uploaded file not found")

    mappings = json.loads(job.column_mappings_json or "[]")
    job.status = ImportJobStatus.importing
    summary = await import_valid_records(
        db, business_id, job.detected_dataset or "orders",
        str(matches[0]), job.filename, mappings,
    )
    job.status = ImportJobStatus.completed
    job.valid_records = summary["imported"]
    job.error_records = summary["failed"]
    return summary


@router.get("/sources/{business_id}", response_model=list[DataSourceResponse])
async def list_sources(
    business_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    result = await db.execute(select(DataSource).where(DataSource.business_id == business_id))
    return result.scalars().all()


@router.post("/shopify/{business_id}", response_model=DataSourceResponse)
async def connect_shopify(
    business_id: int,
    payload: ShopifyConnectRequest,
    user: User = Depends(require_roles(UserRole.admin, UserRole.analyst)),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    config = {"shop_domain": payload.shop_domain, "access_token": payload.access_token}
    source = DataSource(
        business_id=business_id,
        name=payload.name,
        source_type=DataSourceType.shopify,
        status=DataSourceStatus.connected,
        config_encrypted=encrypt_value(json.dumps(config)),
    )
    db.add(source)
    await db.flush()
    await sync_shopify(db, source)
    return source


@router.post("/woocommerce/{business_id}", response_model=DataSourceResponse)
async def connect_woocommerce(
    business_id: int,
    payload: WooCommerceConnectRequest,
    user: User = Depends(require_roles(UserRole.admin, UserRole.analyst)),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    config = {
        "store_url": payload.store_url,
        "consumer_key": payload.consumer_key,
        "consumer_secret": payload.consumer_secret,
    }
    source = DataSource(
        business_id=business_id,
        name=payload.name,
        source_type=DataSourceType.woocommerce,
        status=DataSourceStatus.connected,
        config_encrypted=encrypt_value(json.dumps(config)),
    )
    db.add(source)
    await db.flush()
    await sync_woocommerce(db, source)
    return source


@router.post("/sync/{business_id}/{source_id}")
async def sync_source(
    business_id: int,
    source_id: int,
    user: User = Depends(require_roles(UserRole.admin, UserRole.analyst)),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    result = await db.execute(
        select(DataSource).where(DataSource.id == source_id, DataSource.business_id == business_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")
    if source.source_type == DataSourceType.shopify:
        imported = await sync_shopify(db, source)
    elif source.source_type == DataSourceType.woocommerce:
        imported = await sync_woocommerce(db, source)
    elif source.source_type in (DataSourceType.postgresql, DataSourceType.mysql, DataSourceType.sqlserver):
        imported = await sync_database_source(db, source)
    else:
        imported = 0
    return {"imported": imported, "status": source.status.value}


@router.post("/seed-sample-data/{business_id}")
async def seed_sample_data(
    business_id: int,
    user: User = Depends(require_roles(UserRole.admin, UserRole.analyst)),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    from app.seed_demo_data import seed_365d_store_data
    from app.analytics.engine import invalidate_analytics_cache

    stats = await seed_365d_store_data(db, business_id)
    invalidate_analytics_cache(business_id)

    total_imported = stats.get("orders", 0) + stats.get("products", 0) + stats.get("customers", 0)
    return {
        "success": True,
        "total_imported": total_imported,
        "stats": stats,
        "message": f"Successfully imported {total_imported} sample records into your dashboard store!",
    }


@router.post("/sources/{business_id}/{source_id}/toggle-pause")
async def toggle_pause_source(
    business_id: int,
    source_id: int,
    user: User = Depends(require_roles(UserRole.admin, UserRole.analyst)),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    result = await db.execute(
        select(DataSource).where(DataSource.id == source_id, DataSource.business_id == business_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")
    source.is_paused = not source.is_paused
    source.status = DataSourceStatus.paused if source.is_paused else DataSourceStatus.connected
    await db.flush()
    return {"is_paused": source.is_paused, "status": source.status.value}


@router.delete("/sources/{business_id}/{source_id}")
async def disconnect_source(
    business_id: int,
    source_id: int,
    user: User = Depends(require_roles(UserRole.admin, UserRole.analyst)),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    result = await db.execute(
        select(DataSource).where(DataSource.id == source_id, DataSource.business_id == business_id)
    )
    source = result.scalar_one_or_none()
    if source:
        await db.delete(source)
        await db.flush()
    return {"success": True}


# Local Connector Agent API
@router.post("/connector/register", response_model=ConnectorRegisterResponse)
async def register_connector(
    payload: ConnectorRegisterRequest,
    user: User = Depends(require_roles(UserRole.admin, UserRole.analyst)),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(payload.business_id, user, db)
    agent_token = f"agt_{uuid.uuid4().hex}"
    from passlib.hash import bcrypt
    agent = ConnectorAgent(
        business_id=payload.business_id,
        user_id=user.id,
        name=payload.name,
        agent_token_hash=bcrypt.hash(agent_token),
        status="registered",
    )
    db.add(agent)
    await db.flush()
    return ConnectorRegisterResponse(
        agent_id=agent.id,
        agent_token=agent_token,
        message="Local agent token created. Use this token in connector/agent.py script.",
    )


@router.get("/connector/agents/{business_id}")
async def list_connector_agents(
    business_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_verified_business(business_id, user, db)
    res = await db.execute(select(ConnectorAgent).where(ConnectorAgent.business_id == business_id))
    agents = res.scalars().all()
    return [
        {
            "id": a.id,
            "name": a.name,
            "status": a.status,
            "db_type": a.db_type,
            "last_sync_at": a.last_sync_at,
            "created_at": a.created_at,
        }
        for a in agents
    ]
