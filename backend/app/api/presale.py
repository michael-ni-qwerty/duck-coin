from fastapi import APIRouter, HTTPException, status, Query

from app.schemas.presale import (
    BlockchainType,
    PurchaseRequest,
    PurchaseAuthorizationResponse,
    VestingInfoRequest,
    VestingInfoResponse,
    PresaleConfigResponse,
    PresaleStatsResponse,
    DerivedAddressesResponse,
    SupportedChainsResponse,
)
from app.blockchain import blockchain_registry, BlockchainType as ChainType

router = APIRouter(prefix="/presale", tags=["presale"])


def _map_chain_type(schema_chain: BlockchainType) -> ChainType:
    """Map schema BlockchainType to blockchain module BlockchainType."""
    return ChainType(schema_chain.value)


def _get_services(chain: BlockchainType):
    """Get blockchain services for the specified chain."""
    chain_type = _map_chain_type(chain)
    if not blockchain_registry.is_registered(chain_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Blockchain {chain.value} is not supported"
        )
    return (
        blockchain_registry.get_blockchain_service(chain_type),
        blockchain_registry.get_signature_service(chain_type),
        blockchain_registry.get_nonce_service(chain_type),
    )


@router.get(
    "/supported-chains",
    response_model=SupportedChainsResponse,
    summary="Get supported blockchains",
    description="Returns list of supported blockchains for the presale."
)
async def get_supported_chains() -> SupportedChainsResponse:
    """Get list of supported blockchains."""
    supported = blockchain_registry.get_supported_chains()
    return SupportedChainsResponse(
        chains=[BlockchainType(c.value) for c in supported],
        default_chain=BlockchainType.SOLANA,
    )


@router.post(
    "/authorize-purchase",
    response_model=PurchaseAuthorizationResponse,
    summary="Generate purchase authorization signature",
    description="""
    Generates a signature authorizing a token purchase on the specified blockchain.
    
    The signature scheme depends on the blockchain:
    - Solana: ed25519 signature verified via ed25519_program
    - Ethereum/BSC/Polygon: EIP-712 typed data signature
    - Tron: secp256k1 signature
    
    Flow:
    1. Client calls this endpoint with purchase details and target chain
    2. Backend generates unique nonce and signs the authorization
    3. Client builds chain-specific transaction with signature verification
    4. Client submits transaction to the blockchain
    """
)
async def authorize_purchase(request: PurchaseRequest) -> PurchaseAuthorizationResponse:
    """Generate a signed purchase authorization."""
    
    # Get services for the target chain
    blockchain_service, signature_service, nonce_service = _get_services(request.chain)
    
    # Generate unique nonce
    nonce = await nonce_service.generate_nonce(request.buyer_wallet)
    
    # Verify nonce is available
    is_available = await nonce_service.is_nonce_available(request.buyer_wallet, nonce)
    if not is_available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Nonce collision - please retry"
        )
    
    # Normalize payment type (SOL -> NATIVE for consistency)
    payment_type = request.payment_type.value
    if payment_type == "SOL":
        payment_type = "SOL"  # Keep SOL for Solana compatibility
    
    # Generate signed authorization
    try:
        authorization = signature_service.generate_purchase_authorization(
            buyer_address=request.buyer_wallet,
            payment_type=payment_type,
            payment_amount=request.payment_amount,
            token_amount=request.token_amount,
            nonce=nonce,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Signature generation failed: {str(e)}"
        )
    
    return PurchaseAuthorizationResponse(
        chain=request.chain,
        buyer_wallet=authorization.buyer_address,
        payment_type=authorization.payment_type,
        payment_token_address=authorization.payment_token_address,
        payment_amount=authorization.payment_amount,
        token_amount=authorization.token_amount,
        nonce=authorization.nonce,
        signature=authorization.signature,
        message=authorization.message,
        signer_public_key=authorization.signer_public_key,
        extra_data=authorization.extra_data,
    )


@router.get(
    "/config",
    response_model=PresaleConfigResponse,
    summary="Get presale configuration",
    description="Returns the current presale configuration including token addresses and vesting parameters."
)
async def get_presale_config(
    chain: BlockchainType = Query(default=BlockchainType.SOLANA, description="Target blockchain")
) -> PresaleConfigResponse:
    """Get current presale configuration for a specific chain."""
    
    blockchain_service, _, _ = _get_services(chain)
    
    config = await blockchain_service.get_presale_config()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Presale config not found"
        )
    
    return PresaleConfigResponse(
        chain=chain,
        contract_address=config.program_id,
        presale_token_address=config.presale_token_address,
        treasury_address=config.treasury_address,
        payment_tokens=config.payment_tokens,
        token_price_per_unit=config.token_price_per_unit,
        cliff_duration=config.cliff_duration,
        vesting_start_time=config.vesting_start_time,
        vesting_duration=config.vesting_duration,
        is_active=config.is_active,
        total_sold=config.total_sold,
    )


@router.post(
    "/vesting-info",
    response_model=VestingInfoResponse,
    summary="Get vesting information for a wallet",
    description="Returns the vesting schedule and claimable tokens for a specific wallet."
)
async def get_vesting_info(request: VestingInfoRequest) -> VestingInfoResponse:
    """Get vesting information for a wallet."""
    
    blockchain_service, _, _ = _get_services(request.chain)
    
    vesting_info = await blockchain_service.get_vesting_info(request.wallet_address)
    
    if vesting_info is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch vesting information"
        )
    
    return VestingInfoResponse(
        chain=request.chain,
        wallet_address=vesting_info.wallet_address,
        total_purchased=vesting_info.total_purchased,
        claimed_amount=vesting_info.claimed_amount,
        vested_amount=vesting_info.vested_amount,
        claimable_amount=vesting_info.claimable_amount,
        vesting_start_time=vesting_info.vesting_start_time,
        cliff_end_time=vesting_info.cliff_end_time,
        vesting_end_time=vesting_info.vesting_end_time,
        vesting_percentage=vesting_info.vesting_percentage,
    )


@router.get(
    "/stats",
    response_model=PresaleStatsResponse,
    summary="Get presale statistics",
    description="Returns overall presale statistics including total sold and raised amounts."
)
async def get_presale_stats(
    chain: BlockchainType = Query(default=BlockchainType.SOLANA, description="Target blockchain")
) -> PresaleStatsResponse:
    """Get presale statistics for a specific chain."""
    
    # In production, this would aggregate from on-chain data and/or database
    return PresaleStatsResponse(
        chain=chain,
        total_sold=0,
        total_participants=0,
        total_raised={"NATIVE": 0, "USDT": 0, "USDC": 0},
        is_active=True,
    )


@router.get(
    "/payment-tokens",
    summary="Get accepted payment tokens",
    description="Returns the token addresses for accepted payment methods on a specific chain."
)
async def get_payment_tokens(
    chain: BlockchainType = Query(default=BlockchainType.SOLANA, description="Target blockchain")
):
    """Get accepted payment token addresses for a chain."""
    
    blockchain_service, _, _ = _get_services(chain)
    config = await blockchain_service.get_presale_config()
    
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Presale config not found"
        )
    
    return {
        "chain": chain.value,
        "tokens": config.payment_tokens,
    }


@router.get(
    "/derived-addresses/{wallet_address}",
    response_model=DerivedAddressesResponse,
    summary="Get derived addresses for a wallet",
    description="Returns derived addresses (PDAs, storage slots, etc.) for client-side transaction building."
)
async def get_derived_addresses(
    wallet_address: str,
    chain: BlockchainType = Query(default=BlockchainType.SOLANA, description="Target blockchain")
) -> DerivedAddressesResponse:
    """Get derived addresses for transaction building."""
    
    blockchain_service, _, _ = _get_services(chain)
    
    addresses = blockchain_service.get_pda_addresses(wallet_address)
    
    return DerivedAddressesResponse(
        chain=chain,
        addresses=addresses,
    )
