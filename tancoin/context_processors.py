from .models import ExchangeRate


def tancoin_exchange(request):
    return {"tancoin_exchange": ExchangeRate.get_active()}
