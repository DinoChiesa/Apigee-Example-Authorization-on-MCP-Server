# Copyright © 2025 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import argparse
import asyncio
import atexit
import json
import logging
import os
import re
import sqlite3
import time
from datetime import datetime
from typing import Annotated, List, Optional

import httpx
import inflect
import sqlite_regex
from fastapi import Header
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.middleware import Middleware, MiddlewareContext
from pydantic import BaseModel, Field

mcp = FastMCP(
    name="ACME Products MCP Service",
    version="0.1.2",
)


class UserInfoMiddleware(Middleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        # Access the tool object to check its metadata
        if context.fastmcp_context:
            try:
                tool = await context.fastmcp_context.fastmcp.get_tool(
                    context.message.name
                )
                headers = get_http_headers()
                user_info = headers.get("user-info")
                logging.info(f"tool={tool.name}; {user_info}")

                # Here, could log user_info scope, id, etc.,
                # if desired.

            except Exception:
                # Tool not found or other error - let execution continue
                # and handle the error naturally
                pass

            return await call_next(context)


mcp.add_middleware(UserInfoMiddleware())


class ProductRecord(BaseModel):
    """Represents a single product."""

    id: Annotated[
        int,
        Field(description="the ID for the product."),
    ]
    name: Annotated[
        str,
        Field(description="the name of the product."),
    ]
    description: Annotated[
        str,
        Field(description="the description of the product."),
    ]
    price: Annotated[
        float,
        Field(description="the price of the product."),
    ]
    keywords: Annotated[
        str,
        Field(description="the keywords associated with the product."),
    ]
    available: Annotated[
        int,
        Field(description="the number of items available."),
    ]


class AccountRecord(BaseModel):
    """Represents a single account."""

    id: int
    name: str
    email: str
    signup_date: str


class OrderItemRecord(BaseModel):
    """Represents a single item in an order."""

    id: int
    order_id: int
    product_id: int
    quantity: int
    product_name: Optional[str] = None


class OrderRecord(BaseModel):
    """Represents a single order."""

    id: int
    account_id: int
    order_date: str
    status: str
    total_amount: float
    items: Optional[List[OrderItemRecord]] = None


conn: Optional[sqlite3.Connection] = None


def _get_user_info(user_info_header: str) -> dict:
    """Parses the user-info header string."""
    if not user_info_header:
        # mock data for local testing
        return {"name": "Bo Jackson", "email": "bo@bojackson.com"}
    user_info = {}
    for part in user_info_header.split(";"):
        part = part.strip()
        if "=" in part:
            key, value = part.split("=", 1)
            user_info[key.strip()] = value.strip()
    return user_info


@mcp.tool(
    name="create_account",
    description="Creates a new user account.",
    tags={"account", "create"},
)
async def create_account(
    user_info_header: Annotated[str | None, Header(alias="user-info")] = None,
) -> str:
    user_info = _get_user_info(user_info_header)
    if not user_info.get("name") or not user_info.get("email"):
        raise ToolError("user-info header must include name and email")

    signup_date = datetime.now().isoformat()
    sql = "INSERT INTO accounts (name, email, signup_date) VALUES (?, ?, ?)"
    cursor = conn.cursor()
    try:
        cursor.execute(sql, (user_info["name"], user_info["email"], signup_date))
        conn.commit()
    except sqlite3.IntegrityError:
        raise ToolError("account with that email already exists")
    return "account created successfully"


@mcp.tool(
    name="get_my_account",
    description="Retrieves THE ACCOUNT DETAILS for the current user.",
    tags={"account", "get"},
)
async def get_my_account(
    user_info_header: Annotated[str | None, Header(alias="user-info")] = None,
) -> AccountRecord:
    user_info = _get_user_info(user_info_header)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM accounts WHERE email = ?", (user_info["email"],))
    account = cursor.fetchone()
    if not account:
        raise ToolError("account not registered")
    return AccountRecord(**dict(account))


@mcp.tool(
    name="create_order",
    description="Creates a new order with a list of products.",
    tags={"order", "create"},
)
async def create_order(
    product_ids: Annotated[
        List[int],
        Field(description="List of IDs of product to initially add to the order."),
    ],
    user_info_header: Annotated[str | None, Header(alias="user-info")] = None,
) -> OrderRecord:
    user_info = _get_user_info(user_info_header)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM accounts WHERE email = ?", (user_info["email"],))
    account = cursor.fetchone()
    if not account:
        raise ToolError("account not registered")
    account_id = account["id"]

    if not product_ids or len(product_ids) == 0 or len(product_ids) > 5:
        raise ToolError(
            "invalid products list. Must be an array of 1 to 5 product IDs."
        )

    # product_ids = [p.id for p in products]
    placeholders = ",".join("?" * len(product_ids))
    cursor.execute(
        f"SELECT id, price FROM products WHERE id IN ({placeholders})", product_ids
    )
    product_rows = cursor.fetchall()

    if len(product_rows) != len(product_ids):
        found_ids = {row["id"] for row in product_rows}
        not_found = [pid for pid in product_ids if pid not in found_ids]
        raise ToolError(
            f"one or more invalid product ids: {', '.join(map(str, not_found))}"
        )

    prices = {row["id"]: row["price"] for row in product_rows}
    total_amount = sum(prices[id] for id in product_ids)

    order_date = datetime.now().isoformat()
    order_sql = "INSERT INTO orders (account_id, order_date, total_amount, status) VALUES (?, ?, ?, ?)"
    cursor.execute(order_sql, (account_id, order_date, total_amount, "pending"))
    order_id = cursor.lastrowid

    item_sql = (
        "INSERT INTO order_items (order_id, product_id, quantity) VALUES (?, ?, ?)"
    )
    order_items_to_insert = [(order_id, id, 1) for id in product_ids]
    cursor.executemany(item_sql, order_items_to_insert)

    conn.commit()

    return OrderRecord(
        id=order_id,
        account_id=account_id,
        order_date=order_date,
        status="pending",
        total_amount=total_amount,
    )


@mcp.tool(
    name="list_my_orders",
    description="Lists all orders for the current user.",
    tags={"order", "list"},
)
async def list_my_orders(
    user_info_header: Annotated[str | None, Header(alias="user-info")] = None,
) -> List[OrderRecord]:
    user_info = _get_user_info(user_info_header)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM accounts WHERE email = ?", (user_info["email"],))
    account = cursor.fetchone()
    if not account:
        raise ToolError("account not registered")
    account_id = account["id"]

    cursor.execute("SELECT * FROM orders WHERE account_id = ?", (account_id,))
    orders = cursor.fetchall()
    return [OrderRecord(**dict(order)) for order in orders]


@mcp.tool(
    name="get_order_details",
    description="Retrieves details of a specific order.",
    tags={"order", "get"},
)
async def get_order_details(
    order_id: Annotated[int, Field(description="The ID of the order to retrieve.")],
    details: Annotated[
        bool, Field(description="Whether to include order item details.")
    ] = False,
    user_info_header: Annotated[str | None, Header(alias="user-info")] = None,
) -> OrderRecord:
    user_info = _get_user_info(user_info_header)
    cursor = conn.cursor()
    sql = "SELECT o.* FROM orders o JOIN accounts a ON o.account_id = a.id WHERE o.id = ? AND a.email = ?"
    cursor.execute(sql, (order_id, user_info["email"]))
    order = cursor.fetchone()
    if not order:
        raise ToolError("invalid orderId")

    order_record = OrderRecord(**dict(order))

    if details:
        items_sql = "SELECT oi.*, p.name AS product_name FROM order_items oi JOIN products p ON oi.product_id = p.id WHERE oi.order_id = ?"
        cursor.execute(items_sql, (order_id,))
        items = cursor.fetchall()
        order_record.items = [OrderItemRecord(**dict(item)) for item in items]

    return order_record


@mcp.tool(
    name="amend_order",
    description="Modifies an existing pending order.",
    tags={"order", "amend", "update"},
)
async def amend_order(
    order_id: Annotated[int, Field(description="The ID of the order to amend.")],
    product_id: Annotated[
        int,
        Field(description="ID of product to update in the order."),
    ],
    qty: Annotated[
        int,
        Field(description="new quantity for the product to update in the order."),
    ],
    user_info_header: Annotated[str | None, Header(alias="user-info")] = None,
) -> str:
    user_info = _get_user_info(user_info_header)
    cursor = conn.cursor()
    sql = "SELECT o.* FROM orders o JOIN accounts a ON o.account_id = a.id WHERE o.id = ? AND a.email = ?"
    cursor.execute(sql, (order_id, user_info["email"]))
    order = cursor.fetchone()
    if not order:
        raise ToolError("invalid orderId")
    if order["status"] != "pending":
        raise ToolError("cannot amend a finalized order")

    # AI! implement the logic here to do the following:
    #
    # - if in the table order_items, for entries where order_id == order_id,
    #   there is no item with product_id == product_id, then INSERT
    #   an entry into order_items with order_id, product_id and qty
    #
    # - if in the table order_items, for entries where order_id == order_id,
    #   there IS an item with product_id == product_id, then UPDATE the
    #   order_items entry where order_id == order_id and product_id ==
    #   product_id, with new qty == qty
    #
    ## Then compute the new total_amount for the order_items and qty.

    cursor.execute(
        "UPDATE orders SET total_amount = ? WHERE id = ?", (total_amount, order_id)
    )
    conn.commit()

    return "order amended successfully"


async def _finalize_order(order_id: int, status: str, user_info_header: str) -> str:
    user_info = _get_user_info(user_info_header)
    cursor = conn.cursor()
    sql = "UPDATE orders SET status = ? WHERE id = ? AND account_id = (SELECT id FROM accounts WHERE email = ?)"
    cursor.execute(sql, (status, order_id, user_info["email"]))
    if cursor.rowcount == 0:
        raise ToolError("invalid orderId")
    conn.commit()
    return f"order {status} successfully"


@mcp.tool(
    name="submit_order",
    description="Submits a pending order.",
    tags={"order", "submit"},
)
async def submit_order(
    order_id: Annotated[int, Field(description="The ID of the order to submit.")],
    user_info_header: Annotated[str | None, Header(alias="user-info")] = None,
) -> str:
    return await _finalize_order(order_id, "submitted", user_info_header)


@mcp.tool(
    name="cancel_order",
    description="Cancels a pending order.",
    tags={"order", "cancel"},
)
async def cancel_order(
    order_id: Annotated[int, Field(description="The ID of the order to cancel.")],
    user_info_header: Annotated[str | None, Header(alias="user-info")] = None,
) -> str:
    return await _finalize_order(order_id, "canceled", user_info_header)


@mcp.tool(
    name="update_product_quantity",
    description="Updates the available quantity of the product with the given id.",
    tags={"product", "update", "quantity"},
)
async def update_product_quantity(
    id: Annotated[
        int,
        Field(description="The ID of the product to update."),
    ],
    quantity: Annotated[
        int,
        Field(description="The new non-negative available quantity for the product."),
    ],
) -> ProductRecord:
    """
    This description is ignored for the purposes of MCP, if a description is provided in the decorator above.
    """
    if quantity < 0:
        raise ToolError("Quantity must be a non-negative integer.")

    cursor = conn.cursor()

    sql = "UPDATE products SET available = ? WHERE id = ?"
    cursor.execute(sql, (quantity, id))

    if cursor.rowcount == 0:
        raise ToolError(f"Product with ID {id} not found.")

    # Fetch and return the updated product record
    cursor.execute("SELECT * FROM products WHERE id = ?", (id,))
    updated_row = cursor.fetchone()
    conn.commit()

    return ProductRecord(**dict(updated_row))


@mcp.tool(
    name="update_product_price",
    description="Updates the unit price of the product with the given id.",
    tags={"product", "update", "price"},
)
async def update_product_price(
    id: Annotated[
        int,
        Field(description="The ID of the product to update."),
    ],
    price: Annotated[
        float,
        Field(
            description="The new positive price for the product, with at most 2 decimal digits."
        ),
    ],
) -> ProductRecord:
    """
    This description is ignored for the purposes of MCP, if a description is provided in the decorator above.
    """
    if price <= 0:
        raise ToolError("Price must be a positive number.")

    # Validate that price has at most 2 decimal digits.
    if "." in str(price) and len(str(price).split(".")[1]) > 2:
        raise ToolError("Price can have at most 2 decimal digits.")

    cursor = conn.cursor()

    sql = "UPDATE products SET price = ? WHERE id = ?"
    cursor.execute(sql, (price, id))

    if cursor.rowcount == 0:
        raise ToolError(f"Product with ID {id} not found.")

    # Fetch and return the updated product record
    cursor.execute("SELECT * FROM products WHERE id = ?", (id,))
    updated_row = cursor.fetchone()
    conn.commit()

    return ProductRecord(**dict(updated_row))


@mcp.tool(
    name="retrieve_product_details",
    description="Retrieves details about the product, including price and quantity available, for the given product id.",
    tags={"retrieve", "product", "price", "quantity"},
)
async def retrieve_product_details(
    id: Annotated[
        int,
        Field(description="The ID of the product to update."),
    ],
) -> ProductRecord:
    """
    Ignored in favor of the description provided in the decorator above.
    """

    cursor = conn.cursor()

    cursor.execute("SELECT * FROM products WHERE id = ?", (id,))
    retrieved_row = cursor.fetchone()
    conn.commit()

    return ProductRecord(**dict(retrieved_row))


@mcp.tool(
    name="search_product",
    description="Searches the product list for keywords, either in the product name, the product description, or the keywords associated to the product.",
    tags={"product", "search", "keyword"},
)
async def search_product(
    termExpression: Annotated[
        str,
        Field(
            description="the search term expression. This is a concatenation of all the keywords, separated by |."
        ),
    ],
) -> List[ProductRecord] | None:
    """
    This description is ignored for the purposes of MCP, if a description is provided in the decorator above.
    """
    cursor = conn.cursor()

    p = inflect.engine()
    terms = [
        re.escape(p.singular_noun(t) or t)
        for t in (term.strip() for term in termExpression.split("|"))
        if t
    ]
    regex = "|".join(terms)

    sql = "SELECT id, name, description, price, keywords, available FROM products WHERE keywords REGEXP ? OR name REGEXP ? OR description REGEXP ?"
    cursor.execute(sql, (regex, regex, regex))
    rows = cursor.fetchall()
    products = [ProductRecord(**dict(row)) for row in rows]
    return products


def setup_database():
    """Initializes the database connection and sets up the schema if needed."""
    global conn
    db_path = os.path.join(os.path.dirname(__file__), "products.db")

    # If the database doesn't exist, it will be created by sqlite3.connect,
    # and we'll need to run the setup script.
    needs_setup = not os.path.exists(db_path)

    conn = sqlite3.connect(db_path)

    if needs_setup:
        logging.info("Database not found. Initializing from dbsetup.sql.")
        script_path = os.path.join(os.path.dirname(__file__), "dbsetup.sql")
        with open(script_path, "r") as f:
            conn.executescript(f.read())
        conn.commit()
        logging.info("Database setup complete.")

    conn.enable_load_extension(True)
    sqlite_regex.load(conn)
    conn.row_factory = sqlite3.Row
    atexit.register(conn.close)


if __name__ == "__main__":
    LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
    logging.basicConfig(level=LOGLEVEL)
    setup_database()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--port", type=int, help="The port for the server to listen on."
    )
    args = parser.parse_args()

    port = args.port if args.port is not None else int(os.environ.get("PORT", 9240))
    mcp.run(
        transport="http", host="0.0.0.0", port=port, path="/mcp", stateless_http=True
    )
