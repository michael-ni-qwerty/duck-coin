import logging

from fastapi import APIRouter, HTTPException, status
from solders.pubkey import Pubkey

from app.core.config import settings
import secrets
from datetime import datetime, timedelta, timezone
from app.models.presale import CreditStatus, Payment, AuthMessage
from app.schemas.presale import (
    BindClaimWalletRequest,
    BindClaimWalletResponse,
    ClaimRequest,
    ClaimResponse,
    ContractStatusResponse,
    PresaleConfigResponse,
    PresaleStatsResponse,
    GetMessageResponse,
)
from app.services.solana import solana_service

from .common import (
    is_solana_wallet_address,
    validate_wallet_address,
    classify_wallet_address,
)
from eth_account.messages import encode_defunct
from eth_account import Account

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/config",
    response_model=PresaleConfigResponse,
    summary="Get on-chain presale configuration",
)
async def get_presale_config() -> PresaleConfigResponse:
    """Get the current presale configuration from on-chain."""
    config = await solana_service.get_config_data()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Presale config not found on-chain",
        )

    return PresaleConfigResponse(
        program_id=settings.presale_program_id,
        token_mint=config["token_mint"],
        token_price_usd=config["token_price_usd"],
        tge_percentage=config["tge_percentage"],
        start_time=config["start_time"],
        daily_cap=config["daily_cap"],
        total_sold=config["total_sold"],
        presale_supply=config["presale_supply"],
        total_burned=config["total_burned"],
        status=config["status"],
        total_raised_usd=config["total_raised_usd"],
        sold_today=config["sold_today"],
    )


@router.get(
    "/status",
    response_model=ContractStatusResponse,
    summary="Get contract status",
)
async def get_contract_status() -> ContractStatusResponse:
    """Get current contract status (state + unlock progress)."""
    config = await solana_service.get_config_data()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Presale config not found on-chain",
        )

    status_value = config["status"]
    return ContractStatusResponse(
        status=status_value,
        is_active=status_value == "PresaleActive",
        is_token_launched=status_value == "TokenLaunched",
        tge_percentage=config["tge_percentage"],
        global_unlock_pct=config["global_unlock_pct"],
        start_time=config["start_time"],
    )


@router.get(
    "/message",
    response_model=GetMessageResponse,
    summary="Get message for wallet binding",
)
async def get_message(wallet_address: str) -> GetMessageResponse:
    if not validate_wallet_address(wallet_address):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported wallet_address format.",
        )

    # Check if the wallet has any payments
    payment_exists = await Payment.filter(
        wallet_address__iexact=wallet_address
    ).exists()
    if not payment_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet has no recorded payments.",
        )

    nonce_str = secrets.token_hex(16)
    # Generate an EIP-4361 inspired message to ensure clarity on what the user is signing
    message = (
        f"Welcome to Duck Coin Presale!\n\n"
        f"Click to sign in and verify your ownership of this wallet.\n\n"
        f"Wallet Address: {wallet_address.lower()}\n"
        f"Nonce: {nonce_str}"
    )

    # Messages expire in 5 minutes to mitigate replay attack windows
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    await AuthMessage.update_or_create(
        wallet_address=wallet_address.lower(),
        defaults={"message": message, "expires_at": expires_at},
    )

    return GetMessageResponse(message=message)


@router.post(
    "/bind-claim-wallet",
    response_model=BindClaimWalletResponse,
    summary="Bind claim wallet",
)
async def bind_claim_wallet(body: BindClaimWalletRequest) -> BindClaimWalletResponse:
    if not validate_wallet_address(body.wallet_address):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported wallet_address format.",
        )

    # Check if the wallet has any payments before attempting to bind
    payment_exists = await Payment.filter(
        wallet_address__iexact=body.wallet_address
    ).exists()
    if not payment_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet has no recorded payments.",
        )

    wallet_type = classify_wallet_address(body.wallet_address)
    match wallet_type:
        case "solana":
            # Signature verification for solana is different.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solana wallet binding not yet supported.",
            )
        case "evm":
            try:
                # 1. Fetch the message from the database
                auth_message = await AuthMessage.get_or_none(
                    wallet_address=body.wallet_address.lower()
                )

                # 2. Check if a message exists
                if not auth_message:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid message or message mismatch.",
                    )

                # 3. Check expiration
                if datetime.now(timezone.utc) > auth_message.expires_at:
                    await auth_message.delete()
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Message has expired. Please request a new one.",
                    )

                # 4. Verify the signature itself matches the expected message
                encoded_message = encode_defunct(text=auth_message.message)
                recovered_address = Account.recover_message(
                    encoded_message, signature=body.signature
                )

                if recovered_address.lower() != body.wallet_address.lower():
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Signature verification failed: recovered address does not match wallet_address.",
                    )

                # 5. Prevent replay attacks: delete the message immediately after successful verification
                await auth_message.delete()

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"EVM signature verification error: {e}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid signature format: {str(e)}",
                )
        case _:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported wallet type.",
            )

    try:
        tx_sig = await solana_service.bind_claim_wallet(
            wallet_address=body.wallet_address,
            solana_wallet=body.solana_wallet,
        )
        return BindClaimWalletResponse(tx_signature=tx_sig)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to bind claim wallet: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to bind claim wallet on-chain",
        )


@router.post(
    "/claim",
    response_model=ClaimResponse,
    summary="Prepare claim payload",
)
async def claim_tokens(body: ClaimRequest) -> ClaimResponse:
    """Prepare unsigned claim transaction payload for client-side signing."""
    if not validate_wallet_address(body.wallet_address):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported wallet_address format. Expected Solana or EVM address.",
        )

    resolved_solana_wallet = body.solana_wallet
    if not resolved_solana_wallet and is_solana_wallet_address(body.wallet_address):
        resolved_solana_wallet = body.wallet_address

    if not resolved_solana_wallet:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="solana_wallet is required. Bind claim wallet before claiming.",
        )

    try:
        Pubkey.from_string(resolved_solana_wallet)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid resolved Solana wallet: {e}",
        )

    try:
        payload = await solana_service.prepare_claim_payload(
            wallet_address=body.wallet_address,
            user_wallet=resolved_solana_wallet,
            user_token_account=body.user_token_account,
        )
        return ClaimResponse(
            wallet_address=body.wallet_address,
            resolved_solana_wallet=payload["user_wallet"],
            user_token_account=payload["user_token_account"],
            recent_blockhash=payload["recent_blockhash"],
            unsigned_tx_base64=payload["unsigned_tx_base64"],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to prepare claim payload: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to prepare claim transaction payload",
        )


@router.get(
    "/stats",
    response_model=PresaleStatsResponse,
    summary="Get presale statistics",
)
async def get_presale_stats() -> PresaleStatsResponse:
    """Get aggregate presale statistics from on-chain + DB."""
    config = await solana_service.get_config_data()

    participant_wallets = await Payment.filter(
        credit_status=CreditStatus.CREDITED
    ).values_list("wallet_address", flat=True)
    total_participants = len(set(participant_wallets))

    if config:
        return PresaleStatsResponse(
            total_sold=config["total_sold"],
            total_raised_usd=config["total_raised_usd"],
            total_participants=total_participants,
            presale_supply=config["presale_supply"],
            is_active=config["status"] == "PresaleActive",
        )

    return PresaleStatsResponse(
        total_sold=0,
        total_raised_usd=0,
        total_participants=0,
        presale_supply=0,
        is_active=False,
    )
