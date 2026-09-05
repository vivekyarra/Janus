from app.config import get_settings
from app.integrations.llm_adapter import VercelAIGatewayAdapter
from app.integrations.razorpay_adapter import RazorpayAdapter


def get_semantic_model():
    return VercelAIGatewayAdapter(get_settings())


def get_razorpay_adapter():
    return RazorpayAdapter(get_settings())

