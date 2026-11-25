"""
Seed Data Generator for E-Commerce Analytics & BI Platform.
Generates 1 full year (365 days ago -> today) of realistic, internally-consistent
Indian e-commerce data using a mathematical Trend + Seasonality + Noise model.

Usage via CLI:
    python -m app.seed_demo_data --business-id 1 --seed-val 42
    python -m app.seed_demo_data --reset --business-id 1
"""

import argparse
import asyncio
import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import AsyncSessionLocal
from app.models import (
    Alert,
    AlertSeverity,
    Business,
    Category,
    Customer,
    DataSource,
    DataSourceStatus,
    DataSourceType,
    Insight,
    Inventory,
    MarketingSpend,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    Return,
    User,
    UserRole,
    WebsiteEvent,
)


SYNTHETIC_TAG = "synthetic_seed"

INDIAN_CITIES_STATES = [
    ("Mumbai", "Maharashtra", 0.22),
    ("Delhi", "Delhi", 0.18),
    ("Bengaluru", "Karnataka", 0.16),
    ("Chennai", "Tamil Nadu", 0.10),
    ("Hyderabad", "Telangana", 0.09),
    ("Pune", "Maharashtra", 0.08),
    ("Ahmedabad", "Gujarat", 0.07),
    ("Kolkata", "West Bengal", 0.05),
    ("Jaipur", "Rajasthan", 0.03),
    ("Lucknow", "Uttar Pradesh", 0.02),
]

INDIAN_FIRST_NAMES = [
    "Aarav", "Ananya", "Priya", "Rajesh", "Vikram", "Sneha", "Rohan", "Kavya",
    "Ishaan", "Pooja", "Arjun", "Diya", "Aditya", "Neha", "Rahul", "Meera",
    "Siddharth", "Riya", "Karan", "Tanvi", "Amit", "Shreya", "Nikhil", "Swati",
    "Varun", "Isha", "Manish", "Divya", "Gaurav", "Aarti", "Tarun", "Bhavna",
]

INDIAN_LAST_NAMES = [
    "Sharma", "Patel", "Kumar", "Singh", "Iyer", "Verma", "Mehta", "Nair",
    "Deshmukh", "Banerjee", "Reddy", "Gupta", "Joshi", "Chopra", "Kulkarni", "Rao",
    "Agarwal", "Bhat", "Saxena", "Mukherjee", "Kapoor", "Pillai", "Das", "Shah",
]

CATEGORIES_SPEC = [
    {"name": "Electronics & Accessories", "weight": 0.28},
    {"name": "Ethnic & Fusion Wear", "weight": 0.18},
    {"name": "Home & Kitchenware", "weight": 0.15},
    {"name": "Beauty & Personal Care", "weight": 0.12},
    {"name": "Footwear", "weight": 0.10},
    {"name": "Gourmet Foods & Spices", "weight": 0.07},
    {"name": "Watches & Jewelry", "weight": 0.06},
    {"name": "Books & Stationery", "weight": 0.04},
]

PRODUCTS_SPEC = [
    # Electronics
    ("Noise-Cancelling Wireless Earbuds", "Electronics & Accessories", 2499.0, 1250.0, "SKU-ELE-001"),
    ("Smart Fitness Band Pro", "Electronics & Accessories", 1999.0, 950.0, "SKU-ELE-002"),
    ("Fast Charging Power Bank 20000mAh", "Electronics & Accessories", 1499.0, 720.0, "SKU-ELE-003"),
    ("Ergonomic Wireless Mouse", "Electronics & Accessories", 899.0, 410.0, "SKU-ELE-004"),
    ("Mechanical RGB Gaming Keyboard", "Electronics & Accessories", 3499.0, 1800.0, "SKU-ELE-005"),
    ("Portable Bluetooth Speaker 20W", "Electronics & Accessories", 2999.0, 1400.0, "SKU-ELE-006"),
    ("4K Ultra HD Streaming Dongle", "Electronics & Accessories", 3999.0, 2100.0, "SKU-ELE-007"),
    ("USB-C Multiport Hub", "Electronics & Accessories", 1299.0, 580.0, "SKU-ELE-008"),

    # Ethnic Wear
    ("Pure Silk Kanjivaram Saree", "Ethnic & Fusion Wear", 8999.0, 4500.0, "SKU-ETH-001"),
    ("Designer Anarkali Kurta Set", "Ethnic & Fusion Wear", 3499.0, 1650.0, "SKU-ETH-002"),
    ("Handloom Chanderi Cotton Dupatta", "Ethnic & Fusion Wear", 1299.0, 550.0, "SKU-ETH-003"),
    ("Men's Royal Silk Nehru Jacket", "Ethnic & Fusion Wear", 2799.0, 1300.0, "SKU-ETH-004"),
    ("Embroidered Raw Silk Lehenga", "Ethnic & Fusion Wear", 12999.0, 6800.0, "SKU-ETH-005"),
    ("Printed Cotton Chikankari Kurti", "Ethnic & Fusion Wear", 1599.0, 720.0, "SKU-ETH-006"),
    ("Jacquard Sherwani for Men", "Ethnic & Fusion Wear", 9999.0, 5100.0, "SKU-ETH-007"),

    # Home & Kitchen
    ("Brass Filter Coffee Maker (300ml)", "Home & Kitchenware", 1199.0, 540.0, "SKU-KIT-001"),
    ("Cast Iron Pre-Seasoned Kadhai", "Home & Kitchenware", 1899.0, 920.0, "SKU-KIT-002"),
    ("Handcrafted Ceramic Dinnerware Set", "Home & Kitchenware", 4499.0, 2100.0, "SKU-KIT-003"),
    ("Stainless Steel Multi-Tier Bento Box", "Home & Kitchenware", 999.0, 450.0, "SKU-KIT-004"),
    ("Electric Spice & Coffee Grinder", "Home & Kitchenware", 1699.0, 810.0, "SKU-KIT-005"),
    ("Copper Water Pitcher (1.5L)", "Home & Kitchenware", 1499.0, 680.0, "SKU-KIT-006"),

    # Beauty
    ("Ayurvedic Kumkumadi Night Serum", "Beauty & Personal Care", 1499.0, 520.0, "SKU-BTY-001"),
    ("Organic Cold-Pressed Coconut Hair Oil", "Beauty & Personal Care", 499.0, 180.0, "SKU-BTY-002"),
    ("Saffron & Ubtan Face Wash", "Beauty & Personal Care", 399.0, 140.0, "SKU-BTY-003"),
    ("Rosewater Hydrating Facial Mist", "Beauty & Personal Care", 599.0, 210.0, "SKU-BTY-004"),
    ("Charcoal Deep Cleansing Sheet Mask", "Beauty & Personal Care", 299.0, 90.0, "SKU-BTY-005"),
    ("Sandalwood & Turmeric Moisturizer", "Beauty & Personal Care", 899.0, 320.0, "SKU-BTY-006"),

    # Footwear
    ("Handcrafted Kolhapuri Leather Chappals", "Footwear", 1799.0, 780.0, "SKU-FTW-001"),
    ("Embroidered Jutti for Women", "Footwear", 1499.0, 620.0, "SKU-FTW-002"),
    ("Men's Formal Oxford Leather Shoes", "Footwear", 3999.0, 1850.0, "SKU-FTW-003"),
    ("Breathable Running Sneakers", "Footwear", 2499.0, 1100.0, "SKU-FTW-004"),
    ("Slip-On Canvas Loafers", "Footwear", 1299.0, 540.0, "SKU-FTW-005"),

    # Gourmet Foods
    ("Organic Kashmiri Saffron (1g)", "Gourmet Foods & Spices", 999.0, 480.0, "SKU-FOD-001"),
    ("Single-Origin Malabar Black Pepper", "Gourmet Foods & Spices", 399.0, 160.0, "SKU-FOD-002"),
    ("Artisanal Spiced Chai Blend (250g)", "Gourmet Foods & Spices", 499.0, 190.0, "SKU-FOD-003"),
    ("Raw Forest Wildflower Honey (500g)", "Gourmet Foods & Spices", 699.0, 280.0, "SKU-FOD-004"),
    ("Premium A2 Gir Cow Desi Ghee (500ml)", "Gourmet Foods & Spices", 1199.0, 590.0, "SKU-FOD-005"),

    # Watches & Jewelry
    ("Titanium Chronograph Analog Watch", "Watches & Jewelry", 6999.0, 3200.0, "SKU-WCH-001"),
    ("Minimalist Rose Gold Mesh Watch", "Watches & Jewelry", 4499.0, 1950.0, "SKU-WCH-002"),
    ("925 Sterling Silver Pendant Necklace", "Watches & Jewelry", 2299.0, 890.0, "SKU-WCH-003"),
    ("Kundan Choker Jewelry Set", "Watches & Jewelry", 5499.0, 2400.0, "SKU-WCH-004"),

    # Books
    ("Hardcover Business & Leadership Journal", "Books & Stationery", 799.0, 280.0, "SKU-BOK-001"),
    ("Handmade Jute Cover Diary", "Books & Stationery", 499.0, 160.0, "SKU-BOK-002"),
    ("Brass Calligraphy Fountain Pen Set", "Books & Stationery", 1299.0, 480.0, "SKU-BOK-003"),
]


def _weekly_seasonality(day_of_week: int) -> float:
    # 0=Mon, 6=Sun
    weights = [0.90, 0.92, 0.98, 1.00, 1.12, 1.25, 1.22]
    return weights[day_of_week]


def _monthly_seasonality(day_index: int) -> float:
    # 365 day cycle
    # Diwali / Great Indian Festival (Day 260-275) -> 2.5x spike
    if 260 <= day_index <= 275:
        peak_offset = abs(day_index - 268)
        return 2.5 - (peak_offset * 0.08)
    # Year End Sale (Day 320-330) -> 1.8x
    if 320 <= day_index <= 330:
        return 1.8
    # Summer Clearance (Day 110-120) -> 1.5x
    if 110 <= day_index <= 120:
        return 1.5
    # Republic Day Sale (Day 20-25) -> 1.4x
    if 20 <= day_index <= 25:
        return 1.4
    return 1.0


async def seed_365d_store_data(db: AsyncSession, business_id: int, seed_value: int = 42, reset_first: bool = True) -> dict[str, int]:
    random.seed(seed_value)

    if reset_first:
        await reset_synthetic_seed_data(db, business_id)

    # 0. Ensure missing 'source' columns exist on alerts & insights if created under old schema
    for tbl in ["alerts", "insights"]:
        try:
            await db.execute(text(f"ALTER TABLE {tbl} ADD COLUMN source VARCHAR(64)"))
            await db.commit()
        except Exception:
            await db.rollback()

    # 1. Ensure Business exists
    biz_res = await db.execute(select(Business).where(Business.id == business_id))
    biz = biz_res.scalar_one_or_none()
    if not biz:
        usr_res = await db.execute(select(User).order_by(User.id.asc()).limit(1))
        usr = usr_res.scalar_one_or_none()
        if not usr:
            raise RuntimeError("No user account found in database. Please register an admin account before seeding store data.")
        biz = Business(id=business_id, user_id=usr.id, name="Bharat Bazaar Commerce", currency="INR", timezone="Asia/Kolkata")
        db.add(biz)
        await db.flush()

    # 2. Seed Categories
    category_map = {}
    for spec in CATEGORIES_SPEC:
        cat_res = await db.execute(
            select(Category).where(Category.business_id == business_id, Category.name == spec["name"])
        )
        cat = cat_res.scalar_one_or_none()
        if not cat:
            cat = Category(business_id=business_id, name=spec["name"], source=SYNTHETIC_TAG)
            db.add(cat)
            await db.flush()
        category_map[spec["name"]] = cat.id

    # 3. Seed Products & Inventory
    products = []
    for name, cat_name, price, cost, sku in PRODUCTS_SPEC:
        cat_id = category_map[cat_name]
        p_res = await db.execute(select(Product).where(Product.business_id == business_id, Product.sku == sku))
        p = p_res.scalar_one_or_none()
        if not p:
            p = Product(
                business_id=business_id,
                category_id=cat_id,
                sku=sku,
                name=name,
                price=price,
                cost_price=cost,
                stock=random.randint(15, 200),
                source=SYNTHETIC_TAG,
            )
            db.add(p)
            await db.flush()
        products.append(p)

    # Add inventory items for products
    for p in products:
        inv_res = await db.execute(select(Inventory).where(Inventory.business_id == business_id, Inventory.product_id == p.id))
        if not inv_res.scalar_one_or_none():
            # Randomly set 4 SKUs to low stock (<10) and 2 to out of stock
            stock_val = p.stock
            if p.sku in ("SKU-ELE-004", "SKU-ETH-003", "SKU-KIT-001", "SKU-BTY-005"):
                stock_val = random.randint(2, 8)
            elif p.sku in ("SKU-FTW-002", "SKU-WCH-003"):
                stock_val = 0

            inv = Inventory(
                business_id=business_id,
                product_id=p.id,
                stock_quantity=stock_val,
                reorder_level=15,
                source=SYNTHETIC_TAG,
            )
            db.add(inv)

    # 4. Seed Customers (500 Indian Customers spread across 365 days)
    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=365)).replace(hour=0, minute=0, second=0, microsecond=0)
    customers = []

    for idx in range(500):
        # Weighted random city
        r_val = random.random()
        cum = 0.0
        chosen_city, chosen_state = INDIAN_CITIES_STATES[0][0], INDIAN_CITIES_STATES[0][1]
        for c, s, w in INDIAN_CITIES_STATES:
            cum += w
            if r_val <= cum:
                chosen_city, chosen_state = c, s
                break

        first_name = random.choice(INDIAN_FIRST_NAMES)
        last_name = random.choice(INDIAN_LAST_NAMES)
        full_name = f"{first_name} {last_name}"
        email = f"{first_name.lower()}.{last_name.lower()}{idx+10}@gmail.com"
        signup_dt = start_date + timedelta(days=random.randint(0, 350))

        c_obj = Customer(
            business_id=business_id,
            name=full_name,
            email=email,
            region=chosen_state,
            city=chosen_city,
            country="India",
            created_at=signup_dt,
            source=SYNTHETIC_TAG,
        )
        db.add(c_obj)
        customers.append((c_obj, signup_dt))
    await db.flush()

    # 5. Generate 365 Days Orders & Order Items
    orders_created = 0
    items_created = 0
    returns_created = 0
    events_created = 0

    base_orders_per_day = 12.0
    outlier_days = {
        180: 4.2,  # Flash sale spike
        295: 3.5,  # Brand anniversary
        145: 0.15, # Gateway outage drop
        85: 0.3,   # Supply disruption drop
    }

    channels = ["Direct", "Paid Social", "Organic Search", "Email", "Referral"]
    channel_weights = [0.35, 0.28, 0.20, 0.10, 0.07]
    payment_methods = ["UPI", "Credit Card", "Debit Card", "NetBanking", "COD"]
    payment_weights = [0.52, 0.20, 0.12, 0.08, 0.08]

    products_by_cat: dict[int, list[Product]] = {}
    for p in products:
        products_by_cat.setdefault(p.category_id, []).append(p)

    all_orders = []
    days_span = (now.date() - start_date.date()).days + 1

    for day_idx in range(days_span):
        current_dt = start_date + timedelta(days=day_idx)
        if current_dt.date() > now.date():
            break
        is_today = (current_dt.date() == now.date())
        dow = current_dt.weekday()

        # Growth trend: +35% over 365 days
        growth = 0.35 * (day_idx / 365.0)
        weekly = _weekly_seasonality(dow)
        monthly = _monthly_seasonality(day_idx % 365)
        noise = random.uniform(-0.10, 0.10)

        multiplier = outlier_days.get(day_idx % 365, 1.0)
        expected_orders = base_orders_per_day * (1.0 + growth) * weekly * monthly * (1.0 + noise) * multiplier
        day_order_count = max(1, int(round(expected_orders)))
        if is_today:
            day_order_count = max(day_order_count, len(category_map) * 2)

        # Eligible customers for this day (signed up on or before this day)
        eligible_custs = [c for c, s_dt in customers if s_dt <= current_dt]
        if not eligible_custs:
            eligible_custs = [customers[0][0]]

        order_limit_hour = max(8, min(23, now.hour))

        for order_idx in range(day_order_count):
            cust = random.choice(eligible_custs)
            if is_today:
                ord_h = random.randint(8, order_limit_hour) if order_limit_hour > 8 else 8
                ord_m = random.randint(0, now.minute if ord_h == now.hour else 59)
                order_time = current_dt.replace(hour=ord_h, minute=ord_m, second=random.randint(0, 59))
            else:
                order_time = current_dt + timedelta(hours=random.randint(8, 22), minutes=random.randint(0, 59))

            # Channel & Payment Method
            channel = random.choices(channels, weights=channel_weights)[0]
            pay_method = random.choices(payment_methods, weights=payment_weights)[0]

            # Select products: If today and order_idx < len(category_map), guarantee order for that category
            cat_list = list(category_map.values())
            if is_today and order_idx < len(cat_list):
                target_cat_id = cat_list[order_idx]
                cat_prods = products_by_cat.get(target_cat_id, products)
                chosen_prods = [random.choice(cat_prods)]
                if random.random() < 0.35:
                    other_prods = [p for p in products if p.id != chosen_prods[0].id]
                    chosen_prods.extend(random.sample(other_prods, k=random.randint(1, 2)))
            else:
                num_items = random.choices([1, 2, 3, 4], weights=[0.60, 0.25, 0.10, 0.05])[0]
                chosen_prods = random.sample(products, k=min(num_items, len(products)))

            subtotal = 0.0
            order_items = []
            for p in chosen_prods:
                qty = random.choices([1, 2, 3], weights=[0.80, 0.15, 0.05])[0]
                item_price = p.price
                item_cost = p.cost_price or (p.price * 0.6)
                subtotal += item_price * qty
                order_items.append((p.id, qty, item_price, item_cost))

            discount = round(subtotal * random.choice([0.0, 0.05, 0.10, 0.15]), 2) if subtotal > 1500 else 0.0
            shipping = 0.0 if subtotal > 999 else 70.0
            tax = round((subtotal - discount) * 0.18, 2)
            payment_fee = round((subtotal - discount + shipping + tax) * 0.02, 2)
            total_amount = round(subtotal - discount + shipping + tax, 2)

            # Order status distribution
            st_roll = random.random()
            if st_roll < 0.86:
                status_str = "delivered"
            elif st_roll < 0.92:
                status_str = "shipped"
            elif st_roll < 0.95:
                status_str = "processing"
            elif st_roll < 0.98:
                status_str = "returned"
            else:
                status_str = "cancelled"

            ord_obj = Order(
                business_id=business_id,
                customer_id=cust.id,
                order_date=order_time,
                status=status_str,
                subtotal=subtotal,
                discount=discount,
                shipping_cost=shipping,
                tax=tax,
                payment_fee=payment_fee,
                total_amount=total_amount,
                payment_method=pay_method,
                sales_channel=channel,
                source=SYNTHETIC_TAG,
                source_record_id=f"SEED-ORD-{day_idx+1}-{orders_created+1}",
            )
            db.add(ord_obj)
            await db.flush()
            orders_created += 1

            for p_id, qty, u_price, u_cost in order_items:
                oi = OrderItem(
                    order_id=ord_obj.id,
                    product_id=p_id,
                    quantity=qty,
                    unit_price=u_price,
                    unit_cost=u_cost,
                    discount=0.0,
                )
                db.add(oi)
                items_created += 1

            all_orders.append((ord_obj, order_items))

            # If status returned, generate Return record
            if status_str == "returned":
                ret_dt = order_time + timedelta(days=random.randint(3, 8))
                ret_p_id, ret_qty, ret_price, _ = order_items[0]
                ret_obj = Return(
                    business_id=business_id,
                    order_id=ord_obj.id,
                    product_id=ret_p_id,
                    quantity=ret_qty,
                    reason=random.choice(["Size or fit mismatch", "Defective or damaged", "Product differs from image", "Changed mind"]),
                    refund_amount=round(ret_price * ret_qty, 2),
                    return_date=ret_dt,
                    source=SYNTHETIC_TAG,
                )
                db.add(ret_obj)
                returns_created += 1

        # Generate Website Funnel Events for this day
        # Traffic = 12x order count
        views_count = day_order_count * random.randint(10, 14)
        for _ in range(views_count):
            if is_today:
                ev_h = random.randint(0, order_limit_hour) if order_limit_hour > 0 else 0
                ev_m = random.randint(0, now.minute if ev_h == now.hour else 59)
                ev_dt = current_dt.replace(hour=ev_h, minute=ev_m, second=random.randint(0, 59))
            else:
                ev_dt = current_dt + timedelta(hours=random.randint(0, 23), minutes=random.randint(0, 59))
            ev = WebsiteEvent(
                business_id=business_id,
                session_id=f"SESS-{day_idx}-{random.randint(1000, 9999)}",
                visitor_id=f"VIS-{random.randint(100, 999)}",
                event_type="page_view",
                event_date=ev_dt,
                source=SYNTHETIC_TAG,
            )
            db.add(ev)
            events_created += 1

        # Add to cart events = 2.5x order count
        for _ in range(int(day_order_count * 2.5)):
            if is_today:
                ev_h = random.randint(0, order_limit_hour) if order_limit_hour > 0 else 0
                ev_m = random.randint(0, now.minute if ev_h == now.hour else 59)
                ev_dt = current_dt.replace(hour=ev_h, minute=ev_m, second=random.randint(0, 59))
            else:
                ev_dt = current_dt + timedelta(hours=random.randint(0, 23), minutes=random.randint(0, 59))
            ev = WebsiteEvent(
                business_id=business_id,
                session_id=f"SESS-{day_idx}-{random.randint(1000, 9999)}",
                visitor_id=f"VIS-{random.randint(100, 999)}",
                event_type="add_to_cart",
                product_id=random.choice(products).id,
                event_date=ev_dt,
                source=SYNTHETIC_TAG,
            )
            db.add(ev)
            events_created += 1

        # Marketing Spend per channel for this day
        meta_spend = round(random.uniform(400.0, 1200.0) * (1.0 + monthly * 0.4), 2)
        google_spend = round(random.uniform(300.0, 900.0) * (1.0 + monthly * 0.3), 2)
        email_spend = round(random.uniform(50.0, 150.0), 2)

        for ch_name, sp_val in [("Meta Ads", meta_spend), ("Google Search Ads", google_spend), ("Email Campaign", email_spend)]:
            m_obj = MarketingSpend(
                business_id=business_id,
                campaign=f"Campaign-{ch_name.replace(' ', '')}",
                channel=ch_name,
                spend=sp_val,
                date=current_dt,
                revenue=round(sp_val * random.uniform(2.8, 4.8), 2),
                conversions=int(round(sp_val / random.uniform(150.0, 350.0))),
                source=SYNTHETIC_TAG,
            )
            db.add(m_obj)

    # 6. Seed Business Alerts & Insights
    alert1 = Alert(
        business_id=business_id,
        severity=AlertSeverity.critical,
        title="Critical Low Stock Warning",
        message="SKU-ETH-003 (Handloom Chanderi Cotton Dupatta) has fallen below reorder threshold (3 units remaining).",
        category="inventory",
        source=SYNTHETIC_TAG,
    )
    alert2 = Alert(
        business_id=business_id,
        severity=AlertSeverity.positive,
        title="Festive Revenue Milestone Reached",
        message="Diwali Festive Sale window generated ₹14.8L gross revenue (+145% vs 30-day baseline).",
        category="revenue",
        source=SYNTHETIC_TAG,
    )
    db.add(alert1)
    db.add(alert2)

    insight1 = Insight(
        business_id=business_id,
        insight_type="revenue_growth",
        title="Electronics & Ethnic Wear Drive 46% Gross Margin",
        description="Electronics & Accessories combined with Ethnic Fusion Wear represent 46% of total store contribution margin over the last 365 days.",
        impact="High Margin Impact",
        recommended_action="Increase Meta Ad spend allocation towards high-performing silk sarees and wireless earbuds.",
        source=SYNTHETIC_TAG,
    )
    db.add(insight1)

    # 7. Add Data Source record
    ds_res = await db.execute(select(DataSource).where(DataSource.business_id == business_id, DataSource.name == "365-Day Synthetic Store History"))
    if not ds_res.scalar_one_or_none():
        ds = DataSource(
            business_id=business_id,
            name="365-Day Synthetic Store History",
            source_type=DataSourceType.postgresql,
            status=DataSourceStatus.connected,
            records_imported=orders_created,
        )
        db.add(ds)

    await db.commit()

    # 8. Export CSV, Excel & Shopify JSON Fixtures
    _export_sample_files(products, customers, all_orders)

    return {
        "categories": len(category_map),
        "products": len(products),
        "customers": len(customers),
        "orders": orders_created,
        "order_items": items_created,
        "returns": returns_created,
        "events": events_created,
    }


def _export_sample_files(products, customers, orders):
    sample_dir = Path("sample-data")
    sample_dir.mkdir(parents=True, exist_ok=True)

    # 1. Export orders.csv
    orders_csv = sample_dir / "orders_sample.csv"
    with open(orders_csv, "w", encoding="utf-8") as f:
        f.write("order_id,customer_name,email,order_date,status,total_amount,sales_channel,city,state\n")
        for ord_obj, _ in orders[:300]:
            f.write(f"{ord_obj.source_record_id},{ord_obj.id},{ord_obj.id}@customer.com,{ord_obj.order_date.strftime('%Y-%m-%d')},{ord_obj.status},{ord_obj.total_amount},{ord_obj.sales_channel},Mumbai,Maharashtra\n")

    # 2. Export products.csv
    products_csv = sample_dir / "products_sample.csv"
    with open(products_csv, "w", encoding="utf-8") as f:
        f.write("sku,product_name,category,price,cost_price,stock_quantity\n")
        for p in products:
            f.write(f"{p.sku},{p.name},Category,{p.price},{p.cost_price},{p.stock}\n")

    # 3. Export Shopify JSON Fixtures (GraphQL Admin API format)
    shopify_json = sample_dir / "shopify_fixtures.json"
    shopify_data = {
        "data": {
            "orders": {
                "edges": [
                    {
                        "node": {
                            "id": f"gid://shopify/Order/{o[0].id}",
                            "name": f"#IN-{1000+o[0].id}",
                            "createdAt": o[0].order_date.isoformat(),
                            "totalPriceSet": {"shopMoney": {"amount": str(o[0].total_amount), "currencyCode": "INR"}},
                            "displayFulfillmentStatus": o[0].status.upper(),
                            "lineItems": {
                                "edges": [
                                    {
                                        "node": {
                                            "title": f"Item {item[0]}",
                                            "quantity": item[1],
                                            "originalUnitPriceSet": {"shopMoney": {"amount": str(item[2]), "currencyCode": "INR"}},
                                        }
                                    }
                                    for item in o[1]
                                ]
                            },
                        }
                    }
                    for o in orders[:50]
                ]
            }
        }
    }
    shopify_json.write_text(json.dumps(shopify_data, indent=2), encoding="utf-8")


async def reset_synthetic_seed_data(db: AsyncSession, business_id: int) -> dict[str, int]:
    counts = {}
    try:
        # 1. Clean order items for synthetic orders
        order_ids_subq = select(Order.id).where(Order.business_id == business_id, Order.source == SYNTHETIC_TAG)
        res_oi = await db.execute(delete(OrderItem).where(OrderItem.order_id.in_(order_ids_subq)))
        counts["order_items"] = res_oi.rowcount or 0

        # 2. Clean returns
        res_ret = await db.execute(delete(Return).where(Return.business_id == business_id, Return.source == SYNTHETIC_TAG))
        counts["returns"] = res_ret.rowcount or 0

        for model, name in [
            (Order, "orders"),
            (Customer, "customers"),
            (Inventory, "inventory"),
            (Product, "products"),
            (Category, "categories"),
            (MarketingSpend, "marketing_spend"),
            (WebsiteEvent, "website_events"),
            (Alert, "alerts"),
            (Insight, "insights"),
        ]:
            if hasattr(model, "source"):
                res = await db.execute(delete(model).where(model.business_id == business_id, model.source == SYNTHETIC_TAG))
                counts[name] = res.rowcount or 0
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return counts


async def main():
    parser = argparse.ArgumentParser(description="Seed 365-Day Synthetic Store Data")
    parser.add_argument("--business-id", type=int, default=1, help="Target business ID")
    parser.add_argument("--seed-val", type=int, default=42, help="Fixed random seed")
    parser.add_argument("--reset", action="store_true", help="Reset/remove synthetic seed data")
    args = parser.parse_args()

    async with AsyncSessionLocal() as session:
        if args.reset:
            print(f"Resetting synthetic seed data for business_id={args.business_id}...")
            res = await reset_synthetic_seed_data(session, args.business_id)
            print("Reset complete:", res)
        else:
            print(f"Generating 365-day synthetic store dataset for business_id={args.business_id} (Seed: {args.seed_val})...")
            res = await seed_365d_store_data(session, args.business_id, args.seed_val)
            print("Seeding complete! Statistics:")
            for k, v in res.items():
                print(f"  - {k}: {v}")


if __name__ == "__main__":
    asyncio.run(main())
