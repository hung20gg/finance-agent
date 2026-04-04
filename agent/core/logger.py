import logging

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] - [%(levelname)s] - [%(filename)s:%(lineno)d] - %(message)s'
)
