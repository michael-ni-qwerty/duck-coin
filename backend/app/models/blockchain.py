from tortoise import fields, models
from enum import Enum
from tortoise.contrib.pydantic import pydantic_model_creator


class TransactionType(str, Enum):
    PAYMENT = "payment"

class TransactionStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"

class Blockchain(models.Model):
    id = fields.UUIDField(pk=True)
    name = fields.CharField(max_length=50, unique=True)
    chain_id = fields.BigIntField(null=True, unique=True)
    symbol = fields.CharField(max_length=10)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "blockchains"

class Token(models.Model):
    id = fields.UUIDField(pk=True)
    blockchain = fields.ForeignKeyField("models.Blockchain", related_name="tokens")
    address = fields.CharField(max_length=128, null=True)
    symbol = fields.CharField(max_length=20)
    decimals = fields.IntField()
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "tokens"
        unique_together = (("blockchain", "address"),)

class Address(models.Model):
    id = fields.UUIDField(pk=True)
    blockchain = fields.ForeignKeyField("models.Blockchain", related_name="addresses")
    address = fields.CharField(max_length=128)
    label = fields.CharField(max_length=100, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "addresses"
        unique_together = (("blockchain", "address"),)

class Transaction(models.Model):
    id = fields.UUIDField(pk=True)
    type = fields.CharEnumField(TransactionType, max_length=20, default=TransactionType.PAYMENT)
    blockchain = fields.ForeignKeyField("models.Blockchain", related_name="transactions")
    token = fields.ForeignKeyField("models.Token", related_name="transactions", null=True)
    from_address = fields.ForeignKeyField("models.Address", related_name="sent_transactions")
    to_address = fields.ForeignKeyField("models.Address", related_name="received_transactions", null=True)
    amount = fields.BigIntField()
    tx_hash = fields.CharField(max_length=128, null=True, index=True)
    status = fields.CharEnumField(TransactionStatus, max_length=20, default=TransactionStatus.PENDING)
    metadata = fields.JSONField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    confirmed_at = fields.DatetimeField(null=True)

    class Meta:
        table = "transactions"

Transaction_Pydantic = pydantic_model_creator(Transaction, name="Transaction")
Blockchain_Pydantic = pydantic_model_creator(Blockchain, name="Blockchain")
Token_Pydantic = pydantic_model_creator(Token, name="Token")
Address_Pydantic = pydantic_model_creator(Address, name="Address")