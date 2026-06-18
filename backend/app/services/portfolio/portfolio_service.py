from app.repositories.portfolio_repository import PortfolioRepository

class PortfolioService:
    @staticmethod
    def get_portfolio(user_id: str) -> list[dict]:
        return PortfolioRepository.get_portfolio(user_id)

    @staticmethod
    def add_holding(user_id: str, symbol: str, company_name: str, quantity: float, buy_price: float) -> int | None:
        return PortfolioRepository.add_holding(user_id, symbol, company_name, quantity, buy_price)

    @staticmethod
    def remove_holding(holding_id: int, user_id: str) -> bool:
        return PortfolioRepository.remove_holding(holding_id, user_id)
