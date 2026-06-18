from app.utils.logger import get_logger

logger = get_logger("calculator_service")

class CalculatorService:
    @staticmethod
    def calculate_investment(principal: float, annual_rate: float, years: int, inflation_rate: float = 0.06):
        try:
            if principal <= 0 or annual_rate < 0 or years <= 0:
                return {"error": "Invalid input values"}
            
            future_value = principal * ((1 + annual_rate) ** years)
            profit = future_value - principal
            return_percentage = (profit / principal) * 100
            
            if inflation_rate > 0:
                real_annual_rate = ((1 + annual_rate) / (1 + inflation_rate)) - 1
                real_future_value = principal * ((1 + real_annual_rate) ** years)
                real_return_percentage = ((real_future_value - principal) / principal) * 100
            else:
                real_return_percentage = return_percentage
            
            return {
                "principal": round(principal, 2),
                "future_value": round(future_value, 2),
                "profit": round(profit, 2),
                "return_percentage": round(return_percentage, 2),
                "real_return_percentage": round(real_return_percentage, 2),
                "annual_rate": annual_rate * 100,
                "years": years,
                "inflation_rate": inflation_rate * 100,
            }
        except Exception as e:
            logger.error(f"Calculator error: {e}")
            return {"error": str(e)}

    @staticmethod
    def calculate_portfolio_metrics(stocks: list, budget: float):
        try:
            if not stocks or budget <= 0:
                return {"error": "Invalid input"}
            
            total_allocation = sum(s.get("suggested_allocation", 0) for s in stocks)
            
            risk_distribution = {"low": 0, "medium": 0, "high": 0}
            for stock in stocks:
                risk = stock.get("risk_level", "medium")
                allocation = stock.get("suggested_allocation", 0)
                risk_distribution[risk] += allocation
            
            low_pct = (risk_distribution["low"] / total_allocation * 100) if total_allocation > 0 else 0
            medium_pct = (risk_distribution["medium"] / total_allocation * 100) if total_allocation > 0 else 0
            high_pct = (risk_distribution["high"] / total_allocation * 100) if total_allocation > 0 else 0
            
            portfolio_risk_score = (low_pct * 2 + medium_pct * 5 + high_pct * 8) / 100
            avg_confidence = sum(s.get("confidence", 65) for s in stocks) / len(stocks) if stocks else 65
            
            return {
                "total_allocation": round(total_allocation, 2),
                "num_stocks": len(stocks),
                "portfolio_risk_score": round(portfolio_risk_score, 1),
                "portfolio_risk_label": "Low" if portfolio_risk_score <= 3.5 else "Medium" if portfolio_risk_score <= 6.5 else "High",
                "low_risk_pct": round(low_pct, 1),
                "medium_risk_pct": round(medium_pct, 1),
                "high_risk_pct": round(high_pct, 1),
                "average_confidence": round(avg_confidence, 1),
            }
        except Exception as e:
            logger.error(f"Portfolio metrics error: {e}")
            return {"error": str(e)}

    @staticmethod
    def estimate_returns(stocks: list, annual_growth_rate: float = 0.12, years: int = 3):
        try:
            total_allocation = sum(s.get("suggested_allocation", 0) for s in stocks)
            if total_allocation <= 0:
                return {"error": "Invalid allocation"}
            
            risk_scores = {
                "low": 0.08,
                "medium": 0.12,
                "high": 0.16,
            }
            
            weighted_rate = 0
            for stock in stocks:
                risk = stock.get("risk_level", "medium")
                allocation = stock.get("suggested_allocation", 0)
                rate = risk_scores.get(risk, 0.12)
                weighted_rate += (allocation / total_allocation) * rate
            
            future_value = total_allocation * ((1 + weighted_rate) ** years)
            profit = future_value - total_allocation
            
            inflation_rate = 0.06
            real_return_rate = ((1 + weighted_rate) / (1 + inflation_rate)) - 1
            real_future_value = total_allocation * ((1 + real_return_rate) ** years)
            
            return {
                "principal": round(total_allocation, 2),
                "future_value": round(future_value, 2),
                "profit": round(profit, 2),
                "return_percentage": round((profit / total_allocation * 100), 2),
                "weighted_annual_rate": round(weighted_rate * 100, 2),
                "real_return_percentage": round((real_return_rate * 100), 2),
                "real_future_value": round(real_future_value, 2),
                "years": years,
            }
        except Exception as e:
            logger.error(f"Returns estimation error: {e}")
            return {"error": str(e)}
