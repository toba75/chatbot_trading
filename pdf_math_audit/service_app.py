from pdf_math_audit.service import create_app
from pdf_math_audit.service_config import ServiceConfig


app = create_app(ServiceConfig.from_env())
