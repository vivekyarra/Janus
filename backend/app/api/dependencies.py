from app.config import get_settings
from app.integrations.llm_adapter import GeminiAdapter, VercelAIGatewayAdapter
from app.integrations.razorpay_adapter import RazorpayAdapter


def get_semantic_model():
    settings = get_settings()
    return GeminiAdapter(settings) if settings.gemini_api_key else VercelAIGatewayAdapter(settings)


def get_razorpay_adapter():
    return RazorpayAdapter(get_settings())
