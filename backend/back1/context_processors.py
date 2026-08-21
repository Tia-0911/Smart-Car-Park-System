from decimal import Decimal

from .models import Wallet


def customer_wallet(request):
    """Expose only the authenticated non-admin user's current wallet balance."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or user.is_staff or user.is_superuser:
        return {}
    balance = Wallet.objects.filter(user=user).values_list("balance", flat=True).first()
    return {
        "customer_wallet_balance": (
            balance if balance is not None else Decimal("0.00")
        )
    }
