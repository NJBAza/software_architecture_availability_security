import sqlite3
from typing import Any

from apps.schemas import ShipmentCreate, ShipmentUpdate


class Database:
    """Simple SQLite-based database handler for shipment records.

    This class encapsulates all CRUD operations for the `shipment` table,
    including connection handling and safe query execution.
    """

    def connect_to_db(self) -> None:
        """Establish a connection to the SQLite database.

        Creates a connection and cursor used to execute SQL queries.
        The database file is `sqlite.db`, created automatically if missing.
        """
        self.conn = sqlite3.connect("sqlite.db", check_same_thread=False)
        self.cur = self.conn.cursor()
        print("Connected to sqlite.db ...")

    def create_table(self) -> None:
        """Create the `shipment` table if it does not already exist.

        The table contains:
            - id (int): Primary key
            - content (str): Description of the shipment
            - weight (float): Shipment weight
            - status (str): Current shipment status
        """
        self.cur.execute(
            """
            CREATE TABLE IF NOT EXISTS shipment (
                id INTEGER PRIMARY KEY,
                content TEXT,
                weight REAL,
                status TEXT
            )
            """
        )

    def create(self, shipment: "ShipmentCreate") -> int:
        """Insert a new shipment record into the database.

        Args:
            shipment (ShipmentCreate): Pydantic model with shipment data.

        Returns:
            int: The ID of the newly inserted shipment.

        """
        self.cur.execute("SELECT MAX(id) FROM shipment")
        result = self.cur.fetchone()

        # Handle case where table is empty (result[0] is None)
        new_id = (result[0] or 0) + 1

        self.cur.execute(
            """
            INSERT INTO shipment (id, content, weight, status)
            VALUES (:id, :content, :weight, :status)
            """,
            {
                "id": new_id,
                **shipment.model_dump(),
                "status": "placed",
            },
        )
        self.conn.commit()

        return new_id

    def get(self, id: int) -> dict[str, Any] | None:
        """Retrieve a shipment record by its ID.

        Args:
            id (int): The ID of the shipment to fetch.

        Returns:
            dict[str, Any] | None: Shipment data if found, else None.

        """
        self.cur.execute(
            """
            SELECT id, content, weight, status
            FROM shipment
            WHERE id = ?
            """,
            (id,),
        )

        row = self.cur.fetchone()
        if not row:
            return None

        return (
            {
                "id": row[0],
                "content": row[1],
                "weight": row[2],
                "status": row[3],
            }
            if row
            else None
        )

    def update(self, id: int, shipment: "ShipmentUpdate") -> dict[str, Any]:
        """Update an existing shipment's fields.

        Args:
            id (int): ID of the shipment to update.
            shipment (ShipmentUpdate): Only the fields to update.

        Returns:
            dict[str, Any]: The updated shipment record.

        """
        self.cur.execute(
            """
            UPDATE shipment
            SET status = :status
            WHERE id = :id
            """,
            {
                "id": id,
                **shipment.model_dump(),
            },
        )
        self.conn.commit()

        return self.get(id)

    def delete(self, id: int) -> None:
        """Delete a shipment from the database.

        Args:
            id (int): ID of the shipment to delete.

        """
        self.cur.execute(
            """
            DELETE FROM shipment
            WHERE id = ?
            """,
            (id,),
        )
        self.conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        print("...connection closed")
        self.conn.close()
