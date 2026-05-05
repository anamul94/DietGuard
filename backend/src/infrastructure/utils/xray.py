import os
import logging
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core.async_context import AsyncContext
from aws_xray_sdk.core.models import http
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

XRAY_ENABLED = os.environ.get("XRAY_ENABLED", "true").lower() == "true"

def configure_xray():
    """Configures AWS X-Ray for the application."""
    if not XRAY_ENABLED:
        logger.info("[X-Ray] Tracing disabled.")
        xray_recorder.configure(context_missing='IGNORE_ERROR')
        return

    logger.info("[X-Ray] Tracing enabled. Configuring X-Ray.")

    # Configure the X-Ray recorder
    xray_recorder.configure(
        service="FoodAppBackend",
        context=AsyncContext(),
        context_missing='LOG_ERROR',
        daemon_address=os.environ.get("AWS_XRAY_DAEMON_ADDRESS", "127.0.0.1:2000")
    )

    # Instrument Starlette/FastAPI automatically
    try:
        from aws_xray_sdk.ext.starlette import StarletteInstrumentor
        StarletteInstrumentor().instrument()
        logger.info("[X-Ray] Starlette instrumented.")
    except ImportError:
        logger.warning("[X-Ray] StarletteInstrumentor not found in aws_xray_sdk.ext.starlette. We will fall back to custom XRayMiddleware.")
    except Exception as e:
        logger.error(f"[X-Ray] Failed to instrument Starlette: {e}")

class XRayMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, segment_name: str = "FoodAppBackend"):
        super().__init__(app)
        self.segment_name = segment_name

    async def dispatch(self, request, call_next):
        if not XRAY_ENABLED:
            return await call_next(request)

        segment = xray_recorder.begin_segment(self.segment_name)
        
        req_meta = {
            "url": str(request.url),
            "method": request.method,
            "client_ip": request.client.host if request.client else "",
        }
        segment.put_http_meta(http.URL, req_meta["url"])
        segment.put_http_meta(http.METHOD, req_meta["method"])
        segment.put_http_meta(http.CLIENT_IP, req_meta["client_ip"])

        try:
            response = await call_next(request)
            segment.put_http_meta(http.STATUS, response.status_code)
            return response
        except Exception as e:
            segment.add_exception(e, stacktrace=True)
            segment.put_http_meta(http.STATUS, 500)
            raise
        finally:
            xray_recorder.end_segment()
