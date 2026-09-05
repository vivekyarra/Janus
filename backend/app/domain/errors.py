class JanusError(Exception):
    reason_code = "JANUS_ERROR"
    status_code = 400

    def __init__(self, message: str = "Request could not be completed") -> None:
        super().__init__(message)
        self.message = message


class AuthorizationDenied(JanusError):
    reason_code = "AUTHORIZATION_DENIED"
    status_code = 403


class DuplicateProposal(JanusError):
    reason_code = "DUPLICATE_REQUEST"
    status_code = 409


class RazorpayOrderCreationFailed(JanusError):
    reason_code = "RAZORPAY_ORDER_CREATION_FAILED"
    status_code = 502


class PaymentVerificationFailed(JanusError):
    reason_code = "RAZORPAY_PAYMENT_VERIFICATION_FAILED"
    status_code = 400
