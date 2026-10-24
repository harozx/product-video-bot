"""
Accounts API router.
Manage social media accounts.
"""

from fastapi import APIRouter, HTTPException

from database import execute_query, execute_insert, execute_update
from server.models.schemas import AccountCreate, AccountResponse

router = APIRouter(prefix="/api/accounts", tags=["Accounts"])


@router.get("", response_model=list[AccountResponse])
async def list_accounts(platform: str = None):
    """List all accounts, optionally filtered by platform."""
    if platform:
        return await execute_query(
            "SELECT * FROM accounts WHERE platform = ? ORDER BY account_name",
            (platform,),
        )
    return await execute_query("SELECT * FROM accounts ORDER BY platform, account_name")


@router.post("", response_model=AccountResponse, status_code=201)
async def create_account(account: AccountCreate):
    """Add a new social media account."""
    acc_id = await execute_insert(
        """INSERT INTO accounts (platform, account_name, username, page_id, niche, daily_post_limit)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (account.platform, account.account_name, account.username,
         account.page_id, account.niche, account.daily_post_limit),
    )
    accounts = await execute_query("SELECT * FROM accounts WHERE id = ?", (acc_id,))
    return accounts[0]


@router.patch("/{account_id}/status")
async def update_account_status(account_id: int, status: str):
    """Update account status (active, paused, banned, cooldown)."""
    valid = ("active", "paused", "banned", "cooldown")
    if status not in valid:
        raise HTTPException(400, f"Invalid status. Must be one of: {valid}")
    rows = await execute_update(
        "UPDATE accounts SET status = ? WHERE id = ?", (status, account_id)
    )
    if rows == 0:
        raise HTTPException(404, "Account not found")
    return {"message": f"Account #{account_id} status → '{status}'"}


@router.delete("/{account_id}")
async def delete_account(account_id: int):
    """Delete an account."""
    rows = await execute_update("DELETE FROM accounts WHERE id = ?", (account_id,))
    if rows == 0:
        raise HTTPException(404, "Account not found")
    return {"message": f"Account #{account_id} deleted"}
