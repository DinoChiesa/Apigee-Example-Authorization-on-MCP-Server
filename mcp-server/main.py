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
from typing import Annotated, List, Optional

import httpx
import inflect
import sqlite_regex
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.middleware import Middleware, MiddlewareContext
from pydantic import BaseModel, Field

mcp = FastMCP(
    name="ACME Products MCP Service",
    version="0.1.1",
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


conn: Optional[sqlite3.Connection] = None


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
